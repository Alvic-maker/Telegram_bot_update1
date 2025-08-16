# bot_vnstock.py
from vnstock import stock
import pandas as pd
from datetime import datetime, timedelta

# Cấu hình danh sách mã theo dõi
symbols = ["MBB", "HPG", "SSI", "PVP", "KSB", "QTP"]

# -------------------
# Helper functions
# -------------------

def get_index_info(index_code="VNINDEX"):
    try:
        data = stock.index(index_code, "1D", count=1)
        latest = data.iloc[-1]
        return {
            "index": index_code,
            "close": latest["close"],
            "change": latest["change"],
            "pct_change": latest["pct_change"],
            "volume": latest["volume"]
        }
    except Exception as e:
        return {"index": index_code, "error": str(e)}

def get_foreign_trade(symbol=None):
    try:
        df = stock.foreign_trade(symbol=symbol) if symbol else stock.foreign_trade()
        latest = df.iloc[-1]
        return {
            "buy": latest["buy_value"],
            "sell": latest["sell_value"],
            "net": latest["buy_value"] - latest["sell_value"]
        }
    except Exception as e:
        return {"error": str(e)}

def get_symbol_info(symbol):
    try:
        # Quote hiện tại
        quote = stock.quote(symbol)
        price = quote["lastPrice"]
        change = quote["change"]
        pct_change = quote["percentChange"]
        volume = quote["nmVol"]

        # Lấy lịch sử 10 ngày gần nhất để tính TB tuần
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        history = stock.history(symbol, resolution="1D", start_date=start, end_date=end)
        history = history.tail(5)  # 5 phiên gần nhất

        avg_price = history["close"].mean()
        avg_volume = history["volume"].mean()

        # Khối ngoại
        foreign = get_foreign_trade(symbol)

        return {
            "symbol": symbol,
            "price": price,
            "change": change,
            "pct_change": pct_change,
            "volume": volume,
            "avg_price": round(avg_price, 2),
            "avg_volume": int(avg_volume),
            "foreign_buy": foreign.get("buy", 0),
            "foreign_sell": foreign.get("sell", 0),
            "foreign_net": foreign.get("net", 0)
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

# -------------------
# Build message
# -------------------
def build_message():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Phần 1: Thị trường chung
    vnindex = get_index_info("VNINDEX")
    vn30 = get_index_info("VN30")
    foreign_all = get_foreign_trade()

    msg = f"📊 Báo cáo thị trường — {now}\n"
    if "error" not in vnindex:
        msg += f"VN-Index: {vnindex['close']} ({vnindex['pct_change']}%)\n"
    else:
        msg += f"VN-Index: lỗi dữ liệu\n"
    if "error" not in vn30:
        msg += f"VN30: {vn30['close']} ({vn30['pct_change']}%)\n"
    else:
        msg += f"VN30: lỗi dữ liệu\n"

    msg += f"Khối ngoại (toàn thị trường): Mua {foreign_all.get('buy',0):,}, Bán {foreign_all.get('sell',0):,}, Ròng {foreign_all.get('net',0):,}\n\n"

    # Phần 2: Mỗi mã
    msg += "📌 Chi tiết mã:\n"
    for sym in symbols:
        info = get_symbol_info(sym)
        if "error" in info:
            msg += f"{sym}: lỗi dữ liệu ({info['error']})\n"
        else:
            msg += (f"{sym}: {info['price']} ({info['pct_change']}%), "
                    f"KL={info['volume']:,}, "
                    f"TB tuần: {info['avg_price']} / {info['avg_volume']:,}, "
                    f"Khối ngoại: Mua {info['foreign_buy']:,}, "
                    f"Bán {info['foreign_sell']:,}, "
                    f"Ròng {info['foreign_net']:,}\n")

    return msg

if __name__ == "__main__":
    print(build_message())
