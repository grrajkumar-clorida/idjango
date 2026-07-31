# utils/pe_scraper.py
import time
import os

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

'''
Manual execution (inside container):
  python coredata/utils/pe_scraper.py
  python -c "from coredata.utils.pe_scraper import fetch_nifty_pe; print(fetch_nifty_pe())"
'''

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "idirect.settings")


def _find_chrome_binary():
    candidates = [
        os.environ.get("CHROME_BIN", ""),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _find_chromedriver():
    candidates = [
        os.environ.get("CHROMEDRIVER_PATH", ""),
        "/usr/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _chrome_options():
    options = Options()
    binary = _find_chrome_binary()
    if binary:
        options.binary_location = binary
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return options


def _chrome_driver():
    driver_path = _find_chromedriver()
    options = _chrome_options()
    if driver_path:
        return webdriver.Chrome(service=Service(driver_path), options=options)
    return webdriver.Chrome(options=options)

def fetch_nifty_pe():
    """Scrape Nifty PE via Chromium. Returns None if browser is unavailable."""
    driver = None
    try:
        driver = _chrome_driver()
        driver.get("https://www.screener.in/company/NIFTY/")
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        pe_value = None
        for li in soup.select("ul#top-ratios li"):
            label = li.find("span", class_="name")
            value = li.find("span", class_="number")
            if label and value and "P/E" in label.text:
                pe_value = float(value.text.strip())
                break
        return pe_value
    except Exception:
        return None
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def fetch_screener_table(path="1", name='50'):
    print(f'Fetching NIFTY {name} stocks...')

    driver = _chrome_driver()
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
    driver = _chrome_driver()
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
