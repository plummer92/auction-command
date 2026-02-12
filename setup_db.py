import sqlite3

def init_db():
    conn = sqlite3.connect('hibid_lots.db')
    c = conn.cursor()
    
    # Create the master table with all logistics columns
    c.execute('''
        CREATE TABLE IF NOT EXISTS lots (
            lot_id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            current_bid REAL,
            time_remaining TEXT,
            end_time TEXT,
            shipping_available BOOLEAN DEFAULT 0,
            buyers_premium REAL DEFAULT 0.15,
            pickup_notes TEXT,
            status TEXT DEFAULT 'new',
            market_value REAL DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("[+] Database initialized successfully.")

if __name__ == "__main__":
    init_db()