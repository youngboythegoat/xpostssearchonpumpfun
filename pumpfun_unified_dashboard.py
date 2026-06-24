#!/usr/bin/env python3
"""
Pump.fun Unified Dashboard
- Search Existing Coins (Reverse Lookup) — with optional Birdeye for stronger results
- Monitor New Launches (Forward Monitor) — with multi-tweet + Telegram/Discord alerts

Run: streamlit run pumpfun_unified_dashboard.py
"""
import streamlit as st
import psycopg2
import re
from typing import List, Dict, Optional

DATABASE_URL = st.secrets["DATABASE_URL"]

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def search_coins_by_tweet(tweet_id: str, sort_order: str = "newest") -> List[dict]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT ON (mint) 
                mint, name, symbol, twitter, description, created_at
            FROM pumpfun_coins
            WHERE twitter ILIKE %s OR description ILIKE %s
            ORDER BY mint, created_at DESC
        """, (f"%{tweet_id}%", f"%{tweet_id}%"))
        
        rows = cur.fetchall()
        results = []
        for row in rows:
            results.append({
                "mint": row[0],
                "name": row[1],
                "symbol": row[2],
                "twitter": row[3],
                "description": row[4],
                "created_at": row[5],
                "pump_link": f"https://pump.fun/coin/{row[0]}"
            })
        
        # Sort results in Python (fixed sorting)
        reverse = True if sort_order == "newest" else False
        results.sort(key=lambda x: x["created_at"], reverse=reverse)
        
        return results
    finally:
        cur.close()
        conn.close()

def extract_tweet_id(text: str) -> Optional[str]:
    if not text:
        return None
    if text.isdigit():
        return text
    for pattern in [r"(?:x\.com|twitter\.com)/[^/]+/status/(\d+)", r"status/(\d+)"]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

# ==================== UI ====================
st.set_page_config(page_title="marv's pumpfun alpha tweet search", layout="centered")

st.title("🧵 marv's pumpfun alpha tweet search")
st.caption("Search coins linked to tweets using our indexed database")

tweet_input = st.text_input(
    "Paste Tweet URL or Tweet ID",
    placeholder="https://x.com/user/status/1234567890123456789"
)

# Sort options
sort_option = st.selectbox(
    "Sort by",
    options=["Newest first", "Oldest first"],
    index=0
)
sort_key = "newest" if sort_option == "Newest first" else "oldest"

if st.button("🔍 Search Database", type="primary", use_container_width=True):
    tweet_id = extract_tweet_id(tweet_input)
    
    if not tweet_id:
        st.error("Could not extract a valid tweet ID.")
    else:
        with st.spinner("Searching..."):
            results = search_coins_by_tweet(tweet_id, sort_key)
        
        if results:
            st.success(f"Found {len(results)} matching coin(s)")
            
            for coin in results:
                with st.container(border=True):
                    st.markdown(f"### {coin['name']} (${coin['symbol']})")
                    st.markdown(f"**Mint:** `{coin['mint']}`")
                    
                    if coin.get("twitter"):
                        st.markdown(f"**Twitter:** {coin['twitter']}")
                    
                    if coin.get("description"):
                        st.caption(coin["description"][:200])
                    
                    st.link_button("View on pump.fun", coin["pump_link"], use_container_width=True)
        else:
            st.info("No matching coins found in the database.")

st.divider()
st.caption("Built by Marv • Indexer running on Railway • Sponsored by Insomnia • Database mode")
