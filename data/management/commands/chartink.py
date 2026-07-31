import time
import os
import gspread
import requests
from decouple import config
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Try to import pyperclip for clipboard access
try:
    import pyperclip
except ImportError:
    pyperclip = None
from django.core.management.base import BaseCommand
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials
from data.models import Stocks50MA
from django.db.models import Q
from datetime import datetime
from infra.utils.telegram import send_telegram
from infra.utils.infra import date_format, safe_float
from infra.utils.gfinance import get_gfinance_data, filter_stock, update_gfinance_data


class Command(BaseCommand):
    help = """Fetch 50ma-setup data from chartink using selenium, store in App
    
    IMPORTANT: Clipboard Permissions
    - In headless mode: Permissions are granted automatically via Chrome DevTools Protocol
    - In visible mode (--no-headless): Browser may prompt for clipboard permission
      → Click "Allow" when prompted to enable clipboard access
    - If clipboard is empty, try running with --no-headless and manually grant permission
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--headless',
            action='store_true',
            default=True,
            help='Run browser in headless mode (default: True). Clipboard permissions granted automatically.',
        )
        parser.add_argument(
            '--no-headless',
            action='store_false',
            dest='headless',
            help='Run browser in visible mode (for debugging). You may need to manually grant clipboard permission when prompted.',
        )
        parser.add_argument(
            '--skip-scraping',
            action='store_true',
            help='Skip Chartink scraping, only process Google Sheets data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting 50MA Chartink scraper..."))
        
        #file_path = os.path.join(settings.MEDIA_ROOT, "result_1.html")
        new_stock_list = []
        driver = None

        # Step 1: Scrape Chartink (unless skipped)
        if not options.get('skip_scraping', False):
            try:
                driver = self._setup_selenium(headless=options.get('headless', True))
                new_stock_list = self._scrape_chartink(driver)
                self.stdout.write(self.style.SUCCESS(f"Found {len(new_stock_list)} stocks from Chartink"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error scraping Chartink: {str(e)}"))
                if driver:
                    driver.quit()
                return
            finally:
                if driver:
                    driver.quit()
            
            # CRITICAL: Stop if zero results - don't proceed to Google Sheets
            if not new_stock_list or len(new_stock_list) == 0:
                self.stdout.write(self.style.ERROR("=" * 60))
                self.stdout.write(self.style.ERROR("ZERO STOCKS EXTRACTED - STOPPING PROCESS"))
                self.stdout.write(self.style.ERROR("=" * 60))
                self.stdout.write(self.style.WARNING("No stocks found. Possible reasons:"))
                self.stdout.write(self.style.WARNING("  1. Chartink results table empty / not loaded"))
                self.stdout.write(self.style.WARNING("  2. Page blocked or selectors outdated"))
                self.stdout.write(self.style.WARNING("  3. Clipboard fallback failed (normal in Docker)"))
                self.stdout.write(self.style.WARNING("  4. Parsing failed to extract symbols"))
                self.stdout.write(self.style.ERROR("Process stopped. Google Sheets upload skipped."))
                return

        # Step 2: Update Google Finance Sheet with new stocks (only if we have stocks)
        if new_stock_list and len(new_stock_list) > 0:
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(self.style.SUCCESS(f"SUCCESS: {len(new_stock_list)} stocks extracted - Proceeding to Google Sheets"))
            self.stdout.write(self.style.SUCCESS("=" * 60))
            try:
                self.stdout.write("Updating Google Finance Sheet...")
                list_data = update_gfinance_data("googleFinace", new_stock_list)
                self.stdout.write(self.style.SUCCESS(str(list_data)))
                
                # Trigger Google Apps Script if configured 
                copy_GF_sma = config('GSHEET_APP_SCRIPT', default='')
                if copy_GF_sma:
                    self.stdout.write("Triggering Google Apps Script to process data...")
                    try:
                        response = requests.get(copy_GF_sma, timeout=30)
                        self.stdout.write(f"Google Apps Script response: {response.status_code}")
                        if response.status_code == 200:
                            self.stdout.write(self.style.SUCCESS("Google Apps Script triggered successfully"))
                            # Wait for Google Apps Script to process and update the 50ma sheet
                            self.stdout.write("Waiting for Google Apps Script to process data (this may take 10-30 seconds)...")
                            import time
                            wait_time = 15  # Initial wait
                            self.stdout.write(f"Waiting {wait_time} seconds for data processing...")
                            time.sleep(wait_time)
                        else:
                            self.stdout.write(self.style.WARNING(f"Google Apps Script returned status {response.status_code}"))
                    except Exception as script_error:
                        self.stdout.write(self.style.WARNING(f"Error triggering Google Apps Script: {str(script_error)}"))
                        self.stdout.write(self.style.WARNING("Continuing anyway - data may not be ready in 50ma sheet"))
                else:
                    self.stdout.write(self.style.WARNING("GSHEET_APP_SCRIPT not configured - skipping script trigger"))
                    self.stdout.write(self.style.WARNING("Make sure Google Apps Script runs manually or configure GSHEET_APP_SCRIPT in .env"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Warning updating Google Sheet: {str(e)}"))

        # Step 3: Get SMA50 values from Google Sheets (with retry mechanism)
        try:
            max_retries = 3
            retry_delay = 10  # seconds
            gsheet_data = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    self.stdout.write(f"\nFetching SMA Price from Google Finance (attempt {attempt}/{max_retries})...")
                    spreadsheet_id = settings.GSHEET_ID
                    sheet_name = "50ma"
                    api_key = settings.GSHEET_KEY

                    gsheet_data = get_gfinance_data(spreadsheet_id, sheet_name, api_key)
                    responses = requests.get(gsheet_data, timeout=30)
                    self.stdout.write(f"Google Apps Script response---: {responses.status_code}")
                    if not gsheet_data:
                        if attempt < max_retries:
                            self.stdout.write(self.style.WARNING(f"Failed to fetch Google Sheets data (attempt {attempt}). Retrying in {retry_delay} seconds..."))
                            import time
                            time.sleep(retry_delay)
                            continue
                        else:
                            self.stdout.write(self.style.ERROR("Failed to fetch Google Sheets data after all retries"))
                            return
                    
                    rows = gsheet_data.get("values", [])
                    if not rows:
                        if attempt < max_retries:
                            self.stdout.write(self.style.WARNING(f"No data found in Google Sheets (attempt {attempt}). Retrying in {retry_delay} seconds..."))
                            self.stdout.write(self.style.WARNING("This might mean Google Apps Script hasn't finished processing yet"))
                            import time
                            time.sleep(retry_delay)
                            continue
                        else:
                            self.stdout.write(self.style.ERROR("No data found in Google Sheets after all retries"))
                            self.stdout.write(self.style.ERROR("Possible issues:"))
                            self.stdout.write(self.style.ERROR("  1. Google Apps Script hasn't finished processing"))
                            self.stdout.write(self.style.ERROR("  2. Sheet name '50ma' is incorrect"))
                            self.stdout.write(self.style.ERROR("  3. Google Sheets API key doesn't have access"))
                            return
                    
                    # Successfully got data - break out of retry loop
                    self.stdout.write(self.style.SUCCESS(f"Successfully fetched Google Sheets data on attempt {attempt}"))
                    break
                    
                except Exception as e:
                    if attempt < max_retries:
                        self.stdout.write(self.style.WARNING(f"Error fetching Google Sheets data (attempt {attempt}): {str(e)}"))
                        self.stdout.write(self.style.WARNING(f"Retrying in {retry_delay} seconds..."))
                        import time
                        time.sleep(retry_delay)
                        continue
                    else:
                        self.stdout.write(self.style.ERROR(f"Error fetching Google Sheets data after all retries: {str(e)}"))
                        import traceback
                        self.stdout.write(traceback.format_exc())
                        return
            
            # Process the data (outside retry loop)
            if not gsheet_data:
                self.stdout.write(self.style.ERROR("No data available to process"))
                return
                
            rows = gsheet_data.get("values", [])
            if not rows:
                self.stdout.write(self.style.ERROR("No rows found in Google Sheets data"))
                return
                
            headers = rows[0]
            self.stdout.write(self.style.SUCCESS(f"Found {len(rows)-1} rows in Google Sheets"))
            self.stdout.write(f"Headers: {headers}")
            
            # Create a set of new stock symbols (normalized) for quick lookup
            new_stock_set = {s.strip().upper() for s in new_stock_list} if new_stock_list else set()
            if new_stock_set:
                self.stdout.write(self.style.SUCCESS(f"Will process {len(new_stock_set)} NEW stocks from Chartink: {', '.join(list(new_stock_set)[:10])}{'...' if len(new_stock_set) > 10 else ''}"))

            # Step 4: Process and update database
            bot_txt = self._build_telegram_message()
            updated_count = 0
            created_count = 0
            skipped_count = 0
            processed_new_stocks = set()

            for row in rows[1:]:
                if len(row) < len(headers):
                    skipped_count += 1
                    self.stdout.write(self.style.WARNING(f"Skipping incomplete row: {row[:3]}..."))
                    continue  # Skip incomplete rows

                row_dict = dict(zip(headers, row))
                script = row_dict.get("Stock")

                if not script:
                    continue

                # Normalize script value (trim whitespace, uppercase)
                script = script.strip().upper()
                # Use script as stock_code if stock_code is not provided
                stock_code = script
                
                # If we have new_stock_list, only process those stocks
                if new_stock_set and script not in new_stock_set:
                    # Skip stocks that are not in the new list
                    continue

                try:
                    # Get today's date for checking/creating records
                    from django.utils import timezone
                    today = timezone.now().date()
                        
                    # For NEW stocks from Chartink, check if record exists with today's date
                    # If not found, create new record. If found, update it.
                    # For existing stocks, find the most recent record
                    is_new_stock = script in new_stock_set if new_stock_set else False
                    
                    if is_new_stock:
                        # For new stocks, check by stock_code and today's date (or most recent)
                        obj = Stocks50MA.objects.filter(
                            Q(script__iexact=script) | Q(stock_code__iexact=stock_code)
                        ).order_by('-date', '-created_at').first()
                    else:
                        # For existing stocks, find the most recent record
                        obj = Stocks50MA.objects.filter(
                            Q(script__iexact=script) | Q(stock_code__iexact=stock_code)
                        ).order_by('-date', '-created_at').first()
                    
                    # Debug: Log lookup result
                    if obj:
                        self.stdout.write(f"  [LOOKUP] Found existing: {script} (ID: {obj.id}, stock_code: {obj.stock_code}, date: {obj.date})")
                    else:
                        self.stdout.write(self.style.SUCCESS(f"  [LOOKUP] NEW stock not found in DB: {script}"))

                    if obj:
                        # Backup old state
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

                        # Update fields
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
                        # Update date to today if it's a new stock being updated
                        if is_new_stock and (not obj.date or obj.date < today):
                            obj.date = today
                        obj.save()
                        updated_count += 1
                        if is_new_stock:
                            processed_new_stocks.add(script)
                            self.stdout.write(f"Updated existing stock (NEW from Chartink): {script} (ID: {obj.id})")
                        else:
                            self.stdout.write(f"Updated existing stock: {script} (ID: {obj.id})")

                    else:
                        # Create new record
                        obj = Stocks50MA.objects.create(
                            stock_code=stock_code,
                            script=script,
                            date=today,  # Set today's date
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
                            status=4
                        )
                        created_count += 1
                        processed_new_stocks.add(script)
                        self.stdout.write(self.style.SUCCESS(f"✅ Created NEW stock: {script} (ID: {obj.id})"))

                    # Add to telegram message
                    bot_txt += (
                        f"| {str(row_dict.get('Sno', '')).ljust(6)}"
                        f"| {script.ljust(22)}"
                        f"| {str(row_dict.get('CMP', '')).ljust(7)}"
                        f"| {str(row_dict.get('50MA', '')).ljust(7)}"
                        f"| {str(row_dict.get('Percent 50MA', '')).ljust(10)}|\n"
                    )

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error processing {script}: {str(e)}"))
                    continue

            # Close telegram message
            bot_txt += "+--------+----------------------+--------+--------+------------+\n"
            bot_txt += "```"  # End monospaced block

            # Send telegram notification
            if updated_count > 0 or created_count > 0:
                try:
                    send_telegram(bot_txt)
                    self.stdout.write(self.style.SUCCESS("Telegram notification sent"))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Failed to send Telegram: {str(e)}"))

            # Check if all new stocks were processed
            if new_stock_set:
                missing_stocks = new_stock_set - processed_new_stocks
                if missing_stocks:
                    self.stdout.write(self.style.WARNING(
                        f"\n⚠️  WARNING: {len(missing_stocks)} new stocks from Chartink were NOT found in Google Sheets:\n"
                        f"   Missing: {', '.join(list(missing_stocks)[:10])}{'...' if len(missing_stocks) > 10 else ''}"
                    ))
                    self.stdout.write(self.style.WARNING(
                        "   Possible reasons:\n"
                        "   1. Google Apps Script hasn't processed them yet\n"
                        "   2. Stock symbols don't match (case/format differences)\n"
                        "   3. Stocks were filtered out in Google Sheets"
                    ))
            
            self.stdout.write(self.style.SUCCESS(
                f"\n{'='*60}\nSummary:\n  - Updated: {updated_count} stocks\n  - Created: {created_count} NEW stocks\n  - Skipped: {skipped_count} incomplete rows\n  - Total processed: {updated_count + created_count} stocks"
            ))
            if new_stock_set:
                self.stdout.write(self.style.SUCCESS(
                    f"  - New stocks processed: {len(processed_new_stocks)}/{len(new_stock_set)}"
                ))
            self.stdout.write(self.style.SUCCESS(f"{'='*60}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing Google Sheets data: {str(e)}"))
            import traceback
            self.stdout.write(traceback.format_exc())

    def _setup_selenium(self, headless=True):
        """Setup Selenium WebDriver"""
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        # Disable automation flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Enable clipboard permissions
        prefs = {
            "profile.default_content_setting_values.clipboard": 1,  # Allow clipboard access
            "profile.content_settings.exceptions.clipboard": {
                "https://chartink.com,*": {
                    "setting": 1  # Allow clipboard for chartink.com
                }
            }
        }
        options.add_experimental_option("prefs", prefs)
        
        driver = webdriver.Chrome(options=options)
        
        # Execute script to hide webdriver property
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        })
        
        # Grant clipboard permissions using Chrome DevTools Protocol
        try:
            # Try different permission name formats (Chrome versions vary)
            permission_names = [
                ['clipboardRead', 'clipboardWrite'],  # Modern Chrome
                ['clipboard-read', 'clipboard-write'],  # Alternative format
                ['clipboard'],  # Generic
            ]
            
            granted = False
            for perms in permission_names:
                try:
                    driver.execute_cdp_cmd('Browser.grantPermissions', {
                        'origin': 'https://chartink.com',
                        'permissions': perms
                    })
                    self.stdout.write(f"Granted clipboard permissions via CDP: {perms}")
                    granted = True
                    break
                except:
                    continue
            
            if not granted:
                self.stdout.write(self.style.WARNING("Could not grant clipboard permissions via CDP (may not be supported in this Chrome version)"))
                if not headless:
                    self.stdout.write(self.style.WARNING("Running in visible mode - you may need to manually grant clipboard permission when browser prompts"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"CDP permission grant failed: {str(e)}"))
            if not headless:
                self.stdout.write(self.style.WARNING("Running in visible mode - you may need to manually grant clipboard permission when browser prompts"))
        
        return driver

    def _extract_symbols_from_results_table(self, driver):
        """Primary Docker-safe path: read symbols from scan-results-table (no clipboard)."""
        symbols = []
        seen = set()
        wait = WebDriverWait(driver, 45)

        try:
            wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "table.scan-results-table tbody tr")
            ))
        except TimeoutException:
            self.stdout.write(self.style.WARNING(
                "scan-results-table not ready — page may still be loading or blocked"
            ))
            return []

        # Prefer larger page size so we avoid pagination when possible
        try:
            per_page = driver.execute_script("""
                const labels = [...document.querySelectorAll('button, div, span, select')]
                  .filter(el => /per\\s*page/i.test(el.textContent || ''));
                // vue-good-table style: clickable page-size options
                const candidates = [...document.querySelectorAll('button, li, a, span')]
                  .filter(el => {
                    const t = (el.textContent || '').trim();
                    return t === '50' || t === '40' || t === '30';
                  });
                for (const el of candidates) {
                  if (el.offsetParent !== null) {
                    el.click();
                    return el.textContent.trim();
                  }
                }
                return null;
            """)
            if per_page:
                self.stdout.write(f"Set results per page to {per_page}")
                time.sleep(2)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Could not change per-page size: {e}"))

        max_pages = 20
        for page in range(1, max_pages + 1):
            page_symbols = driver.execute_script("""
                const table = document.querySelector('table.scan-results-table');
                if (!table) return [];
                const rows = [...table.querySelectorAll('tbody tr')];
                const out = [];
                for (const row of rows) {
                  const cells = [...row.querySelectorAll('td')];
                  let sym = '';
                  // Column layout: Sr | Stock Name | Symbol | close | %_change | volume
                  if (cells.length >= 3) {
                    sym = (cells[2].textContent || '').trim();
                  }
                  if (!sym) {
                    const a = row.querySelector('a[href*="symbol="]');
                    if (a) {
                      const m = (a.getAttribute('href') || '').match(/symbol=([^&]+)/);
                      if (m) sym = decodeURIComponent(m[1]);
                    }
                  }
                  if (sym) out.push(sym.toUpperCase());
                }
                return out;
            """) or []

            added = 0
            for sym in page_symbols:
                clean = ''.join(c for c in sym.strip().upper() if c.isalnum() or c == '-')
                if clean and len(clean) <= 20 and clean not in seen:
                    seen.add(clean)
                    symbols.append(clean)
                    added += 1

            self.stdout.write(
                f"Table page {page}: read {len(page_symbols)} rows, +{added} new "
                f"(total {len(symbols)})"
            )

            # Click Next if available and not disabled
            clicked_next = driver.execute_script("""
                const buttons = [...document.querySelectorAll('button')];
                const next = buttons.find(b => {
                  const t = (b.textContent || '').trim();
                  return t === 'Next' || t === 'Next >>' || /^next$/i.test(t);
                });
                if (!next) return false;
                if (next.disabled || next.classList.contains('disabled') ||
                    next.getAttribute('aria-disabled') === 'true' ||
                    /opacity-40|cursor-not-allowed/.test(next.className || '')) {
                  return false;
                }
                const before = document.querySelector('table.scan-results-table tbody tr td');
                const beforeText = before ? before.textContent : '';
                next.click();
                return beforeText || true;
            """)

            if not clicked_next:
                break

            # Wait for first row to change or settle
            time.sleep(1.5)
            try:
                wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "table.scan-results-table tbody tr")
                ))
            except TimeoutException:
                break

            if added == 0 and page > 1:
                # No new symbols after Next — stop
                break

        if symbols:
            self.stdout.write(self.style.SUCCESS(
                f"Extracted {len(symbols)} symbols from results table"
            ))
            self.stdout.write(
                f"Symbols: {', '.join(symbols[:15])}{'...' if len(symbols) > 15 else ''}"
            )
        else:
            self.stdout.write(self.style.WARNING("Table scrape found 0 symbols"))

        return symbols

    def _scrape_chartink(self, driver):
        """Scrape Chartink screener — table first (Docker-safe), clipboard optional."""
        if pyperclip is None:
            self.stdout.write(self.style.WARNING(
                "pyperclip not installed — clipboard fallback disabled. "
                "Table scrape will be used (recommended in Docker)."
            ))
        
        url = "https://chartink.com/screener/50ma-setup"
        driver.get(url)
        wait = WebDriverWait(driver, 30)
        self.stdout.write(f"Fetching data from {url}")

        # Grant clipboard permissions again after page load (optional; table path does not need this)
        try:
            permission_names = [
                ['clipboardRead', 'clipboardWrite'],
                ['clipboard-read', 'clipboard-write'],
                ['clipboard'],
            ]
            for perms in permission_names:
                try:
                    driver.execute_cdp_cmd('Browser.grantPermissions', {
                        'origin': 'https://chartink.com',
                        'permissions': perms
                    })
                    self.stdout.write(f"Re-granted clipboard permissions after page load: {perms}")
                    break
                except:
                    continue
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Could not re-grant permissions: {str(e)}"))

        # Wait for page to fully load - Chartink uses React/JS
        time.sleep(10)
        
        # Take screenshot after page load
        screenshot_dir = os.path.join(settings.MEDIA_ROOT, "screenshots")
        try:
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_1 = os.path.join(screenshot_dir, "01_page_loaded.png")
            driver.save_screenshot(screenshot_1)
            self.stdout.write(f"Screenshot saved: {screenshot_1}")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Could not save screenshot: {str(e)}"))

        # PRIMARY: DOM table (works headless / Docker without clipboard)
        self.stdout.write("Extracting symbols from scan-results-table (primary method)...")
        table_stocks = self._extract_symbols_from_results_table(driver)
        if table_stocks:
            return table_stocks

        self.stdout.write(self.style.WARNING(
            "Table extraction returned 0 stocks — falling back to Copy/clipboard methods"
        ))
        
        new_stock_list = []
        
        try:
            # Find the copy button - it's a DIV, not a BUTTON!
            # Structure: <div class="secondary-button ..."><div><span>Copy</span></div></div>
            copy_button_selectors = [
                # Primary selectors - looking for div with secondary-button class containing "Copy"
                "//div[contains(@class, 'secondary-button')]//span[contains(text(), 'Copy')]/ancestor::div[contains(@class, 'secondary-button')]",
                "//div[@class='secondary-button w-fit px-2 lg:px-4 py-1.5 opacity-100 cursor-pointer']//span[contains(text(), 'Copy')]/ancestor::div[contains(@class, 'secondary-button')]",
                "//div[contains(@class, 'secondary-button') and contains(., 'Copy')]",
                "div.secondary-button:has(span:contains('Copy'))",  # CSS selector (may not work in all browsers)
                "//div[contains(@class, 'secondary-button')][.//span[contains(text(), 'Copy')]]",
            ]
            
            copy_button = None
            found_selector = None
            
            # First, let's see all divs with secondary-button class for debugging
            try:
                all_divs = driver.find_elements(By.CSS_SELECTOR, "div.secondary-button")
                self.stdout.write(f"Found {len(all_divs)} divs with 'secondary-button' class")
                for idx, div in enumerate(all_divs[:10]):  # Show first 10
                    try:
                        div_text = div.text.strip()
                        div_classes = div.get_attribute("class") or ""
                        # Check if it contains Copy
                        has_copy = "copy" in div_text.lower()
                        self.stdout.write(f"  Div {idx+1}: text='{div_text[:50]}', classes='{div_classes[:100]}', has_copy={has_copy}")
                    except:
                        pass
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error listing divs: {str(e)}"))
            
            # Try XPath selectors first (most reliable)
            for selector in copy_button_selectors:
                try:
                    if selector.startswith("//"):
                        copy_button = wait.until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        # CSS selector
                        copy_button = wait.until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    if copy_button:
                        found_selector = selector
                        self.stdout.write(self.style.SUCCESS(f"Found copy div using selector: {selector[:80]}..."))
                        # Take screenshot of found button
                        try:
                            screenshot_2 = os.path.join(screenshot_dir, "02_copy_button_found.png")
                            driver.save_screenshot(screenshot_2)
                            self.stdout.write(f"Screenshot saved: {screenshot_2}")
                        except:
                            pass
                        break
                except TimeoutException:
                    continue
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Error with selector {selector[:50]}...: {str(e)}"))
                    continue
            
            if not copy_button:
                # Fallback: Find all divs with secondary-button class and check for "Copy" text
                try:
                    all_divs = driver.find_elements(By.CSS_SELECTOR, "div.secondary-button")
                    self.stdout.write(f"Searching {len(all_divs)} divs with 'secondary-button' class for 'Copy' text...")
                    for div in all_divs:
                        try:
                            div_text = div.text.strip().lower()
                            div_classes = div.get_attribute("class") or ""
                            # Check if this div contains "Copy" text
                            if "copy" in div_text:
                                copy_button = div
                                found_selector = f"text search in div: '{div.text.strip()}'"
                                self.stdout.write(self.style.SUCCESS(f"Found copy div by text search: '{div.text.strip()}'"))
                                self.stdout.write(f"  Div classes: {div_classes}")
                                break
                        except Exception as e:
                            continue
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Error searching divs: {str(e)}"))
            
            if not copy_button:
                self.stdout.write(self.style.ERROR("Could not find copy div!"))
                # Save page source and screenshot for debugging
                try:
                    page_source = driver.page_source
                    debug_file = os.path.join(settings.MEDIA_ROOT, "chartink_debug.html")
                    with open(debug_file, "w", encoding="utf-8") as f:
                        f.write(page_source)
                    self.stdout.write(f"Page source saved to: {debug_file}")
                    
                    screenshot_3 = os.path.join(screenshot_dir, "03_no_copy_button.png")
                    driver.save_screenshot(screenshot_3)
                    self.stdout.write(f"Screenshot saved: {screenshot_3}")
                except Exception as e:
                    self.stdout.write(f"Could not save debug files: {str(e)}")
                return new_stock_list
            
            # Clear clipboard first
            try:
                import subprocess
                if os.name == 'nt':  # Windows
                    subprocess.run(['clip'], input='', text=True, check=False)
                else:  # Linux/Mac
                    subprocess.run(['xclip', '-selection', 'clipboard'], input='', text=True, check=False)
            except:
                pass  # Ignore clipboard clear errors
            
            # Click the copy div (it's a div, not a button!)
            self.stdout.write(f"Clicking copy div (found with: {found_selector[:80]}...)...")
            
            # Scroll button into view first
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", copy_button)
                time.sleep(1)
            except:
                pass
            
            # Try multiple click methods
            try:
                copy_button.click()
                self.stdout.write("Clicked using .click() method")
            except Exception as e:
                self.stdout.write(f"Standard click failed: {str(e)}, trying JavaScript click...")
                try:
                    driver.execute_script("arguments[0].click();", copy_button)
                    self.stdout.write("Clicked using JavaScript")
                except Exception as e2:
                    self.stdout.write(self.style.ERROR(f"JavaScript click also failed: {str(e2)}"))
                    return new_stock_list
            
            # Take screenshot after click
            try:
                screenshot_4 = os.path.join(screenshot_dir, "04_after_copy_click.png")
                driver.save_screenshot(screenshot_4)
                self.stdout.write(f"Screenshot saved: {screenshot_4}")
            except:
                pass
            
            # Wait for dialog/menu to appear (Chartink asks what to copy)
            time.sleep(2)
            
            # Find and click "Symbols" option in the dialog
            # Structure: <span class="cursor-pointer hover:underline"><span class="hidden sm:inline">symbols</span></span>
            # We need to click the parent span with cursor-pointer class
            symbols_option = None
            
            # First try: Find parent span that contains "symbols" text (case-insensitive)
            # This should match: <span class="cursor-pointer hover:underline">...symbols...</span>
            symbols_selectors = [
                # Primary: Parent span containing symbols (case-insensitive text search)
                "//span[contains(@class, 'cursor-pointer') and contains(@class, 'hover:underline')][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'symbols')]",
                # Alternative: Find via child span with hidden sm:inline
                "//span[contains(@class, 'hidden') and contains(@class, 'sm:inline')][contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'symbols')]/ancestor::span[contains(@class, 'cursor-pointer')][1]",
                # Simpler: any span with cursor-pointer that contains symbols text
                "//span[contains(@class, 'cursor-pointer')][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'symbols')]",
                # Legacy: direct text match
                "//span[contains(text(), 'symbols')]/ancestor::span[contains(@class, 'cursor-pointer')][1]",
                "//span[contains(text(), 'Symbols')]/ancestor::span[contains(@class, 'cursor-pointer')][1]",
            ]
            
            self.stdout.write("Looking for 'Symbols' option in dialog...")
            
            # First, let's see what's visible on the page
            try:
                # Look for common dialog/menu containers
                dialog_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'menu') or contains(@class, 'dropdown') or contains(@class, 'popup') or contains(@class, 'dialog')]")
                self.stdout.write(f"Found {len(dialog_elements)} potential dialog/menu elements")
                
                # List all clickable elements with text
                all_clickables = driver.find_elements(By.XPATH, "//*[self::div or self::button or self::span or self::a][contains(text(), 'Symbol') or contains(text(), 'Table')]")
                self.stdout.write(f"Found {len(all_clickables)} elements with 'Symbol' or 'Table' text")
                for idx, elem in enumerate(all_clickables[:5]):
                    try:
                        elem_text = elem.text.strip()
                        elem_tag = elem.tag_name
                        elem_classes = elem.get_attribute("class") or ""
                        self.stdout.write(f"  Element {idx+1}: <{elem_tag}> text='{elem_text}', classes='{elem_classes[:80]}'")
                    except:
                        pass
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Error inspecting dialog: {str(e)}"))
            
            # Try to find and click "Symbols" option
            for selector_idx, selector in enumerate(symbols_selectors, 1):
                try:
                    self.stdout.write(f"Trying selector {selector_idx}...")
                    symbols_option = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if symbols_option:
                        # Verify it's the right element (contains "symbols" text, not "table")
                        try:
                            elem_text = symbols_option.text.strip().lower()
                            self.stdout.write(f"  Found element with text: '{elem_text[:50]}'")
                            if "table" in elem_text and "symbols" not in elem_text:
                                self.stdout.write(f"  Skipping - found 'table' option instead")
                                symbols_option = None
                                continue
                            if "symbols" not in elem_text and "symbol" not in elem_text:
                                self.stdout.write(f"  Skipping - doesn't contain 'symbols'")
                                symbols_option = None
                                continue
                        except Exception as verify_err:
                            self.stdout.write(f"  Could not verify text: {str(verify_err)[:50]}")
                        
                        if symbols_option:
                            # Make sure it's clickable
                            try:
                                WebDriverWait(driver, 2).until(EC.element_to_be_clickable(symbols_option))
                            except:
                                pass  # Try anyway
                            
                            self.stdout.write(self.style.SUCCESS(f"Found 'Symbols' option using selector {selector_idx}"))
                            # Scroll into view
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", symbols_option)
                            time.sleep(0.5)
                            # Click it
                            try:
                                symbols_option.click()
                                self.stdout.write("Clicked 'Symbols' option")
                            except Exception as click_err:
                                self.stdout.write(f"Standard click failed: {str(click_err)[:50]}, trying JavaScript...")
                                driver.execute_script("arguments[0].click();", symbols_option)
                                self.stdout.write("Clicked 'Symbols' option using JavaScript")
                            break
                except TimeoutException:
                    self.stdout.write(f"  Timeout - element not found")
                    continue
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  Error: {str(e)[:60]}..."))
                    continue
            
            if not symbols_option:
                # Fallback: Search for clickable spans with "symbols" text
                try:
                    self.stdout.write("Trying fallback: searching for clickable spans with 'symbols' text...")
                    # Find all spans with cursor-pointer class
                    all_clickable_spans = driver.find_elements(By.XPATH, "//span[contains(@class, 'cursor-pointer')]")
                    self.stdout.write(f"Found {len(all_clickable_spans)} clickable spans")
                    for elem in all_clickable_spans:
                        try:
                            elem_text = elem.text.strip().lower()
                            # Check if it contains "symbols" but not "table"
                            if "symbols" in elem_text or ("symbol" in elem_text and "table" not in elem_text):
                                self.stdout.write(f"Found element with text: '{elem.text.strip()}'")
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                                time.sleep(0.5)
                                driver.execute_script("arguments[0].click();", elem)
                                self.stdout.write(self.style.SUCCESS("Clicked 'Symbols' option (fallback)"))
                                symbols_option = elem
                                break
                        except Exception as e:
                            self.stdout.write(f"  Error checking element: {str(e)[:50]}")
                            continue
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Fallback search failed: {str(e)}"))
            
            if symbols_option:
                # Take screenshot after selecting symbols
                try:
                    screenshot_5 = os.path.join(screenshot_dir, "05_symbols_selected.png")
                    driver.save_screenshot(screenshot_5)
                    self.stdout.write(f"Screenshot saved: {screenshot_5}")
                except:
                    pass
                time.sleep(2)  # Wait for clipboard to be populated
            else:
                self.stdout.write(self.style.WARNING("Could not find 'Symbols' option. Proceeding anyway..."))
                time.sleep(3)
            
            # CRITICAL: Try to read clipboard BEFORE dismissing the dialog
            # Chartink copies to browser clipboard, which we can access via JavaScript
            clipboard_content = ""
            
            # Method 1: Request clipboard permissions and try JavaScript clipboard API FIRST
            # This should work even before dismissing the dialog
            try:
                self.stdout.write("Requesting clipboard permissions...")
                # Request clipboard permissions using Permissions API
                driver.execute_script("""
                    navigator.permissions.query({name: 'clipboard-read'}).then(function(result) {
                        console.log('Clipboard permission state:', result.state);
                        if (result.state === 'prompt' || result.state === 'granted') {
                            console.log('Clipboard permission available');
                        } else {
                            console.log('Clipboard permission denied or not supported');
                        }
                    }).catch(function(err) {
                        console.log('Permission query failed:', err);
                    });
                """)
                time.sleep(1)  # Wait for permission prompt if any
                
                self.stdout.write("Trying JavaScript clipboard.readText() (browser context)...")
                clipboard_content = driver.execute_async_script("""
                    var callback = arguments[arguments.length - 1];
                    
                    // First, try to request permission explicitly
                    navigator.permissions.query({name: 'clipboard-read'}).then(function(permissionStatus) {
                        console.log('Permission state:', permissionStatus.state);
                        
                        // Try to read clipboard
                        return navigator.clipboard.readText();
                    }).then(function(text) {
                        callback(text || '');
                    }).catch(function(err) {
                        console.log('Clipboard read error:', err);
                        // If permission denied, try to request it
                        if (err.name === 'NotAllowedError' || err.message.includes('permission')) {
                            console.log('Permission denied, trying to request...');
                            // Try reading again - browser might prompt user
                            return navigator.clipboard.readText().then(function(text) {
                                callback(text || '');
                            }).catch(function(err2) {
                                console.log('Second attempt failed:', err2);
                                callback('');
                            });
                        } else {
                            callback('');
                        }
                    });
                """)
                if clipboard_content and clipboard_content.strip():
                    self.stdout.write(self.style.SUCCESS(f"Got {len(clipboard_content)} chars from JS clipboard API"))
                    preview = clipboard_content[:200].replace('\n', '\\n').replace('\t', '\\t')
                    self.stdout.write(f"Clipboard preview: {preview}...")
                else:
                    self.stdout.write(self.style.WARNING("JS clipboard API returned empty content (may need permission)"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"JS clipboard API failed: {str(e)}"))
                self.stdout.write("This is normal if clipboard permissions are not granted. Trying fallback methods...")
            
            # Method 2: If JS clipboard API failed, try reading from a textarea element
            # Sometimes Chartink puts the data in a hidden element
            if not clipboard_content or not clipboard_content.strip():
                try:
                    self.stdout.write("Trying to find clipboard data in page elements...")
                    # Look for any element that might contain the copied symbols
                    # Chartink might store it temporarily in a hidden element
                    clipboard_content = driver.execute_script("""
                        // Try to find any element with stock symbols
                        var elements = document.querySelectorAll('*');
                        for (var i = 0; i < elements.length; i++) {
                            var text = elements[i].textContent || elements[i].innerText || '';
                            // Look for patterns like stock symbols (uppercase, 3-20 chars)
                            if (text.match(/^[A-Z]{3,20}(\\s*\\n\\s*[A-Z]{3,20}){5,}$/)) {
                                return text.trim();
                            }
                        }
                        return '';
                    """)
                    if clipboard_content and clipboard_content.strip():
                        self.stdout.write(self.style.SUCCESS(f"Found {len(clipboard_content)} chars in page elements"))
                except Exception as e:
                    self.stdout.write(f"Element search failed: {str(e)}")
            
            # Method 3: Dismiss the dialog and try again
            # Find and click "Ok" button on "Symbols copied successfully" dialog
            if not clipboard_content or not clipboard_content.strip():
                self.stdout.write("Clipboard not accessible yet. Looking for 'Ok' button to dismiss dialog...")
                try:
                    # Look for "Ok" button in the success dialog
                    ok_button_selectors = [
                        "//button[contains(text(), 'Ok')]",
                        "//button[contains(text(), 'OK')]",
                        "//button[contains(text(), 'ok')]",
                        "//div[contains(@class, 'button') and contains(text(), 'Ok')]",
                        "//span[contains(text(), 'Ok')]/ancestor::button[1]",
                        "//*[contains(text(), 'Symbols copied successfully')]/following::button[contains(text(), 'Ok')]",
                    ]
                    
                    ok_button = None
                    for selector in ok_button_selectors:
                        try:
                            ok_button = WebDriverWait(driver, 2).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                            if ok_button:
                                self.stdout.write(f"Found 'Ok' button using: {selector[:60]}...")
                                break
                        except:
                            continue
                    
                    if ok_button:
                        # Click Ok to dismiss dialog
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", ok_button)
                            time.sleep(0.5)
                            ok_button.click()
                            self.stdout.write("Clicked 'Ok' button to dismiss dialog")
                            time.sleep(1)  # Wait for dialog to close
                        except Exception as e:
                            self.stdout.write(f"Could not click Ok button: {str(e)}")
                            # Try JavaScript click
                            try:
                                driver.execute_script("arguments[0].click();", ok_button)
                                self.stdout.write("Clicked 'Ok' using JavaScript")
                                time.sleep(1)
                            except:
                                pass
                except Exception as e:
                    self.stdout.write(f"Error finding Ok button: {str(e)}")
                
                # After dismissing dialog, try JavaScript clipboard API again
                if not clipboard_content or not clipboard_content.strip():
                    try:
                        self.stdout.write("Retrying JavaScript clipboard.readText() after dismissing dialog...")
                        clipboard_content = driver.execute_async_script("""
                            var callback = arguments[arguments.length - 1];
                            navigator.clipboard.readText()
                                .then(function(text) {
                                    callback(text || '');
                                })
                                .catch(function(err) {
                                    callback('');
                                });
                        """)
                        if clipboard_content and clipboard_content.strip():
                            self.stdout.write(self.style.SUCCESS(f"Got {len(clipboard_content)} chars after dismissing dialog"))
                            preview = clipboard_content[:200].replace('\n', '\\n').replace('\t', '\\t')
                            self.stdout.write(f"Clipboard preview: {preview}...")
                    except Exception as e:
                        self.stdout.write(f"Retry JS clipboard API failed: {str(e)}")
            
            # Method 4: Try pyperclip (system clipboard) - may work after dialog is dismissed
            if not clipboard_content or not clipboard_content.strip():
                try:
                    self.stdout.write("Trying pyperclip (system clipboard)...")
                    if pyperclip:
                        clipboard_content = pyperclip.paste()
                        if clipboard_content and clipboard_content.strip():
                            self.stdout.write(self.style.SUCCESS(f"Retrieved {len(clipboard_content)} characters from system clipboard (pyperclip)"))
                            preview = clipboard_content[:200].replace('\n', '\\n').replace('\t', '\\t')
                            self.stdout.write(f"Clipboard preview: {preview}...")
                        else:
                            self.stdout.write(self.style.WARNING("System clipboard empty or whitespace only"))
                    else:
                        self.stdout.write(self.style.WARNING("pyperclip not available - install with: pip install pyperclip"))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"pyperclip.paste() failed: {str(e)}"))
            
            # Method 5: Try document.execCommand (legacy method)
            if not clipboard_content or not clipboard_content.strip():
                try:
                    self.stdout.write("Trying document.execCommand('paste')...")
                    clipboard_content = driver.execute_script("""
                        try {
                            var textarea = document.createElement('textarea');
                            textarea.style.position = 'fixed';
                            textarea.style.left = '-9999px';
                            textarea.style.top = '-9999px';
                            textarea.style.opacity = '0';
                            document.body.appendChild(textarea);
                            textarea.focus();
                            var success = document.execCommand('paste');
                            var text = textarea.value || '';
                            document.body.removeChild(textarea);
                            return text;
                        } catch(e) {
                            return '';
                        }
                    """)
                    if clipboard_content and clipboard_content.strip():
                        self.stdout.write(self.style.SUCCESS(f"Got {len(clipboard_content)} chars from execCommand"))
                        preview = clipboard_content[:200].replace('\n', '\\n').replace('\t', '\\t')
                        self.stdout.write(f"Clipboard preview: {preview}...")
                except Exception as e:
                    self.stdout.write(f"execCommand method failed: {str(e)}")
            
            # Method 6: Fallback - Extract symbols directly from table if clipboard fails
            # This is a reliable backup method that doesn't depend on clipboard
            if not clipboard_content or not clipboard_content.strip():
                self.stdout.write("Clipboard methods failed. Trying table extraction again...")
                table_fallback = self._extract_symbols_from_results_table(driver)
                if table_fallback:
                    return table_fallback
                self.stdout.write(self.style.WARNING("Could not extract symbols from table"))
            
            # Final check - if we still don't have content, return empty
            if not clipboard_content or not clipboard_content.strip():
                self.stdout.write(self.style.ERROR("=" * 60))
                self.stdout.write(self.style.ERROR("COULD NOT RETRIEVE CLIPBOARD CONTENT"))
                self.stdout.write(self.style.ERROR("=" * 60))
                self.stdout.write("Possible issues:")
                self.stdout.write("  1. Results table empty / not loaded")
                self.stdout.write("  2. Clipboard permissions not granted (normal in Docker headless)")
                self.stdout.write("  3. Chartink UI changed")
                self.stdout.write("\nSaving final screenshot for debugging...")
                try:
                    screenshot_6 = os.path.join(screenshot_dir, "06_no_clipboard_content.png")
                    driver.save_screenshot(screenshot_6)
                    self.stdout.write(f"Screenshot saved: {screenshot_6}")
                except:
                    pass
                self.stdout.write(self.style.WARNING("\nTIP: Table scrape is primary — check media/screenshots/01_page_loaded.png"))
                return new_stock_list
            
            # We have content! Proceed directly to parsing - no more checks
            self.stdout.write(self.style.SUCCESS(f"Clipboard content ready: {len(clipboard_content)} characters"))
            
            # Parse clipboard content (symbols only - can be comma-separated on single line or one per line)
            self.stdout.write("Parsing clipboard data...")
            
            # Clean clipboard content
            clipboard_content = clipboard_content.strip()  # Remove leading/trailing whitespace
            
            # Check if it's a single line with comma-separated symbols
            lines = [line.strip() for line in clipboard_content.split('\n') if line.strip()]
            self.stdout.write(f"Found {len(lines)} lines in clipboard data")
            
            if len(lines) == 0:
                self.stdout.write(self.style.ERROR("No lines found in clipboard content after cleaning!"))
                self.stdout.write(f"Original content length: {len(clipboard_content)}")
                return new_stock_list
            
            # Debug: Show first few lines
            self.stdout.write(f"First 3 lines: {lines[:3]}")
            
            # Handle single line with comma-separated symbols
            if len(lines) == 1 and ',' in lines[0]:
                self.stdout.write("Detected single line with comma-separated symbols")
                # Split by comma and extract symbols
                symbols = [s.strip() for s in lines[0].split(',') if s.strip()]
                self.stdout.write(f"Found {len(symbols)} symbols in comma-separated list")
                
                for symbol in symbols:
                    # Clean symbol: uppercase, remove extra whitespace, keep alphanumeric and hyphens
                    script = symbol.strip().upper()
                    script = ''.join(c for c in script if c.isalnum() or c == '-')
                    
                    if script and len(script) <= 20:
                        if script not in new_stock_list:
                            new_stock_list.append(script)
                            self.stdout.write(f"  Added symbol: {script}")
                    else:
                        self.stdout.write(f"  Skipping invalid symbol: {symbol.strip()}")
                
                # Skip the rest of the parsing logic since we've already processed everything
                if len(new_stock_list) > 0:
                    self.stdout.write(self.style.SUCCESS(f"Successfully extracted {len(new_stock_list)} stocks from comma-separated list"))
                    self.stdout.write(f"Stocks: {', '.join(new_stock_list[:10])}{'...' if len(new_stock_list) > 10 else ''}")
                return new_stock_list
            
            # Handle multiple lines (one symbol per line) or table format
            # Check if this is simple symbol list (one symbol per line) or table format
            is_simple_symbol_list = True
            if lines:
                first_line = lines[0].strip()
                # If first line has tabs or multiple comma-separated columns, it's probably a table
                if '\t' in first_line or (',' in first_line and len([s for s in first_line.split(',') if s.strip()]) > 3):
                    is_simple_symbol_list = False
                    self.stdout.write("Detected table format (tab/comma separated)")
                else:
                    self.stdout.write("Detected simple symbol list (one per line)")
            
            # Skip header row if present (for table format)
            start_idx = 0
            if not is_simple_symbol_list and len(lines) > 0:
                first_line_lower = lines[0].lower()
                if any(keyword in first_line_lower for keyword in ['script', 'symbol', 'stock', 'name', 'sno', 'no', 'sr']):
                    start_idx = 1
                    self.stdout.write("Skipping header row")
            
            # Parse each line
            for line_idx, line in enumerate(lines[start_idx:], start=start_idx+1):
                if not line.strip():
                    continue
                
                script = ""
                chg_percent = None
                
                if is_simple_symbol_list:
                    # Simple case: each line is just a symbol
                    script = line.strip().upper()
                    # Remove any extra whitespace or special chars
                    script = ''.join(c for c in script if c.isalnum() or c == '-')
                    if script and len(script) <= 20:
                        if script not in new_stock_list:
                            new_stock_list.append(script)
                            self.stdout.write(f"  Line {line_idx}: Found symbol: {script}")
                    else:
                        self.stdout.write(f"  Line {line_idx}: Skipping invalid symbol: {line.strip()}")
                        continue
                else:
                    # Table format: Try tab-separated first, then comma-separated
                    if '\t' in line:
                        cols = line.split('\t')
                    elif ',' in line:
                        cols = line.split(',')
                    else:
                        # Space-separated
                        cols = line.split()
                    
                    if len(cols) < 1:
                        continue
                    
                    # Try to identify script column (usually column 2 or 3)
                    for col_idx, col in enumerate(cols):
                        col = col.strip()
                        if not col:
                            continue
                        
                        # Script is usually uppercase, short, alphanumeric
                        if not script and col.isupper() and len(col) <= 20 and col.replace('-', '').isalnum():
                            script = col
                        # Change % contains % symbol
                        if "%" in col:
                            try:
                                chg_percent = float(col.replace("%", "").replace(",", "").strip())
                            except:
                                pass
                    
                    # Fallback: use column positions
                    if not script:
                        # Usually script is in column 2 (index 1) or 3 (index 2)
                        if len(cols) >= 3:
                            script = cols[2].strip()
                        elif len(cols) >= 2:
                            script = cols[1].strip()
                        else:
                            script = cols[0].strip()
                
                if not script:
                    continue
                
                # Filter stocks with change % < 6
                should_add = False
                if chg_percent:
                    try:
                        chg_val = float(chg_percent)
                        if chg_val < 6:
                            should_add = True
                            self.stdout.write(f"Row {line_idx}: {script} (Chg%: {chg_val}%) - Added")
                        else:
                            self.stdout.write(f"Row {line_idx}: {script} (Chg%: {chg_val}%) - Skipped (>6%)")
                    except ValueError:
                        # If chg_percent is not a number, add anyway
                        should_add = True
                        self.stdout.write(f"Row {line_idx}: {script} (Chg%: N/A) - Added")
                else:
                    # No change % available, add anyway
                    should_add = True
                    self.stdout.write(f"Row {line_idx}: {script} - Added (no Chg% data)")
                
                if should_add and script not in new_stock_list:
                    new_stock_list.append(script)
            
            # Final validation: Check if we actually extracted any stocks
            if len(new_stock_list) == 0:
                self.stdout.write(self.style.ERROR("=" * 60))
                self.stdout.write(self.style.ERROR("ZERO STOCKS EXTRACTED FROM CLIPBOARD"))
                self.stdout.write(self.style.ERROR("=" * 60))
                self.stdout.write(self.style.WARNING("Clipboard was read successfully but no stocks were extracted."))
                self.stdout.write(self.style.WARNING("This could mean:"))
                self.stdout.write(self.style.WARNING("  1. Clipboard contained invalid data"))
                self.stdout.write(self.style.WARNING("  2. All stocks were filtered out (change % >= 6%)"))
                self.stdout.write(self.style.WARNING("  3. Parsing logic failed to extract symbols"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Successfully extracted {len(new_stock_list)} stocks from clipboard"))
                self.stdout.write(f"Stocks: {', '.join(new_stock_list[:10])}{'...' if len(new_stock_list) > 10 else ''}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during scraping: {str(e)}"))
            import traceback
            self.stdout.write(traceback.format_exc())
        
        return new_stock_list

    def _build_telegram_message(self):
        """Build the initial Telegram message header"""
        signal_type = "UPSIDE"
        part_number = 1
        strategy_name = "15 Mins ORB Crossed"
        trigger_time = datetime.now().strftime("%d-%b-%Y %H:%M:%S")

        bot_txt = (
            f"Tamil Harmonic Bot Alerts\n"
            f"*{signal_type}*\n"
            f"Trigger Time: {trigger_time}\n"
            f"Part {part_number}\n"
            f"{strategy_name}\n\n"
        )

        # Table header
        bot_txt += "```\n"  # Start monospaced block
        bot_txt += "+--------+----------------------+--------+--------+------------+\n"
        bot_txt += "|   #    | 50MA Stock Code      |  CMP   | SMA50  | % SMA50    |\n"
        bot_txt += "+--------+----------------------+--------+--------+------------+\n"

        return bot_txt
