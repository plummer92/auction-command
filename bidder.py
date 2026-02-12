import asyncio
from playwright.async_api import async_playwright
import aiosqlite
import config 

DB_NAME = 'hibid_lots.db'

async def calculate_max_bid(market_value, lot_data):
    """
    Calculates max bid using SLIDING SCALE logic.
    """
    # --- 1. DETERMINE REQUIRED PROFIT ---
    if market_value < 50:
        required_profit = config.PROFIT_MIN_LOW
    elif market_value < 200:
        required_profit = config.PROFIT_MIN_MID
    else:
        # For high value, we want a percentage (e.g., 25% of the value)
        required_profit = market_value * config.PROFIT_PERCENT_HIGH

    # --- 2. LOGISTICS COST ---
    # Defaulting to PICKUP (Change logic here if you want to force shipping calculation)
    logistics_cost = config.PICKUP_COST_FLAT 

    # --- 3. REVENUE (After eBay takes 13%) ---
    net_revenue = market_value * (1 - config.EBAY_FEES)
    
    # --- 4. ALLOWABLE SPEND ---
    # We take the revenue and subtract the Profit we DEMAND and the Logistics costs.
    # What's left is the maximum "Total Cost" (Bid + Fees) we can afford.
    allowable_spend = net_revenue - required_profit - logistics_cost
    
    if allowable_spend <= 0:
        return 0 # The item is not worth buying at ANY price.

    # --- 5. REVERSE ENGINEER THE BID ---
    # Total Paid = Bid * (1 + BP + Tax)
    # So: Bid = Total Paid / (1 + BP + Tax)
    
    bp = lot_data[0] if lot_data[0] > 0 else config.DEFAULT_BP
    fee_multiplier = 1 + bp + config.TAX_RATE
    
    max_bid = allowable_spend / fee_multiplier
    
    # Safety Brake
    if max_bid > config.HARD_MAX_BID_LIMIT:
        max_bid = config.HARD_MAX_BID_LIMIT
    
    return round(max_bid, 2)

async def run_bidder():
    async with aiosqlite.connect(DB_NAME) as db:
        # Get Valued items that we haven't bid on yet
        query = "SELECT lot_id, title, url, market_value, buyers_premium, shipping_available FROM lots WHERE status='valued' AND market_value > 0"
        async with db.execute(query) as cursor:
            candidates = await cursor.fetchall()

        if not candidates:
            print("No valued items found.")
            return

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False) # Keep False to see it work
            context = await browser.new_context()
            page = await context.new_page()

            # Login
            print("Logging in...")
            await page.goto("https://hibid.com/login")
            await page.fill("#username", config.HIBID_USERNAME)
            await page.fill("#password", config.HIBID_PASSWORD)
            await page.click("button[type='submit']")
            await page.wait_for_url("**/home**", timeout=20000)

            for lot in candidates:
                lot_id, title, url, mkt_val, bp, shipping = lot
                
                my_limit = await calculate_max_bid(mkt_val, (bp, shipping))
                
                if my_limit <= 1: continue

                print(f"Checking: {title} | Value: ${mkt_val} | My Limit: ${my_limit}")
                
                # Navigate and Bid logic here
                # (Dry Run Only logic is enabled in config)
                if config.DRY_RUN:
                    print(f"  [DRY RUN] Would bid ${my_limit}")
                
                await asyncio.sleep(2)

            await browser.close()

if __name__ == '__main__':
    asyncio.run(run_bidder())