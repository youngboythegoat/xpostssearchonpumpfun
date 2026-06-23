# Pump.fun Unified Alpha Dashboard

One tool that does **both** things you need:

1. **Search Existing Coins** — Paste a viral post → find coins that *already* link to it (reverse lookup)
2. **Monitor New Launches** — Track multiple posts and get alerts the moment a matching coin launches

Includes **Birdeye API** support for much stronger search results.

## Quick Start

```bash
pip install -r requirements_unified.txt
streamlit run pumpfun_unified_dashboard.py
```

## Features

### Tab 1: Search Existing Coins (Lookup)
- Paste any X post
- Uses **Pump.fun API** + **Birdeye** (if you add free API key)
- Returns matching coins sorted by market cap
- Much better coverage than Pump.fun alone

### Tab 2: Monitor New Launches
- Add multiple tweets to track
- Real-time or polling mode
- Telegram + Discord instant alerts when a match appears
- Live matches table

## Birdeye API Key (Recommended)

1. Go to [birdeye.so](https://birdeye.so) → Developers
2. Get free API key
3. Paste it in the sidebar

This dramatically improves the "Search Existing Coins" results.

## Files

- `pumpfun_unified_dashboard.py` — The full merged tool
- `requirements_unified.txt`

Enjoy the alpha. This is now the complete version of what you originally wanted.
