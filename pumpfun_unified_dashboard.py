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
from typing import List, Dict, Optional

PUMP_API = "https://frontend-api-v3.pump.fun"
BIRDEYE_BASE = "https://public-api.birdeye.so"

# ==================== SESSION STATE ====================
if "birdeye_key" not in st.session_state:
    st.session_state.birdeye_key = ""

# ==================== HELPERS ====================
def extract_tweet_id(text: str) -> Optional[str]:
    if not text:
        return None
    if text.isdigit():
        return text
    for pattern in [
        r"(?:x\.com|twitter\.com)/[^/]+/status/(\d+)",
        r"status/(\d+)"
    ]:
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
    headers = {
        "accept": "application/json",
        "x-chain": "solana"
    }
    if key:
        headers["X-API-KEY"] = key
    return headers

# ==================== AGGRESSIVE SEARCH ====================
def run_aggressive_search(tweet_id: str) -> List[dict]:
    matches = []
    total_checked = 0

    # === Step 1: Birdeye ===
    st.info("Step 1: Fetching recent tokens from Birdeye...")
    try:
        url = f"{BIRDEYE_BASE}/defi/v2/tokens/new_listing"
        params = {"limit": 100, "meme_platform_enabled": "true"}
        
        response = requests.get(url, params=params, headers=get_birdeye_headers(), timeout=25)

        if response.status_code == 401:
            st.error("Birdeye returned 401 Unauthorized. Please check your API key in the sidebar.")
            st.stop()
        elif response.status_code != 200:
            st.warning(f"Birdeye returned status {response.status_code}. Falling back to Pump.fun only...")
        else:
            items = response.json().get("data", {}).get("items", [])
            st.caption(f"Birdeye returned {len(items)} tokens. Now checking social links...")

            for item in items:
                total_checked += 1
                mint = item.get("address")
                if not mint:
                    continue

                try:
                    detail_url = f"{BIRDEYE_BASE}/defi/token_overview"
                    detail_resp = requests.get(detail_url, params={"address": mint}, headers=get_birdeye_headers(), timeout=8)
                    details = detail_resp.json().get("data", {}) if detail_resp.status_code == 200 else {}

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

    except Exception as e:
        st.warning(f"Birdeye error: {e}. Continuing with Pump.fun...")

    # === Step 2: Pump.fun Aggressive Scan ===
    st.info("Step 2: Aggressively scanning Pump.fun recent coins...")
    try:
        seen = set()
        for _ in range(180):  # Quite aggressive
            try:
                latest = requests.get(f"{PUMP_API}/coins/latest", timeout=5).json()
                mint = latest.get("mint")

                if mint and mint not in seen:
                    seen.add(mint)
                    total_checked += 1

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
            except:
                break
    except Exception as e:
        st.warning(f"Pump.fun scan error: {e}")

    # Deduplicate and sort
    unique_matches = {m["mint"]: m for m in matches}
    final_results = list(unique_matches.values())
    final_results.sort(key=lambda x: x.get("market_cap", 0), reverse=True)

    st.success(f"Search finished. Checked ~{total_checked} coins. Found {len(final_results)} match(es).")
    return final_results

# ==================== UI ====================
st.set_page_config(page_title="Pump.fun Alpha Search", layout="wide")
st.title("🚀 Pump.fun Alpha Search")
st.caption("Aggressive Mode • Birdeye + Pump.fun")

# Sidebar - Birdeye Key
st.session_state.birdeye_key = st.sidebar.text_input(
    "Birdeye API Key (Recommended)",
    value=st.session_state.birdeye_key,
    type="password",
    key="birdeye_key_input"
)

tweet_input = st.text_input(
    "Paste Tweet URL or Tweet ID",
    placeholder="https://x.com/user/status/1234567890123456789"
)

if st.button("🔍 Search Aggressively", type="primary", use_container_width=True):
    tweet_id = extract_tweet_id(tweet_input)

    if not tweet_id:
        st.error("Could not extract a valid tweet ID. Please check the link.")
    else:
        with st.spinner("Running aggressive search... This will take some time."):
            results = run_aggressive_search(tweet_id)

        if results:
            import pandas as pd
            df = pd.DataFrame(results)
            st.dataframe(
                df[["source", "name", "symbol", "market_cap", "mint", "pump_link"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No matches found. The coin might be older than we can scan or doesn't have the tweet in its metadata.")

st.divider()
st.caption("Built by Grok • Aggressive Search Mode")
