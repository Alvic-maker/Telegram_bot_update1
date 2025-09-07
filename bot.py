#!/usr/bin/env python3
<<<<<<< HEAD
# bot.py - stock reporter (uses yfinance) with VN timezone-aware timestamps and clean formatting
import os, traceback
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
=======
# bot.py - single-file robust bot (fixed quotes)
import os, traceback
from datetime import datetime
>>>>>>> parent of 6f7af73 (trước chạy được, cấu hình lại timezone)
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

<<<<<<< HEAD
# symbols to report (CSV string or env SECRET)
SYMBOLS = [s.strip().upper() for s in os.getenv("SYMBOLS", "MBB,HPG,SSI,PVP,KSB,QTP").split(",") if s.strip()]

def now_vn_str():
    if ZoneInfo is not None:
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    else:
        # fallback: assume system tz is UTC and add 7 hours
        now = datetime.utcnow() + timedelta(hours=7)
    return now.strftime("%Y-%m-%d %H:%M:%S")
=======
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
>>>>>>> parent of 6f7af73 (trước chạy được, cấu hình lại timezone)

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
<<<<<<< HEAD
        prev = float(close.iloc[-2]) if len(close) >= 2 else last
        pct = (last/prev - 1) * 100 if prev != 0 else 0.0
        vol = int(hist['Volume'].astype(float).iloc[-1]) if 'Volume' in hist and len(hist['Volume'].dropna())>0 else None
        avg5_price = float(close.tail(5).mean()) if len(close) >= 5 else None
        avgvol20 = int(hist['Volume'].astype(float).tail(20).mean()) if 'Volume' in hist and len(hist['Volume'].dropna())>=20 else None
        return {"source":"yfinance","symbol":sym,"price": last,"pct": pct,"vol": vol,"avg5_price": avg5_price,"avg5_vol": avgvol20}
    except Exception as e:
        print("fetch_symbol_yf error", sym, e)
        return None
=======
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
>>>>>>> parent of 6f7af73 (trước chạy được, cấu hình lại timezone)

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
<<<<<<< HEAD
    now = now_vn_str()
    lines = []
    lines.append(f"📊 Báo cáo thị trường — {now}")
    # VN-Index attempt via yfinance
    idx = fetch_index_yf()
    if idx and idx.get("price") is not None:
        lines.append(f"📈 VN-Index: {idx['price']:.2f} {fm_pct(idx.get('pct'))} (src={idx.get('source')})")
    else:
        lines.append("📈 VN-Index: — (lỗi dữ liệu)")
=======
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines=[f"📊 Báo cáo thị trường — {now}"]
    idx=yf_get_index()
    if idx: lines.append(f"📈 VN-Index: {idx['price']:.2f} {fm_pct(idx.get('pct'))}")
    else: lines.append("📈 VN-Index: — (lỗi dữ liệu)")
>>>>>>> parent of 6f7af73 (trước chạy được, cấu hình lại timezone)
    lines.append("")

    # Summary (simple counts)
    up = down = 0
    details = []
    for s in symbols:
<<<<<<< HEAD
        info = fetch_symbol_yf(s)
        if not info or info.get("price") is None:
            details.append(f"{s}: — (lỗi dữ liệu)")
            continue
        pct = info.get("pct")
        if pct is not None:
            if pct > 0: up += 1
            elif pct < 0: down += 1
        vol = info.get("vol")
        avgvol = info.get("avg5_vol")
        vol_ratio = None
        if vol and avgvol:
            try:
                vol_ratio = vol / avgvol if avgvol>0 else None
            except Exception:
                vol_ratio = None
        vol_ratio_s = f" (VolRatio={vol_ratio:.2f}×)" if vol_ratio else ""
        details.append(f"{s}: {int(info.get('price'))} {fm_pct(pct)} | KL={fm_shares_million(vol)}{vol_ratio_s} | TB tuần: {info.get('avg5_price') or '—'} / {fm_shares_million(avgvol)}")
    lines.append(f"Summary: Tăng {up} / Giảm {down}")
    lines.append("🔻 Chi tiết mã:")
    lines.extend(details)
    lines.append("")
    lines.append("⚠️ Alerts:")
    # simple alert example
    for s in symbols:
        info = fetch_symbol_yf(s)
        if not info: continue
        pct = info.get("pct") or 0
        if pct >= 5:
            lines.append(f"  {s} tăng mạnh {fm_pct(pct)}")
        if pct <= -5:
            lines.append(f"  {s} giảm mạnh {fm_pct(pct)}")
    lines.append("")
    lines.append(f"(Thời gian báo cáo: {now}) - Bot_fixed")
    # Join with actual newline characters (not escaped)
=======
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
>>>>>>> parent of 6f7af73 (trước chạy được, cấu hình lại timezone)
    return "\n".join(lines)

def send_to_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
<<<<<<< HEAD
        print("Missing BOT_TOKEN/CHAT_ID - printing preview:\\n")
        print(text)
        return False
    base = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    ok = True
    try:
        r = requests.post(base, data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}, timeout=20)
        print("Telegram response", r.status_code, r.text[:400])
        if r.status_code != 200:
            ok = False
    except Exception as e:
        print("Telegram send error", e)
        ok = False
=======
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
>>>>>>> parent of 6f7af73 (trước chạy được, cấu hình lại timezone)
    return ok

def main():
    report=build_report(SYMBOLS)
    print("=== Report preview ==="); print(report)
    send_to_telegram(report)

if __name__=="__main__": main()
