# utils/pe_scraper.py
import time
import os
#import django
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
#from infra.models import Tickers


'''
Manual execution python coredata/utils/pe_scraper.py --fetch_nifty_50
'''

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "idjango.settings")  # Replace with your project
#django.setup()

def fetch_nifty_pe():
    options = Options()
    options.headless = True
    driver = webdriver.Chrome(options=options)

    driver.get("https://www.screener.in/company/NIFTY/") #https://www.niftyindices.com/reports/historical-data
    time.sleep(5)  # Wait for JS to load

    soup = BeautifulSoup(driver.page_source, "html.parser")
    pe_value = 0
    # Update this selector based on the actual page
    for li in soup.select("ul#top-ratios li"):
        label = li.find("span", class_="name")
        value = li.find("span", class_="number")
        if label and "P/E" in label.text:
            pe_value = float(value.text.strip())

    
    driver.quit()

    return pe_value


def fetch_screener_table(path="1", name='50'):
    print(f'Fetching NIFTY {name} stocks...')

    # Setup headless Chrome browser
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    path = "https://www.screener.in/company/NIFTY/?sort=name&order=asc"
    try:
        url = path #"https://www.screener.in/company/NIFTY/?sort=name&order=asc"
        driver.get(url)

        # Wait until the data-table is loaded
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "data-table"))
        )

        # Give additional time to ensure table fully loads
        time.sleep(10)

        # Parse the page source with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.select_one('.data-table tbody')
        rows = table.find_all('tr')

        nifty_stocks = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                if cols:
                    link_tag = cols[1].find("a")  # Assuming the symbol is in a hyperlink
                if link_tag:
                    url = link_tag.get("href")  # e.g., "/company/IC/consolidated/"
                    symbol = url.split("/")[2]  # Extracts 'IOC'

                name = cols[1].text.strip()
                price = cols[2].text.strip()
                pe = cols[3].text.strip()
                roce = cols[10].text.strip()

                #print(symbol, name, price, pe, roce)
                nifty_stocks.append({'symbol': symbol, 'name': name, 'price': price , 'PE': pe , 'ROCE':roce})

        print(f"\n✅ Total NIFTY {name} Stocks Fetched: {len(nifty_stocks)}")

        return nifty_stocks

    finally:
        driver.quit()


def fetch_nifty_tickers(path="1", name='50'):
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    path = "https://www.screener.in/company/NIFTY/?sort=name&order=asc"
    url = path #"https://www.screener.in/company/NIFTY/?sort=name&order=asc"
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.get(url)
    # while True:
    #     print('fff')
    #fetch_screener_table(path="1", name='50')
    
    try:
        # Try to click 'Next' if not disabled
        #next_btn = driver.find_element(By.CLASS_NAME, "pagination a")
        next_link = soup.find("pagination a", string=lambda s: s and "Next" in s)
        #class_attr = next_li.get_attribute("class")
        print(next_link, "next Link")

        # if "disabled" in class_attr:
        #     print("Reached last page.")
        #     break
        # else:
        #     next_link = next_li.find_element(By.TAG_NAME, "a") # Click the <a> inside the <li>
        #     driver.execute_script("arguments[0].click();", next_link)
        #     time.sleep(5)  # Wait for new page to load

    except Exception as e:
        print("Pagination error:", e)
        #break


if __name__ == "__main__":
    fetch_nifty_tickers()
