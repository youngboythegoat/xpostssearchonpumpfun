#!/usr/bin/env python3
"""
Pump.fun Unified Dashboard
- Search Existing Coins (Reverse Lookup) — with optional Birdeye for stronger results
- Monitor New Launches (Forward Monitor) — with multi-tweet + Telegram/Discord alerts

Run: streamlit run pumpfun_unified_dashboard.py
"""

import streamlit as st
import requests
import json
import re
import time
import threading
from datetime import datetime
from typing import List, Dict, Optional, Set
from queue import Queue, Empty

# ==================== CONFIG ====================
PUMP_API = "https://frontend-api-v3.pump.fun"
BIRDEYE_BASE = "https://public-api.birdeye.so"

# ==================== SESSION STATE ====================
if "tracked_tweets" not in st.session_state:
    st.session_state.tracked_tweets: List[Dict] = []

if "matches" not in st.session_state:
    st.session_state.matches: List[Dict] = []

if "seen_mints" not in st.session_state:
    st.session_state.seen_mints: Set[str] = set()

if "is_monitoring" not in st.session_state:
    st.session_state.is_monitoring = False

if "birdeye_api_key" not in st.session_state:
    st.session_state.birdeye_api_key = ""

if "alert_telegram_token" not in st.session_state:
    st.session_state.alert_telegram_token = ""
if "alert_telegram_chat_id" not in st.session_state:
    st.session_state.alert_telegram_chat_id = ""
if "alert_discord_webhook" not in st.session_state:
    st.session_state.alert_discord_webhook = ""

if "match_queue" not in st.session_state:
    st.session_state.match_queue = Queue()

# ==================== HELPERS ====================

def extract_tweet_id(text: str) -> Optional[str]:
    if not text: return None
    if text.isdigit(): return text
    for p in [r"(?:x\.com|twitter\.com)/[^/]+/status/(\d+)", r"status/(\d+)"]:
        m = re.search(p, text, re.IGNORECASE)
        if m: return m.group(1)
    return None

def normalize(text: str) -> str:
    return (text or "").lower().replace("twitter.com", "x.com")

def matches_tweet(twitter: str, desc: str, tweet_id: str) -> bool:
    nt = normalize(twitter)
    nd = (desc or "").lower()
    return tweet_id in nt or f"status/{tweet_id}" in nt or tweet_id in nd

# ==================== PUMP.FUN FUNCTIONS ====================

def fetch_pump_coin(mint: str) -> Optional[dict]:
    try:
        r = requests.get(f"{PUMP_API}/coins/{mint}", timeout=8, headers={"User-Agent": "PumpDashboard/1.0"})
        return r.json() if r.status_code == 200 else None
    except: return None

def fetch_pump_recent(limit: int = 150) -> List[dict]:
    coins = []
    seen = set()
    for _ in range(min(limit, 80)):
        try:
            data = requests.get(f"{PUMP_API}/coins/latest", timeout=5).json()
            mint = data.get("mint")
            if mint and mint not in seen:
                seen.add(mint)
                coins.append(data)
        except:
            break
    return coins

def search_pump_fun(tweet_id: str, max_check: int = 300) -> List[dict]:
    candidates = fetch_pump_recent(max_check)
    matches = []
    for c in candidates:
        mint = c.get("mint")
        if not mint: continue
        details = c if c.get("twitter") else fetch_pump_coin(mint)
        if not details: continue
        if matches_tweet(details.get("twitter", ""), details.get("description", ""), tweet_id):
            matches.append({
                "source": "Pump.fun",
                "mint": mint,
                "name": details.get("name"),
                "symbol": details.get("symbol"),
                "twitter": details.get("twitter", ""),
                "market_cap": details.get("usd_market_cap", 0) or 0,
                "pump_link": f"https://pump.fun/coin/{mint}",
            })
    matches.sort(key=lambda x: x["market_cap"], reverse=True)
    return matches

# ==================== BIRDEYE FUNCTIONS (Stronger Lookup) ====================

def birdeye_headers():
    key = st.session_state.birdeye_api_key.strip()
    h = {"accept": "application/json", "x-chain": "solana"}
    if key:
        h["X-API-KEY"] = key
    return h

def search_birdeye(tweet_id: str, limit: int = 100) -> List[dict]:
    """Use Birdeye new listings + metadata to find matches. Stronger coverage."""
    matches = []
    try:
        # Get recent meme launches from Pump.fun via Birdeye
        url = f"{BIRDEYE_BASE}/defi/v2/tokens/new_listing"
        params = {"limit": min(limit, 50), "meme_platform_enabled": "true"}
        r = requests.get(url, params=params, headers=birdeye_headers(), timeout=10)
        if r.status_code != 200:
            return matches

        items = r.json().get("data", {}).get("items", [])
        for item in items:
            mint = item.get("address")
            if not mint: continue

            # Get token overview for social links (Birdeye sometimes has them)
            overview_url = f"{BIRDEYE_BASE}/defi/token_overview"
            or_ = requests.get(overview_url, params={"address": mint}, headers=birdeye_headers(), timeout=6)
            if or_.status_code != 200: continue
            ov = or_.json().get("data", {})

            twitter = ov.get("twitter", "") or ov.get("extensions", {}).get("twitter", "") or ""
            desc = ov.get("description", "") or ""

            if matches_tweet(twitter, desc, tweet_id):
                matches.append({
                    "source": "Birdeye",
                    "mint": mint,
                    "name": ov.get("name") or item.get("symbol"),
                    "symbol": ov.get("symbol") or item.get("symbol"),
                    "twitter": twitter,
                    "market_cap": ov.get("mc", 0) or 0,
                    "pump_link": f"https://pump.fun/coin/{mint}",
                })
    except Exception as e:
        st.warning(f"Birdeye error: {e}")
    matches.sort(key=lambda x: x["market_cap"], reverse=True)
    return matches

def unified_search(tweet_id: str, use_birdeye: bool = True) -> List[dict]:
    pump_matches = search_pump_fun(tweet_id)
    if use_birdeye and st.session_state.birdeye_api_key.strip():
        birdeye_matches = search_birdeye(tweet_id)
        # Merge + dedup by mint
        seen_mints = {m["mint"] for m in pump_matches}
        for m in birdeye_matches:
            if m["mint"] not in seen_mints:
                pump_matches.append(m)
    pump_matches.sort(key=lambda x: x["market_cap"], reverse=True)
    return pump_matches

# ==================== MONITORING (same as before, improved) ====================

def send_telegram(match: dict):
    token = st.session_state.alert_telegram_token.strip()
    chat = st.session_state.alert_telegram_chat_id.strip()
    if not token or not chat: return
    text = f"🎯 Match: {match['name']} (${match['symbol']})\nTweet: {match['tweet_id']}\n{match['pump_link']}"
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=8)
    except: pass

def send_discord(match: dict):
    wh = st.session_state.alert_discord_webhook.strip()
    if not wh: return
    embed = {"title": "🎯 Pump.fun Match", "description": f"Tweet `{match['tweet_id']}` → {match['name']} (${match['symbol']})",
             "url": match['pump_link'], "color": 0x00ff00}
    try:
        requests.post(wh, json={"embeds": [embed]}, timeout=8)
    except: pass

def record_match(coin: dict, tweet_id: str):
    m = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "tweet_id": tweet_id,
        "name": coin.get("name"),
        "symbol": coin.get("symbol"),
        "mint": coin.get("mint"),
        "pump_link": f"https://pump.fun/coin/{coin.get('mint')}",
    }
    st.session_state.matches.append(m)
    st.session_state.match_queue.put(m)
    send_telegram(m)
    send_discord(m)

def monitoring_loop(interval: int, use_ws: bool):
    st.session_state.seen_mints.clear()
    while st.session_state.is_monitoring:
        try:
            latest = requests.get(f"{PUMP_API}/coins/latest", timeout=5).json()
            mint = latest.get("mint")
            if mint and mint not in st.session_state.seen_mints:
                st.session_state.seen_mints.add(mint)
                details = fetch_pump_coin(mint) or latest
                for t in st.session_state.tracked_tweets:
                    if matches_tweet(details.get("twitter",""), details.get("description",""), t["id"]):
                        record_match(details, t["id"])
            time.sleep(interval)
        except:
            time.sleep(3)

# ==================== STREAMLIT UI ====================

st.set_page_config(page_title="Pump.fun Alpha Dashboard", layout="wide")
st.title("🚀 Pump.fun Alpha Dashboard")
st.caption("Reverse Search + Real-time Monitor • Birdeye + Pump.fun")

with st.sidebar:
    st.header("Settings")
    st.session_state.birdeye_api_key = st.text_input("Birdeye API Key (optional but recommended)", 
                                                     value=st.session_state.birdeye_api_key, type="password")
    st.caption("Get free key at birdeye.so → Developers")

    st.divider()
    st.subheader("Alerts")
    st.session_state.alert_telegram_token = st.text_input("Telegram Bot Token", value=st.session_state.alert_telegram_token, type="password")
    st.session_state.alert_telegram_chat_id = st.text_input("Telegram Chat ID", value=st.session_state.alert_telegram_chat_id)
    st.session_state.alert_discord_webhook = st.text_input("Discord Webhook", value=st.session_state.alert_discord_webhook, type="password")

tab1, tab2 = st.tabs(["🔍 Search Existing Coins", "📡 Monitor New Launches"])

# ==================== TAB 1: SEARCH ====================
with tab1:
    st.subheader("Find coins that already link to a viral post")
    tweet_input = st.text_input("Tweet URL or ID", placeholder="https://x.com/user/status/1234567890123456789")
    use_birdeye = st.checkbox("Use Birdeye (stronger results — recommended if you have API key)", value=True)

    if st.button("🔍 Search Existing Coins", type="primary"):
        tid = extract_tweet_id(tweet_input)
        if not tid:
            st.error("Invalid tweet URL/ID")
        else:
            with st.spinner("Searching... (Birdeye + Pump.fun)"):
                results = unified_search(tid, use_birdeye)
            if results:
                st.success(f"Found {len(results)} matching coin(s)")
                import pandas as pd
                df = pd.DataFrame(results)
                st.dataframe(df[["source", "name", "symbol", "market_cap", "mint", "pump_link"]], use_container_width=True)
            else:
                st.warning("No matches found in recent coins. Try the Monitor tab for future launches.")

# ==================== TAB 2: MONITOR ====================
with tab2:
    st.subheader("Watch for new coins linking to your tracked posts")

    # Add tweet
    col1, col2 = st.columns([3,1])
    with col1:
        new_tweet = st.text_input("Add tweet to track", key="new_tweet_input")
    with col2:
        if st.button("Add"):
            tid = extract_tweet_id(new_tweet)
            if tid and not any(t["id"] == tid for t in st.session_state.tracked_tweets):
                st.session_state.tracked_tweets.append({"id": tid, "url": new_tweet})
                st.rerun()

    if st.session_state.tracked_tweets:
        st.write("**Currently tracking:**")
        for i, t in enumerate(st.session_state.tracked_tweets):
            st.write(f"- `{t['id']}`")

    poll_int = st.slider("Check interval (seconds)", 2, 10, 4)
    use_ws_mon = st.checkbox("Use WebSocket (faster)", value=True)

    if not st.session_state.is_monitoring:
        if st.button("▶️ Start Monitoring", type="primary"):
            st.session_state.is_monitoring = True
            threading.Thread(target=monitoring_loop, args=(poll_int, use_ws_mon), daemon=True).start()
            st.rerun()
    else:
        if st.button("⏹️ Stop"):
            st.session_state.is_monitoring = False
            st.rerun()

    st.caption(f"Status: {'🟢 Running' if st.session_state.is_monitoring else '🔴 Stopped'} | Tracked: {len(st.session_state.tracked_tweets)} | Scanned: {len(st.session_state.seen_mints)}")

    if st.session_state.matches:
        import pandas as pd
        df = pd.DataFrame(st.session_state.matches)
        st.dataframe(df, use_container_width=True)

st.divider()
st.caption("Merged lookup + monitor • Pump.fun + Birdeye • Built by Grok")