@echo off
title AUCTION BOT - LIVE VIEW
color 0a

:: --- LAUNCH NGROK TUNNEL (Force Current Folder) ---
:: %~dp0 tells Windows "Look in the same folder as this script"
echo Launching Ngrok Tunnel...
start "Ngrok Tunnel" "%~dp0ngrok.exe" http 8501
:: ---------------------------

:loop
echo =================================================
echo [TIME] %TIME%

echo [STATUS] Running Scraper v9.9 (Self-Healing)...
:: No ">> bot_log.txt" means you see the data live!
python scraper_v8.py 

echo [STATUS] Running Validator v6 (Visible eBay)...
python validator_v6.py 

echo [STATUS] Checking for profitable bids...
python bidder_v2.py 

echo [STATUS] Scan complete. Resting to mimic human behavior...
python smart_wait.py

goto loop