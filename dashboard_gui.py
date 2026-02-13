# ============================================================
# AUCTION COMMAND – HYBRID INTELLIGENCE DASHBOARD
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
    conn = get_db()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# ===================== DEAL ENGINE ======================

@st.cache_data(ttl=60)
def load_historical_data():
    return run_query("""
        SELECT final_price
        FROM lots
        WHERE status='sold_history'
        AND final_price IS NOT NULL
    """)

def assign_bucket(price):
    if price <= 25:
        return "low"
    elif price <= 100:
        return "mid"
    elif price <= 500:
        return "high"
    else:
        return "premium"

historical_df = load_historical_data()

if not historical_df.empty:
    historical_df["bucket"] = historical_df["final_price"].apply(assign_bucket)
    bucket_medians = (
        historical_df.groupby("bucket")["final_price"]
        .median()
        .to_dict()
    )
else:
    bucket_medians = {}

def compute_deal_score(row):
    if not row["current_bid"]:
        return 0

    adjusted_current = row["current_bid"] * 1.15
    bucket = assign_bucket(adjusted_current)

    expected = bucket_medians.get(bucket, 0)
    if expected == 0:
        return 0

    ratio = expected / adjusted_current
    score = (ratio - 1) * 100

    return max(0, min(100, score))

# ===================== HEADER ======================

st.title("🛡️ Auction Command – Hybrid Intelligence")

metrics_df = run_query("""
    SELECT COUNT(*) as total,
           SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as active,
           SUM(CASE WHEN status='sold_history' THEN 1 ELSE 0 END) as sold
    FROM lots
""")

if not metrics_df.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Lots", int(metrics_df['total'].iloc[0] or 0))
    col2.metric("Active Lots", int(metrics_df['active'].iloc[0] or 0))
    col3.metric("Historical Sold", int(metrics_df['sold'].iloc[0] or 0))

st.divider()

# ===================== TABS ======================

tab1, tab2, tab3 = st.tabs(
    ["🎯 Active Hunt", "🏛️ Sold Archive", "📈 Metals"]
)

# ============================================================
# TAB 1 – ACTIVE HUNT
# ============================================================

with tab1:

    df = run_query("""
        SELECT *
        FROM lots
        WHERE status='pending'
        AND minutes_left > 0
        ORDER BY minutes_left ASC
        LIMIT 200
    """)

    if df.empty:
        st.info("No active auctions.")
    else:

        df["minutes_left"] = df["minutes_left"].fillna(999999)
        df["deal_score"] = df.apply(compute_deal_score, axis=1)

        # -------- Filters --------

        col1, col2, col3 = st.columns([2,1,1])

        with col1:
            search = st.text_input("Search")

        with col2:
            ending_soon = st.checkbox("🔥 < 60 min")

        with col3:
            sort_by = st.selectbox(
                "Sort",
                ["Ending Soonest", "Best Deal", "Lowest Bid"]
            )

        if search:
            df = df[df["title"].str.contains(search, case=False, na=False)]

        if ending_soon:
            df = df[df["minutes_left"] <= 60]

        if sort_by == "Ending Soonest":
            df = df.sort_values("minutes_left")
        elif sort_by == "Best Deal":
            df = df.sort_values("deal_score", ascending=False)
        elif sort_by == "Lowest Bid":
            df = df.sort_values("current_bid")

        st.caption(f"Showing {len(df)} active lots")

        show_images = st.checkbox("Show Images", value=True)

        for _, row in df.iterrows():
            with st.container(border=True):

                c1, c2, c3 = st.columns([4,2,2])

                with c1:
                    st.subheader(row["title"])
                    st.caption(f"Deal Score: {row['deal_score']:.1f}")

                with c2:
                    st.write(f"Bid: ${row['current_bid']:,.2f}")
                    st.write(f"Time: {row['time_remaining']}")

                with c3:
                    if row["deal_score"] > 50:
                        st.success("🔥 Strong Deal")
                    elif row["deal_score"] > 20:
                        st.warning("⚠️ Moderate")
                    else:
                        st.caption("Low Edge")

                if show_images and row["image_url"]:
                    st.image(row["image_url"], width=180)

                st.link_button("View Lot", row["url"])

# ============================================================
# TAB 2 – SOLD ARCHIVE
# ============================================================

with tab2:

    df_sold = run_query("""
        SELECT title, final_price, bid_count, last_seen
        FROM lots
        WHERE status='sold_history'
        ORDER BY final_price DESC
        LIMIT 200
    """)

    st.dataframe(df_sold)

# ============================================================
# TAB 3 – METALS
# ============================================================

@st.cache_data(ttl=300)
def get_live_metals():
    gold, silver = 0, 0
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

with tab3:
    gold, silver = get_live_metals()
    col1, col2 = st.columns(2)
    col1.metric("Gold", f"${gold:,.2f}")
    col2.metric("Silver", f"${silver:,.2f}")
    st.caption(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
