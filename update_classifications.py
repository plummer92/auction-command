import sqlite3
import csv

DB_NAME = "hibid_lots.db"
CSV_FILE = "classified_sold_history.csv"

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

with open(CSV_FILE, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cursor.execute("""
            UPDATE lots
            SET predicted_category = ?,
                confidence = ?
            WHERE lot_id = ?
        """, (
            row["predicted_category"],
            float(row["confidence"]),
            row["lot_id"]
        ))

conn.commit()
conn.close()

print("Classification backfill complete.")
