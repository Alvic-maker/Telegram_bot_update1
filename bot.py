
import datetime

# Dummy data for testing
data = {
    "VN-Index": {"price": None, "change_pct": None, "volume": None, "foreign_buy": None, "foreign_sell": None},
    "VN30": {"price": None, "change_pct": None, "volume": None, "foreign_buy": None, "foreign_sell": None},
    "MBB": {"price": 28250, "change_pct": 2.36, "volume": 121_513_479, "foreign_buy": 1_200_000, "foreign_sell": 900_000},
    "HPG": {"price": 28000, "change_pct": -0.71, "volume": 108_066_934, "foreign_buy": 500_000, "foreign_sell": 1_000_000},
    "SSI": {"price": 36550, "change_pct": -0.68, "volume": 58_531_482, "foreign_buy": 700_000, "foreign_sell": 1_200_000},
    "PVP": {"price": 15250, "change_pct": 0.00, "volume": 460_338, "foreign_buy": 50_000, "foreign_sell": 50_000},
    "KSB": {"price": 19700, "change_pct": -2.72, "volume": 5_053_876, "foreign_buy": 30_000, "foreign_sell": 100_000},
    "QTP": {"price": None, "change_pct": None, "volume": None, "foreign_buy": None, "foreign_sell": None}
}

symbols = ["MBB", "HPG", "SSI", "PVP", "KSB", "QTP"]

def format_value(value):
    if value is None:
        return "— (lỗi dữ liệu)"
    return f"{value:,.0f}"

def format_change(change):
    if change is None:
        return ""
    arrow = "🔼" if change > 0 else "🔽" if change < 0 else "⏺"
    return f"{arrow} ({change:+.2f}%)"

def build_report(data, symbols):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Summary for VN-Index
    vn_index_info = data.get("VN-Index", {})
    vn_index_text = f"📈 VN-Index: {format_value(vn_index_info.get('price'))} {format_change(vn_index_info.get('change_pct'))}"
    
    # Market summary
    ups = [s for s in symbols if data[s]["change_pct"] and data[s]["change_pct"] > 0]
    downs = [s for s in symbols if data[s]["change_pct"] and data[s]["change_pct"] < 0]
    summary_text = f"Summary: Tăng {len(ups)} / Giảm {len(downs)}"
    
    # Top gainers & losers
    top_gainers = sorted(ups, key=lambda s: data[s]["change_pct"], reverse=True)[:3]
    top_losers = sorted(downs, key=lambda s: data[s]["change_pct"])[:3]
    
    top_gain_text = "\n".join([
        f"  {s}: {format_value(data[s]['price'])} {format_change(data[s]['change_pct'])}, KL={format_value(data[s]['volume'])}" 
        for s in top_gainers
    ]) or "  —"
    
    top_lose_text = "\n".join([
        f"  {s}: {format_value(data[s]['price'])} {format_change(data[s]['change_pct'])}, KL={format_value(data[s]['volume'])}" 
        for s in top_losers
    ]) or "  —"
    
    # Details with foreign trading
    details_lines = []
    for s in ["VN-Index", "VN30"] + symbols:
        info = data[s]
        details_lines.append(
            f"{s}: {format_value(info['price'])} {format_change(info['change_pct'])}, KL={format_value(info['volume'])}, "
            f"NN Mua={format_value(info['foreign_buy'])}, NN Bán={format_value(info['foreign_sell'])}"
        )
    
    details_text = "\n".join(details_lines)
    
    # Build full message
    message = f"""📊 Báo cáo nhanh — {now}
{vn_index_text}
{summary_text}
🔺 Top tăng:
{top_gain_text}
🔻 Top giảm:
{top_lose_text}

Chi tiết mã:
{details_text}

(Thời gian báo cáo: {now}) — Bot
"""
    return message

if __name__ == "__main__":
    print(build_report(data, symbols))
