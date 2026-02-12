import time
import random
import datetime

# CONFIGURATION: How long to wait between scans (in minutes)
MIN_MINUTES = 1
MAX_MINUTES = 3

def smart_sleep():
    # Calculate a random wait time to look human
    wait_seconds = random.randint(MIN_MINUTES * 60, MAX_MINUTES * 60)
    
    # Calculate when the next run will happen
    now = datetime.datetime.now()
    next_run = now + datetime.timedelta(seconds=wait_seconds)
    
    print(f"[-] Scan complete. Sleeping for {wait_seconds // 60} minutes...")
    print(f"[-] Next scan scheduled for: {next_run.strftime('%I:%M:%S %p')}")
    
    # The actual pause
    time.sleep(wait_seconds)

if __name__ == "__main__":
    smart_sleep()