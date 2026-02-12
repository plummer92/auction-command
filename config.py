# --- CREDENTIALS ---
HIBID_USERNAME = "jaredwolfe19@yahoo.com"
HIBID_PASSWORD = "Jmikel2121!"

# --- STRATEGY SETTINGS ---
DRY_RUN = True 
HARD_MAX_BID_LIMIT = 200.00 

# --- SLIDING SCALE PROFIT RULES ---
# "If Market Value is X, I demand Y profit"
# 1. Low Value Items (Under $50 value): Must make at least $15
PROFIT_MIN_LOW = 15.00  

# 2. Mid Value Items ($50 - $200 value): Must make at least $40
PROFIT_MIN_MID = 40.00

# 3. High Value Items (Over $200 value): Must make 25% margin
# (e.g., if value is $300, profit must be at least $75)
PROFIT_PERCENT_HIGH = 0.25 

# --- LOGISTICS COSTS ---
PICKUP_COST_FLAT = 0.00 
ESTIMATED_SHIPPING_COST = 15.00 

# --- FEES ---
DEFAULT_BP = 0.15 
TAX_RATE = 0.08 
EBAY_FEES = 0.13