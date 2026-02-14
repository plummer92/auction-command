import sqlite3
from datetime import datetime, timedelta

DB = "hibid_lots.db"


def run_lifecycle():

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    now = datetime.utcnow()
    stale_cutoff = now - timedelta(hours=2)

    # ------------------------------
    # 1️⃣ Move expired active lots to ended
    # ------------------------------

    cursor.execute("""
        UPDATE lots
        SET status='ended',
            ended_at=CURRENT_TIMESTAMP
        WHERE status='pending'
        AND (
            minutes_left <= 0
            OR (minutes_left IS NULL AND last_seen < ?)
        )
    """, (stale_cutoff,))

    expired_count = cursor.rowcount

    # ------------------------------
    # 2️⃣ Move ended lots to sold_history ONLY if final_price exists
    # ------------------------------

    cursor.execute("""
        UPDATE lots
        SET status='sold_history'
        WHERE status='ended'
        AND final_price IS NOT NULL
    """)

    sold_count = cursor.rowcount

    conn.commit()
    conn.close()

    print(f"Lifecycle: {expired_count} moved to ended, {sold_count} moved to sold_history.")
