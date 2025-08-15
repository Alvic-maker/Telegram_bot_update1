#!/usr/bin/env python3
"""
Telegram Stock Reporter bot (ready for GitHub Actions)
- Reads BOT_TOKEN and CHAT_ID from environment variables (set them as GitHub Secrets)
- Uses yfinance by default. If vnstock is installed and you prefer, set USE_VNSTOCK=1 in env to use it.
- Sends a compact report for a list of symbols.
"""

import os
import time
from datetime import datetime, timezone, timedelta
import requests

USE_VNSTOCK = os.getenv("USE_VNSTOCK", "") not in ("", "0", "False", "false")

SYMBOLS = {
    "VN-Index": "^VNINDEX",
    "VN30": "^VN30",
    "MBB": "MBB.VN",
    "HPG": "HPG.VN",
    "SSI": "SSI.VN",
    "PVP": "PVP.VN",
    "KSB": "KSB.VN",
    "QTP": "QTP.VN"
}

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise SystemExit("Error: BOT_TOKEN and CHAT_ID must be set in environment variables. Add them as GitHub Secrets.")

SEND_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def safe_request(url, params=None, timeout=15):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        print("HTTP error:", e)
        return None

def get_with_yfinance(ticker_symbol):
    try:
        import yfinance as yf
    except Exception as e:
        print("yfinance not installed or import error:", e)
        return None

    try:
        tk = yf.Ticker(ticker_symbol)
        # request a short history: 7 days to be robust across weekends/holidays
        hist = tk.history(period='7d', auto_adjust=False)
        if hist.empty or 'Close' not in hist:
            return None
        # last available close
        last = float(hist['Close'].iloc[-1])
        prev = float(hist['Close'].iloc[-2]) if len(hist['Close']) >= 2 else last
        pct = (last / prev - 1) * 100 if prev != 0 else 0.0
        volume = int(hist['Volume'].iloc[-1]) if 'Volume' in hist and not hist['Volume'].isna().all() else None
        # optional SMA50 signal
        sma50 = None
        if 'Close' in hist and len(hist['Close']) >= 50:
            sma50 = float(hist['Close'].rolling(50).mean().iloc[-1])
        return dict(last=last, prev=prev, pct=pct, volume=volume, sma50=sma50)
    except Exception as e:
        print("yfinance fetch error for", ticker_symbol, e)
        return None

def get_with_vnstock(list_symbols):
    # vnstock price_board works per symbol list; this function attempts to return a dict of results similar to yfinance
    try:
        import vnstock as vns
    except Exception as e:
        print("vnstock not installed or import error:", e)
        return {}
    out = {}
    try:
        data = vns.price_board(list_symbols)
        # data: dict keyed by symbol with fields price, ceiling/floor, etc. Adapt as available.
        for sym in list_symbols:
            d = data.get(sym)
            if not d:
                continue
            # vnstock returns price as string sometimes; try to make float
            try:
                last = float(d.get("reference") or d.get("close") or d.get("price") or 0)
            except:
                last = None
            out[sym] = dict(last=last, prev=None, pct=None, volume=None, sma50=None)
    except Exception as e:
        print("vnstock error:", e)
    return out

def format_line(name, ticker, info):
    if not info:
        return f"{name}: — (lỗi dữ liệu)"
    last = info.get("last")
    pct = info.get("pct")
    vol = info.get("volume")
    sma50 = info.get("sma50")
    if last is None:
        return f"{name}: — (không có giá)"
    vol_s = f", KL={vol:,}" if vol not in (None, 0) else ""
    pct_s = f" ({pct:+.2f}%)" if pct is not None else ""
    sig = ""
    if sma50:
        sig = " 🔼" if last > sma50 else " 🔽"
    return f"{name}: {last:.0f}{sig}{pct_s}{vol_s}"

def build_report(symbols):
    lines = []
    lines.append("Báo cáo nhanh — " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if USE_VNSTOCK:
        # try vnstock for batch retrieval
        vn_symbols = [s.split(".")[0] for s in symbols.values() if s.endswith(".VN")]
        vn_data = get_with_vnstock(vn_symbols)
    else:
        vn_data = {}
    for name, ticker in symbols.items():
        info = None
        # prefer vnstock result for VN tickers if available
        if USE_VNSTOCK and ticker.endswith(".VN"):
            sym_key = ticker.replace(".VN","")
            info = vn_data.get(sym_key)
        if info is None:
            info = get_with_yfinance(ticker)
        lines.append(format_line(name, ticker, info))
    return "\n".join(lines)

def send_report(text):
    params = {"chat_id": CHAT_ID, "text": text}
    r = safe_request(SEND_URL, params=params)
    if r is None:
        print("Failed to send message.")
        return False
    j = r.json()
    if not j.get("ok"):
        print("Telegram API error:", j)
        return False
    return True

def main():
    report = build_report(SYMBOLS)
    print(report)
    ok = send_report(report)
    if ok:
        print("Sent to Telegram OK.")
    else:
        print("Send failed. See logs.")

if __name__ == "__main__":
    main()
