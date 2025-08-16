
def fetch_foreign(symbol=None):
    try:
        try:
            import vnstock as vns
        except Exception:
            import vnstock3 as vns
        # common patterns
        if hasattr(vns, 'stock') and hasattr(vns.stock, 'foreign_trade'):
            if symbol:
                df = vns.stock.foreign_trade(symbol=symbol)
            else:
                df = vns.stock.foreign_trade()
            if hasattr(df, 'iloc'):
                row = df.iloc[-1].to_dict()
            elif isinstance(df, dict):
                row = df
            else:
                row = dict(df)
            return {"source":"vnstock", "buy": row.get('buy') or row.get('buy_value') or row.get('buy_total'), "sell": row.get('sell') or row.get('sell_value') or row.get('sell_total')}
        if hasattr(vns, 'foreign_trade'):
            df = vns.foreign_trade() if not symbol else vns.foreign_trade(symbol)
            if hasattr(df, 'iloc'):
                row = df.iloc[-1].to_dict(); return {"source":"vnstock","buy":row.get('buy'),"sell":row.get('sell')}
    except Exception as e:
        return {"error": str(e), "source":"vnstock"}
    return None
