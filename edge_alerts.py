import sqlite3

DB = "hibid_lots.db"

ALERT_THRESHOLD = 50

conn = sqlite3.connect(DB)
cursor = conn.cursor()

cursor.execute("""
SELECT lot_id, title, edge_score
FROM lots
WHERE status='pending'
AND edge_score > ?
ORDER BY edge_score DESC
LIMIT 5;
""", (ALERT_THRESHOLD,))

rows = cursor.fetchall()

for row in rows:
    print("🔥 HIGH EDGE DEAL:", row)

conn.close()
