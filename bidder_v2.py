import asyncio
import aiosqlite
import random
import requests
from datetime import datetime

# --- CONFIGURATION ---
DB_NAME = "hibid_lots.db"
MY_MAX_BID_PERCENT = 0.70 
MIN_PROFIT_MARGIN = 40.0 

# --- YOUR DISCORD LINK (DO NOT SHARE THIS) ---
DISCORD_WEBHOOK = "https://discordapp.com/api/webhooks/1469494844824227924/HGLLuchNpK5gJYb0Sl05ZsE4a6gi4f_mYqUJudBa-Voa_FqC0bXR9fhv2hAfPnaEUZZJ"

async def send_alert(lot_id, title, profit, url, img_url):
    if "YOUR_WEBHOOK" in DISCORD_WEBHOOK: return 
    
    # Create the Rich Embed (The fancy card format)
    embed = {
        "title": f"💰 PROFIT ALERT: ${profit:.0f}",
        "description": f"**{title}**\n[👉 Click to Bid]({url})",
        "color": 5763719, # Green Color
        "thumbnail": {"url": img_url},
        "fields": [
            {"name": "Est. Profit", "value": f"${profit:.2f}", "inline": True},
            {"name": "Lot ID", "value": str(lot_id), "inline": True}
        ],
        "footer": {"text": f"Auction Bot • {datetime.now().strftime('%I:%M %p')}"}
    }
    
    data = {
        "content": "🚨 **New Deal Found!**", 
        "embeds": [embed]
    }
    
    try:
        requests.post(DISCORD_WEBHOOK, json=data)
    except Exception as e:
        print(f"[!] Discord Alert Failed: {e}")

async def run_bidder():
    print("--- BIDDER V3.0 (ALERTS ACTIVE) ---")
    
    try:
        db = await aiosqlite.connect(DB_NAME)
        
        # We look for PENDING items that have a VALUE > 0
        query = """
            SELECT lot_id, title, current_bid, market_value, url, image_url, buyers_premium 
            FROM lots 
            WHERE status = 'pending' AND market_value > 0
        """
        
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            
            for row in rows:
                lot_id, title, current_bid, market_value, url, img, bp = row
                
                # Default to 15% BP if missing
                if bp is None: bp = 0.15
                
                # Math: Cost vs Value
                total_cost = current_bid * (1 + bp)
                my_limit = market_value * MY_MAX_BID_PERCENT
                potential_profit = market_value - total_cost - 15 # Minus shipping est
                
                # THE DECISION MAKER
                if total_cost < my_limit and potential_profit > MIN_PROFIT_MARGIN:
                    print(f"[!] PROFITABLE: {title[:20]}... (Profit: ${potential_profit:.0f})")
                    
                    # ALERT PHONE
                    await send_alert(lot_id, title, potential_profit, url, img)
                    
                    # SLOW DOWN (So we don't spam Discord too fast)
                    await asyncio.sleep(2) 

        await db.close()
        print("--- BIDDER CYCLE COMPLETE ---")
        
    except Exception as e:
        print(f"[ERROR] Bidder Crash: {e}")

if __name__ == "__main__":
    asyncio.run(run_bidder())