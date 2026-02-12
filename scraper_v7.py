import asyncio
from playwright.async_api import async_playwright
import aiosqlite
import re
import datetime

# CONFIGURATION
TARGET_URL = "https://hibid.com/lots?zip=62629&miles=50&lot_type=ONLINE" 

async def save_lot(lot):
    async with aiosqlite.connect('hibid_lots.db') as db:
        try:
            # 1. Insert or Ignore
            await db.execute('''
                INSERT OR IGNORE INTO lots 
                (lot_id, title, url, current_bid, time_remaining, shipping_available, buyers_premium, end_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (lot['id'], lot['title'], lot['url'], lot['price'], lot['time'], 
                  lot['shipping'], 0.15, lot['time']))
            
            # 2. Force Update the Price and Time
            await db.execute('''
                UPDATE lots 
                SET current_bid=?, time_remaining=?, end_time=?, last_updated=CURRENT_TIMESTAMP
                WHERE lot_id=?
            ''', (lot['price'], lot['time'], lot['time'], lot['id']))
            
            await db.commit()
            
            # Only print if we found a valid price or time
            if lot['price'] > 0:
                print(f"[+] {lot['title'][:15]}... | Bid: ${lot['price']} | Ends: {lot['time']}")
                
        except Exception as e:
            print(f"[!] DB Error: {e}")

async def run():
    async with async_playwright() as p:
        # Launch Browser (Visible for debugging)
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print(f"Navigating to {TARGET_URL}...")
        try:
            await page.goto(TARGET_URL, timeout=60000)
            await page.wait_for_selector('a[href*="/lot/"]', timeout=30000)
        except:
            print("[!] Timeout loading HiBid.")
            await browser.close()
            return

        print("Scrolling to load items...")
        for _ in range(5):
            await page.mouse.wheel(0, 1000)
            await asyncio.sleep(1)

        # --- V7 NUCLEAR EXTRACTOR ---
        lots = await page.evaluate('''() => {
            const items = [];
            // Find all container boxes that look like a lot
            const containers = document.querySelectorAll('.lot-row, .ng-star-inserted');
            
            containers.forEach(box => {
                const text = box.innerText;
                const linkEl = box.querySelector('a[href*="/lot/"]');
                
                if (linkEl && text.length > 20) {
                    
                    // 1. PRICE HUNT (Find largest number with a $ sign)
                    // Matches: $50, $50.00, $1,200.00
                    const moneyMatches = text.match(/\$([0-9,]+(\.[0-9]{2})?)/g);
                    let price = 0.0;
                    if (moneyMatches) {
                        // Extract numbers, sort them, and pick the highest one < $10,000 (Avoids "Retail Price")
                        const values = moneyMatches.map(m => parseFloat(m.replace(/[^0-9.]/g, '')));
                        const validValues = values.filter(v => v < 10000); 
                        if (validValues.length > 0) {
                             // Usually the bid is the highest number shown next to the button
                             price = Math.max(...validValues);
                        }
                    }

                    // 2. TIME HUNT (Find "Xh Ym" or "Xd Xh")
                    // Matches: 4d 2h, 12h 30m, 50s
                    let timeRemaining = "Unknown";
                    const timeMatch = text.match(/(\d+d\s\d+h|\d+h\s\d+m|\d+m\s\d+s|\d+h|\d+m)/);
                    if (timeMatch) {
                        timeRemaining = timeMatch[0];
                    } else if (text.toLowerCase().includes("closing")) {
                        timeRemaining = "Closing Now";
                    }

                    // 3. TITLE
                    const title = linkEl.innerText.split('\\n')[0].trim();

                    items.push({
                        id: linkEl.href, 
                        title: title,
                        price: price,
                        time: timeRemaining,
                        url: linkEl.href,
                        shipping: text.toLowerCase().includes("shipping")
                    });
                }
            });
            return items;
        }''')

        print(f"Found {len(lots)} lots. Updating Database...")
        for lot in lots:
            await save_lot(lot)
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
    