
#!/usr/bin/env python3
import os, traceback
from datetime import datetime
from sources import yfinance_api, vnstock_api, scrapers
from normalizers import normalize_market_record, normalize_symbol_record
from cache import get_cache, set_cache
import requests

BOT_TOKEN = os.getenv('BOT_TOKEN','').strip()
CHAT_ID = os.getenv('CHAT_ID','').strip()
USE_VNSTOCK = os.getenv('USE_VNSTOCK','1').lower() not in ('0','false','no','')
SYMBOLS = os.getenv('SYMBOLS','MBB,HPG,SSI,PVP,KSB,QTP').split(',')

def dbg(msg):
    print(f\"[DEBUG] {msg}\", flush=True)

def fm_money_million(v):
    if v is None: return '—'
    try: return f\"{v/1_000_000:,.0f} Mn\"
    except: return str(v)

def fm_shares_million(v):
    if v is None: return '—'
    try: return f\"{v/1_000_000:,.2f} Mn\"
    except: return str(v)

def fm_pct(x):
    if x is None: return '—'
    try: return f\"{x:+.2f}%\"
    except: return str(x)

def get_market():
    c = get_cache('market')
    if c: return c
    # 1) vnstock market foreign & index (if available)
    if USE_VNSTOCK:
        try:
            mf = vnstock_api.fetch_foreign(None)
            rec = normalize_market_record(mf or {}, 'vnstock')
            if rec.get('price') or rec.get('foreign_buy') or rec.get('foreign_sell'):
                set_cache('market', rec, ttl=50); return rec
        except Exception as e:
            dbg(f\"vnstock market error: {e}\")
    # 2) yfinance index
    try:
        yfidx = yfinance_api.fetch_index('^VNINDEX')
        rec = normalize_market_record(yfidx or {}, 'yfinance')
        if rec.get('price') is not None:
            set_cache('market', rec, ttl=50); return rec
    except Exception as e:
        dbg(f\"yfinance market error: {e}\")
    # 3) scraping fallbacks
    try:
        s = scrapers.scrape_vietstock_market() or scrapers.scrape_cafef_market()
        rec = normalize_market_record(s or {}, 'scrape')
        set_cache('market', rec, ttl=50); return rec
    except Exception as e:
        dbg(f\"scrape market error: {e}\")
    return {'price':None,'pct':None,'foreign_buy':None,'foreign_sell':None,'source':'none'}

def get_symbol(symbol):
    c = get_cache(f'sym_{symbol}')
    if c: return c
    # 1) yfinance primary
    try:
        info = yfinance_api.fetch_symbol(symbol)
        rec = normalize_symbol_record(info or {}, 'yfinance')
        if rec.get('price') is not None:
            set_cache(f'sym_{symbol}', rec, ttl=30); return rec
    except Exception as e:
        dbg(f'yf symbol {symbol} error: {e}')
    # 2) vnstock foreign info only (if available)
    if USE_VNSTOCK:
        try:
            fr = vnstock_api.fetch_foreign(symbol)
            if fr and ('buy' in fr or 'sell' in fr):
                rec = normalize_symbol_record(fr or {}, 'vnstock')
                set_cache(f'sym_{symbol}', rec, ttl=30); return rec
        except Exception as e:
            dbg(f'vnstock symbol {symbol} error: {e}')
    return {'symbol':symbol,'price':None,'pct':None,'vol':None,'avg5_price':None,'avg5_vol':None,'sma20':None,'sma50':None,'source':'none'}

def build_report(symbols):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    m = get_market()
    lines = [f\"📊 Báo cáo thị trường — {now}\"]
    if m.get('price') is not None:
        lines.append(f\"📈 VN-Index: {m.get('price'):.2f} {fm_pct(m.get('pct'))} | GTGD: {fm_money_million(m.get('gtgd'))}\")
    else:
        lines.append(\"📈 VN-Index: — (lỗi dữ liệu)\")
    if m.get('foreign_buy') is not None or m.get('foreign_sell') is not None:
        lines.append(f\"🔁 Khối ngoại (toàn TT): Mua {fm_money_million(m.get('foreign_buy'))} / Bán {fm_money_million(m.get('foreign_sell'))} → Ròng {fm_money_million((m.get('foreign_buy') or 0) - (m.get('foreign_sell') or 0))}\")
    else:
        lines.append(\"🔁 Khối ngoại (toàn TT): —\")
    lines.append(\"\"); lines.append('📌 Chi tiết mã:')
    for s in symbols:
        info = get_symbol(s)
        if info.get('price') is None:
            lines.append(f\"{s}: — (lỗi dữ liệu)\")
            continue
        vol_ratio = None
        try:
            vol = info.get('vol') or 0
            avg = info.get('avg5_vol') or info.get('avg5_vol') or None
            if avg:
                vol_ratio = vol / avg if avg else None
        except:
            vol_ratio = None
        vol_ratio_s = f\" (VolRatio={vol_ratio:.2f}×)\" if vol_ratio else \"\"
        lines.append(f\"{s}: {info.get('price')} {fm_pct(info.get('pct'))} | KL={fm_shares_million(info.get('vol'))}{vol_ratio_s} | TB tuần: {info.get('avg5_price') or '—'} / {fm_shares_million(info.get('avg5_vol'))} | NN: Mua {fm_money_million(None)} / Bán {fm_money_million(None)}\")
    lines.append(\"\"); lines.append('⚠️ Alerts:'); lines.append(''); lines.append(f\"(Thời gian báo cáo: {now}) - Bot_multi_source\")
    return '\\n'.join(lines)

def chunk_text(s, limit=3500):
    if not s: return ['']
    if len(s) <= limit: return [s]
    chunks = []
    cur = s
    while len(cur) > limit:
        cut = cur.rfind('\\n', 0, limit)
        if cut == -1: cut = limit
        chunks.append(cur[:cut]); cur = cur[cut:]
    if cur: chunks.append(cur)
    return chunks

def send_to_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        dbg('BOT_TOKEN/CHAT_ID missing - print preview'); print(text); return False
    base = f\"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage\"
    dbg(f\"Sending to Telegram CHAT_ID={CHAT_ID} (token masked)\")
    ok = True
    for i, part in enumerate(chunk_text(text), 1):
        payload = {'chat_id': CHAT_ID, 'text': part, 'disable_web_page_preview': True}
        try:
            r = requests.post(base, data=payload, timeout=20)
            dbg(f\"Telegram resp {r.status_code}: {r.text[:200]}\")
            if r.status_code != 200: ok = False
        except Exception as e:
            dbg(f\"Telegram send error: {e}\"); ok = False
    return ok

def main():
    try:
        report = build_report(SYMBOLS)
        print('=== Report preview ==='); print(report)
        sent = send_to_telegram(report)
        if sent: dbg('Sent/attempted.')
        else: dbg('Not sent.')
    except Exception as e:
        print('Fatal error', e); traceback.print_exc()

if __name__ == '__main__':
    main()
