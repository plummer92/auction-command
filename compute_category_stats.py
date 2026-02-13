import sqlite3
import statistics

DB = "hibid_lots.db"

conn = sqlite3.connect(DB)
cursor = conn.cursor()

# Get all distinct categories
cursor.execute("""
    SELECT DISTINCT predicted_category
    FROM lots
    WHERE status='sold_history'
    AND predicted_category IS NOT NULL
""")

categories = [row[0] for row in cursor.fetchall()]

for category in categories:
    cursor.execute("""
        SELECT final_price, bid_count
        FROM lots
        WHERE status='sold_history'
        AND predicted_category = ?
    """, (category,))
    
    rows = cursor.fetchall()
    prices = [r[0] for r in rows if r[0] is not None]
    bids = [r[1] for r in rows if r[1] is not None]

    if len(prices) == 0:
        continue

    median_price = statistics.median(prices)
    avg_price = sum(prices) / len(prices)
    avg_bid = sum(bids) / len(bids) if bids else 0
    total_sold = len(prices)

    cursor.execute("""
        INSERT OR REPLACE INTO category_stats
        (category, median_price, avg_price, avg_bid_count, total_sold)
        VALUES (?, ?, ?, ?, ?)
    """, (category, median_price, avg_price, avg_bid, total_sold))

conn.commit()
conn.close()

print("Category stats updated.")
