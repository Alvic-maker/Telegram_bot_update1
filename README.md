# Telegram Stock Reporter (GitHub Actions)

Tải xuống và push toàn bộ thư mục này lên 1 repo GitHub public/private (nếu private thì cần có runner/plan tương ứng).
Các file chính: `bot.py`, `requirements.txt`, `.github/workflows/notify.yml`.

## Các bước nhanh
1. Tạo bot trên Telegram bằng @BotFather → lưu **BOT_TOKEN**.
2. Lấy **CHAT_ID** (bằng @userinfobot hoặc add bot vào nhóm và lấy id).
3. Tạo repo trên GitHub, push toàn bộ file từ thư mục này.
4. Vào **Settings → Secrets** của repo, thêm `BOT_TOKEN` và `CHAT_ID` (giá trị là token và id).
5. Push commit. Workflow sẽ chạy theo cron mỗi 5 phút (GitHub dùng UTC). Bạn có thể chạy thủ công từ tab Actions → chọn workflow → Run workflow.

## Lưu ý & debug nhanh
- Nếu bot không gửi: kiểm tra **Actions logs**, kiểm tra secrets, kiểm tra bot đã được start/allowed chưa.
- yfinance có thể trả về Volume = NaN cho một số chỉ số; code đã xử lý.
- Nếu cần dữ liệu nhanh hơn/chi tiết hơn (khớp lệnh, KLGD), bật `USE_VNSTOCK=1` và cài `vnstock` (thêm secret nếu cần).

## Muốn thêm
- Báo động >5%/ < -5%, so sánh đầu tháng, xuất file cấu hình người dùng... mình hỗ trợ tiếp, nhưng file này đã sẵn sàng để **download → push → chạy**.
