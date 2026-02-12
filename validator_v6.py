import sqlite3
import time
import re
import logging
import random
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# --- CONFIGURATION ---
DB_NAME = "hibid_lots.db"
LOG_FILE = "validator_log.txt"

CHROMIUM_PATH = "/usr/bin/chromium"
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"


# -------------------- LOGGING -------------------- #

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)


# -------------------- DATABASE SETUP -------------------- #

def setup_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE lots ADD COLUMN ref_url TEXT")
    except:
        pass
    conn.commit()
    conn.close()


# -------------------- DRIVER SETUP -------------------- #

def get_driver():
    chrome_options = Options()
    chrome_options.binary_location = CHROMIUM_PATH

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


# -------------------- VALIDATOR -------------------- #

def run_validator():
    logging.info("=== VALIDATOR STARTED (CLOUD MODE) ===")
    setup_db()

    driver = get_driver()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT lot_id, title 
        FROM lots 
        WHERE (market_value IS NULL OR market_value = 0)
        AND status='pending'
        LIMIT 25
    """)
    rows = cursor.fetchall()

    logging.info(f"Found {len(rows)} items to validate")

    for i, (lot_id, title) in enumerate(rows, start=1):

        clean = re.sub(r'Lot\s+#?\d+', '', title, flags=re.IGNORECASE)
        clean = re.sub(r'[^\w\s]', '', clean)
        search = " ".join(clean.split()[:4])

        logging.info(f"[{i}/{len(rows)}] Checking: {search}")

        try:
            url = (
                "https://www.ebay.com/sch/i.html?"
                f"_nkw={search.replace(' ', '+')}"
                "&LH_Sold=1&LH_Complete=1"
            )

            driver.get(url)
            time.sleep(random.uniform(2.5, 4.5))

            items = driver.find_elements(By.CSS_SELECTOR, "li.s-item")

            found_data = []

            for item in items[:15]:  # limit parsing
                try:
                    text = item.text
                    match = re.search(r'\$([\d,]+\.\d{2})', text)
                    if not match:
                        continue

                    price = float(match.group(1).replace(',', ''))

                    if 2.0 < price < 5000.0:
                        try:
                            link_el = item.find_element(By.TAG_NAME, "a")
                            link = link_el.get_attribute("href")
                        except:
                            link = ""

                        found_data.append((price, link))

                except:
                    continue

            if not found_data:
                logging.info("   ⚠️ No comps found")
                continue

            # Trim outliers
            prices = sorted([d[0] for d in found_data])
            if len(prices) > 5:
                prices = prices[1:-1]  # remove lowest & highest

            avg_price = sum(prices) / len(prices)

            closest_item = min(found_data, key=lambda x: abs(x[0] - avg_price))
            best_link = closest_item[1]

            img_url = ""
            try:
                imgs = driver.find_elements(By.CSS_SELECTOR, ".s-item__image-img")
                for img in imgs:
                    src = img.get_attribute("src")
                    if src and "ebayimg" in src:
                        img_url = src
                        break
            except:
                pass

            cursor.execute("""
                UPDATE lots
                SET market_value = ?, ref_image = ?, ref_url = ?
                WHERE lot_id = ?
            """, (avg_price, img_url, best_link, lot_id))

            conn.commit()

            logging.info(f"   ✅ Avg: ${avg_price:.2f}")

        except Exception as e:
            logging.error(f"   ❌ Error: {e}")
            continue

    driver.quit()
    conn.close()

    logging.info("=== VALIDATOR FINISHED ===")


if __name__ == "__main__":
    run_validator()
