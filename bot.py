#!/usr/bin/env python3
# bot_fixed.py - Telegram stock reporter (fixed & enhanced)
# Replace your current bot.py with this file or run directly.
# Requirements: yfinance, pandas, numpy, requests. vnstock optional (for foreign flows).
# Example requirements.txt entries:
# yfinance
# pandas
# numpy
# requests
# vnstock  # optional

import os
import re
import math
from datetime import datetime, timedelta
import requests
import traceback

import pandas as pd
import numpy as np
import yfinance as yf

USE_VNSTOCK = os.getenv("USE_VNSTOCK", "") not in ("", "0", "False", "false")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise SystemExit("Error: BOT_TOKEN and CHAT_ID must be set as environment variables.")

SEND_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# Watchlist - adjust as needed
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

# Alerts thresholds (env override possible)
PCT_ALERT_UP = float(os.getenv("PCT_ALERT_UP", "2.0"))
PCT_ALERT_DOWN = float(os.getenv("PCT_ALERT_DOWN", "-2.0"))
VOL_SURGE_MULT = float(os.getenv("VOL_SURGE_MULT", "2.0"))

# ---------------- HTTP helper ----------------
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
    out = {}
    if df is None or df.empty or 'Close' not in df:
        return out
    close = df['Close'].astype(float).dropna()
    if close.empty:
        return out

    out['last'] = float(close.iloc[-1])
    out['prev'] = float(close.iloc[-2]) if len(close) >= 2 else out['last']
    out['pct'] = (out['last'] / out['prev'] - 1) * 100 if out['prev'] != 0 else 0.0

    for n in (20, 50, 200):
        out[f'sma{n}'] = float(close.rolling(n).mean().iloc[-1]) if len(close) >= n else None

    # RSI14 (EWMA)
    if len(close) >= 15:
        delta = close.diff().dropna()
        ups = delta.clip(lower=0)
        downs = -delta.clip(upper=0)
        roll_up = ups.ewm(alpha=1/14, adjust=False).mean()
        roll_down = downs.ewm(alpha=1/14, adjust=False).mean()
        try:
            if roll_down.iloc[-1] == 0:
                out['rsi14'] = 100.0
            else:
                rs = roll_up.iloc[-1] / roll_down.iloc[-1]
                out['rsi14'] = 100 - (100 / (1 + rs))
        except Exception:
            out['rsi14'] = None
    else:
        out['rsi14'] = None

    # MACD 12,26,9
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
        try:
            high = df['High'].astype(float)
            low = df['Low'].astype(float)
            close_shift = df['Close'].astype(float).shift(1)
            tr1 = high - low
            tr2 = (high - close_shift).abs()
            tr3 = (low - close_shift).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).dropna()
            out['atr14'] = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else None
        except Exception:
            out['atr14'] = None
    else:
        out['atr14'] = None

    return out

# ---------------- Robust yfinance fetch ----------------
def get_with_yfinance(ticker_symbol, period='365d'):
    """
    Try multiple periods and fallback to yfinance.download to reduce empty-history cases.
    Returns indicators dict or None.
    """
    periods_to_try = [period, '240d', '120d', '60d', '30d', '14d', '7d', '5d', '2d']
    last_exc = None
    for p in periods_to_try:
        try:
            tk = yf.Ticker(ticker_symbol)
            hist = tk.history(period=p, auto_adjust=False)
            if hist is not None and not hist.empty and 'Close' in hist:
                info = indicators_from_df(hist)
                info['history_rows'] = len(hist)
                try:
                    info['name'] = tk.info.get('shortName') if hasattr(tk, 'info') else None
                except Exception:
                    info['name'] = None
                print(f"[yfinance] {ticker_symbol} got {len(hist)} rows (period={p})")
                return info
            else:
                print(f"[yfinance] {ticker_symbol} empty for period={p}")
        except Exception as e:
            last_exc = e
            print(f"[yfinance] error for {ticker_symbol} period={p}: {e}")
    # fallback: yfinance.download
    try:
        df = yf.download(ticker_symbol, period='60d', progress=False)
        if df is not None and not df.empty:
            info = indicators_from_df(df)
            info['history_rows'] = len(df)
            print(f"[yfinance.download] {ticker_symbol} got {len(df)} rows")
            return info
    except Exception as e:
        print("yfinance.download fallback error:", e)
    print(f"[yfinance] All attempts failed for {ticker_symbol}. Last exception: {last_exc}")
    return None

# ---------------- Foreign flows (vnstock best-effort) ----------------
def _extract_buy_sell_from_obj(obj):
    if obj is None:
        return (None, None)
    if isinstance(obj, dict):
        data = obj
    else:
        try:
            data = {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}
        except Exception:
            return (None, None)
    buy = None; sell = None
    def parse_num(x):
        if x is None: return None
        if isinstance(x, (int, float)): return float(x)
        s = str(x)
        s2 = re.sub(r"[^\d\.\-]", "", s)
        if s2 in ("", ".", "-"): return None
        try: return float(s2)
        except: return None
    for k, v in data.items():
        kl = str(k).lower()
        if any(tok in kl for tok in ("buy","mua","foreignbuy","nn_mua","muarong","mua_rong")) and buy is None:
            buy = parse_num(v)
        if any(tok in kl for tok in ("sell","ban","foreignsell","nn_ban","banrong","ban_rong")) and sell is None:
            sell = parse_num(v)
        if any(tok in kl for tok in ("net","ròng","rong","muanet","ban_net")) and (buy is None and sell is None):
            val = parse_num(v)
            if val is not None:
                if val >= 0:
                    buy = val; sell = 0.0
                else:
                    buy = 0.0; sell = abs(val)
    return (buy, sell)

def get_foreign_for_symbol(symbol):
    try:
        import vnstock as vns
    except Exception:
        return None
    sym = symbol.replace('.VN','')
    candidates = []
    for fn in ("foreign", "fii", "get_foreign", "foreign_flow", "foreign_trading", "fii_trading"):
        try:
            if hasattr(vns, fn):
                try:
                    res = getattr(vns, fn)(sym)
                    candidates.append(res)
                except Exception:
                    pass
        except Exception:
            pass
    try:
        if hasattr(vns, "price_board"):
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
        except Exception:
            out[s] = None
    return out

# ---------------- Formatting ----------------
def format_line_with_foreign(name, ticker, info, foreign_info=None):
    """
    Arrow = today's movement (pct). SMA displayed separately.
    """
    if not info:
        base = f"{name}: — (lỗi dữ liệu)"
    else:
        last = info.get('last')
        pct = info.get('pct')
        vol = info.get('vol')
        # direction based on today's pct
        if pct is None:
            dir_arrow = ""
        else:
            dir_arrow = "🔼" if pct > 0 else ("🔽" if pct < 0 else "—")
        sma50 = info.get('sma50')
        sma_label = f" | SMA50={int(sma50):,}" if sma50 else ""
        vol_s = f", KL={vol:,}" if vol not in (None, 0) else ""
        pct_s = f" ({pct:+.2f}%)" if pct is not None else ""
        base = f"{name}: {last:,.0f} {dir_arrow}{pct_s}{vol_s}{sma_label}"

    if foreign_info:
        b = foreign_info.get("buy")
        s = foreign_info.get("sell")
        def fmt_num(x):
            if x is None: return "—"
            try: return f"{int(x):,}"
            except: return str(x)
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
    except Exception as e:
        print("Error fetching index base:", e)
        return None

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
    try:
        last_52 = hist.tail(252) if len(hist) >= 252 else hist
        info['52w_high'] = float(last_52['High'].max())
        info['52w_low']  = float(last_52['Low'].min())
    except Exception:
        info['52w_high'] = info['52w_low'] = None

    # breadth & top contributors if list provided
    if vn30_tickers:
        adv = dec = neu = 0
        contribs = []
        for t in vn30_tickers:
            try:
                tk2 = yf.Ticker(t)
                h = tk2.history(period='7d', auto_adjust=False)
                if h is None or h.empty:
                    continue
                last = float(h['Close'].iloc[-1])
                prev = float(h['Close'].iloc[-2]) if len(h['Close']) >= 2 else last
                pct = (last/prev - 1) * 100 if prev != 0 else 0
                mcap = None
                try:
                    mcap = tk2.info.get('marketCap') if hasattr(tk2, 'info') else None
                except Exception:
                    mcap = None
                contrib = (mcap or 0) * (pct/100.0) if mcap else None
                contribs.append({"ticker": t, "pct": pct, "mcap": mcap, "contrib": contrib})
                if pct > 0:
                    adv += 1
                elif pct < 0:
                    dec += 1
                else:
                    neu += 1
            except Exception:
                continue
        info['breadth'] = {"adv": adv, "dec": dec, "neu": neu}
        with_contrib = [c for c in contribs if c.get('contrib') not in (None, 0)]
        if with_contrib:
            top = sorted(with_contrib, key=lambda x: abs(x['contrib']), reverse=True)[:3]
        else:
            top = sorted(contribs, key=lambda x: abs(x['pct']), reverse=True)[:3]
        info['top_contributors'] = top

    return info

def format_index_block(index_info):
    if not index_info:
        return "📈 VN-Index: — (lỗi dữ liệu)"
    last = index_info.get('last')
    pct = index_info.get('pct')
    pct_month = index_info.get('pct_vs_month_start')
    sma20 = index_info.get('sma20'); sma50 = index_info.get('sma50'); sma200 = index_info.get('sma200')
    h52 = index_info.get('52w_high'); l52 = index_info.get('52w_low')
    atr = index_info.get('atr14'); breadth = index_info.get('breadth', {}); topc = index_info.get('top_contributors', [])

    lines = []
    lines.append(f"📈 VN-Index: {last:,.2f} ({pct:+.2f}%)" if last is not None and pct is not None else "📈 VN-Index: — (lỗi dữ liệu)")
    if pct_month is not None:
        lines.append(f"   So với đầu tháng: {pct_month:+.2f}%")
    sma_line = " | ".join([f"SMA20={int(sma20):,}" if sma20 else "SMA20=—",
                           f"SMA50={int(sma50):,}" if sma50 else "SMA50=—",
                           f"SMA200={int(sma200):,}" if sma200 else "SMA200=—"])
    lines.append("   " + sma_line)
    if h52 and l52:
        lines.append(f"   52w: {l52:,.0f} — {h52:,.0f}")
    if atr:
        lines.append(f"   ATR14: {atr:.2f}")
    if breadth:
        lines.append(f"   Breadth (VN30): ↑ {breadth.get('adv',0)} / ↓ {breadth.get('dec',0)} / = {breadth.get('neu',0)}")
    if topc:
        topstr = ", ".join([f"{c['ticker'].replace('.VN','')}: {c['pct']:+.2f}%" + (f" (mcap={int(c['mcap']):,})" if c.get('mcap') else "") for c in topc])
        lines.append(f"   Top contributors: {topstr}")
    return "\n".join([l for l in lines if l])

# ---------------- Build report ----------------
def build_report(symbols):
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"📊 Báo cáo nhanh — {now}")

    # VN-Index block (use VN tickers for breadth if available)
    vn30_list = [t for t in symbols.values() if t.endswith('.VN')]
    index_info = get_index_info("^VNINDEX", vn30_tickers=vn30_list if vn30_list else None)
    lines.append(format_index_block(index_info))

    # foreign flows (best-effort)
    vn_symbols = [t for t in symbols.values() if t.endswith('.VN')]
    foreign_map = {}
    if USE_VNSTOCK and vn_symbols:
        try:
            foreign_map = get_foreign_for_symbols([s.replace('.VN','') for s in vn_symbols])
        except Exception as e:
            print("Foreign fetch error:", e)
            foreign_map = {}

    # details (skip symbols starting with '^')
    details = []
    for name, ticker in symbols.items():
        if str(ticker).startswith("^"):
            continue
        info = get_with_yfinance(ticker, period='120d')
        finfo = None
        if ticker.endswith('.VN'):
            finfo = foreign_map.get(ticker.replace('.VN','')) if foreign_map else None
        details.append((name, ticker, info, finfo))

    up_count = sum(1 for (_,_,info,_) in details if info and info.get('pct',0)>0)
    down_count = sum(1 for (_,_,info,_) in details if info and info.get('pct',0)<0)
    lines.append(f"Summary: Tăng {up_count} / Giảm {down_count}")

    # top movers
    movers = [(name, ticker, info) for (name,ticker,info,_) in details if info]
    top_up = sorted([m for m in movers if m[2].get('pct',0)>0], key=lambda x: -x[2]['pct'])[:3]
    top_down = sorted([m for m in movers if m[2].get('pct',0)<0], key=lambda x: x[2]['pct'])[:3]

    if top_up:
        lines.append("🔺 Top tăng:")
        for name, tick, info in top_up:
            foreign_info = None
            if USE_VNSTOCK:
                foreign_info = foreign_map.get(tick.replace('.VN','')) if foreign_map else None
            lines.append("  " + format_line_with_foreign(name, tick, info, foreign_info=foreign_info))
    if top_down:
        lines.append("🔻 Top giảm:")
        for name, tick, info in top_down:
            foreign_info = None
            if USE_VNSTOCK:
                foreign_info = foreign_map.get(tick.replace('.VN','')) if foreign_map else None
            lines.append("  " + format_line_with_foreign(name, tick, info, foreign_info=foreign_info))

    lines.append("")
    lines.append("Chi tiết mã:")
    for name, ticker, info, finfo in details:
        lines.append(format_line_with_foreign(name, ticker, info, foreign_info=finfo))

    # alerts
    alert_lines = []
    for name, ticker, info, finfo in details:
        if not info:
            continue
        pct = info.get('pct', 0)
        vol_ratio = info.get('vol_ratio')
        if pct is not None and pct >= PCT_ALERT_UP:
            alert_lines.append(f"{name} {pct:+.2f}% (↑)")
        if pct is not None and pct <= PCT_ALERT_DOWN:
            alert_lines.append(f"{name} {pct:+.2f}% (↓)")
        if vol_ratio and vol_ratio >= VOL_SURGE_MULT:
            alert_lines.append(f"{name} Vol surge {vol_ratio:.2f}×")

    if alert_lines:
        lines.append("")
        lines.append("⚠️ Alerts:")
        for a in alert_lines:
            lines.append("  " + a)

    lines.append("")
    lines.append(f"(Thời gian báo cáo: {now}) - Bot")
    return "\n".join(lines)

# ---------------- Send ----------------
def send_report(text):
    params = {"chat_id": CHAT_ID, "text": text}
    r = safe_request(SEND_URL, params=params)
    if r is None:
        print("Failed to send message.")
        return False
    try:
        j = r.json()
        if not j.get("ok"):
            print("Telegram API error:", j)
            return False
    except Exception as e:
        print("Response parse error:", e)
        return False
    return True

# ---------------- Main ----------------
def main():
    try:
        report = build_report(SYMBOLS)
        print("=== Report preview ===")
        print(report)
        ok = send_report(report)
        if ok:
            print("Sent to Telegram OK.")
        else:
            print("Send failed. Check logs and secrets.")
    except Exception as e:
        print("Fatal error in main:", e)
        traceback.print_exc()

if __name__ == "__main__":
    main()
