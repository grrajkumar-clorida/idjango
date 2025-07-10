import time
import django
import os
import gspread
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from django.core.management.base import BaseCommand
from data.models import Source
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials
from data.models import Stocks50MA
from datetime import datetime
from data.utils import moving_average, get_50ma_google_sheet_data, filter_stock, update_google_sheet  # 👈 import here

class Command(BaseCommand):
    help = "Fetch 50ma-setup data from chartink using selenium, store in database"

    def handle(self, *args, **kwargs):
        file_path = os.path.join(settings.MEDIA_ROOT, "result_1.html")  # ✅ Correct file system path
        output_csv = "/home/gr8/Documents/gr8/processed_stock_data.csv"  # Update path

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "idjango.settings")  # Replace with your project
django.setup()

# Setup Selenium driver
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Optional: run in background
driver = webdriver.Chrome(options=options)

# Go to the Chartink screener page
url = "https://chartink.com/screener/50ma-setup"
driver.get(url)
wait = WebDriverWait(driver, 10)
print("Fetching data from ",url)
# Wait for the table to load

wait.until(EC.presence_of_element_located((By.ID, "DataTables_Table_0")))
time.sleep(5)
new_stock_list = []
def extract_table_rows():
    rows = driver.find_elements(By.CSS_SELECTOR, "#DataTables_Table_0 tbody tr")
    
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) >= 6:
            sid = cols[0].text.strip()
            name = cols[1].text.strip()
            script = cols[2].text.strip()
            ltp = cols[2].text.replace(",", "")
            chg_percent = cols[4].text.replace("%", "").replace(",", "").strip()
            ltp = cols[5].text.replace(",", "")

            if float(chg_percent) < 6:
                new_stock_list.append(script)

            stock_entry = Source(
                script = script,
                name = name,
                trade = '50MA',
                market = 'Equity',
                price = ltp,
                percent = chg_percent,
                status = "open",  # Default status open
                raw_data = 'ref',  # Store the full row as JSON
                notes = 'Source from chartink selenium',
            )
            #stock_entry.save()
            print(f"Saved: {sid} - {script} - {ltp} - {chg_percent}")

# Loop through pagination
while True:
    extract_table_rows()
    
    try:
        # Try to click 'Next' if not disabled
        next_li = driver.find_element(By.ID, "DataTables_Table_0_next")
        class_attr = next_li.get_attribute("class")

        if "disabled" in class_attr:
            print("Reached last page.")
            break
        else:
            # Click the <a> inside the <li>
            next_link = next_li.find_element(By.TAG_NAME, "a")
            driver.execute_script("arguments[0].click();", next_link)
            time.sleep(5)  # Wait for new page to load

    except Exception as e:
        print("Pagination error:", e)
        break

print('Fetch SMA Price from Google Finance:')
# Fetch SMA value from Googel Finance Sheet 
#configurations
spreadsheet_id = settings.GSHEET_ID
api_key = settings.GSHEET_KEY
sheet_name = "50ma"

# pass the new stock list to get SMA50 Values
list_result = update_google_sheet(new_stock_list)
print(list_result)
copyGF_sma = "https://script.google.com/macros/s/AKfycbx9fP7OrBbXlziY9HlWKrdNJfFWKMI2j6KC3wvcwwu8N-Leaz9NNGf02hqEVl2vqwgc/exec"
response = requests.get(copyGF_sma)
print(response)

# Get SMA50 Value from Sheet
gsheet_data = get_50ma_google_sheet_data(spreadsheet_id,sheet_name, api_key)
rows = gsheet_data.get("values", [])
headers = rows[0]

def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.00

for row in rows[1:]:
    row_dict = dict(zip(headers, row))
    stock_name = row_dict.get("Stock")
    if(stock_name):
        obj, created = Stocks50MA.objects.update_or_create(
            stock_code = stock_name,
            defaults= {
                "script": stock_name,
                "stock_cmp": safe_float(row_dict.get("CMP")),
                "moving_average_50": safe_float(row_dict.get("50MA")),
                "moving_average_20": safe_float(row_dict.get("20MA")),
                "range_50ma": safe_float(row_dict.get("Range 50MA")),
                "percent_50sma": safe_float(row_dict.get("Percent 50SMA")),
                "target_1": safe_float(row_dict.get("Target 1")),
                "target_2": safe_float(row_dict.get("Target 2")),
                #"cmp_date": row_dict.get("Trad Date"),
                "status": 1
            }
        )
        action = "Created" if created else "Updated"
        print(f"{action} {stock_name}")



driver.quit()

