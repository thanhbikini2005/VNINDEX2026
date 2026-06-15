# 🤖 VN-Index Analysis Bot

Bot tự động quét dữ liệu VN-Index, phân tích kỹ thuật và gửi báo cáo qua Telegram mỗi ngày.

---

## 📊 Báo cáo gồm những gì?

| Mục | Nội dung |
|---|---|
| Điểm số | Giá real-time, thay đổi, khối lượng, số mã tăng/giảm |
| Xu hướng | Ngắn hạn, momentum |
| Kháng cự/Hỗ trợ | Các vùng S/R quan trọng |
| Fibonacci | Các mức Fib từ đáy lớn → đỉnh lịch sử |
| Ngày/Tuần/Tháng | Nhận định theo từng khung thời gian |
| Dự báo 2 tuần | 3 kịch bản với xác suất |
| Lời khuyên | Gợi ý mua/bán/giữ + ví dụ mã cụ thể |
| Tin tức | Tiêu đề nóng từ CafeF & Vietstock |
| Nguồn dữ liệu | Link đến từng nguồn |

---

## 🕐 Lịch gửi báo cáo

- **7:00 sáng** — Báo cáo đầu phiên (Thứ 2 – Thứ 6)
- **16:30 chiều** — Báo cáo cuối phiên (Thứ 2 – Thứ 6)
- **Cuối tuần**: Bot tự động nghỉ

---

## 🔗 Nguồn dữ liệu

| Nguồn | Link | Dữ liệu |
|---|---|---|
| SSI iBoard | https://iboard.ssi.com.vn/ | Giá real-time, khối lượng, breadth |
| Investing.com VN | https://vn.investing.com/indices/vn-index | Giá & biến động |
| CafeF | https://cafef.vn/thi-truong-chung-khoan.chn | Tin tức thị trường |
| Vietstock | https://vietstock.vn/chu-de/nhan-dinh-thi-truong.htm | Nhận định phân tích |
| VnEconomy | https://vneconomy.vn/chung-khoan.htm | Tin kinh tế vĩ mô |
| HOSE Official | https://www.hsx.vn/ | Dữ liệu sàn chính thức |

---

## ⚙️ Hướng dẫn setup (5 bước)

### Bước 1 — Tạo Telegram Bot

1. Mở Telegram, tìm **@BotFather**
2. Gõ `/newbot` → đặt tên → lấy **TOKEN**
3. Tìm **@userinfobot** → gõ `/start` → lấy **CHAT ID** của bạn

### Bước 2 — Upload lên GitHub

1. Tạo repo mới tên `vnindex-bot`
2. Upload toàn bộ file lên repo

### Bước 3 — Thêm Secrets

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret name | Giá trị |
|---|---|
| `TELEGRAM_TOKEN` | Token từ BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID của bạn |

### Bước 4 — Bật GitHub Actions

Tab **Actions** → Enable workflows

### Bước 5 — Test thử

**Actions** → **VN-Index Bot** → **Run workflow** → kiểm tra Telegram

---

## 🧪 Chạy local

```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="xxx"
export TELEGRAM_CHAT_ID="xxx"
python vnindex_bot.py
```

---

## ⚠️ Disclaimer

Bot chỉ mang tính tham khảo, không phải tư vấn đầu tư chính thức. DYOR!
