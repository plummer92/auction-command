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
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
DB_NAME = "hibid_lots.db"
RADIUS = 50
MAX_PAGES_PER_CITY = 20

TARGETS = [
    {"zip": "62629", "name": "Chatham, IL"},
    {"zip": "46173", "name": "Rushville, IN"}
]

def setup_db():
    db_path = os.path.abspath(DB_NAME)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try: cursor.execute("ALTER TABLE lots ADD COLUMN final_price REAL")
    except: pass
    try: cursor.execute("ALTER TABLE lots ADD COLUMN location TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE lots ADD COLUMN ref_url TEXT")
    except: pass
    
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
            location TEXT,
            ref_url TEXT
        )
    ''')
    conn.commit()
    conn.close()
    return db_path

def run_multi_city_scraper():
    print(f"--- SCRAPER V29.0 (THE INDUSTRIAL VACUUM) ---")
    db_path = setup_db()
    
    chrome_options = Options()
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") 
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    prefs = {
        "profile.default_content_setting_values.geolocation": 2, 
        "profile.default_content_setting_values.notifications": 2 
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    for target in TARGETS:
        city_name = target['name']
        zip_code = target['zip']
        
        print(f"\n==========================================")
        print(f"📍 TRAVELING TO: {city_name} ({zip_code})")
        print(f"==========================================")
        
        # FORCE "PAST" URL DIRECTLY
        base_url = f"https://hibid.com/lots/past?zip={zip_code}&miles={RADIUS}"
        driver.get(base_url)
        time.sleep(5)
        
        # Check Mode
        try:
            first_card = driver.find_element(By.TAG_NAME, "app-lot-tile")
            if "Current Bid" in first_card.text and "Price Realized" not in first_card.text:
                print("   ⚠️ WARNING: Redirected to Active Lots. Attempting force click...")
                try:
                     driver.find_element(By.CSS_SELECTOR, "a[href='/lots/past']").click()
                     time.sleep(5)
                except: pass
            else:
                print("   ✅ History Mode Active.")
        except: pass

        harvested_count = 0
        current_page = 1
        missed_examples = 0
        
        while current_page <= MAX_PAGES_PER_CITY:
            print(f"   [Page {current_page}] Vacuuming...")
            
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)
            driver.execute_script("window.scrollBy(0, 2000);")
            time.sleep(2)
            
            cards = driver.find_elements(By.TAG_NAME, "app-lot-tile")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            for card in cards:
                try:
                    card_text = card.text.replace("\n", " | ")
                    
                    # 1. FIND LINK
                    link_el = None
                    try:
                        links = card.find_elements(By.TAG_NAME, "a")
                        for l in links:
                            if "/lot/" in l.get_attribute("href"):
                                link_el = l
                                break
                        if not link_el: link_el = card.find_element(By.CSS_SELECTOR, "h2 a")
                    except: pass
                    if not link_el: continue

                    title = link_el.text.strip()
                    link = link_el.get_attribute("href")
                    lot_id = link.split('/')[-2] if 'lot' in link else link[-10:]

                    # 2. EXTRACT PRICE (Aggressive Logic) 💰
                    price = 0.0
                    
                    # Method A: Look for "Price Realized" or "High Bid" followed by ANY number
                    # This catches "Price Realized: 10.00" even without "$"
                    match = re.search(r'(?:Price Realized|Sold|High Bid)[^\d]*([\d,]+\.\d{2})', card_text)
                    if match:
                        price = float(match.group(1).replace(',', ''))
                    
                    # Method B: Look for specific HTML classes often used in archives
                    if price == 0:
                        try:
                            # Try multiple class names used by HiBid
                            for cls in ["lot-realized-price", "lot-high-bid", "lot-price"]:
                                try:
                                    el = card.find_element(By.CLASS_NAME, cls)
                                    val = el.text.replace("$", "").replace("USD", "").replace(",", "").strip()
                                    price = float(val)
                                    if price > 0: break
                                except: pass
                        except: pass

                    # Method C: Last Resort - Grab the biggest number that looks like money
                    if price == 0:
                        numbers = re.findall(r'\$([\d,]+\.\d{2})', card_text)
                        if numbers:
                            # Usually the highest dollar amount on a card is the price
                            vals = [float(n.replace(',', '')) for n in numbers]
                            price = max(vals)

                    # LOGGING MISSED ITEMS (First 3 only)
                    if price == 0:
                        if missed_examples < 3:
                            print(f"      [Skipped - No Price Detected]: {card_text[:80]}...")
                            missed_examples += 1
                        continue 

                    # 3. IMAGE
                    img_url = ""
                    try: img_url = card.find_element(By.TAG_NAME, "img").get_attribute("src")
                    except: pass
                    
                    # SAVE
                    cursor.execute("""
                        INSERT INTO lots (lot_id, title, final_price, status, url, image_url, location)
                        VALUES (?, ?, ?, 'sold_history', ?, ?, ?)
                        ON CONFLICT(lot_id) DO UPDATE SET
                            final_price=excluded.final_price,
                            status='sold_history',
                            location=?, 
                            last_seen=CURRENT_TIMESTAMP
                    """, (lot_id, title, price, link, img_url, city_name, city_name))
                    
                    harvested_count += 1
                except: continue
            
            conn.commit()
            conn.close()

            # NEXT PAGE
            try:
                next_xpath = "//a[contains(@class, 'page-link') and .//span[contains(text(), 'Next')]]"
                next_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, next_xpath)))
                driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(3)
                current_page += 1
            except:
                print(f"   [X] End of {city_name} history.")
                break
        
        print(f"✅ Finished {city_name}. Harvested: {harvested_count}")

    driver.quit()
    print("--- GLOBAL HARVEST COMPLETE ---")

if __name__ == "__main__":
    run_multi_city_scraper()