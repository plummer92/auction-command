import asyncio
from playwright.async_api import async_playwright
import aiosqlite

# CONFIGURATION
# Search: Zip 62629 (Chatham), 50 Miles, Internet Only
TARGET_URL = "https://hibid.com/lots?zip=62629&miles=50&lot_type=ONLINE" 

async def save_lot(lot):
    async with aiosqlite.connect('hibid_lots.db') as db:
        try:
            # 1. Insert if new
            await db.execute('''
                INSERT OR IGNORE INTO lots 
                (lot_id, title, url, current_bid, time_remaining, shipping_available, buyers_premium, end_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (lot['id'], lot['title'], lot['url'], lot['price'], lot['time'], 
                  lot['shipping'], lot['bp'], lot['end_time']))
            
            # 2. ALWAYS UPDATE the bid and time (Crucial for "Stale Data" fix)
            await db.execute('''
                UPDATE lots 
                SET current_bid=?, time_remaining=?, end_time=?, last_updated=CURRENT_TIMESTAMP
                WHERE lot_id=?
            ''', (lot['price'], lot['time'], lot['end_time'], lot['id']))
            
            await db.commit()
            print(f"[+] Scraped: {lot['title'][:20]}... | Bid: ${lot['price']} | Ends: {lot['time']}")
        except Exception as e:
            print(f"[!] Save Error: {e}")

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print(f"Navigating to {TARGET_URL}...")
        try:
            await page.goto(TARGET_URL, timeout=60000)
            await page.wait_for_selector('a[href*="/lot/"]', timeout=30000)
        except:
            print("[!] Timeout or Error loading HiBid.")
            await browser.close()
            return

        print("Scrolling to refresh bids...")
        for _ in range(5):
            await page.mouse.wheel(0, 1000)
            await asyncio.sleep(1)

        # --- UPDATED JAVASCRIPT EXTRACTOR ---
        lots = await page.evaluate('''() => {
            const items = [];
            const links = Array.from(document.querySelectorAll('a[href*="/lot/"]'));
            
            links.forEach(link => {
                const container = link.closest('.lot-row') || link.closest('.ng-star-inserted') || link.parentElement;
                
                if (container && link.innerText.length > 3) {
                    const text = container.innerText;
                    
                    // IMPROVED PRICE FINDER
                    // We look for "Current Bid: $X" or "High Bid: $X" specifically
                    let price = 0;
                    // Regex looks for "Bid" followed by anything then a "$" then numbers
                    const bidMatch = text.match(/(Current|High|Starting)\s?Bid\s?:?\s?[\$]([0-9,\.]+)/i);
                    
                    if (bidMatch && bidMatch[2]) {
                        price = parseFloat(bidMatch[2].replace(/,/g, ''));
                    } else {
                        // Fallback: Just grab the first money amount if strict match fails (Safety net)
                        const simpleMatch = text.match(/[\$]([0-9,\.]+)/);
                        if (simpleMatch) price = parseFloat(simpleMatch[1].replace(/,/g, ''));
                    }

                    // SHIPPING
                    const shipping = text.toLowerCase().includes("shipping available");
                    
                    // BP
                    let bp = 0.15; 
                    const bpMatch = text.match(/(\d+)%\s?BP/i);
                    if (bpMatch) bp = parseFloat(bpMatch[1]) / 100;

                    // TIME REMAINING (Extract "1d 2h" or date)
                    let timeRemaining = "Unknown";
                    // Try to find the specific clock icon or time class
                    const timeEl = container.querySelector('.lot-time-left') || container.querySelector('.lot-end-date');
                    if (timeEl) {
                        timeRemaining = timeEl.innerText.trim();
                    } else {
                        // Regex search for date-like or time-like strings in text
                        const timeMatch = text.match(/(\d+d\s\d+h|\d+h\s\d+m|Ends\s[0-9\/]+)/);
                        if (timeMatch) timeRemaining = timeMatch[0];
                    }

                    items.push({
                        id: link.href, 
                        title: link.innerText.split('\\n')[0].trim(),
                        price: price,
                        time: timeRemaining,
                        end_time: timeRemaining, // Use same field for now
                        url: link.href,
                        shipping: shipping,
                        bp: bp
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