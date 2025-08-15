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


# ---------------------- Foreign flows (NN = Nhà đầu tư nước ngoài) ----------------------
# Best-effort extractor: tries to use `vnstock` if available; otherwise returns None.
# vnstock may provide foreign flows; different libraries/APIs use different keys.
# This code inspects returned dicts and tries to extract numeric values for buy/sell.
import math

def _extract_buy_sell_from_obj(obj):
    '''
    Try to find buy/sell numbers in a returned object/dict by searching keys that match
    english/vietnamese terms (buy/sell, mua/ban, foreign, NN, net). Returns (buy, sell) or (None,None).
    '''
    if obj is None:
        return (None, None)
    # If it's not a dict, try to convert
    data = {}
    if isinstance(obj, dict):
        data = obj
    else:
        # try to turn into dict via attributes
        try:
            data = {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}
        except Exception:
            return (None, None)
    buy = None
    sell = None
    # helper to parse a numeric from string
    def parse_num(x):
        if x is None: 
            return None
        # try direct numeric
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x)
        # remove non-numeric except dot and minus
        s2 = re.sub(r"[^\d\.\-]", "", s)
        if s2 == "" or s2 == "." or s2 == "-":
            return None
        try:
            return float(s2)
        except:
            return None

    for k, v in data.items():
        kl = k.lower()
        if any(tok in kl for tok in ("buy","mua","mua_rong","mua_net","foreignbuy","foreign_buy","nn_mua","nn_buy")) and buy is None:
            buy = parse_num(v)
        if any(tok in kl for tok in ("sell","ban","ban_rong","ban_net","foreignsell","foreign_sell","nn_ban","nn_sell")) and sell is None:
            sell = parse_num(v)
        # some APIs provide net flows directly
        if any(tok in kl for tok in ("net","ròng","mua_ròng","mua_rong")) and buy is None and sell is None:
            val = parse_num(v)
            if val is not None:
                # approximate: net positive -> buy=net, sell=0 (best-effort)
                if val >= 0:
                    buy = val
                    sell = 0.0
                else:
                    buy = 0.0
                    sell = abs(val)
    return (buy, sell)

def get_foreign_for_symbol(symbol):
    '''
    Return dict {'buy': float or None, 'sell': float or None} for a given ticker like 'MBB.VN' or 'MBB'.
    Strategy:
      1) If vnstock present, try to call common functions and inspect results.
      2) If not available, return None. You can replace this function to call an API you have.
    '''
    # try vnstock first
    try:
        import vnstock as vns
    except Exception:
        return None  # vnstock not installed — user can enable it or provide API endpoint

    # Try a few likely function names and fall back to price_board details
    candidates = []
    try:
        # some versions may have "foreign" or "fii" functions, try generically
        for fn in ("foreign", "fii", "get_foreign", "foreign_flow", "foreign_trading"):
            if hasattr(vns, fn):
                try:
                    res = getattr(vns, fn)(symbol.replace(".VN",""))
                    candidates.append(res)
                except Exception:
                    pass
        # vnstock.price_board returns summary info and may include foreign buy/sell
        if hasattr(vns, "price_board"):
            try:
                data = vns.price_board([symbol.replace(".VN","")])
                # price_board returns dict keyed by symbol
                if isinstance(data, dict):
                    candidates.append(data.get(symbol.replace(".VN","")) or data)
                else:
                    candidates.append(data)
            except Exception:
                pass
    except Exception:
        pass

    # try to extract numeric buy/sell
    for cand in candidates:
        b, s = _extract_buy_sell_from_obj(cand)
        if b is not None or s is not None:
            return {"buy": b, "sell": s}
    return None

def get_foreign_for_symbols(symbols):
    '''
    Batch utility: symbols is list of tickers like ['MBB.VN','HPG.VN',...']
    Returns mapping ticker -> {'buy':..., 'sell':...} or None
    '''
    out = {}
    for s in symbols:
        try:
            res = get_foreign_for_symbol(s)
            out[s] = res
        except Exception as e:
            out[s] = None
    return out

# ------------------- Integration into formatting -------------------
# We'll update format_line to accept optional foreign info and display it.
def format_line_with_foreign(name, ticker, info, foreign_info=None):
    base = format_line(name, ticker, info)
    if foreign_info:
        b = foreign_info.get("buy")
        s = foreign_info.get("sell")
        b_s = f"NN Mua={int(b):,}" if (b is not None) else "NN Mua=—"
        s_s = f"NN Bán={int(s):,}" if (s is not None) else "NN Bán=—"
        return f"{base} | {b_s} | {s_s}"
    return base

# To use: when building the report, call get_foreign_for_symbols for the list of tickers (with .VN suffix for vnstock).
# Example insertion into build_report (pseudo):
# vn_symbols = [t for t in symbols.values() if t.endswith('.VN')]
# foreign_map = get_foreign_for_symbols(vn_symbols)
# then for each symbol use format_line_with_foreign(..., foreign_info=foreign_map.get(ticker.replace('.VN','')))
# Note: function returns numbers in units provided by API (often shares or value); adjust formatting as needed.
