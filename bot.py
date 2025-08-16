#!/usr/bin/env python3
# bot.py - single-file robust bot (yfinance primary, vnstock optional, scrapers fallback)
# Put this file at the repo root (replace existing bot.py). Workflow should run: python bot.py
# Requirements: yfinance, pandas, numpy, requests, beautifulsoup4, vnstock3 (optional)
# Ensure BOT_TOKEN and CHAT_ID are set in GitHub Secrets.

import os, traceback
from datetime import datetime
import requests

# small helper imports - local try/except to keep file robust if libs missing
try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
except Exception:
    yf = None
    pd = None
    np = None

try:
    from bs4 import BeautifulSoup
    import re
except Exception:
    BeautifulSoup = None
    re = None

# try vnstock (optional)
try:
    import vnstock as vnstock_mod
except Exception:
    try:
        import vnstock3 as vnstock_mod
    except Exception:
        vnstock_mod = None

BOT_TOKEN = os.getenv('BOT_TOKEN','').strip()
CHAT_ID = os.getenv('CHAT_ID','').strip()
USE_VNSTOCK = os.getenv('USE_VNSTOCK','1').lower() not in ('0','false','no','')

# Symbols to report (comma-separated in env allowed)
SYMBOLS = os.getenv('SYMBOLS','MBB,HPG,SSI,PVP,KSB,QTP').split(',')

def dbg(msg):
    # simple debug printer - avoids f-string issues in some environments
    try:
        print("[DEBUG] " + str(msg), flush=True)
    except Exception:
        try:
            print("[DEBUG]", msg, flush=True)
        except:
            pass

def fm_money_million(v):
    if v is None:
        return '—'
    try:
        return f"{v/1_000_000:,.0f} Mn"
    except Exception:
        return str(v)

def fm_shares_million(v):
    if v is None:
        return '—'
    try:
        return f"{v/1_000_000:,.2f} Mn"
    except Exception:
        return str(v)

def fm_pct(x):
    if x is None:
        return '—'
    try:
        return f"{x:+.2f}%"
    except Exception:
        return str(x)

# --- primary: yfinance per-symbol and index ---
def yf_get_symbol(symbol):
    if yf is None:
        return None
    try:
        ticker = f"{symbol}.VN"
        tk = yf.Ticker(ticker)
        hist = tk.history(period='60d', auto_adjust=False)
        if hist is None or hist.empty:
            return None
        close = hist['Close'].astype(float).dropna()
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else last
        pct = (last/prev - 1) * 100 if prev != 0 else 0.0
        vol = int(hist['Volume'].astype(float).iloc[-1]) if 'Volume' in hist else None
        avg5 = float(close.tail(5).mean()) if len(close) >= 5 else None
        avgvol20 = int(hist['Volume'].astype(float).tail(20).mean()) if 'Volume' in hist and len(hist['Volume'].dropna())>=20 else None
        sma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
        sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
        return {"source":"yfinance","symbol":symbol,"price": last,"pct": pct,"vol": vol,"avg5_price": avg5,"avg5_vol": avgvol20,"sma20": sma20,"sma50": sma50}
    except Exception as e:
        dbg("yf_get_symbol error: " + str(e))
        return None

def yf_get_index():
    if yf is None:
        return None
    try:
        tk = yf.Ticker('^VNINDEX')
        hist = tk.history(period='120d', auto_adjust=False)
        if hist is None or hist.empty:
            return None
        close = hist['Close'].astype(float).dropna()
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else last
        pct = (last/prev - 1) * 100 if prev != 0 else 0.0
        return {"source":"yfinance","price": last,"pct": pct}
    except Exception as e:
        dbg("yf_get_index error: " + str(e))
        return None

# --- vnstock foreign (best-effort) ---
def vnstock_foreign(symbol=None):
    if vnstock_mod is None:
        return None
    try:
        # try common API shapes
        if hasattr(vnstock_mod, 'stock') and hasattr(vnstock_mod.stock, 'foreign_trade'):
            func = getattr(vnstock_mod.stock, 'foreign_trade')
            if symbol:
                df = func(symbol=symbol)
            else:
                df = func()
            if hasattr(df, 'iloc'):
                row = df.iloc[-1].to_dict()
                return {"source":"vnstock","buy": row.get('buy') or row.get('buy_value') or row.get('buy_total'), "sell": row.get('sell') or row.get('sell_value') or row.get('sell_total')}
        # fallback direct function
        if hasattr(vnstock_mod, 'foreign_trade'):
            func = getattr(vnstock_mod, 'foreign_trade')
            df = func() if not symbol else func(symbol)
            if hasattr(df, 'iloc'):
                row = df.iloc[-1].to_dict()
                return {"source":"vnstock","buy": row.get('buy'), "sell": row.get('sell')}
    except Exception as e:
        dbg("vnstock_foreign error: " + str(e))
        return None
    return None

# --- scraping fallback for market-level VN-Index and foreign totals ---
def scrape_vietstock():
    if BeautifulSoup is None:
        return None
    urls = ["https://finance.vietstock.vn/ket-qua-giao-dich","https://finance.vietstock.vn/"]
    headers = {"User-Agent":"Mozilla/5.0 (compatible; Bot/1.0)"}
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            text = soup.get_text(' ', strip=True)
            # simple regex parsing
            import re as _re
            m = _re.search(r"VN[- ]?Index[:\\s]*([0-9\\.,]+)", text, _re.IGNORECASE)
            idx = None
            if m:
                try:
                    idx = float(m.group(1).replace(',', ''))
                except:
                    idx = None
            fb = fs = None
            m2 = _re.search(r"(Khối ngoại|Nước ngoài|NN).*?Mua[:\\s]*([0-9\\.,]+).*?Bán[:\\s]*([0-9\\.,]+)", text, _re.IGNORECASE)
            if m2:
                try:
                    fb = float(m2.group(2).replace(',', '')); fs = float(m2.group(3).replace(',', ''))
                except:
                    fb = fs = None
            if idx or fb or fs:
                return {"source":"vietstock","index": idx, "fbuy": fb, "fsell": fs}
        except Exception as e:
            dbg("scrape_vietstock error: " + str(e))
            continue
    return None

# Build final report string
def build_report(symbols):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = [f"📊 Báo cáo thị trường — {now}"]
    # VN-Index: try vnstock -> yfinance -> scrape
    idx = None
    try:
        if vnstock_mod is not None:
            # try vnstock index (if available)
            if hasattr(vnstock_mod, 'stock') and hasattr(vnstock_mod.stock, 'index'):
                try:
                    df = vnstock_mod.stock.index('VNINDEX', '1D', count=5)
                    if df is not None and hasattr(df, 'iloc') and 'close' in df.columns:
                        idx = {"price": float(df['close'].iloc[-1]), "pct": float(df['pct_change'].iloc[-1]) if 'pct_change' in df.columns else None}
                except Exception:
                    idx = None
    except Exception:
        idx = None
    if idx is None:
        idx = yf_get_index()
    if idx is None or idx.get('price') is None:
        scraped = scrape_vietstock() or None
        if scraped and scraped.get('index') is not None:
            idx = {"price": scraped.get('index'), "pct": None}
    if idx and idx.get('price') is not None:
        lines.append(f"📈 VN-Index: {idx['price']:.2f} {fm_pct(idx.get('pct'))} | GTGD: —")
    else:
        lines.append("📈 VN-Index: — (lỗi dữ liệu)")
    # foreign market totals
    mf = None
    try:
        if vnstock_mod is not None:
            mf = vnstock_foreign(None)
    except Exception:
        mf = None
    if mf and (mf.get('buy') is not None or mf.get('sell') is not None):
        fb = mf.get('buy'); fs = mf.get('sell'); fn = (fb or 0) - (fs or 0)
        lines.append(f"🔁 Khối ngoại (toàn TT): Mua {fm_money_million(fb)} / Bán {fm_money_million(fs)} → Ròng {fm_money_million(fn)}")
    else:
        # try scraping totals
        scraped = scrape_vietstock() if BeautifulSoup is not None else None
        if scraped and (scraped.get('fbuy') is not None or scraped.get('fsell') is not None):
            fb = scraped.get('fbuy'); fs = scraped.get('fsell'); fn = (fb or 0) - (fs or 0)
            lines.append(f"🔁 Khối ngoại (toàn TT): Mua {fm_money_million(fb)} / Bán {fm_money_million(fs)} → Ròng {fm_money_million(fn)}")
        else:
            lines.append("🔁 Khối ngoại (toàn TT): —")
    lines.append("")
    lines.append("📌 Chi tiết mã:")
    for s in symbols:
        info = yf_get_symbol(s)
        if not info or info.get('price') is None:
            lines.append(f"{s}: — (lỗi dữ liệu)")
            continue
        vol_ratio = None
        try:
            vol = info.get('vol') or 0
            avg = info.get('avg5_vol') or None
            if avg and avg > 0:
                vol_ratio = vol / avg
        except Exception:
            vol_ratio = None
        vol_ratio_s = f\" (VolRatio={vol_ratio:.2f}×)\" if vol_ratio else \"\"
        lines.append(f\"{s}: {info.get('price')} {fm_pct(info.get('pct'))} | KL={fm_shares_million(info.get('vol'))}{vol_ratio_s} | TB tuần: {info.get('avg5_price') or '—'} / {fm_shares_million(info.get('avg5_vol'))} | NN: Mua — / Bán —\")
    lines.append(\"\") 
    lines.append(\"⚠️ Alerts:\") 
    lines.append(\"\") 
    lines.append(f\"(Thời gian báo cáo: {now}) - Bot_single\") 
    return '\\n'.join(lines)

def chunk_text(s, limit=3500):
    if not s: return ['']
    if len(s) <= limit: return [s]
    parts = []
    cur = s
    while len(cur) > limit:
        cut = cur.rfind('\\n', 0, limit)
        if cut == -1:
            cut = limit
        parts.append(cur[:cut])
        cur = cur[cut:]
    if cur:
        parts.append(cur)
    return parts

def send_to_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        dbg('BOT_TOKEN/CHAT_ID missing - printing preview'); print(text); return False
    base = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    dbg("Sending message to Telegram (masked token)")
    ok = True
    for part in chunk_text(text):
        payload = {'chat_id': CHAT_ID, 'text': part, 'disable_web_page_preview': True}
        try:
            r = requests.post(base, data=payload, timeout=20)
            dbg(f"Telegram response {r.status_code}: {r.text[:300]}")
            if r.status_code != 200:
                ok = False
        except Exception as e:
            dbg("Telegram send error: " + str(e)); ok = False
    return ok

def main():
    try:
        report = build_report(SYMBOLS)
        print('=== Report preview ===')
        print(report)
        sent = send_to_telegram(report)
        dbg('Sent' if sent else 'Not sent')
    except Exception as e:
        print('Fatal error', e)
        traceback.print_exc()

if __name__ == '__main__':
    main()
