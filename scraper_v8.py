import sqlite3
import time
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
DB_NAME = "hibid_lots.db"
ZIP_CODE = "62629"
RADIUS = 50
MAX_PAGES = 10

CHROMIUM_PATH = "/usr/bin/chromium"
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"


# -------------------- DATABASE SETUP -------------------- #

def setup_db():
    db_path = os.path.abspath(DB_NAME)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lots (
            lot_id TEXT PRIMARY KEY,
            title TEXT,
            current_bid REAL,
            bid_count INTEGER,
            time_remaining TEXT,
            url TEXT,
            image_url TEXT,
            market_value REAL,
            ref_image TEXT,
            status TEXT DEFAULT 'pending',
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            buyers_premium REAL DEFAULT 0.15,
            shipping_available INTEGER DEFAULT 1,
            final_price REAL,
            location TEXT
        )
    ''')

    conn.commit()
    conn.close()
    return db_path


# -------------------- DRIVER SETUP -------------------- #

def get_driver():
    chrome_options = Options()
    chrome_options.binary_location = CHROMIUM_PATH

    # Cloud-safe headless config
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)

    return driver


# -------------------- SCRAPER -------------------- #

def run_scraper():
    print("=== AUCTION SCRAPER (CLOUD MODE) ===")

    db_path = setup_db()
    driver = get_driver()

    base_url = f"https://hibid.com/lots?zip={ZIP_CODE}&miles={RADIUS}&lot_type=ONLINE"
    print(f"Navigating: {base_url}")
    driver.get(base_url)

    total_saved = 0
    current_page = 1

    while current_page <= MAX_PAGES:
        print(f"\n[PAGE {current_page}]")

        time.sleep(3)

        # Scroll to trigger lazy loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        cards = driver.find_elements(By.TAG_NAME, "app-lot-tile")
        print(f"Found {len(cards)} items")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for card in cards:
            try:
                link_el = None
                links = card.find_elements(By.TAG_NAME, "a")
                for l in links:
                    href = l.get_attribute("href")
                    if href and "/lot/" in href:
                        link_el = l
                        break

                if not link_el:
                    continue

                title = link_el.text.strip()
                link = link_el.get_attribute("href")
                lot_id = link.split('/')[-2]

                # --- PRICE ---
                price = 0.0
                try:
                    price_el = card.find_element(By.CLASS_NAME, "lot-high-bid")
                    price_text = price_el.text.replace("High Bid:", "").replace("USD", "").strip()
                    price = float(price_text.replace(",", ""))
                except:
                    match = re.search(r'\$([\d,]+\.?\d*)', card.text)
                    if match:
                        price = float(match.group(1).replace(',', ''))

                # --- BID COUNT ---
                bid_count = 0
                try:
                    bid_el = card.find_element(By.CLASS_NAME, "lot-bid-history")
                    bid_count = int(re.sub(r'\D', '', bid_el.text))
                except:
                    pass

                # --- TIME REMAINING ---
                time_left = "Unknown"
                match = re.search(r'(\d+[dhms]\s*)+', card.text)
                if match:
                    time_left = match.group(0).strip()

    def parse_time_to_minutes(time_str):
        if not isinstance(time_str, str):
            return 999999

        total = 0
        d = re.search(r'(\d+)d', time_str)
        h = re.search(r'(\d+)h', time_str)
        m = re.search(r'(\d+)m', time_str)

        if d: total += int(d.group(1)) * 1440
        if h: total += int(h.group(1)) * 60
        if m: total += int(m.group(1))

        return total if total > 0 else 999999

    minutes_left = parse_time_to_minutes(time_left)


                # --- IMAGE ---
                img_url = ""
                try:
                    img_url = card.find_element(By.TAG_NAME, "img").get_attribute("src")
                except:
                    pass

                cursor.execute("""
                    INSERT INTO lots (
                        lot_id, title, current_bid, bid_count,
                        time_remaining, minutes_left, url, image_url, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                    ON CONFLICT(lot_id) DO UPDATE SET
                        current_bid=excluded.current_bid,
                        bid_count=excluded.bid_count,
                        time_remaining=excluded.time_remaining,
                        minutes_left=excluded.minutes_left,
                        last_seen=CURRENT_TIMESTAMP
                """, (lot_id, title, price, bid_count,
                      time_left, minutes_left, link, img_url))


                total_saved += 1

            except Exception:
                continue

        conn.commit()
        conn.close()

        print(f"Saved/Updated: {total_saved}")

        # --- NEXT PAGE ---
        try:
            next_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(@class, 'page-link') and .//span[contains(text(), 'Next')]]")
                )
            )
            driver.execute_script("arguments[0].click();", next_btn)
            current_page += 1
            time.sleep(4)
        except:
            print("No more pages.")
            break

    driver.quit()
    print("Scrape complete.")


if __name__ == "__main__":
    run_scraper()
