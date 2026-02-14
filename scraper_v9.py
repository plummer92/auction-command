import sqlite3
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import lifecycle_manager

DB = "hibid_lots.db"

ZIP_CODES = ["62629", "62704"]
RADIUS = 50
MAX_PAGES = 10

CHROMIUM_PATH = "/usr/bin/chromium"
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"


# ------------------------------
# Parse Time → Minutes
# ------------------------------
def parse_minutes(text):
    if not text:
        return None

    total = 0

    d = re.search(r'(\d+)d', text)
    h = re.search(r'(\d+)h', text)
    m = re.search(r'(\d+)m', text)

    if d:
        total += int(d.group(1)) * 1440
    if h:
        total += int(h.group(1)) * 60
    if m:
        total += int(m.group(1))

    return total if total > 0 else None


# ------------------------------
# DB Connection
# ------------------------------
def get_db():
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ------------------------------
# Selenium Driver
# ------------------------------
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


# ------------------------------
# Scrape One ZIP
# ------------------------------
def scrape_zip(driver, zip_code):

    base_url = f"https://hibid.com/lots?zip={zip_code}&miles={RADIUS}&lot_type=ONLINE"
    driver.get(base_url)
    time.sleep(3)

    for page in range(1, MAX_PAGES + 1):

        print(f"[ZIP {zip_code}] PAGE {page}")

        time.sleep(2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        cards = driver.find_elements(By.TAG_NAME, "app-lot-tile")

        if not cards:
            break

        conn = get_db()
        cursor = conn.cursor()

        for card in cards:
            try:
                link_el = card.find_element(By.TAG_NAME, "a")
                link = link_el.get_attribute("href")
                lot_id = link.split("/")[-2]
                title = link_el.text.strip()

                text = card.text

                # Current bid
                bid_match = re.search(r'\$([\d,]+\.?\d*)', text)
                current_bid = float(bid_match.group(1).replace(",", "")) if bid_match else 0.0

                # Bid count
                bid_count_match = re.search(r'(\d+)\s+Bid', text)
                bid_count = int(bid_count_match.group(1)) if bid_count_match else 0

                # Time remaining
                time_match = re.search(r'(\d+d)?\s*(\d+h)?\s*(\d+m)', text)
                time_remaining = time_match.group(0).strip() if time_match else None
                minutes_left = parse_minutes(time_remaining)

                # Image
                try:
                    img_url = card.find_element(By.TAG_NAME, "img").get_attribute("src")
                except:
                    img_url = None

                status = "pending" if minutes_left and minutes_left > 0 else "ended"

                cursor.execute("""
                INSERT INTO lots (
                    lot_id,
                    title,
                    current_bid,
                    bid_count,
                    time_remaining,
                    minutes_left,
                    url,
                    image_url,
                    status,
                    last_seen
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(lot_id) DO UPDATE SET
                    current_bid=excluded.current_bid,
                    bid_count=excluded.bid_count,
                    time_remaining=excluded.time_remaining,
                    minutes_left=excluded.minutes_left,
                    status=CASE
                        WHEN excluded.minutes_left > 0 THEN 'pending'
                        ELSE lots.status
                    END,
                    last_seen=CURRENT_TIMESTAMP
                """, (
                    lot_id,
                    title,
                    current_bid,
                    bid_count,
                    time_remaining,
                    minutes_left,
                    link,
                    img_url,
                    status
                ))

            except Exception as e:
                continue

        conn.commit()
        conn.close()

        # Try next page
        try:
            next_btn = driver.find_element(By.XPATH, "//a[contains(@class,'page-link') and contains(.,'Next')]")
            driver.execute_script("arguments[0].click();", next_btn)
            time.sleep(3)
        except:
            break


# ------------------------------
# Main Runner
# ------------------------------
def run_scraper():

    print("=== AUCTION SCRAPER (SELENIUM PRO) ===")

    driver = get_driver()

    for zip_code in ZIP_CODES:
        scrape_zip(driver, zip_code)

    driver.quit()

    print("Running lifecycle...")
    lifecycle_manager.run_lifecycle()

    print("Scrape complete.")


if __name__ == "__main__":
    run_scraper()
