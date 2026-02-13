import sqlite3

DB = "hibid_lots.db"

conn = sqlite3.connect(DB)
cursor = conn.cursor()

cursor.execute("""
    SELECT lot_id, bid_count, minutes_left
    FROM lots
    WHERE status='pending'
""")

rows = cursor.fetchall()

for lot_id, bid_count, minutes_left in rows:
    if bid_count is None or minutes_left is None:
        continue
    
    velocity = bid_count / (minutes_left + 1)
    
    cursor.execute("""
        UPDATE lots
        SET velocity = ?
        WHERE lot_id = ?
    """, (velocity, lot_id))

conn.commit()
conn.close()

print("Velocity updated.")
