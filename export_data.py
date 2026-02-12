import sqlite3
import pandas as pd
import datetime

# CONFIGURATION (Must match your Dashboard)
PROFIT_MIN_LOW = 15.00
PROFIT_MIN_MID = 40.00
PROFIT_PERCENT_HIGH = 0.25
HARD_LIMIT = 200.00
TAX_RATE = 0.08
EBAY_FEES = 0.13
DEFAULT_BP = 0.15

DB_NAME = 'hibid_lots.db'

def calculate_safe_limit(row):
    try:
        market_value = row['market_value']
        if market_value <= 0: return 0
        
        bp = row['buyers_premium'] if pd.notnull(row['buyers_premium']) else DEFAULT_BP

        if market_value < 50:
            required_profit = PROFIT_MIN_LOW
        elif market_value < 200:
            required_profit = PROFIT_MIN_MID
        else:
            required_profit = market_value * PROFIT_PERCENT_HIGH

        net_revenue = market_value * (1 - EBAY_FEES)
        allowable_spend = net_revenue - required_profit
        
        if allowable_spend <= 0: return 0.00

        fee_multiplier = 1 + bp + TAX_RATE
        max_bid = allowable_spend / fee_multiplier
        
        return round(min(max_bid, HARD_LIMIT), 2)
    except:
        return 0

def export():
    print(f"Reading database: {DB_NAME}...")
    conn = sqlite3.connect(DB_NAME)
    
    # Get ALL data, not just valued ones
    query = "SELECT * FROM lots ORDER BY last_updated DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("Database is empty! (The bot hasn't saved anything yet).")
        return

    print(f"Processing {len(df)} records...")

    # Re-calculate the columns for the report
    df['my_max_bid'] = df.apply(calculate_safe_limit, axis=1)
    df['potential_spread'] = df['market_value'] - df['current_bid']
    
    # Label the status
    df['action_recommendation'] = df.apply(
        lambda x: "BUY NOW" if (x['current_bid'] < x['my_max_bid'] and x['market_value'] > 0) else "IGNORE", 
        axis=1
    )

    # Generate Filename with Timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"FULL_EXPORT_{timestamp}.csv"

    # Save
    df.to_csv(filename, index=False)
    print(f"\n✅ SUCCESS! Data saved to: {filename}")
    print(f"   Contains {len(df)} items.")

if __name__ == "__main__":
    export()