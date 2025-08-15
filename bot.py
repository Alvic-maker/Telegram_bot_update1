import datetime

def send_report_to_telegram():
    # Giả sử đây là hàm gửi báo cáo
    print("📊 Gửi báo cáo tới Telegram")

def is_trading_time():
    now = datetime.datetime.now()  # Nếu server ở VN
    # Nếu server chạy UTC thì dùng: now = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    if now.weekday() >= 5:  # 5 = Thứ 7, 6 = CN
        return False
    if not (9 <= now.hour < 15):  # Giờ VN
        return False
    return True

if is_trading_time():
    send_report_to_telegram()
else:
    print("⏳ Ngoài giờ giao dịch, bot không gửi báo cáo.")
