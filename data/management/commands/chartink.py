import time
import django
import os
import gspread
import requests
from decouple import config
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from django.core.management.base import BaseCommand
#from data.models import Source
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials
from data.models import Stocks50MA
from datetime import datetime
from django.core.mail import send_mail
from infra.utils.telegram import send_telegram
from infra.utils.infra import date_format, safe_float
from infra.utils.gfinance import get_gfinance_data, filter_stock, update_gfinance_data
#from stocks.utils.telegram_bot import send_telegram_message

#from data.utils import send_telegram_message, moving_average, get_google_sheet_data, filter_stock, update_google_sheet, 
# 👈 import here
#from stocks.utils.telegram_bot import send_telegram_message


class Command(BaseCommand):
    help = "Fetch 50ma-setup data from chartink using selenium, store in App"

    def handle(self, *args, **kwargs):
        file_path = os.path.join(settings.MEDIA_ROOT, "result_1.html")  # ✅ Correct file system path
        output_csv = "/home/gr8/Documents/gr8/processed_stock_data.csv"  # Update path
        self.stdout.write(self.style.SUCCESS("50MA stocks are added"))

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "idjango.settings")  # Replace with your project
django.setup()
bot_txt = ''

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
    #50ma page get the page table.
    rows = driver.find_elements(By.CSS_SELECTOR, "#DataTables_Table_0 tbody tr")

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) >= 6:

            sid = cols[0].text.strip()
            name = cols[1].text.strip()
            script = cols[2].text.strip()
            chg_percent = cols[4].text.replace("%", "").replace(",", "").strip()
            ltp = cols[5].text.replace(",", "")
            vol = cols[6].text.strip
            
            if float(chg_percent) < 6:
                new_stock_list.append(script)

            print(f"{sid} - {script} - {ltp} - {chg_percent}")

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
            next_link = next_li.find_element(By.TAG_NAME, "a") # Click the <a> inside the <li>
            driver.execute_script("arguments[0].click();", next_link)
            time.sleep(5)  # Wait for new page to load

    except Exception as e:
        print("Pagination error:", e)
        break

print('Fetch SMA Price from Google Finance:')
'''
    * Fetch SMA value from Googel Finance Sheet
    * 
    * 
'''

#configurations
spreadsheet_id, sheet_name, api_key = settings.GSHEET_ID, "50ma", settings.GSHEET_KEY 

'''
    # pass the new stocks list to get SMA50 Values
    #
'''

list_data = update_gfinance_data("googleFinace", new_stock_list)
print(list_data)
copy_GF_sma = config('GSHEET_APP_SCRIPT')
response = requests.get(copy_GF_sma)
print(response)

# Get SMA50 Value from Sheet
gsheet_data = get_gfinance_data(spreadsheet_id, sheet_name, api_key)
rows = gsheet_data.get("values", [])
headers = rows[0]

sma50Stocks = []

#bot_txt = "```\n"  # Start monospaced block
bot_txt += "+--------+----------------------+--------+--------+------------+\n"
bot_txt += "|   #    | 50MA Stock Code      |  CMP   | SMA50  | % SMA50    |\n"
bot_txt += "+--------+----------------------+--------+--------+------------+\n"

for row in rows[1:]:
    row_dict = dict(zip(headers, row))
    script = row_dict.get("Stock")

    if(script):
        try:
            obj = Stocks50MA.objects.get(script=script)

            # ✅ Backup selected values to JSON field
            backup_entry = {
                "moving_average_50": obj.moving_average_50,
                "stock_cmp": obj.stock_cmp,
                "cmp_date": obj.cmp_date.isoformat() if obj.cmp_date else None,
                "range_50ma": obj.range_50ma,
                "target_1": obj.target_1,
                "target_2": obj.target_2,
            }

            # Initialize as list if None
            if not isinstance(obj.pre_data, list):
                obj.pre_data = []

            # Append current state to history
            obj.pre_data.append(backup_entry)

            # ✅ Update values
            obj.name = row_dict.get("Name")
            obj.stock_cmp = safe_float(row_dict.get("CMP"))
            obj.moving_average_50 = safe_float(row_dict.get("50MA"))
            obj.moving_average_20 = safe_float(row_dict.get("20MA"))
            obj.range_50ma = safe_float(row_dict.get("Range 50MA"))
            obj.percent_50sma = safe_float(row_dict.get("Percent 50SMA"))
            obj.target_1 = safe_float(row_dict.get("Target 1"))
            obj.target_2 = safe_float(row_dict.get("Target 2"))
            #obj.cmp_date = row_dict.get("Trad Date")  # Or from your data
            obj.cmp_date = date_format(row_dict.get("Trad Date"))
            obj.status = 7

            obj.save()
            print(f"Updated {script}")

        except Stocks50MA.DoesNotExist:
            # New create
            obj = Stocks50MA.objects.create(
                script=script,
                name=row_dict.get("Name"),
                stock_cmp=safe_float(row_dict.get("CMP")),
                moving_average_50=safe_float(row_dict.get("50MA")),
                moving_average_20=safe_float(row_dict.get("20MA")),
                range_50ma=safe_float(row_dict.get("Range 50MA")),
                percent_50sma=safe_float(row_dict.get("Percent 50SMA")),
                target_1=safe_float(row_dict.get("Target 1")),
                target_2=safe_float(row_dict.get("Target 2")),
                cmp_date= date_format(row_dict.get("Trad Date")),
                status= 6
            )
            print(f"Created {script}")
        
        bot_txt += (f"| {row_dict.get("Sno")}  |  {script}   |  {row_dict.get("CMP")} |  {row_dict.get("50MA")}  | {row_dict.get("Percent 50SMA")} \n")

bot_txt += "+--------+----------------------+--------+--------+------------+\n"
#bot_txt += "```"  # End monospaced block

send_telegram(bot_txt)
print()
driver.quit()

