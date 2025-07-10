import time
from datetime import datetime, timedelta
from django.utils import timezone
from data.models import Source
import pandas as pd
from data.models import Stocks50MA
from data.utils import send_telegram_message
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Fetch 50ma-setup data from chartink using selenium, store in database"

    def handle(self, *args, **kwargs):
        print('Tracking SMA50 Stock status')

yesterday = datetime.now().date() - timedelta(days=1)
print(yesterday)
sma50s = Stocks50MA.objects.all().filter(status=1)
print(Stocks50MA.objects.all().filter(status=1))
print(sma50s)

'''
def download_chartink_csv():
    options = Options()
    options.add_argument("--headless")  # Run in headless mode
    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://chartink.com/screener/50ma-setup")
        time.sleep(5)  # Wait for JS to load table

        # Find the table and extract it
        table_html = driver.find_element("id", "DataTables_Table_0").get_attribute('outerHTML')

        # Optional: download via CSV button (if it triggers JS to download)
        # csv_button = driver.find_element("xpath", "//button[contains(text(), 'CSV')]")
        # csv_button.click()

        # Convert HTML table to DataFrame
        df = pd.read_html(table_html)[0]
        print(df)
        return df

    finally:
        driver.quit()

# Example usage
df = download_chartink_csv()
print(df.head())  # Or save to DB/file
'''