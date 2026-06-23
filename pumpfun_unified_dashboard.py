#!/usr/bin/env python3
"""
Pump.fun Unified Dashboard
- Search Existing Coins (Reverse Lookup) — with optional Birdeye for stronger results
- Monitor New Launches (Forward Monitor) — with multi-tweet + Telegram/Discord alerts

Run: streamlit run pumpfun_unified_dashboard.py
"""
import streamlit as st
import requests
import re
import time
from typing import List, Dict, Optional

PUMP_API = "https://frontend-api-v3.pump.fun"
BIRDEYE_BASE = "https://public-api.birdeye.so"

if "birdeye_key" not in st.session_state:
    st.session_state.birdeye_key = ""

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

def normalize(text: str) -> str:
    return (text or "").lower().replace("twitter.com", "x.com")

def matches_tweet(twitter: str, description: str, tweet_id: str) -> bool:
    nt = normalize(twitter)
    nd = (description or "").lower()
    return tweet_id in nt or f"status/{tweet_id}" in nt or tweet_id in nd

def get_birdeye_headers():
    key = st.session_state.birdeye_key.strip()
    headers = {"accept": "application/json", "x-chain": "solana"}
    if key:
        headers["X-API-KEY"] = key
    return headers

def aggressive_search(tweet_id: str) -> List[dict]:
    matches = []
    total_checked = 0

    # === BIRDEYE ===
    st.info("Step 1/2: Trying Birdeye (more data)...")
    try:
        url = f"{BIRDEYE_BASE}/defi/v2/tokens/new_listing"
        # Try with boolean True instead of string
        params = {"limit": 80, "meme_platform_enabled": True}
        
        r = requests.get(url, params=params, headers=get_birdeye_headers(), timeout=20)
        
        if r.status_code == 200:
            items = r.json().get("data", {}).get("items", [])
            st.caption(f"Birdeye returned {len(items)} tokens. Checking socials...")

            for item in items:
                total_checked += 1
                mint = item.get("address")
                if not mint:
                    continue

                try:
                    detail_r = requests.get(
                        f"{BIRDEYE_BASE}/defi/token_overview",
                        params={"address": mint},
                        headers=get_birdeye_headers(),
                        timeout=6
                    )
                    details = detail_r.json().get("data", {}) if detail_r.status_code == 200 else {}

                    twitter = details.get("twitter", "") or details.get("extensions", {}).get("twitter", "") or ""
                    desc = details.get("description", "") or ""

                    if matches_tweet(twitter, desc, tweet_id):
                        matches.append({
                            "source": "Birdeye",
                            "mint": mint,
                            "name": details.get("name") or item.get("symbol", "Unknown"),
                            "symbol": details.get("symbol") or item.get("symbol", "???"),
                            "twitter": twitter,
                            "market_cap": details.get("mc", 0),
                            "pump_link": f"https://pump.fun/coin/{mint}",
                        })
                except:
                    continue
        else:
            st.warning(f"Birdeye returned status {r.status_code}. Using Pump.fun only...")

    except Exception as e:
        st.warning(f"Birdeye failed: {e}. Using Pump.fun only...")

    # === PUMP.FUN (Aggressive) ===
    st.info("Step 2/2: Aggressively scanning Pump.fun (this will take time)...")
    
    try:
        seen = set()
        progress = st.empty()

        for i in range(250):  # Very aggressive
            try:
                latest = requests.get(f"{PUMP_API}/coins/latest", timeout=5).json()
                mint = latest.get("mint")

                if mint and mint not in seen:
                    seen.add(mint)
                    total_checked += 1

                    if total_checked % 30 == 0:
                        progress.caption(f"Checked {total_checked} coins so far...")

                    details = requests.get(f"{PUMP_API}/coins/{mint}", timeout=6).json()

                    if matches_tweet(details.get("twitter", ""), details.get("description", ""), tweet_id):
                        matches.append({
                            "source": "Pump.fun",
                            "mint": mint,
                            "name": details.get("name"),
                            "symbol": details.get("symbol"),
                            "twitter": details.get("twitter", ""),
                            "market_cap": details.get("usd_market_cap", 0),
                            "pump_link": f"https://pump.fun/coin/{mint}",
                        })

                time.sleep(0.08)  # Small delay to be nice to the API

            except:
                time.sleep(0.2)
                continue

    except Exception as e:
        st.warning(f"Pump.fun scanning error: {e}")

    # Final results
    unique = {m["mint"]: m for m in matches}
    final = list(unique.values())
    final.sort(key=lambda x: x.get("market_cap", 0), reverse=True)

    st.success(f"Search finished. Checked ~{total_checked} coins. Found {len(final)} match(es).")
    return final

# ==================== UI ====================
st.set_page_config(page_title="Pump.fun Alpha Search", layout="wide")
st.title("🚀 Pump.fun Alpha Search")
st.caption("Aggressive Mode • Birdeye + Pump.fun")

st.session_state.birdeye_key = st.sidebar.text_input(
    "Birdeye API Key (Recommended)",
    value=st.session_state.birdeye_key,
    type="password",
    key="birdeye_input"
)

tweet_input = st.text_input("Paste Tweet URL or Tweet ID")

if st.button("🔍 Search Aggressively", type="primary", use_container_width=True):
    tid = extract_tweet_id(tweet_input)
    if not tid:
        st.error("Invalid tweet URL or ID")
    else:
        with st.spinner("Running deep aggressive search... Please wait."):
            results = aggressive_search(tid)

        if results:
            import pandas as pd
            df = pd.DataFrame(results)
            st.dataframe(df[["source", "name", "symbol", "market_cap", "mint", "pump_link"]], 
                        use_container_width=True, hide_index=True)
        else:
            st.warning("No matches found after deep scan.")
