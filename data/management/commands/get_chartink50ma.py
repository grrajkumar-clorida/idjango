"""
Fetch symbols from any ChartInk screener, then (for configured screeners)
run the same post-steps as chartink.py:

  1. Scrape ChartInk (Copy → symbols / table fallback)
  2. Update Google Finance stock column
  3. Trigger Google Apps Script (GSHEET_APP_SCRIPT)
  4. Read SMA sheet from Google Sheets (retry)
  5. Upsert Stocks50MA + Telegram

Usage:
  python manage.py get_chartink50ma 50ma
  python manage.py get_chartink50ma smc --print-only
  python manage.py get_chartink50ma 50ma --symbols-only
  python manage.py get_chartink50ma --list
"""
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone
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

# Named screeners — add new keys here for other ChartInk pages
SCREENERS = {
    "50ma": {
        "url": "https://chartink.com/screener/50ma-setup",
        "sheet": "googleFinace",  # symbol upload worksheet
        "result_sheet": "50ma",  # SMA values worksheet (after Apps Script)
        "apps_script_env": "GSHEET_APP_SCRIPT",
        "update_db": True,
        "label": "50MA setup",
    },
    "smc": {
        "url": "https://chartink.com/screener/breakout-stocks-7032491",
        "sheet": None,
        "result_sheet": None,
        "apps_script_env": None,
        "update_db": False,
        "label": "SMC / breakout stocks",
    },
}

DEFAULT_SCREENER = "50ma"


class Command(BaseCommand):
    help = (
        "Fetch ChartInk screener symbols by name (50ma, smc, ...) then optionally "
        "trigger Apps Script, read SMA sheet, and update Stocks50MA."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "screener",
            nargs="?",
            default=None,
            help=f"Screener key: {', '.join(SCREENERS)} (default: {DEFAULT_SCREENER}).",
        )
        parser.add_argument(
            "--screener",
            dest="screener_opt",
            default=None,
            help="Same as positional screener key (alternative form).",
        )
        parser.add_argument(
            "--url",
            default=None,
            help="Custom ChartInk screener URL (overrides named screener).",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List known screener keys and exit.",
        )
        parser.add_argument(
            "--sheet",
            default=None,
            help="Google worksheet for symbol upload (update_gfinance_data).",
        )
        parser.add_argument(
            "--result-sheet",
            default=None,
            help="Google worksheet to read SMA rows from (default: screener config, e.g. 50ma).",
        )
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
            help="Only scrape+print symbols; skip sheet/Apps Script/DB.",
        )
        parser.add_argument(
            "--symbols-only",
            action="store_true",
            help="Upload symbols to Google sheet only; skip Apps Script/DB.",
        )
        parser.add_argument(
            "--skip-db",
            action="store_true",
            help="Skip Stocks50MA DB update (still runs Apps Script + sheet read).",
        )
        parser.add_argument(
            "--skip-telegram",
            action="store_true",
            help="Skip Telegram notification after DB update.",
        )
        parser.add_argument(
            "--save-screenshots",
            action="store_true",
            default=True,
            help="Save debug screenshots under MEDIA_ROOT/screenshots (default: True).",
        )

    def handle(self, *args, **options):
        if options.get("list"):
            self.stdout.write("Known ChartInk screeners:")
            for key, meta in SCREENERS.items():
                self.stdout.write(
                    f"  {key:8}  {meta['label']}\n"
                    f"           url={meta['url']}\n"
                    f"           sheet={meta.get('sheet') or '(none)'}  "
                    f"result_sheet={meta.get('result_sheet') or '(none)'}  "
                    f"update_db={meta.get('update_db', False)}"
                )
            return

        key, url, sheet, result_sheet, apps_script_env, update_db, label = (
            self._resolve_screener(options)
        )
        headless = options.get("headless", True)
        prefix = re.sub(r"[^a-z0-9_-]+", "", key.lower()) or "chartink"

        self.stdout.write(self.style.SUCCESS(f"Starting ChartInk fetch: {label} ({key})"))
        self.stdout.write(f"URL: {url}")

        # ---- Step 1: Scrape ChartInk ----
        driver = None
        try:
            driver = self._setup_driver(headless=headless)
            symbols = self._scrape_symbols(
                driver,
                url=url,
                prefix=prefix,
                save_screenshots=options.get("save_screenshots", True),
            )
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Scrape failed: {exc}"))
            raise
        finally:
            if driver:
                driver.quit()

        if not symbols:
            self.stdout.write(self.style.ERROR("No symbols collected — stopping."))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Step 1 OK: {len(symbols)} symbols from [{key}]"
        ))
        self.stdout.write(", ".join(symbols))

        if options.get("print_only"):
            return

        # ---- Step 2: Update Google Finance stock column ----
        if not sheet:
            self.stdout.write(self.style.WARNING(
                f"No upload sheet mapped for '{key}'. Pass --sheet NAME or use --print-only."
            ))
            return

        try:
            from infra.utils.gfinance import update_gfinance_data

            self.stdout.write(f"Step 2: Updating stock column on worksheet '{sheet}'...")
            result = update_gfinance_data(sheet, symbols)
            self.stdout.write(self.style.SUCCESS(str(result)))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Stock column update failed: {exc}"))
            return

        if options.get("symbols_only"):
            self.stdout.write("Stopped after symbol upload (--symbols-only).")
            return

        # ---- Step 2b: Trigger Google Apps Script ----
        self._trigger_apps_script(apps_script_env)

        # ---- Step 3: Read SMA / result sheet (retry) ----
        if not result_sheet:
            self.stdout.write(self.style.WARNING(
                f"No result_sheet for '{key}'. Pass --result-sheet NAME to continue pipeline."
            ))
            return

        gsheet_data = self._fetch_result_sheet(result_sheet)
        if not gsheet_data:
            return

        # ---- Step 4: Process + update DB ----
        if options.get("skip_db") or not update_db:
            rows = gsheet_data.get("values", [])
            self.stdout.write(self.style.SUCCESS(
                f"Step 3 OK: {max(len(rows) - 1, 0)} data rows from '{result_sheet}' "
                f"(DB update skipped)"
            ))
            return

        self._process_and_update_db(
            gsheet_data,
            new_stock_list=symbols,
            send_telegram_msg=not options.get("skip_telegram"),
        )

    def _resolve_screener(self, options):
        """Return (key, url, sheet, result_sheet, apps_script_env, update_db, label)."""
        custom_url = (options.get("url") or "").strip()
        key = (
            options.get("screener_opt")
            or options.get("screener")
            or DEFAULT_SCREENER
        )
        key = str(key).strip().lower()

        if custom_url:
            if not custom_url.startswith("http"):
                raise CommandError(f"Invalid --url: {custom_url}")
            return (
                "custom",
                custom_url,
                options.get("sheet"),
                options.get("result_sheet"),
                "GSHEET_APP_SCRIPT" if options.get("result_sheet") else None,
                bool(options.get("result_sheet")) and not options.get("skip_db"),
                "custom URL",
            )

        if key not in SCREENERS:
            known = ", ".join(SCREENERS)
            raise CommandError(
                f"Unknown screener '{key}'. Known: {known}. "
                f"Use --list, or pass --url for any ChartInk page."
            )

        meta = SCREENERS[key]
        sheet = options.get("sheet") if options.get("sheet") is not None else meta.get("sheet")
        result_sheet = (
            options.get("result_sheet")
            if options.get("result_sheet") is not None
            else meta.get("result_sheet")
        )
        return (
            key,
            meta["url"],
            sheet,
            result_sheet,
            meta.get("apps_script_env"),
            meta.get("update_db", False),
            meta.get("label", key),
        )

    def _trigger_apps_script(self, apps_script_env):
        """Trigger Google Apps Script if configured in .env."""
        env_name = apps_script_env or "GSHEET_APP_SCRIPT"
        script_url = ""
        # Prefer process/env via settings BASE_DIR idirect/.env (tolerant parse)
        env_map = self._load_env_file(Path(settings.BASE_DIR) / "idirect" / ".env")
        if env_name:
            script_url = (env_map.get(env_name) or "").strip()
        if not script_url:
            self.stdout.write(self.style.WARNING(
                f"{env_name or 'GSHEET_APP_SCRIPT'} not configured — skipping Apps Script. "
                "Run the script manually if needed."
            ))
            return False

        self.stdout.write(f"Step 2b: Triggering Google Apps Script ({env_name})...")
        try:
            response = requests.get(script_url, timeout=60)
            self.stdout.write(f"Google Apps Script response: {response.status_code}")
            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS("Google Apps Script triggered"))
                wait_time = 15
                self.stdout.write(
                    f"Waiting {wait_time}s for Apps Script to fill result sheet..."
                )
                time.sleep(wait_time)
                return True
            self.stdout.write(self.style.WARNING(
                f"Apps Script returned status {response.status_code} — continuing anyway"
            ))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"Error triggering Apps Script: {exc} — continuing anyway"
            ))
        return False

    def _fetch_result_sheet(self, sheet_name, max_retries=3, retry_delay=10):
        """Step 3: Read SMA/result sheet via Sheets API with retries."""
        from infra.utils.gfinance import get_gfinance_data

        # Prefer Django settings (idirect/.env via RepositoryEnv).
        # Also fall back to parsing idirect/.env with tolerant KEY = value spacing.
        spreadsheet_id = str(getattr(settings, "GSHEET_ID", "") or "").strip()
        api_key = str(getattr(settings, "GSHEET_KEY", "") or "").strip()

        if not spreadsheet_id or not api_key:
            env_path = Path(settings.BASE_DIR) / "idirect" / ".env"
            env_map = self._load_env_file(env_path)
            spreadsheet_id = spreadsheet_id or env_map.get("GSHEET_ID", "").strip()
            api_key = api_key or env_map.get("GSHEET_KEY", "").strip()

        if not spreadsheet_id or not api_key:
            missing = [n for n, v in (("GSHEET_ID", spreadsheet_id), ("GSHEET_KEY", api_key)) if not v]
            self.stdout.write(self.style.ERROR(
                f"{' / '.join(missing)} empty after settings + idirect/.env. "
                "Use KEY=value with no spaces around '=', then re-run."
            ))
            return None

        self.stdout.write(
            f"Using GSHEET_ID={spreadsheet_id[:6]}… GSHEET_KEY={api_key[:4]}… "
            f"(lengths {len(spreadsheet_id)}/{len(api_key)})"
        )

        for attempt in range(1, max_retries + 1):
            try:
                self.stdout.write(
                    f"\nStep 3: Fetching '{sheet_name}' from Google Sheets "
                    f"(attempt {attempt}/{max_retries})..."
                )
                # get_gfinance_data already performs the HTTP GET and returns JSON
                gsheet_data = get_gfinance_data(spreadsheet_id, sheet_name, api_key)
                if not gsheet_data:
                    raise RuntimeError("get_gfinance_data returned empty")

                rows = gsheet_data.get("values", [])
                if not rows:
                    raise RuntimeError("Sheet has no rows yet")

                self.stdout.write(self.style.SUCCESS(
                    f"Fetched {len(rows) - 1} data rows from '{sheet_name}' "
                    f"on attempt {attempt}"
                ))
                self.stdout.write(f"Headers: {rows[0]}")
                return gsheet_data

            except Exception as exc:
                if attempt < max_retries:
                    self.stdout.write(self.style.WARNING(
                        f"Attempt {attempt} failed: {exc}. Retrying in {retry_delay}s..."
                    ))
                    time.sleep(retry_delay)
                else:
                    self.stdout.write(self.style.ERROR(
                        f"Failed to fetch '{sheet_name}' after {max_retries} attempts: {exc}"
                    ))
                    self.stdout.write(self.style.ERROR(
                        "Check: Apps Script finished? Sheet name correct? API key access?"
                    ))
                    return None
        return None

    def _load_env_file(self, env_path):
        """Parse KEY=value from env file; tolerates spaces around '='."""
        data = {}
        try:
            path = Path(env_path)
            if not path.exists():
                self.stdout.write(self.style.WARNING(f"Env file not found: {env_path}"))
                return data
            for raw in path.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key:
                    data[key] = val
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"Could not read {env_path}: {exc}"))
        return data

    def _process_and_update_db(self, gsheet_data, new_stock_list, send_telegram_msg=True):
        """Step 4: Upsert Stocks50MA from sheet rows (same logic as chartink.py)."""
        from data.models import Stocks50MA
        from infra.utils.infra import date_format, safe_float
        from infra.utils.telegram import send_telegram

        rows = gsheet_data.get("values", [])
        if not rows:
            self.stdout.write(self.style.ERROR("No rows to process"))
            return

        headers = rows[0]
        new_stock_set = {s.strip().upper() for s in new_stock_list} if new_stock_list else set()
        if new_stock_set:
            preview = ", ".join(list(new_stock_set)[:10])
            more = "..." if len(new_stock_set) > 10 else ""
            self.stdout.write(self.style.SUCCESS(
                f"Step 4: Processing {len(new_stock_set)} ChartInk symbols: {preview}{more}"
            ))

        bot_txt = self._build_telegram_message()
        updated_count = 0
        created_count = 0
        skipped_count = 0
        processed_new_stocks = set()
        today = timezone.now().date()

        for row in rows[1:]:
            if len(row) < len(headers):
                skipped_count += 1
                continue

            row_dict = dict(zip(headers, row))
            script = row_dict.get("Stock")
            if not script:
                continue

            script = script.strip().upper()
            stock_code = script

            if new_stock_set and script not in new_stock_set:
                continue

            is_new_stock = script in new_stock_set if new_stock_set else False

            try:
                obj = Stocks50MA.objects.filter(
                    Q(script__iexact=script) | Q(stock_code__iexact=stock_code)
                ).order_by("-date", "-created_at").first()

                if obj:
                    backup_entry = {
                        "moving_average_50": obj.moving_average_50,
                        "stock_cmp": obj.stock_cmp,
                        "cmp_date": obj.cmp_date.isoformat() if obj.cmp_date else None,
                        "range_50ma": obj.range_50ma,
                        "target_1": obj.target_1,
                        "target_2": obj.target_2,
                    }
                    if not isinstance(obj.pre_data, list):
                        obj.pre_data = []
                    obj.pre_data.append(backup_entry)

                    obj.name = row_dict.get("Name")
                    obj.stock_cmp = safe_float(row_dict.get("CMP"))
                    obj.moving_average_50 = safe_float(row_dict.get("50MA"))
                    obj.moving_average_20 = safe_float(row_dict.get("20MA"))
                    obj.moving_average_09 = safe_float(row_dict.get("09MA"))
                    obj.range_50ma = safe_float(row_dict.get("Range 50MA"))
                    obj.range_20ma = safe_float(row_dict.get("Range 20MA"))
                    obj.range_09ma = safe_float(row_dict.get("Range 09MA"))
                    obj.percent_50ma = safe_float(row_dict.get("Percent 50MA"))
                    obj.percent_20ma = safe_float(row_dict.get("Percent 20MA"))
                    obj.percent_09ma = safe_float(row_dict.get("Percent 09MA"))
                    obj.target_1 = safe_float(row_dict.get("Target 1"))
                    obj.target_2 = safe_float(row_dict.get("Target 2"))
                    obj.cmp_date = date_format(row_dict.get("Trad Date"))
                    obj.status = 5
                    if is_new_stock and (not obj.date or obj.date < today):
                        obj.date = today
                    obj.save()
                    updated_count += 1
                    if is_new_stock:
                        processed_new_stocks.add(script)
                    self.stdout.write(f"Updated: {script} (ID {obj.id}, status=5)")
                else:
                    Stocks50MA.objects.create(
                        stock_code=stock_code,
                        script=script,
                        date=today,
                        name=row_dict.get("Name"),
                        stock_cmp=safe_float(row_dict.get("CMP")),
                        moving_average_50=safe_float(row_dict.get("50MA")),
                        moving_average_20=safe_float(row_dict.get("20MA")),
                        moving_average_09=safe_float(row_dict.get("09MA")),
                        range_50ma=safe_float(row_dict.get("Range 50MA")),
                        range_20ma=safe_float(row_dict.get("Range 20MA")),
                        range_09ma=safe_float(row_dict.get("Range 09MA")),
                        percent_50ma=safe_float(row_dict.get("Percent 50MA")),
                        percent_20ma=safe_float(row_dict.get("Percent 20MA")),
                        percent_09ma=safe_float(row_dict.get("Percent 09MA")),
                        target_1=safe_float(row_dict.get("Target 1")),
                        target_2=safe_float(row_dict.get("Target 2")),
                        cmp_date=date_format(row_dict.get("Trad Date")),
                        status=4,
                    )
                    created_count += 1
                    processed_new_stocks.add(script)
                    self.stdout.write(self.style.SUCCESS(
                        f"Created: {script} (status=4)"
                    ))

                bot_txt += (
                    f"| {str(row_dict.get('Sno', '')).ljust(6)}"
                    f"| {script.ljust(22)}"
                    f"| {str(row_dict.get('CMP', '')).ljust(7)}"
                    f"| {str(row_dict.get('50MA', '')).ljust(7)}"
                    f"| {str(row_dict.get('Percent 50MA', '')).ljust(10)}|\n"
                )
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Error processing {script}: {exc}"))
                continue

        bot_txt += "+--------+----------------------+--------+--------+------------+\n"
        bot_txt += "```"

        if send_telegram_msg and (updated_count > 0 or created_count > 0):
            try:
                send_telegram(bot_txt)
                self.stdout.write(self.style.SUCCESS("Telegram notification sent"))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Telegram failed: {exc}"))

        if new_stock_set:
            missing = new_stock_set - processed_new_stocks
            if missing:
                self.stdout.write(self.style.WARNING(
                    f"{len(missing)} ChartInk symbols missing from result sheet: "
                    f"{', '.join(list(missing)[:15])}"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"\n{'=' * 60}\n"
            f"Summary:\n"
            f"  Updated: {updated_count}\n"
            f"  Created: {created_count}\n"
            f"  Skipped incomplete rows: {skipped_count}\n"
            f"  Total processed: {updated_count + created_count}\n"
            f"{'=' * 60}"
        ))

    def _build_telegram_message(self):
        trigger_time = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
        bot_txt = (
            "ChartInk 50MA Update\n"
            f"Trigger Time: {trigger_time}\n\n"
        )
        bot_txt += "```\n"
        bot_txt += "+--------+----------------------+--------+--------+------------+\n"
        bot_txt += "|   #    | 50MA Stock Code      |  CMP   | SMA50  | % SMA50    |\n"
        bot_txt += "+--------+----------------------+--------+--------+------------+\n"
        return bot_txt

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

    def _scrape_symbols(self, driver, url, prefix="chartink", save_screenshots=True):
        wait = WebDriverWait(driver, 40)
        driver.get(url)
        self.stdout.write("Waiting for scan results...")

        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "table.scan-results-table tbody tr")
                )
            )
        except TimeoutException:
            self._screenshot(driver, f"{prefix}_01_no_table.png", save_screenshots)
            self.stdout.write(self.style.ERROR("Results table never appeared"))
            return []

        time.sleep(2)
        self._screenshot(driver, f"{prefix}_01_loaded.png", save_screenshots)

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
        self._screenshot(driver, f"{prefix}_02_after_copy.png", save_screenshots)

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
        self._screenshot(driver, f"{prefix}_03_after_symbols.png", save_screenshots)

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
