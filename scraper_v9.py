import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time
import lifecycle_manager

DB = "hibid_lots.db"

ZIP_CODES = ["62629", "62704"]   # Add as many as you want
MILES = 50


# ------------------------------
# Utility: Parse minutes
# ------------------------------
def parse_minutes(time_text):
    if not time_text:
        return None

    time_text = time_text.lower()

    minutes = 0

    hours_match = re.search(r"(\d+)\s*h", time_text)
    minutes_match = re.search(r"(\d+)\s*m", time_text)

    if hours_match:
        minutes += int(hours_match.group(1)) * 60
    if minutes_match:
        minutes += int(minutes_match.group(1))

    return minutes if minutes > 0 else None


# ------------------------------
# DB Connection
# ------------------------------
def get_db():
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ------------------------------
# Scrape One ZIP
# ------------------------------
def scrape_zip(zip_code):

    conn = get_db()
    cursor = conn.cursor()

    page = 1

    while True:
        url = f"https://hibid.com/lots?zip={zip_code}&miles={MILES}&lot_type=ONLINE&page={page}"
        print(f"[ZIP {zip_code}] PAGE {page}")

        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        lots = soup.select(".lot-card")

        if not lots:
            break

        for lot in lots:
            try:
                lot_id = lot.get("data-lotid")
                title = lot.select_one(".lot-title").text.strip()

                bid_text = lot.select_one(".current-bid").text.strip()
                current_bid = float(re.sub(r"[^\d.]", "", bid_text)) if bid_text else 0.0

                bid_count_text = lot.select_one(".bid-count")
                bid_count = int(re.sub(r"[^\d]", "", bid_count_text.text)) if bid_count_text else 0

                time_text_elem = lot.select_one(".time-remaining")
                time_remaining = time_text_elem.text.strip() if time_text_elem else None
                minutes_left = parse_minutes(time_remaining)

                image_elem = lot.select_one("img")
                image_url = image_elem["src"] if image_elem else None

                url_elem = lot.select_one("a")
                lot_url = "https://hibid.com" + url_elem["href"] if url_elem else None

                # ACTIVE lots are always pending
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
                    url=excluded.url,
                    image_url=excluded.image_url,
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
                    lot_url,
                    image_url,
                    status
                ))

            except Exception as e:
                print("Error parsing lot:", e)
                continue

        conn.commit()
        page += 1
        time.sleep(1)

    conn.close()


# ------------------------------
# Main Runner
# ------------------------------
def run_scraper():
    print("=== AUCTION SCRAPER (PRO MODE) ===")

    for zip_code in ZIP_CODES:
        scrape_zip(zip_code)

    print("Running lifecycle manager...")
    lifecycle_manager.run_lifecycle()

    print("Scrape complete.")


if __name__ == "__main__":
    run_scraper()
