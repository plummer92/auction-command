import sqlite3
import os
import time

print("--- DATABASE RESET TOOL ---")

# 1. Try to connect and wipe table
try:
    print("Attempting to wipe data...")
    conn = sqlite3.connect("hibid_lots.db")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS lots")
    conn.commit()
    conn.close()
    print("✅ SUCCESS: Old data wiped. Table deleted.")
    
except Exception as e:
    print(f"❌ Could not wipe data: {e}")
    print("Trying to force close Python processes...")
    # Force kill any stuck python tasks
    os.system("taskkill /f /im python.exe")
    print("Python processes killed. Try running this script again.")

print("---------------------------")
print("You can now run 'run_247.bat' for a fresh start.")
time.sleep(5)