#!/usr/bin/env python3
# bot.py - single-file robust bot (fixed quotes)
import os, traceback
from datetime import datetime
import requests

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
except Exception:
    BeautifulSoup = None

try:
    import vnstock as vnstock_mod
except Exception:
    try:
        import vnstock3 as vnstock_mod
    except Exception:
        vnstock_mod = None

BOT_TOKEN = os.getenv('BOT_TOKEN','').strip()
CHAT_ID = os.getenv('CHAT_ID','').strip()
SYMBOLS = os.getenv('SYMBOLS','MBB,HPG,SSI,PVP,KSB,QTP').split(',')

def dbg(msg):
    try: print("[DEBUG]", msg, flush=True)
    except: pass

def fm_money_million(v):
    try: return f"{v/1_000_000:,.0f} Mn" if v is not None else "—"
    except: return str(v)

def fm_shares_million(v):
    try: return f"{v/1_000_000:,.2f} Mn" if v is not None else "—"
    except: return str(v)

def fm_pct(x):
    try: return f"{x:+.2f}%" if x is not None else "—"
    except: return str(x)

def yf_get_symbol(symbol):
    if yf is None: return None
    try:
        tk = yf.Ticker(f"{symbol}.VN")
        hist = tk.history(period='60d')
        if hist.empty: return None
        close = hist['Close'].astype(float).dropna()
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close)>=2 else last
        pct = (last/prev - 1) * 100 if prev else 0
        vol = int(hist['Volume'].iloc[-1]) if 'Volume' in hist else None
        avg5 = float(close.tail(5).mean()) if len(close)>=5 else None
        avgvol20 = int(hist['Volume'].tail(20).mean()) if 'Volume' in hist else None
        sma20 = float(close.rolling(20).mean().iloc[-1]) if len(close)>=20 else None
        sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close)>=50 else None
        return {"symbol":symbol,"price":last,"pct":pct,"vol":vol,"avg5_price":avg5,"avg5_vol":avgvol20,"sma20":sma20,"sma50":sma50}
    except Exception as e:
        dbg(f"yf_get_symbol error {symbol}: {e}"); return None

def yf_get_index():
    if yf is None: return None
    try:
        tk = yf.Ticker('^VNINDEX')
        hist = tk.history(period='120d')
        if hist.empty: return None
        close = hist['Close'].astype(float).dropna()
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close)>=2 else last
        pct = (last/prev - 1) * 100 if prev else 0
        return {"price":last,"pct":pct}
    except Exception as e:
        dbg("yf_get_index error: "+str(e)); return None

def build_report(symbols):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines=[f"📊 Báo cáo thị trường — {now}"]
    idx=yf_get_index()
    if idx: lines.append(f"📈 VN-Index: {idx['price']:.2f} {fm_pct(idx.get('pct'))}")
    else: lines.append("📈 VN-Index: — (lỗi dữ liệu)")
    lines.append("")
    lines.append("📌 Chi tiết mã:")
    for s in symbols:
        info=yf_get_symbol(s)
        if not info: 
            lines.append(f"{s}: — (lỗi dữ liệu)"); continue
        vol_ratio=None
        if info.get('vol') and info.get('avg5_vol'):
            try: vol_ratio=info['vol']/info['avg5_vol']
            except: pass
        vol_ratio_s=f" (VolRatio={vol_ratio:.2f}×)" if vol_ratio else ""
        lines.append(f"{s}: {info['price']:.0f} {fm_pct(info['pct'])} | KL={fm_shares_million(info['vol'])}{vol_ratio_s} | TB tuần: {info.get('avg5_price') or '—'} / {fm_shares_million(info.get('avg5_vol'))}")
    lines.append("")
    lines.append("⚠️ Alerts:")
    lines.append("")
    lines.append(f"(Thời gian báo cáo: {now}) - Bot_fixed")
    return "\n".join(lines)

def send_to_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID"); print(text); return False
    url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    ok=True
    for part in [text]:
        try:
            r=requests.post(url,data={"chat_id":CHAT_ID,"text":part})
            dbg(f"Telegram response {r.status_code}: {r.text[:200]}")
            if r.status_code!=200: ok=False
        except Exception as e:
            dbg("Telegram error: "+str(e)); ok=False
    return ok

def main():
    report=build_report(SYMBOLS)
    print("=== Report preview ==="); print(report)
    send_to_telegram(report)

if __name__=="__main__": main()
