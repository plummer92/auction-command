# ============================================================
# AUCTION COMMAND DASHBOARD – INTELLIGENCE BUILD
# ============================================================

import os
import streamlit as st
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime

# ===================== CONFIG ======================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "hibid_lots.db")

st.set_page_config(
    page_title="Auction Command",
    layout="wide",
    page_icon="🛡️"
)

# ===================== DATABASE ======================

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def run_query(query, params=()):
    try:
        conn = get_db()
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database Error: {e}")
        return pd.DataFrame()

def execute_command(command, params=()):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(command, params)
    conn.commit()
    conn.close()

# ===================== MARKET DATA ======================

@st.cache_data(ttl=300)
def get_live_metals():
    gold, silver = 2650.00, 32.50
    try:
        g = yf.Ticker("GC=F").history(period="1d")
        s = yf.Ticker("SI=F").history(period="1d")
        if not g.empty:
            gold = g['Close'].iloc[-1]
        if not s.empty:
            silver = s['Close'].iloc[-1]
    except:
        pass
    return gold, silver

# ===================== HEADER ======================

st.title("🛡️ Auction Command Intelligence")

metrics_df = run_query("""
    SELECT COUNT(*) as total,
           AVG(current_bid) as avg_bid,
           MAX(last_seen) as last_scrape
    FROM lots
""")

if not metrics_df.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Lots", int(metrics_df['total'].iloc[0] or 0))
    col2.metric("Average Bid", f"${(metrics_df['avg_bid'].iloc[0] or 0):,.2f}")
    col3.metric("Last Scrape", metrics_df['last_scrape'].iloc[0] or "N/A")

st.divider()

# ===================== TABS ======================

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["🎯 Active Hunt", "📦 Inventory", "🗄️ Graveyard", "🏛️ Archives", "📈 Metals"]
)

# ============================================================
# TAB 1 — ACTIVE HUNT
# ============================================================

with tab1:

    df = run_query("""
        SELECT *,
               (market_value - (current_bid * 1.15) - 15) as potential_profit
        FROM lots
        WHERE status='pending'
    """)

    if df.empty:
        st.info("No active items.")
    else:

        # ------------- FILTERS -------------

        col1, col2, col3, col4 = st.columns([2,1,1,1])

        with col1:
            search = st.text_input("Search Title")

        with col2:
            min_profit = st.number_input("Min Profit", value=0)

        with col3:
            ending_soon = st.checkbox("🔥 < 60 min")

        with col4:
            sort_by = st.selectbox(
                "Sort",
                ["Ending Soonest", "Highest Profit", "Lowest Bid", "Highest Value"]
            )

        if search:
            df = df[df['title'].str.contains(search, case=False, na=False)]

        df['potential_profit'] = df['potential_profit'].fillna(-9999)

        if min_profit > 0:
            df = df[df['potential_profit'] >= min_profit]

        if ending_soon:
            df = df[df['minutes_left'] <= 60]

        # ------------- SORTING -------------

        if sort_by == "Ending Soonest":
            df = df.sort_values("minutes_left")
        elif sort_by == "Highest Profit":
            df = df.sort_values("potential_profit", ascending=False)
        elif sort_by == "Lowest Bid":
            df = df.sort_values("current_bid")
        elif sort_by == "Highest Value":
            df = df.sort_values("market_value", ascending=False)

        st.caption(f"Showing {len(df)} items")

        # ------------- DISPLAY -------------

        for _, row in df.iterrows():
            with st.container(border=True):

                c1, c2, c3 = st.columns([4,2,2])

                with c1:
                    st.subheader(f"${row['potential_profit']:.0f} Profit")
                    st.write(row['title'])

                    if row.get("predicted_category"):
                        st.caption(
                            f"Category: {row['predicted_category']} "
                            f"(Confidence: {round((row['confidence'] or 0)*100)}%)"
                        )

                with c2:
                    bid_display = f"${row['current_bid']:,.0f}" if row['current_bid'] else "N/A"
                    value_display = f"${row['market_value']:,.0f}" if row['market_value'] else "N/A"
                    st.write(f"{bid_display} / {value_display}")

                    if row.get("deal_score"):
                        st.metric("Deal Score", f"{row['deal_score']:.1f}%")

                with c3:
                    if row['minutes_left'] <= 60:
                        st.error(f"⏳ {row['time_remaining']}")
                    else:
                        st.caption(f"⏳ {row['time_remaining']}")

                c4, c5 = st.columns([2,2])

                with c4:
                    if row['image_url']:
                        st.image(row['image_url'], width=150)

                with c5:
                    st.link_button("View on HiBid", row['url'])
                    if row.get("ref_url"):
                        st.link_button("eBay Source", row['ref_url'])

# ============================================================
# TAB 2 — INVENTORY
# ============================================================

with tab2:
    df_won = run_query("SELECT * FROM lots WHERE status='won'")
    if df_won.empty:
        st.info("Inventory empty.")
    else:
        st.metric("Total Inventory Value", f"${df_won['market_value'].sum():,.2f}")
        st.dataframe(df_won)

# ============================================================
# TAB 3 — GRAVEYARD
# ============================================================

with tab3:
    if st.button("Empty Trash"):
        execute_command("DELETE FROM lots WHERE status='archived'")
        st.rerun()

    df_arch = run_query("SELECT * FROM lots WHERE status='archived' LIMIT 50")
    st.dataframe(df_arch)

# ============================================================
# TAB 4 — ARCHIVES
# ============================================================

with tab4:
    df_sold = run_query("""
        SELECT title, final_price, location, last_seen
        FROM lots
        WHERE status='sold_history'
        ORDER BY final_price DESC
        LIMIT 50
    """)
    st.dataframe(df_sold)

# ============================================================
# TAB 5 — METALS
# ============================================================

with tab5:
    st.header("Live Metals Market")
    gold, silver = get_live_metals()
    col1, col2 = st.columns(2)
    col1.metric("Gold (GC=F)", f"${gold:,.2f}")
    col2.metric("Silver (SI=F)", f"${silver:,.2f}")
    st.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
