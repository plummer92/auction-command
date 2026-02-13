import sqlite3

DB = "hibid_lots.db"

conn = sqlite3.connect(DB)
cursor = conn.cursor()

cursor.execute("""
UPDATE lots
SET edge_score =
    (
        -- 1️⃣ Price Delta (normalized undervalue %)
        CASE
            WHEN predicted_value IS NOT NULL
                 AND predicted_value > 0
                 AND current_bid IS NOT NULL
            THEN ((predicted_value - current_bid) / predicted_value) * 40
            ELSE 0
        END
    )
    +
    (
        -- 2️⃣ Demand Velocity (scaled)
        CASE
            WHEN velocity IS NOT NULL
            THEN velocity * 10
            ELSE 0
        END
    )
    +
    (
        -- 3️⃣ Time Compression Boost
        CASE
            WHEN minutes_left IS NOT NULL AND minutes_left <= 30 THEN 25
            WHEN minutes_left IS NOT NULL AND minutes_left <= 60 THEN 20
            WHEN minutes_left IS NOT NULL AND minutes_left <= 180 THEN 10
            ELSE 0
        END
    )
WHERE status='pending';
""")

conn.commit()
conn.close()

print("Edge scores updated.")
