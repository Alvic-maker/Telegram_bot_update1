#!/usr/bin/env python3
# bot.py - Telegram stock reporter (updated)
# Copy this file to replace your current bot.py

import os
import re
import math
import time
from datetime import datetime, timedelta
import requests

# Third-party libs
import pandas as pd
import numpy as np
import yfinance as yf

USE_VNSTOCK = os.getenv("USE_VNSTOCK", "") not in ("", "0", "False", "false")

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise SystemExit("Error: BOT_TOKEN and CHAT_ID must be set as environment variables.")

SEND_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# === Your watchlist / test symbols ===
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

# ---------------- Utility HTTP ----------------
def safe_request(url, params=None, timeout=15):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        print("HTTP error:", e)
        return None

# ---------------- Indicators helper ----------------
def indicators_from_df(df):
    """
    Input: df with columns ['Open','High','Low','Close','Volume'] indexed by datetime (oldest..newest)
    Returns dict with last, prev, pct, sma20/50/200, rsi14, macd, macd_signal, avgvol20, vol, vol_ratio, atr14
    """
    out = {}
    if df is None or df.empty or 'Close' not in df:
        return out
    close = df['Close'].astype(float).dropna()
    if close.empty:
        return out

    out['last'] = float(close.iloc[-1])
    out['prev'] = float(close.iloc[-2]) if len(close) >= 2 else out['last']
    out['pct'] = (out['last'] / out['prev'] - 1) * 100 if out['prev'] != 0 else 0.0

    # SMAs
    for n in (20, 50, 200):
        if len(close) >= n:
            out[f'sma{n}'] = float(close.rolling(n).mean().iloc[-1])
        else:
            out[f'sma{n}'] = None

    # RSI14 (EWMA-style)
    if len(close) >= 15:
        delta = close.diff().dropna()
        ups = delta.clip(lower=0)
        downs = -delta.clip(upper=0)
        roll_up = ups.ewm(alpha=1/14, adjust=False).mean()
        roll_down = downs.ewm(alpha=1/14, adjust=False).mean()
        if roll_down.iloc[-1] == 0:
            rs = float('inf')
            out['rsi14'] = 100.0
        else:
            rs = roll_up.iloc[-1] / roll_down.iloc[-1]
            out['rsi14'] = 100 - (100 / (1 + rs))
    else:
        out['rsi14'] = None

    # MACD (12,26,9)
    if len(close) >= 26:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        out['macd'] = float(macd.iloc[-1])
        out['macd_signal'] = float(signal.iloc[-1])
    else:
        out['macd'] = out['macd_signal'] = None

    # AvgVol20 and vol ratio
    if 'Volume' in df and len(df['Volume'].dropna()) >= 20:
        vol = df['Volume'].astype(float).fillna(0)
        out['avgvol20'] = int(vol.rolling(20).mean().iloc[-1])
        out['vol'] = int(vol.iloc[-1])
        out['vol_ratio'] = (out['vol'] / out['avgvol20']) if out['avgvol20'] and out['avgvol20'] > 0 else None
    else:
        out['avgvol20'] = out['vol'] = out['vol_ratio'] = None

    # ATR14
    if len(df) >= 15 and {'High','Low','Close'}.issubset(df.columns):
        high = df['High'].astype(float)
        low = df['Low'].astype(float)
        close_shift = df['Close'].astype(float).shift(1)
        tr1 = high - low
        tr2 = (high - close_shift).abs()
        tr3 = (low - close_shift).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).dropna()
        if len(tr) >= 14:
            out['atr14'] = float(tr.rolling(14).mean().iloc[-1])
        else:
            out['atr14'] = None
    else:
        out['atr14'] = None

    return out

# ---------------- yfinance symbol fetch ----------------
def get_with_yfinance(ticker_symbol, period='365d'):
    try:
        tk = yf.Ticker(ticker_symbol)
        # get enough days for SMA200/52w
        hist = tk.history(period=period, auto_adjust=False)
        if hist is None or hist.empty:
            print(f"yfinance empty for {ticker_symbol}")
            return None
        info = indicators_from_df(hist)
        # add some raw metadata
        info['history_rows'] = len(hist)
        # include name if available
        try:
            info['name'] = tk.info.get('shortName') if hasattr(tk, 'info') else None
        except Exception:
            info['name'] = None
        return info
    except Exception as e:
        print("yfinance fetch error for", ticker_symbol, e)
        return None

# ---------------- Foreign flows (best-effort via vnstock) ----------------
def _extract_buy_sell_from_obj(obj):
    """Try to parse common buy/sell keys from an object/dict returned by vnstock or similar"""
    if obj is None:
        return (None, None)
    # unify to dict
    if isinstance(obj, dict):
        data = obj
    else:
        try:
            data = {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}
        except Exception:
            return (None, None)
    buy = None
    sell = None
    def parse_num(x):
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x)
        s2 = re.sub(r"[^\d\.\-]", "", s)
        if s2 in ("", ".", "-"):
            return None
        try:
            return float(s2)
        except:
            return None
    for k, v in data.items():
        kl = str(k).lower()
        if any(tok in kl for tok in ("buy","mua","foreignbuy","nn_mua","f_buy","muarong","mua_rong","mua_ròng")) and buy is None:
            buy = parse_num(v)
        if any(tok in kl for tok in ("sell","ban","foreignsell","nn_ban","f_sell","banrong","ban_rong","ban_ròng")) and sell is None:
            sell = parse_num(v)
        # net flows
        if any(tok in kl for tok in ("net","ròng","rong","muanet","ban_net")) and (buy is None and sell is None):
            val = parse_num(v)
            if val is not None:
                if val >= 0:
                    buy = val; sell = 0.0
                else:
                    buy = 0.0; sell = abs(val)
    return (buy, sell)

def get_foreign_for_symbol(symbol):
    """
    Best-effort attempt to fetch foreign buy/sell info for a single symbol.
    Returns dict {'buy':float or None, 'sell':float or None} or None.
    """
    try:
        import vnstock as vns
    except Exception:
        return None

    sym = symbol.replace('.VN','')
    candidates = []
    # try common functions
    for fn in ("foreign", "fii", "get_foreign", "foreign_flow", "foreign_trading", "fii_trading"):
        if hasattr(vns, fn):
            try:
                candidates.append(getattr(vns, fn)(sym))
            except Exception:
                pass
    # try price_board
    if hasattr(vns, "price_board"):
        try:
            pb = vns.price_board([sym])
            if isinstance(pb, dict):
                candidates.append(pb.get(sym) or pb)
            else:
                candidates.append(pb)
        except Exception:
            pass

    for cand in candidates:
        b, s = _extract_buy_sell_from_obj(cand)
        if b is not None or s is not None:
            return {"buy": b, "sell": s}
    return None

def get_foreign_for_symbols(symbols):
    out = {}
    for s in symbols:
        try:
            out[s] = get_foreign_for_symbol(s)
        except Exception as e:
            out[s] = None
    return out

# ---------------- Formatting ----------------
def format_line_with_foreign(name, ticker, info, foreign_info=None):
    if not info:
        base = f"{name}: — (lỗi dữ liệu)"
    else:
        last = info.get('last')
        pct = info.get('pct')
        vol = info.get('vol')
        vol_ratio = info.get('vol_ratio')
        sig = ""
        if info.get('sma50') and last:
            sig = " 🔼" if last > info.get('sma50') else " 🔽"
        vol_s = f", KL={vol:,}" if vol not in (None, 0, None) else ""
        if pct is not None:
            base = f"{name}: {last:,.0f}{sig} ({pct:+.2f}%)" + vol_s
        else:
            base = f"{name}: {last:,.0f}{sig}" + vol_s

    if foreign_info:
        b = foreign_info.get("buy")
        s = foreign_info.get("sell")
        # show as integer if large, else raw
        def fmt_num(x):
            if x is None:
                return "—"
            try:
                xi = int(x)
                return f"{xi:,}"
            except:
                return str(x)
        return f"{base} | NN Mua={fmt_num(b)} | NN Bán={fmt_num(s)}"
    return base

# ---------------- VN-Index block ----------------
def get_index_info(index_ticker="^VNINDEX", vn30_tickers=None):
    try:
        tk = yf.Ticker(index_ticker)
        hist = tk.history(period='365d', auto_adjust=False)
        if hist is None or hist.empty:
            print("VN-Index history empty")
            return None
        info = indicators_from_df(hist)
        # pct vs month start
        try:
            now = datetime.utcnow()
            month_start = datetime(now.year, now.month, 1)
            hist_month = tk.history(start=month_start.strftime("%Y-%m-%d"), end=(now + timedelta(days=1)).strftime("%Y-%m-%d"))
            if hist_month is not None and not hist_month.empty:
                month_open = float(hist_month['Open'].iloc[0])
                info['pct_vs_month_start'] = (info['last'] / month_open - 1) * 100 if month_open != 0 else None
            else:
                info['pct_vs_month_start'] = None
        except Exception:
            info['pct_vs_month_start'] = None

        # 52w high/low
        last_52 = hist.tail(252) if len(hist) >= 252 else hist
        info['52w_high'] = float(last_52['High'].max())
        info['52w_low']  = float(last_52['Low'].min())
    except Exception as e:
        print("Error fetching index:", e)
        return None

    # breadth & top contributors if vn30 tickers provided
    if vn30_tickers:
        adv = dec = neu = 0
        contribs = []
        for t in vn30_tickers:
            try:
                tk = yf.Ticker(t)
                h = tk.history(period='7d', auto_adjust=False)
                if h is None or h.empty:
                    continue
