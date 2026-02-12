import streamlit as st
import sqlite3
import pandas as pd
import time
import re
import yfinance as yf
from datetime import datetime, timedelta

# --- CONFIGURATION ---
DB_NAME = "hibid_lots.db"
st.set_page_config(page_title="Auction Command V21.0", layout="wide", page_icon="⏳")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .stButton button { width: 100%; border-radius: 5px; }
    
    /* FLOATING BACK TO TOP BUTTON */
    .floating-btn {
        position: fixed; bottom: 20px; right: 20px;
        background-color: #262730; color: white;
        border: 1px solid #41444c; border-radius: 50%;
        width: 50px; height: 50px; text-align: center;
        line-height: 50px; font-size: 24px; cursor: pointer;
        z-index: 9999; text-decoration: none;
    }
    .floating-btn:hover { background-color: #41444c; }
    </style>
    <div id="top"></div>
    <a href="#top" class="floating-btn" title="Back to Top">⬆</a>
    """, unsafe_allow_html=True)

# --- TIME PARSING LOGIC (THE FIX) 🧠 ---
def parse_time_to_minutes(time_str):
    """Converts '1d 4h', '25m', etc. into total minutes for sorting."""
    if not isinstance(time_str, str): return 999999 # Push unknown to bottom
    if "Closed" in time_str or "Unknown" in time_str: return 999999
    
    total_min = 0
    # Find days
    d = re.search(r'(\d+)d', time_str)
    if d: total_min += int(d.group(1)) * 1440
    # Find hours
    h = re.search(r'(\d+)h', time_str)
    if h: total_min += int(h.group(1)) * 60
    # Find minutes
    m = re.search(r'(\d+)m', time_str)
    if m: total_min += int(m.group(1))
    # Find seconds (treat as < 1 min)
    s = re.search(r'(\d+)s', time_str)
    if s and total_min == 0: total_min = 0.5 
    
    return total_min if total_min > 0 else 999999

# --- DATABASE FUNCTIONS ---
def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def clean_dead_stock():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE lots SET status = 'archived' 
            WHERE status = 'pending' AND (
                last_seen < datetime('now', '-1 day') OR 
                time_remaining LIKE '%Closed%' OR 
                time_remaining IS NULL
            )
        """)
        c = cursor.rowcount
        conn.commit()
        conn.close()
        return c
    except: return 0

def run_query(query, params=()):
    try:
        conn = get_db()
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except: return pd.DataFrame()

def execute_command(command, params=()):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(command, params)
        conn.commit()
        conn.close()
    except Exception as e: st.error(f"DB Error: {e}")

# --- LIVE METALS ---
@st.cache_data(ttl=300)
def get_live_metals():
    gold, silver = 2650.00, 32.50
    try:
        g = yf.Ticker("GC=F").history(period="1d")
        if not g.empty: gold = g['Close'].iloc[-1]
        else:
            ge = yf.Ticker("GLD").history(period="1d")
            if not ge.empty: gold = ge['Close'].iloc[-1] * 10.8
        
        s = yf.Ticker("SI=F").history(period="1d")
        if not s.empty: silver = s['Close'].iloc[-1]
        return gold, silver
    except: return 2650.00, 32.50

# --- AUTO-CLEAN ---
cleaned = clean_dead_stock()
if cleaned > 0: st.toast(f"🧹 Cleaned {cleaned} items.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("📈 Market Data")
    gp, sp = get_live_metals()
    c1, c2 = st.columns(2)
    c1.metric("Gold", f"${gp:,.0f}")
    c2.metric("Silver", f"${sp:,.2f}")
    
    st.write("---")
    st.subheader("⚖️ Scrap Calculator")
    metal = st.radio("Type", ["Gold", "Silver"], horizontal=True)
    melt = 0.0
    if metal == "Gold":
        purity = st.selectbox("Purity", ["10k", "14k", "18k", "24k"])
        wt = st.number_input("Grams", min_value=0.0)
        k_map = {"10k":.417, "14k":.585, "18k":.750, "24k":.999}
        melt = (gp/31.1)*k_map[purity]*wt
    else:
        purity = st.selectbox("Purity", ["Sterling (.925)", "Fine (.999)"])
        wt = st.number_input("Grams", min_value=0.0)
        s_map = {"Sterling (.925)":.925, "Fine (.999)":.999}
        melt = (sp/31.1)*s_map[purity]*wt
    
    if melt>0: st.success(f"🔥 ${melt:.2f}")
    if st.button("🔄 Refresh"): st.rerun()

# --- MAIN APP ---
st.title("🛡️ Auction Command V21.0")
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Active Hunt", "📦 Inventory", "🗄️ Graveyard", "🏛️ Archives"])

# --- TAB 1: ACTIVE ---
with tab1:
    df = run_query("SELECT *, (market_value - (current_bid * 1.15) - 15) as potential_profit FROM lots WHERE status='pending'")
    
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: search = st.text_input("Search:", placeholder="Type name...")
    with c2: min_p = st.number_input("Min Profit", value=20)
    with c3: 
        sort_by = st.selectbox("Sort By", ["Ending Soonest", "Highest Profit", "Lowest Bid", "Highest Value"])
    
    if not df.empty:
        # FILTER
        if search: df = df[df['title'].str.contains(search, case=False, na=False)]
        df = df[df['potential_profit'] >= min_p]
        
        # CALCULATE MINUTES FOR SORTING
        df['minutes_left'] = df['time_remaining'].apply(parse_time_to_minutes)

        # SORTING LOGIC
        if sort_by == "Ending Soonest":
            df = df.sort_values(by='minutes_left', ascending=True)
        elif sort_by == "Highest Profit":
            df = df.sort_values(by='potential_profit', ascending=False)
        elif sort_by == "Lowest Bid":
            df = df.sort_values(by='current_bid', ascending=True)
        elif sort_by == "Highest Value":
            df = df.sort_values(by='market_value', ascending=False)

        st.caption(f"Showing {len(df)} items")
        
        for i, row in df.iterrows():
            with st.container(border=True):
                # Header
                col_a, col_b, col_c = st.columns([4, 2, 2])
                with col_a:
                    st.subheader(f"${row['potential_profit']:.0f} Profit")
                    st.write(f"**{row['title']}**")
                with col_b:
                    st.caption("Bid / eBay Avg")
                    st.write(f"**${row['current_bid']:.0f}** / ${row['market_value']:.0f}")
                with col_c:
                    # Highlight Time if Urgent
                    t_str = row['time_remaining']
                    if row['minutes_left'] < 60: # Less than 1 hour
                        st.error(f"⏳ {t_str} (HURRY!)")
                    elif row['minutes_left'] < 360: # Less than 6 hours
                        st.warning(f"⏳ {t_str}")
                    else:
                        st.caption(f"⏳ {t_str}")
                
                col_x, col_y, col_z = st.columns([2, 2, 2])
                with col_x:
                    if row['image_url']: st.image(row['image_url'], width=150)
                with col_y:
                    st.link_button("View on HiBid", row['url'])
                    if row['ref_url']: st.link_button("🔎 eBay Source", row['ref_url'])
                    else: st.caption("No Source Link")
                with col_z:
                     if st.button("✅ Won", key=f"w{row['lot_id']}"):
                         execute_command("UPDATE lots SET status='won' WHERE lot_id=?", (row['lot_id'],))
                         st.rerun()
                     if st.button("🗑️ Archive", key=f"a{row['lot_id']}"):
                         execute_command("UPDATE lots SET status='archived' WHERE lot_id=?", (row['lot_id'],))
                         st.rerun()
    else: st.info("No active items.")

# --- TAB 2: INVENTORY ---
with tab2:
    df_won = run_query("SELECT * FROM lots WHERE status='won'")
    if not df_won.empty:
        st.metric("Total Inventory Value", f"${df_won['market_value'].sum():,.2f}")
        for i, row in df_won.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([1,3,2])
                with c1: 
                    if row['image_url']: st.image(row['image_url'], width=100)
                with c2:
                    st.write(f"**{row['title']}**")
                    st.caption(f"Cost: ${row['current_bid']:.2f} | Val: ${row['market_value']:.2f}")
                with c3:
                    if st.button("Sold", key=f"s{row['lot_id']}"):
                        execute_command("UPDATE lots SET status='sold' WHERE lot_id=?", (row['lot_id'],))
                        st.rerun()
    else: st.write("Empty.")

# --- TAB 3: GRAVEYARD ---
with tab3:
    if st.button("Empty Trash"):
        execute_command("DELETE FROM lots WHERE status='archived'")
        st.rerun()
    df_arch = run_query("SELECT * FROM lots WHERE status='archived' LIMIT 50")
    st.dataframe(df_arch)

# --- TAB 4: ARCHIVES ---
with tab4:
    df_rush = run_query("SELECT * FROM lots WHERE status='sold_history' ORDER BY final_price DESC LIMIT 50")
    st.dataframe(df_rush[['title', 'final_price', 'location', 'last_seen']])