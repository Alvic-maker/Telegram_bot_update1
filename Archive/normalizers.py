
def normalize_market_record(rec, source_name):
    out = {"price": None, "pct": None, "gtgd": None, "foreign_buy": None, "foreign_sell": None, "source": source_name}
    if not rec:
        return out
    for k in ('price','last','close','index'):
        if k in rec and rec[k] is not None:
            out['price'] = rec[k]; break
    for k in ('pct','pct_change','percentChange','changePercent'):
        if k in rec and rec[k] is not None:
            out['pct'] = rec[k]; break
    for k in ('fbuy','buy','buy_value','buy_total'):
        if k in rec and rec[k] is not None:
            out['foreign_buy'] = rec[k]; break
    for k in ('fsell','sell','sell_value','sell_total'):
        if k in rec and rec[k] is not None:
            out['foreign_sell'] = rec[k]; break
    out['source'] = source_name
    return out

def normalize_symbol_record(rec, source_name):
    out = {"symbol": None, "price": None, "pct": None, "vol": None, "avg5_price": None, "avg5_vol": None, "sma20": None, "sma50": None, "source": source_name}
    if not rec:
        return out
    if isinstance(rec, dict):
        out['symbol'] = rec.get('symbol') or rec.get('ticker')
        out['price'] = rec.get('price') or rec.get('last') or rec.get('close')
        out['pct'] = rec.get('pct') or rec.get('percentChange') or rec.get('changePercent')
        out['vol'] = rec.get('vol') or rec.get('volume') or rec.get('nmVol')
        out['avg5_price'] = rec.get('avg5_price') or rec.get('avg5') or rec.get('avg_price')
        out['avg5_vol'] = rec.get('avg5_vol') or rec.get('avgvol20') or rec.get('avgvol')
        out['sma20'] = rec.get('sma20'); out['sma50'] = rec.get('sma50')
    return out
