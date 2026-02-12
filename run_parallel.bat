@echo off
title AUCTION COMMAND CENTER (ALWAYS ON)

echo =================================================
echo    STARTING PARALLEL PROCESSING ENGINE 🚀
echo =================================================

:: 1. Start the Dashboard (Only once, it stays open)
start "THE DASHBOARD" cmd /k python -m streamlit run dashboard_gui.py

:LOOP
echo.
echo [STATUS] Starting Batch Scan at %TIME%...

:: 2. Start the Scraper (Wait for it to finish)
:: /wait means "Don't do anything else until this is done"
start /wait "THE SCRAPER" cmd /c python scraper_v8.py

:: 3. Start the Validator (Wait for it to finish)
start /wait "THE VALIDATOR" cmd /c python validator_v6.py

echo.
echo [STATUS] Scan Complete. Resting for 5 minutes...
echo (Press CTRL+C to stop)
timeout /t 300

:: 4. RESTART THE LOOP
goto LOOP