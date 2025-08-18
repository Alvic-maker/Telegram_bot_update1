
import yfinance as yf
from datetime import datetime

def fetch_symbol(symbol, days=60):
    try:
        ticker = f"{symbol}.VN"
        tk = yf.Ticker(ticker)
        hist = tk.history(period=f"{days}d", auto_adjust=False)
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
        return {"source": "yfinance", "symbol": symbol, "price": last, "pct": pct, "vol": vol, "avg5_price": avg5, "avg5_vol": avgvol20, "sma20": sma20, "sma50": sma50, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"error": str(e), "source":"yfinance"}

def fetch_index(index_ticker='^VNINDEX', days=120):
    try:
        tk = yf.Ticker(index_ticker)
        hist = tk.history(period=f"{days}d", auto_adjust=False)
        if hist is None or hist.empty:
            return None
        close = hist['Close'].astype(float).dropna()
        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else last
        pct = (last/prev - 1) * 100 if prev != 0 else 0.0
        return {"source":"yfinance", "index":index_ticker, "price": last, "pct": pct, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"error": str(e), "source":"yfinance"}
