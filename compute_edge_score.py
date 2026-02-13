import sqlite3

DB = "hibid_lots.db"

conn = sqlite3.connect(DB)
cursor = conn.cursor()

cursor.execute("""
UPDATE lots
SET edge_score =
    (
        -- Price Delta (undervalued boost)
        (COALESCE(predicted_value, 0) - current_bid) * 0.4
    )
    +
    (
        -- Velocity
        COALESCE(velocity, 0) * 0.2
    )
    +
    (
        -- Time Compression
        CASE 
            WHEN minutes_left < 60 THEN 20
            WHEN minutes_left < 180 THEN 10
            ELSE 0
        END
    )
WHERE status='pending';
""")

conn.commit()
conn.close()

print("Edge scores updated.")
