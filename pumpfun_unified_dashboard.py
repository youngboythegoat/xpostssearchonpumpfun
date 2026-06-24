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

# Get database URL from Streamlit secrets
DATABASE_URL = st.secrets["DATABASE_URL"]

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def search_coins_by_tweet(tweet_id: str) -> List[dict]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT mint, name, symbol, twitter, description, created_at
            FROM pumpfun_coins
            WHERE twitter ILIKE %s OR description ILIKE %s
            ORDER BY created_at DESC
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
st.set_page_config(page_title="Pump.fun Alpha Search", layout="wide")
st.title("🚀 Pump.fun Alpha Search (Database Mode)")
st.caption("Searching from saved coins in the database")

tweet_input = st.text_input("Paste Tweet URL or Tweet ID")

if st.button("🔍 Search in Database", type="primary", use_container_width=True):
    tweet_id = extract_tweet_id(tweet_input)
    
    if not tweet_id:
        st.error("Could not extract a valid tweet ID.")
    else:
        with st.spinner("Searching database..."):
            results = search_coins_by_tweet(tweet_id)
        
        if results:
            st.success(f"Found {len(results)} matching coin(s) in the database!")
            for coin in results:
                st.markdown(f"""
                **{coin['name']} (${coin['symbol']})**  
                Mint: `{coin['mint']}`  
                Twitter: {coin['twitter'] or 'N/A'}  
                [View on pump.fun]({coin['pump_link']})
                ---
                """)
        else:
            st.warning("No matches found in the database yet. The coin might not have been indexed or doesn't contain the tweet ID.")

st.divider()
st.caption("Database-powered search • Indexer running on Railway")
