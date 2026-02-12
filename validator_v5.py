import asyncio
from playwright.async_api import async_playwright
import aiosqlite
import urllib.parse
import random

# CONFIGURATION
DB_NAME = 'hibid_lots.db'

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Check if ref_image column exists, if not, create it
        try:
            await db.execute("SELECT ref_image FROM lots LIMIT 1")
        except:
            print("[*] Upgrading Database to support Reference Images...")
            await db.execute("ALTER TABLE lots ADD COLUMN ref_image TEXT")
            await db.commit()

async def get_ebay_value(context, title):
    # Clean title for search (remove "Lot 123 |")
    clean_title = title.split('|')[-1].strip()
    encoded_query = urllib.parse.quote(clean_title)
    
    # eBay "Sold Items" Search URL
    url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&_sacat=0&LH_Sold=1&LH_Complete=1&_ipg=60"
    
    page = await context.new_page()
    try:
        await page.goto(url, timeout=10000)
        
        # Extract Prices and the First Image
        data = await page.evaluate('''() => {
            const items = document.querySelectorAll('.s-item__info');
            const prices = [];
            let refImg = "";
            
            items.forEach((item, index) => {
                const priceEl = item.querySelector('.s-item__price');
                if (priceEl) {
                    // Extract Price
                    const text = priceEl.innerText.replace(/[^0-9.]/g, '');
                    const val = parseFloat(text);
                    if (val > 0) prices.push(val);
                    
                    // Extract Image (Only from the first valid result)
                    // We skip index 0 often because it can be a "Shop on eBay" header or sponsored
                    if (index >= 1 && !refImg) { 
                         const container = item.closest('.s-item');
                         const imgEl = container.querySelector('img');
                         if (imgEl) refImg = imgEl.src;
                    }
                }
            });
            return { prices, refImg };
        }''')
        
        await page.close()
        
        prices = data['prices']
        ref_image = data['refImg']
        
        if not prices: return 0.0, ""
        
        # Calculate Average Price
        avg_price = sum(prices) / len(prices)
        return round(avg_price, 2), ref_image
        
    except Exception as e:
        await page.close()
        return 0.0, ""

async def run():
    await init_db()
    
    async with aiosqlite.connect(DB_NAME) as db:
        # Get items that need valuation
        # We can also re-value items if we want to fetch images for them
        async with db.execute("SELECT lot_id, title FROM lots WHERE status='scraped'") as cursor:
            rows = await cursor.fetchall()
            
    if not rows:
        print("No new lots to value.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        print(f"Starting valuation for {len(rows)} items...")
        
        for lot_id, title in rows:
            print(f"Valuing: {title}...")
            
            # Random sleep to be human
            await asyncio.sleep(random.uniform(2, 5))
            
            market_value, ref_image = await get_ebay_value(context, title)
            
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute('''
                    UPDATE lots 
                    SET market_value=?, ref_image=?, status='valued', last_updated=CURRENT_TIMESTAMP
                    WHERE lot_id=?
                ''', (market_value, ref_image, lot_id))
                await db.commit()
            
            if market_value > 0:
                print(f"   -> Found Value: ${market_value} (Img: {'Yes' if ref_image else 'No'})")
            else:
                print("   -> No comps found.")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())