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

DB_NAME = "hibid_lots.db"
ZIP_CODES = ["62629", "46173"]
RADIUS = 50
MAX_PAGES = 10

CHROMIUM_PATH = "/usr/bin/chromium"
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"


# -------------------- TIME PARSER -------------------- #

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


# -------------------- DATABASE SETUP -------------------- #

def setup_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lots (
            lot_id TEXT PRIMARY KEY,
            title TEXT,
            current_bid REAL,
            bid_count INTEGER,
            time_remaining TEXT,
            minutes_left INTEGER,
            url TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'pending',
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            final_price REAL,
            ended_checked INTEGER DEFAULT 0,
            velocity REAL,
            edge_score REAL,
            predicted_value REAL,
            classifier_confidence REAL
        )
    """)

    conn.commit()
    conn.close()


# -------------------- DRIVER -------------------- #

def get_driver():
    options = Options()
    options.binary_location = CHROMIUM_PATH
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


# -------------------- FINAL PRICE SCRAPER -------------------- #

def scrape_final_price(driver, url):
    try:
        driver.get(url)
        time.sleep(2)
        text = driver.page_source
        match = re.search(r'Price Realized:\s*\$?([\d,\.]+)', text)
        if match:
            return float(match.group(1).replace(",", ""))
    except:
        pass
    return None


# -------------------- MAIN SCRAPER -------------------- #

def run_scraper():
    print("=== AUCTION SCRAPER ===")

    setup_db()
    driver = get_driver()

    for zip_code in ZIP_CODES:

        base_url = f"https://hibid.com/lots?zip={zip_code}&miles={RADIUS}&lot_type=ONLINE"
        print(f"\nScanning ZIP: {zip_code}")
        driver.get(base_url)

        for page in range(1, MAX_PAGES + 1):

            print(f"[PAGE {page}]")
            time.sleep(3)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            cards = driver.find_elements(By.TAG_NAME, "app-lot-tile")
            print(f"Found {len(cards)} items")

            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()

            for card in cards:
                try:
                    link_el = card.find_element(By.TAG_NAME, "a")
                    link = link_el.get_attribute("href")
                    lot_id = link.split('/')[-2]
                    title = link_el.text.strip()

                    # PRICE
                    price = 0.0
                    match = re.search(r'\$([\d,]+\.?\d*)', card.text)
                    if match:
                        price = float(match.group(1).replace(",", ""))

                    # BIDS
                    bid_count = 0
                    match = re.search(r'(\d+)\s+Bid', card.text)
                    if match:
                        bid_count = int(match.group(1))

                    # TIME
                    time_match = re.search(r'(\d+[dhm].*)', card.text)
                    time_left = time_match.group(0) if time_match else "Unknown"
                    minutes_left = parse_time_to_minutes(time_left)

                    status = "pending" if minutes_left > 0 else "ended"

                    # IMAGE
                    img_url = ""
                    try:
                        img_url = card.find_element(By.TAG_NAME, "img").get_attribute("src")
                    except:
                        pass

                    cursor.execute("""
                        INSERT INTO lots (
                            lot_id, title, current_bid, bid_count,
                            time_remaining, minutes_left,
                            url, image_url, status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(lot_id) DO UPDATE SET
                            current_bid=excluded.current_bid,
                            bid_count=excluded.bid_count,
                            time_remaining=excluded.time_remaining,
                            minutes_left=excluded.minutes_left,
                            status=excluded.status,
                            last_seen=CURRENT_TIMESTAMP
                    """, (
                        lot_id, title, price, bid_count,
                        time_left, minutes_left,
                        link, img_url, status
                    ))

                except:
                    continue

            conn.commit()
            conn.close()

            try:
                next_btn = driver.find_element(By.XPATH, "//a[contains(@class,'page-link') and contains(.,'Next')]")
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(3)
            except:
                break

    # FINAL PRICE CHECK
    print("Checking ended lots...")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT lot_id, url
        FROM lots
        WHERE status='ended'
        AND ended_checked=0
        LIMIT 20
    """)

    for lot_id, url in cursor.fetchall():
        final_price = scrape_final_price(driver, url)

        cursor.execute("""
            UPDATE lots
            SET final_price=?,
                status='sold_history',
                minutes_left=0,
                ended_checked=1
            WHERE lot_id=?
        """, (final_price, lot_id))

    conn.commit()
    conn.close()

    driver.quit()
    print("Scrape complete.")
