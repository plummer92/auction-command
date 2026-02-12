import asyncio
from playwright.async_api import async_playwright
import aiosqlite

# CONFIGURATION
# Search: Zip 62629 (Chatham), 50 Miles, Internet Only
TARGET_URL = "https://hibid.com/lots?zip=62629&miles=50&lot_type=ONLINE" 

async def save_lot(lot):
    async with aiosqlite.connect('hibid_lots.db') as db:
        try:
            # Insert new or Update existing
            await db.execute('''
                INSERT OR IGNORE INTO lots 
                (lot_id, title, url, current_bid, time_remaining, shipping_available, buyers_premium, end_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (lot['id'], lot['title'], lot['url'], lot['price'], lot['time'], 
                  lot['shipping'], lot['bp'], lot['end_time']))
            
            await db.execute('''
                UPDATE lots 
                SET current_bid=?, time_remaining=?, end_time=?, shipping_available=?, buyers_premium=?
                WHERE lot_id=?
            ''', (lot['price'], lot['time'], lot['end_time'], lot['shipping'], lot['bp'], lot['id']))
            
            await db.commit()
            print(f"[+] Scraped: {lot['title'][:30]}... (${lot['price']})")
        except Exception as e:
            pass

async def run():
    async with async_playwright() as p:
        # HEADLESS=TRUE IS CRITICAL FOR BACKGROUND RUNNING
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print(f"Navigating to {TARGET_URL}...")
        await page.goto(TARGET_URL, timeout=60000)
        
        try:
            await page.wait_for_selector('a[href*="/lot/"]', timeout=30000)
        except:
            print("[!] Timeout waiting for lots.")
            await browser.close()
            return

        print("Scrolling to load items...")
        for _ in range(5):
            await page.mouse.wheel(0, 1000)
            await asyncio.sleep(1)

        lots = await page.evaluate('''() => {
            const items = [];
            const links = Array.from(document.querySelectorAll('a[href*="/lot/"]'));
            
            links.forEach(link => {
                const container = link.closest('.lot-row') || link.closest('.ng-star-inserted') || link.parentElement;
                
                if (container && link.innerText.length > 3) {
                    const text = container.innerText;
                    
                    // 1. Price
                    const priceMatch = text.match(/[\$][\s]?[0-9,\.]+/);
                    let price = 0;
                    if (priceMatch) price = parseFloat(priceMatch[0].replace(/[^0-9.]/g, ''));
                    
                    // 2. Shipping
                    const shipping = text.toLowerCase().includes("shipping available");
                    
                    // 3. Buyer's Premium (BP)
                    let bp = 0.15; 
                    const bpMatch = text.match(/(\d+)%\s?BP/i);
                    if (bpMatch) bp = parseFloat(bpMatch[1]) / 100;

                    // 4. Time
                    let timeRemaining = "Unknown";
                    const timeEl = container.querySelector('.lot-time-left');
                    if (timeEl) timeRemaining = timeEl.innerText.trim();

                    items.push({
                        id: link.href, 
                        title: link.innerText.split('\\n')[0].trim(),
                        price: price,
                        time: timeRemaining,
                        end_time: timeRemaining,
                        url: link.href,
                        shipping: shipping,
                        bp: bp
                    });
                }
            });
            return items;
        }''')

        print(f"Found {len(lots)} lots.")
        for lot in lots:
            await save_lot(lot)
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())