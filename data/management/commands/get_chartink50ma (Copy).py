"""
Fetch symbols from ChartInk 50ma-setup screener.

Clicks: Copy button → "symbols" option, then reads symbol list.
Falls back to scanning the results table if clipboard is unavailable (Docker/headless).

Usage:
  python manage.py get_chartink50ma
  python manage.py get_chartink50ma --no-headless
  python manage.py get_chartink50ma --print-only
"""
import os
import re
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    import pyperclip
except ImportError:
    pyperclip = None

CHARTINK_URL = "https://chartink.com/screener/50ma-setup"


class Command(BaseCommand):
    help = (
        "Open ChartInk 50ma-setup, click Copy → symbols, and collect stock symbols."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--headless",
            action="store_true",
            default=True,
            help="Run Chrome headless (default: True).",
        )
        parser.add_argument(
            "--no-headless",
            action="store_false",
            dest="headless",
            help="Show the browser window (debug).",
        )
        parser.add_argument(
            "--print-only",
            action="store_true",
            help="Only print symbols; do not write DB/sheets.",
        )
        parser.add_argument(
            "--save-screenshots",
            action="store_true",
            default=True,
            help="Save debug screenshots under MEDIA_ROOT/screenshots (default: True).",
        )

    def handle(self, *args, **options):
        headless = options.get("headless", True)
        self.stdout.write(self.style.SUCCESS("Starting get_chartink50ma..."))
        self.stdout.write(f"URL: {CHARTINK_URL}")

        driver = None
        try:
            driver = self._setup_driver(headless=headless)
            symbols = self._scrape_symbols(driver, save_screenshots=options.get("save_screenshots", True))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Scrape failed: {exc}"))
            raise
        finally:
            if driver:
                driver.quit()

        if not symbols:
            self.stdout.write(self.style.ERROR("No symbols collected."))
            return

        self.stdout.write(self.style.SUCCESS(f"Collected {len(symbols)} symbols"))
        self.stdout.write(", ".join(symbols))

        if options.get("print_only"):
            return

        # Optional: push into the same Google Finance / DB path as chartink command
        try:
            from infra.utils.gfinance import update_gfinance_data

            self.stdout.write("Updating 50MA Stocks in Google Finance sheet...")
            result = update_gfinance_data("googleFinace", symbols)
            self.stdout.write(self.style.SUCCESS(str(result)))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"Skipped Google Sheets update ({exc}). Use --print-only to avoid this step."
            ))

    def _setup_driver(self, headless=True):
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option(
            "prefs",
            {"profile.default_content_setting_values.clipboard": 1},
        )

        driver = webdriver.Chrome(options=options)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            },
        )

        # Best-effort clipboard permission (often unsupported in Docker Chrome)
        for perms in (
            ["clipboardRead", "clipboardWrite"],
            ["clipboard-read", "clipboard-write"],
        ):
            try:
                driver.execute_cdp_cmd(
                    "Browser.grantPermissions",
                    {"origin": "https://chartink.com", "permissions": perms},
                )
                self.stdout.write(f"Granted clipboard permissions: {perms}")
                break
            except Exception:
                continue
        else:
            self.stdout.write(self.style.WARNING(
                "Clipboard CDP permission not granted — will use table fallback if needed"
            ))

        return driver

    def _screenshot(self, driver, name, enabled=True):
        if not enabled:
            return
        try:
            folder = os.path.join(settings.MEDIA_ROOT, "screenshots")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, name)
            driver.save_screenshot(path)
            self.stdout.write(f"Screenshot: {path}")
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"Screenshot failed: {exc}"))

    def _scrape_symbols(self, driver, save_screenshots=True):
        wait = WebDriverWait(driver, 40)
        driver.get(CHARTINK_URL)
        self.stdout.write("Waiting for scan results...")

        # Wait until results table has rows (scan finished)
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "table.scan-results-table tbody tr")
                )
            )
        except TimeoutException:
            self._screenshot(driver, "get50ma_01_no_table.png", save_screenshots)
            self.stdout.write(self.style.ERROR("Results table never appeared"))
            return []

        time.sleep(2)
        self._screenshot(driver, "get50ma_01_loaded.png", save_screenshots)

        # 1) Click Copy button (new ChartInk UI)
        copy_btn = self._find_copy_button(driver, wait)
        if not copy_btn:
            self.stdout.write(self.style.WARNING("Copy button not found — table fallback"))
            return self._symbols_from_table(driver)

        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", copy_btn
        )
        time.sleep(0.5)
        try:
            copy_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", copy_btn)
        self.stdout.write("Clicked Copy button")
        time.sleep(1)
        self._screenshot(driver, "get50ma_02_after_copy.png", save_screenshots)

        # 2) Click "symbols" option in the submenu
        symbols_btn = self._find_symbols_option(driver, wait)
        if not symbols_btn:
            self.stdout.write(self.style.WARNING(
                "Copy symbols option not found — table fallback"
            ))
            return self._symbols_from_table(driver)

        try:
            symbols_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", symbols_btn)
        self.stdout.write("Clicked Copy symbols")
        time.sleep(1.5)
        self._screenshot(driver, "get50ma_03_after_symbols.png", save_screenshots)

        # 3) Read clipboard (browser JS → pyperclip)
        clipboard_text = self._read_clipboard(driver)
        symbols = self._parse_symbols(clipboard_text)
        if symbols:
            self.stdout.write(self.style.SUCCESS(
                f"Got {len(symbols)} symbols from clipboard"
            ))
            return symbols

        self.stdout.write(self.style.WARNING(
            "Clipboard empty/unavailable — falling back to results table"
        ))
        return self._symbols_from_table(driver)

    def _find_copy_button(self, driver, wait):
        selectors = [
            (By.CSS_SELECTOR, 'button[aria-label="Copy"]'),
            (By.XPATH, '//button[@aria-label="Copy"]'),
            (By.XPATH, '//button[.//span[normalize-space()="Copy"]]'),
            (By.XPATH, '//button[contains(@aria-controls, "action-button-submenu")]'),
            (By.XPATH, '//*[self::button or self::div][contains(., "Copy") and '
                       '(@aria-label="Copy" or contains(@class, "secondary-button"))]'),
        ]
        for by, sel in selectors:
            try:
                el = wait.until(EC.element_to_be_clickable((by, sel)))
                if el:
                    self.stdout.write(f"Found Copy via: {sel}")
                    return el
            except TimeoutException:
                continue
            except Exception:
                continue

        # Last resort: any visible control whose text is exactly Copy
        for el in driver.find_elements(By.XPATH, "//button|//div|//span"):
            try:
                if (el.text or "").strip() == "Copy" and el.is_displayed():
                    self.stdout.write("Found Copy via text search")
                    return el
            except Exception:
                continue
        return None

    def _find_symbols_option(self, driver, wait):
        selectors = [
            (By.CSS_SELECTOR, 'button[aria-label="Copy symbols"]'),
            (By.XPATH, '//button[@aria-label="Copy symbols"]'),
            (By.XPATH, '//button[.//span[contains(translate(normalize-space(.),'
                       '"SYMBOLS","symbols"),"symbols")]]'),
            (By.XPATH, '//*[@role="group" and contains(@aria-label, "Copy options")]'
                       '//button[contains(@aria-label, "symbol") or '
                       './/span[contains(translate(normalize-space(.),'
                       '"SYMBOLS","symbols"),"symbols")]]'),
            (By.XPATH, '//span[contains(@class, "sm:inline") and '
                       'contains(translate(normalize-space(.),"SYMBOLS","symbols"),"symbols")]'
                       '/ancestor::button[1]'),
        ]
        for by, sel in selectors:
            try:
                el = wait.until(EC.element_to_be_clickable((by, sel)))
                if el:
                    self.stdout.write(f"Found symbols option via: {sel[:80]}")
                    return el
            except TimeoutException:
                continue
            except Exception:
                continue

        # Text search inside copy-options group
        for el in driver.find_elements(
            By.CSS_SELECTOR, '[role="group"][aria-label*="Copy"] button, button'
        ):
            try:
                label = (el.get_attribute("aria-label") or "").lower()
                text = (el.text or "").strip().lower()
                if "symbol" in label or text == "symbols":
                    if el.is_displayed():
                        self.stdout.write("Found symbols option via text search")
                        return el
            except Exception:
                continue
        return None

    def _read_clipboard(self, driver):
        # Browser clipboard API
        try:
            text = driver.execute_async_script(
                """
                const done = arguments[0];
                navigator.clipboard.readText()
                  .then(t => done(t || ''))
                  .catch(() => done(''));
                """
            )
            if text and text.strip():
                self.stdout.write(f"Clipboard (JS) length={len(text)}")
                return text
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"JS clipboard.readText failed: {exc}"))

        # System clipboard
        if pyperclip is not None:
            try:
                text = pyperclip.paste() or ""
                if text.strip():
                    self.stdout.write(f"Clipboard (pyperclip) length={len(text)}")
                    return text
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"pyperclip failed: {exc}"))
        else:
            self.stdout.write(self.style.WARNING("pyperclip not installed"))

        return ""

    def _parse_symbols(self, text):
        if not text or not text.strip():
            return []

        raw = text.strip()
        parts = []
        if "\n" in raw:
            parts = [p.strip() for p in raw.splitlines() if p.strip()]
        elif "," in raw:
            parts = [p.strip() for p in raw.split(",") if p.strip()]
        elif "\t" in raw:
            # table paste — take first token that looks like a symbol per line
            for line in raw.splitlines():
                cols = [c.strip() for c in line.split("\t") if c.strip()]
                for col in cols:
                    if re.fullmatch(r"[A-Za-z0-9-]{2,20}", col) and col.isupper():
                        parts.append(col)
                        break
        else:
            parts = [raw]

        symbols = []
        seen = set()
        skip = {"SYMBOL", "SYMBOLS", "STOCK", "NAME", "SR", "SR.", "CLOSE", "VOLUME"}
        for part in parts:
            # If a line has multiple columns, prefer an uppercase token
            token = part
            if "\t" in part or " " in part:
                for col in re.split(r"[\t, ]+", part):
                    col = col.strip()
                    if re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{1,19}", col) and col.upper() == col:
                        token = col
                        break
            sym = re.sub(r"[^A-Za-z0-9-]", "", token).upper()
            if not sym or sym in skip or len(sym) < 2 or len(sym) > 20:
                continue
            if sym not in seen:
                seen.add(sym)
                symbols.append(sym)
        return symbols

    def _symbols_from_table(self, driver):
        """Read Symbol column from table.scan-results-table, with pagination."""
        symbols = []
        seen = set()
        wait = WebDriverWait(driver, 20)

        # Prefer larger page size
        try:
            driver.execute_script(
                """
                const candidates = [...document.querySelectorAll('button, li, a, span')]
                  .filter(el => {
                    const t = (el.textContent || '').trim();
                    return t === '50' || t === '40' || t === '30';
                  });
                for (const el of candidates) {
                  if (el.offsetParent !== null) { el.click(); return; }
                }
                """
            )
            time.sleep(1.5)
        except Exception:
            pass

        for page in range(1, 21):
            page_syms = driver.execute_script(
                """
                const table = document.querySelector('table.scan-results-table');
                if (!table) return [];
                return [...table.querySelectorAll('tbody tr')].map(row => {
                  const cells = [...row.querySelectorAll('td')];
                  let sym = cells.length >= 3 ? (cells[2].textContent || '').trim() : '';
                  if (!sym) {
                    const a = row.querySelector('a[href*="symbol="]');
                    if (a) {
                      const m = (a.getAttribute('href') || '').match(/symbol=([^&]+)/);
                      if (m) sym = decodeURIComponent(m[1]);
                    }
                  }
                  return (sym || '').toUpperCase();
                }).filter(Boolean);
                """
            ) or []

            added = 0
            for sym in page_syms:
                clean = re.sub(r"[^A-Z0-9-]", "", sym.upper())
                if clean and clean not in seen and 2 <= len(clean) <= 20:
                    seen.add(clean)
                    symbols.append(clean)
                    added += 1

            self.stdout.write(
                f"Table page {page}: {len(page_syms)} rows, +{added} (total {len(symbols)})"
            )

            clicked = driver.execute_script(
                """
                const buttons = [...document.querySelectorAll('button')];
                const next = buttons.find(b => {
                  const t = (b.textContent || '').trim();
                  return t === 'Next' || t === 'Next >>';
                });
                if (!next || next.disabled ||
                    /opacity-40|cursor-not-allowed/.test(next.className || '')) {
                  return false;
                }
                next.click();
                return true;
                """
            )
            if not clicked:
                break
            time.sleep(1.5)
            try:
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "table.scan-results-table tbody tr")
                    )
                )
            except TimeoutException:
                break
            if added == 0 and page > 1:
                break

        if symbols:
            self.stdout.write(self.style.SUCCESS(
                f"Extracted {len(symbols)} symbols from results table"
            ))
        return symbols
