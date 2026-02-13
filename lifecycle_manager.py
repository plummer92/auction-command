import sqlite3
from datetime import datetime, timedelta

DB = "hibid_lots.db"

def run_lifecycle():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    now = datetime.utcnow()
    stale_cutoff = now - timedelta(hours=2)

    # 1️⃣ Move pending -> ended if minutes_left <= 0
    cursor.execute("""
        UPDATE lots
        SET status='ended',
            ended_at=?
        WHERE status='pending'
        AND minutes_left IS NOT NULL
        AND minutes_left <= 0
    """, (now,))
    
    moved_time = cursor.rowcount

    # 2️⃣ Failsafe: stale lots not seen in 2 hours
    cursor.execute("""
        UPDATE lots
        SET status='ended',
            ended_at=?
        WHERE status='pending'
        AND last_seen < ?
    """, (now, stale_cutoff))
    
    moved_stale = cursor.rowcount

    conn.commit()
    conn.close()

    print(f"Moved {moved_time} expired + {moved_stale} stale lots to ended.")
