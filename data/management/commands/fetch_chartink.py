from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import pandas as pd

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


# Disabled: this used to scrape ChartInk on every Django command import.
# Use: python manage.py get_chartink50ma 50ma
# df = download_chartink_csv()
# print(df.head())

