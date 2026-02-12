import asyncio
import aiosqlite
import re
import statistics
from playwright.async_api import async_playwright
import urllib.parse
import random

DB_NAME = 'hibid_lots.db'
BATCH_SIZE = 50 

# "BAD WORDS" filter to skip junk
BAD_WORDS = ['assortment', 'misc', 'group of', 'box of', 'pallet', 'shelf contents', 'lot of', 'bundle']

def clean_title(title):
    if '|' in title: title = title.split('|', 1)[1]
    title = re.sub(r'^(Lot|Item)\s*[\#\d]+[:\-\.]?\s*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'[^a-zA-Z0-9\s]', '', title)
    return title.strip()

async def get_ebay_sold_price(page, search_query):
    encoded_query = urllib.parse.quote_plus(search_query)
    # Search Sold + Completed
    target_url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&LH_Sold=1&LH_Complete=1&_sop=12"
    
    try:
        await page.goto(target_url, timeout=20000)
        
        # --- NUCLEAR OPTION: Regex Text Scan ---
        # Instead of looking for a class, we grab EVERYTHING that looks like a price "$ 12.34"
        print("  -> Scanning page for prices...")
        
        # This javascript pulls every single piece of text that matches a price pattern
        price_texts = await page.evaluate('''() => {
            const matches = [];
            // Get all elements that contain a dollar sign
            const elements = document.querySelectorAll('span, div, b');
            elements.forEach(el => {
                if (el.childElementCount === 0 && el.innerText.includes('$')) {
                    matches.push(el.innerText);
                    // VISUAL DEBUG: Highlight what we found in GREEN
                    el.style.backgroundColor = 'lightgreen';
                    el.style.border = '2px solid green';
                }
            });
            return matches;
        }''')

        valid_prices = []
        for p in price_texts:
            # Clean up: "$14.99" -> 14.99
            clean_p = re.sub(r'[^\d\.]', '', p)
            if clean_p:
                try:
                    val = float(clean_p)
                    # Filter out tiny values (shipping costs usually) and huge outliers
                    if val > 1.00 and val < 10000: 
                        valid_prices.append(val)
                except: continue
        
        if not valid_prices: 
            # Double check: Did we get 0 results?
            if await page.query_selector('.srp-save-null-search__heading'):
                print("  [!] eBay says 'No Results Found'")
            return 0, 0
            
        # We likely grabbed some shipping prices ($5.00) mixed with item prices ($50.00).
        # Strategy: Take the Median. It filters out the low shipping and high outliers.
        median_price = statistics.median(valid_prices)
        
        # If the median is tiny (like $5), it might have grabbed only shipping costs. 
        # So we take the max of the median vs the mean to be safe.
        final_price = max(median_price, statistics.mean(valid_prices))

        return final_price, len(valid_prices)

    except Exception as e:
        print(f"  [!] Error: {e}")
        return 0, 0

async def process_lots():
    async with aiosqlite.connect(DB_NAME) as db:
        # Reset 'unknown' items so we can retry them with the new code
        await db.execute("UPDATE lots SET status='new' WHERE status='unknown'")
        await db.commit()

        async with db.execute("SELECT lot_id, title FROM lots WHERE status='new' LIMIT ?", (BATCH_SIZE,)) as cursor:
            lots = await cursor.fetchall()
            
        if not lots:
            print("No new lots to check.")
            return

        async with async_playwright() as p:
            # HEADLESS=FALSE so you can see the GREEN BOXES
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # --- DEBUG PAUSE ---
            # We perform one dummy search first to let you check the window
            print("--- WARMING UP ---")
            print("I will search for 'iphone' first. Please watch the browser.")
            await get_ebay_sold_price(page, "iphone")
            print("Did you see Green Boxes on the prices? (Continuing in 5 seconds...)")
            await asyncio.sleep(5)
            print("------------------")

            for lot_id, raw_title in lots:
                cleaned = clean_title(raw_title)
                
                if any(bad in cleaned.lower() for bad in BAD_WORDS):
                    print(f"Skipping junk: {cleaned}")
                    await db.execute("UPDATE lots SET status='skipped' WHERE lot_id=?", (lot_id,))
                    await db.commit()
                    continue

                print(f"Checking: {cleaned}...")
                await asyncio.sleep(random.uniform(2, 4))
                
                price, count = await get_ebay_sold_price(page, cleaned)
                
                # Retry Logic: Shorten title if failed
                if count == 0 and len(cleaned.split()) > 3:
                    short_title = " ".join(cleaned.split()[:3])
                    print(f"  -> No hits. Retrying: {short_title}...")
                    await asyncio.sleep(2)
                    price, count = await get_ebay_sold_price(page, short_title)

                if count > 0:
                    print(f"  $$$ VALUED AT: ${price:.2f} ({count} prices found)")
                    await db.execute("UPDATE lots SET status='valued', market_value=?, last_updated=CURRENT_TIMESTAMP WHERE lot_id=?", (price, lot_id))
                else:
                    print("  [x] No data found.")
                    # Don't mark unknown yet, keep retrying
                
                await db.commit()
            await browser.close()

if __name__ == '__main__':
    asyncio.run(process_lots())