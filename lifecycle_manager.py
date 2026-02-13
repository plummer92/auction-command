import sqlite3
from datetime import datetime

DB = "hibid_lots.db"

def run_lifecycle():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    # Move pending -> ended
    cursor.execute("""
        SELECT lot_id
        FROM lots
        WHERE status='pending'
        AND minutes_left IS NOT NULL
        AND minutes_left <= 0
    """)

    ended_lots = cursor.fetchall()

    for (lot_id,) in ended_lots:
        cursor.execute("""
            UPDATE lots
            SET status='ended',
                ended_at=?
            WHERE lot_id=?
        """, (datetime.utcnow(), lot_id))

    conn.commit()
    conn.close()

    print(f"Moved {len(ended_lots)} lots to ended.")

if __name__ == "__main__":
    run_lifecycle()
