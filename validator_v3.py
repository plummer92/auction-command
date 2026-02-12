import asyncio
import aiosqlite
import re
import statistics
from playwright.async_api import async_playwright
import urllib.parse
import random

DB_NAME = 'hibid_lots.db'
BATCH_SIZE = 50 
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
        await page.goto(target_url, timeout=15000)
        
        # Check for CAPTCHA (User must solve manually)
        if "captcha" in page.url or await page.query_selector('div.g-recaptcha'):
            print("  [!] CAPTCHA DETECTED. Pausing 20s for you to solve...")
            await asyncio.sleep(20)

        # Check for "No Results" text
        if await page.query_selector('.srp-save-null-search__heading'):
            return 0, 0

        # --- SHOTGUN STRATEGY: Try 3 ways to find price ---
        price_texts = []
        
        # Method 1: Standard Class
        elements = await page.locator('.s-item__price').all_inner_texts()
        if elements:
            price_texts = elements
        else:
            # Method 2: Look for any text starting with "$" inside item wrappers
            # This is slower but works if class names change
            print("  [!] Standard selector failed. Trying fuzzy search...")
            price_texts = await page.evaluate('''() => {
                const prices = [];
                document.querySelectorAll('.s-item__details').forEach(el => {
                    const text = el.innerText;
                    const match = text.match(/\$[0-9,]+\.[0-9]{2}/);
                    if (match) prices.push(match[0]);
                });
                return prices;
            }''')

        # Highlight found prices on screen (Visual Debug)
        await page.evaluate("document.querySelectorAll('.s-item__price').forEach(el => el.style.border = '2px solid red')")

        valid_prices = []
        for p in price_texts:
            # Clean: Remove "Sold", "to", and extra junk
            clean_p = re.sub(r'[^\d\.]', '', p)
            if clean_p:
                try:
                    val = float(clean_p)
                    if val > 0: valid_prices.append(val)
                except: continue
        
        if not valid_prices: 
            return 0, 0
            
        # Median math
        return statistics.median(valid_prices), len(valid_prices)

    except Exception as e:
        # Debug: Save screenshot if it crashes
        await page.screenshot(path=f"debug_error_{search_query[:10]}.png")
        print(f"  [!] Error: {e} (Saved screenshot)")
        return 0, 0

async def process_lots():
    async with aiosqlite.connect(DB_NAME) as db:
        # Reset 'unknown' items so we can retry them
        await db.execute("UPDATE lots SET status='new' WHERE status='unknown'")
        await db.commit()

        async with db.execute("SELECT lot_id, title FROM lots WHERE status='new' LIMIT ?", (BATCH_SIZE,)) as cursor:
            lots = await cursor.fetchall()
            
        if not lots:
            print("No new lots to check.")
            return

        async with async_playwright() as p:
            # HEADLESS=FALSE so you can see it working
            browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            for lot_id, raw_title in lots:
                cleaned = clean_title(raw_title)
                
                if any(bad in cleaned.lower() for bad in BAD_WORDS):
                    print(f"Skipping junk: {cleaned}")
                    await db.execute("UPDATE lots SET status='skipped' WHERE lot_id=?", (lot_id,))
                    await db.commit()
                    continue

                print(f"Checking: {cleaned}...")
                await asyncio.sleep(random.uniform(3, 5)) # Human pause
                
                price, count = await get_ebay_sold_price(page, cleaned)
                
                # Retry Logic: If fails, try first 3 words
                if count == 0 and len(cleaned.split()) > 3:
                    short_title = " ".join(cleaned.split()[:3])
                    print(f"  -> No hits. Retrying: {short_title}...")
                    await asyncio.sleep(2)
                    price, count = await get_ebay_sold_price(page, short_title)

                if count > 0:
                    print(f"  $$$ VALUED AT: ${price:.2f} ({count} sales)")
                    await db.execute("UPDATE lots SET status='valued', market_value=?, last_updated=CURRENT_TIMESTAMP WHERE lot_id=?", (price, lot_id))
                else:
                    print("  [x] No data found.")
                    await db.execute("UPDATE lots SET status='unknown' WHERE lot_id=?", (lot_id,))
                
                await db.commit()
            await browser.close()

if __name__ == '__main__':
    asyncio.run(process_lots())