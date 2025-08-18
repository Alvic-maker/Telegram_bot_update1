
Multi-source Telegram stock bot (VN market)
------------------------------------------

Files:
- bot_multi_source.py       : orchestrator (main). Run this.
- sources/yfinance_api.py   : yfinance fetchers (primary for per-symbol).
- sources/vnstock_api.py    : vnstock wrapper (optional, for foreign flows).
- sources/scrapers.py       : scrapers for VietStock/CafeF (fallback for index/NN totals).
- normalizers.py            : normalize raw outputs.
- cache.py                  : simple TTL cache.
- requirements.txt          : dependencies.
- .github/workflows/main.yml: GitHub Actions workflow (run Mon-Fri 09:00-15:00 VN time).

Usage:
- Add secrets BOT_TOKEN and CHAT_ID to GitHub repo.
- Ensure requirements installed (via workflow or locally): pip install -r requirements.txt
- Run: python bot_multi_source.py

Notes:
- The scrapers are fragile; prefer vnstock or official data feeds for production.
- The package uses yfinance as the reliable primary source for per-symbol OHLC/volume.
