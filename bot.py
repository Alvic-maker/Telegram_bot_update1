#!/usr/bin/env python3
# bot.py - stock reporter (uses yfinance) with VN timezone-aware timestamps
import os, traceback, math
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
import requests

# optional imports
try:
    import yfinance as yf
    import pandas as pd
except Exception:
    yf = None
    pd = None

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

# symbols to report
SYMBOLS = os.getenv("SYMBOLS", "MBB,HPG,SSI,PVP,KSB,QTP").split(",")

def now_vn_str():
    if ZoneInfo is not None:
        now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    else:
        # fallback: assume system tz is UTC and add 7 hours
        now = datetime.utcnow() + __import__("datetime").timedelta(hours=7)
    return now.strftime("%Y-%m-%d %H:%M:%S")

def fm_money_million(v):
    if v is None:
        return "—"
    try:
        return f"{v/1_000_000:,.0f} Mn"
    except Exception:
        return str(v)

def fm_shares_million(v):
    if v is None:
        return "—"
    try:
        return f"{v/1_000_000:,.2f} Mn"
    except Exception:
        return str(v)

def fm_pct(x):
    if x is None:
        return "—"
    try:
        return f"{x:+.2f}%"
    except Exception:
        return str(x)

def fetch_symbol_yf(sym):
    if yf is None:
        return None
    ticker = f"{sym}.VN" if not sym.endswith(".VN") else sym
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="60d", auto_adjust=False)
        if hist is None or hist.empty:
            return None
        close = hist['Close'].astype(float).dropna()
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else last
        pct = (last/prev - 1) * 100 if prev != 0 else 0.0
        vol = int(hist['Volume'].astype(float).iloc[-1]) if 'Volume' in hist else None
        avg5_price = float(close.tail(5).mean()) if len(close) >= 5 else None
        avgvol20 = int(hist['Volume'].astype(float).tail(20).mean()) if 'Volume' in hist and len(hist['Volume'].dropna())>=20 else None
        return {"source":"yfinance","symbol":sym,"price": last,"pct": pct,"vol": vol,"avg5_price": avg5_price,"avg5_vol": avgvol20}
    except Exception as e:
        # avoid crashing whole script
        print("fetch_symbol_yf error", sym, e)
        return None

def fetch_index_yf():
    if yf is None:
        return None
    try:
        tk = yf.Ticker("^VNINDEX")
        hist = tk.history(period="120d", auto_adjust=False)
        if hist is None or hist.empty:
            return None
        close = hist['Close'].astype(float).dropna()
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else last
        pct = (last/prev - 1) * 100 if prev != 0 else 0.0
        return {"source":"yfinance","price": last,"pct": pct}
    except Exception as e:
        print("fetch_index_yf error", e)
        return None

def build_report(symbols):
    now = now_vn_str()
    lines = [f"📊 Báo cáo thị trường — {now}"]
    # VN-Index attempt via yfinance
    idx = fetch_index_yf()
    if idx and idx.get("price") is not None:
        lines.append(f"📈 VN-Index: {idx['price']:.2f} {fm_pct(idx.get('pct'))} (src={idx.get('source')})")
    else:
        lines.append("📈 VN-Index: — (lỗi dữ liệu)")
    lines.append("")
    lines.append("📌 Chi tiết mã:")
    for s in symbols:
        s = s.strip().upper()
        info = fetch_symbol_yf(s)
        if not info or info.get("price") is None:
            lines.append(f"{s}: — (lỗi dữ liệu)")
            continue
        vol = info.get("vol")
        vol_ratio = None
        try:
            avg = info.get("avg5_vol")
            if avg and avg>0 and vol:
                vol_ratio = vol / avg
        except Exception:
            vol_ratio = None
        vol_ratio_s = f" (VolRatio={vol_ratio:.2f}×)" if vol_ratio else ""
        lines.append(f"{s}: {int(info.get('price'))} {fm_pct(info.get('pct'))} | KL={fm_shares_million(vol)}{vol_ratio_s} | TB tuần: {info.get('avg5_price') or '—'} / {fm_shares_million(info.get('avg5_vol'))}")
    lines.append("")
    lines.append(f"(Thời gian báo cáo: {now}) - Bot_fixed")
    return "\\n".join(lines)

def send_to_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID - printing preview:\\n")
        print(text)
        return False
    base = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    ok = True
    parts = [text]
    for part in parts:
        try:
            r = requests.post(base, data={"chat_id": CHAT_ID, "text": part, "disable_web_page_preview": True}, timeout=20)
            print("Telegram response", r.status_code, r.text[:400])
            if r.status_code != 200:
                ok = False
        except Exception as e:
            print("Telegram send error", e)
            ok = False
    return ok

if __name__ == "__main__":
    try:
        report = build_report(SYMBOLS)
        print("=== Report preview ===")
        print(report)
        sent = send_to_telegram(report)
        print("Sent:", sent)
    except Exception as e:
        print("Fatal", e)
        traceback.print_exc()
