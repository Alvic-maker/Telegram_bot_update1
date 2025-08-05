import os
import requests
import yfinance as yf

BOT_TOKEN = os.environ['BOT_TOKEN']
CHAT_ID   = os.environ['CHAT_ID']

symbols = {
    "VN-Index": "^VNINDEX",
    "VN30": "^VN30",
    "MBB": "MBB.VN",
    "HPG": "HPG.VN",
    "SSI": "SSI.VN",
    "PVP": "PVP.VN",
    "KSB": "KSB.VN",
    "QTP": "QTP.VN"
}

lines = []
for name, ticker in symbols.items():
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period='2d')
        last = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        pct  = (last/prev - 1) * 100
        vol  = int(hist['Volume'].iloc[-1])
        lines.append(f"{name}: {last:.0f} ({pct:+.2f}%), KL={vol}")
    except Exception as e:
        lines.append(f"{name}: lỗi dữ liệu")

text = "\n".join(lines)
requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
             params={"chat_id": CHAT_ID, "text": text})

