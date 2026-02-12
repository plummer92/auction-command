import sqlite3
import time
import re
import logging
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# ============================================================
# ======================= CONFIGURATION ======================
# ============================================================

DB_NAME = "hibid_lots.db"
LOG_FILE = "validator_log.txt"

CHROMIUM_PATH = "/usr/bin/chromium"
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"

MAX_ITEMS_PER_RUN = 25
MAX_EBAY_RESULTS = 15
MIN_VALID_PRICE = 2.0
MAX_VALID_PRICE = 5000.0
DEBUG_MODE = True   # 🔥 Toggle deep debugging here


# ============================================================
# ========================== LOGGING =========================
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)


# ============================================================
# ======================== DB LAYER ==========================
# ============================================================

def setup_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE lots ADD COLUMN ref_url TEXT")
    except:
        pass
    conn.commit()
    conn.close()


def get_pending_lots(limit):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT lot_id, title
        FROM lots
        WHERE (market_value IS NULL OR market_value = 0)
        AND status='pending'
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()
    return rows


def update_lot_value(lot_id, avg_price, img_url, best_link):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE lots
        SET market_value = ?, ref_image = ?, ref_url = ?
        WHERE lot_id = ?
    """, (avg_price, img_url, best_link, lot_id))

    conn.commit()
    conn.close()


# ============================================================
# ====================== DRIVER LAYER ========================
# ============================================================

def get_driver():
    options = Options()
    options.binary_location = CHROMIUM_PATH

    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)

    return driver


# ============================================================
# ====================== SEARCH CLEANER ======================
# ============================================================

def build_search_query(title):
    clean = re.sub(r'Lot\s+#?\d+', '', title, flags=re.IGNORECASE)
    clean = re.sub(r'[^\w\s]', '', clean)
    words = clean.split()

    # Remove quantity numbers at start
    if words and words[0].isdigit():
        words = words[1:]

    return " ".join(words[:4])


# ============================================================
# ===================== EBAY SCRAPER =========================
# ============================================================

def fetch_ebay_results(driver, search_query):
    url = (
        "https://www.ebay.com/sch/i.html?"
        f"_nkw={search_query.replace(' ', '+')}"
        "&LH_Sold=1&LH_Complete=1"
    )

    driver.get(url)
    time.sleep(random.uniform(2.5, 4.5))

    if DEBUG_MODE:
        logging.info(f"   Page title: {driver.title}")
        logging.info(f"   URL: {driver.current_url}")

    if DEBUG_MODE:
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logging.info("   🔍 Saved debug_page.html")


    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)


    items = driver.find_elements(
        By.XPATH,
        "//*[contains(@class,'s-item')]"
    )



    if DEBUG_MODE:
        logging.info(f"   Found {len(items)} raw eBay items")

    return items


def extract_prices_from_items(items):
    found_data = []

    for item in items[:MAX_EBAY_RESULTS]:
        try:
            text = item.text
            match = re.search(r'\$([\d,]+\.\d{2})', text)

            if not match:
                continue

            price = float(match.group(1).replace(',', ''))

            if MIN_VALID_PRICE < price < MAX_VALID_PRICE:
                try:
                    link_el = item.find_element(By.TAG_NAME, "a")
                    link = link_el.get_attribute("href")
                except:
                    link = ""

                found_data.append((price, link))

        except:
            continue

    return found_data


# ============================================================
# ===================== PRICE PROCESSING =====================
# ============================================================

def compute_average_price(found_data):
    prices = sorted([d[0] for d in found_data])

    if len(prices) > 5:
        prices = prices[1:-1]  # remove outliers

    return sum(prices) / len(prices)


def extract_reference_image(driver):
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, ".s-item__image-img")
        for img in imgs:
            src = img.get_attribute("src")
            if src and "ebayimg" in src:
                return src
    except:
        pass

    return ""


# ============================================================
# ========================= MAIN RUN =========================
# ============================================================

def run_validator():
    logging.info("=== VALIDATOR STARTED (CLOUD MODE) ===")

    setup_db()
    driver = get_driver()

    rows = get_pending_lots(MAX_ITEMS_PER_RUN)
    logging.info(f"Found {len(rows)} items to validate")

    for i, (lot_id, title) in enumerate(rows, start=1):

        search_query = build_search_query(title)
        logging.info(f"[{i}/{len(rows)}] Checking: {search_query}")

        try:
            items = fetch_ebay_results(driver, search_query)
            found_data = extract_prices_from_items(items)

            if not found_data:
                logging.info("   ⚠️ No comps found")

                if DEBUG_MODE:
                    driver.save_screenshot(f"debug_{lot_id}.png")

                continue

            avg_price = compute_average_price(found_data)
            best_link = min(found_data, key=lambda x: abs(x[0] - avg_price))[1]
            img_url = extract_reference_image(driver)

            update_lot_value(lot_id, avg_price, img_url, best_link)

            logging.info(f"   ✅ Avg: ${avg_price:.2f}")

        except Exception as e:
            logging.error(f"   ❌ Error: {e}")
            continue

    driver.quit()
    logging.info("=== VALIDATOR FINISHED ===")


# ============================================================
# ========================= ENTRY ============================
# ============================================================

if __name__ == "__main__":
    run_validator()
