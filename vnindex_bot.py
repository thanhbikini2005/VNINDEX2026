"""
VN-Index Analysis Bot
Tự động quét dữ liệu, phân tích kỹ thuật và gửi báo cáo qua Telegram.
"""

import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import json
import re

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ─── NGUỒN DỮ LIỆU ──────────────────────────────────────────────────────────
SOURCES = {
    "SSI iBoard": "https://iboard.ssi.com.vn/",
    "Vietstock": "https://vietstock.vn/chu-de/thi-truong-chung-khoan.htm",
    "CafeF": "https://cafef.vn/thi-truong-chung-khoan.chn",
    "VnEconomy": "https://vneconomy.vn/chung-khoan.htm",
    "FireAnt": "https://fireant.vn/",
    "investing.com VN": "https://vn.investing.com/indices/vn-index",
    "HOSE Official": "https://www.hsx.vn/",
}

# ─── LẤY DỮ LIỆU VNINDEX TỪ INVESTING.COM ───────────────────────────────────
def fetch_vnindex_price():
    """Lấy giá VN-Index từ investing.com (widget API không cần JS)."""
    try:
        url = "https://vn.investing.com/indices/vn-index"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # Tìm giá hiện tại
        price_tag = soup.find("span", {"data-test": "instrument-price-last"})
        change_tag = soup.find("span", {"data-test": "instrument-price-change"})
        pct_tag = soup.find("span", {"data-test": "instrument-price-change-percent"})

        price = price_tag.text.strip().replace(",", "") if price_tag else None
        change = change_tag.text.strip() if change_tag else None
        pct = pct_tag.text.strip() if pct_tag else None

        return {
            "price": float(price) if price else None,
            "change": change,
            "pct": pct,
        }
    except Exception as e:
        print(f"[investing.com] Lỗi: {e}")
        return {}


def fetch_vnindex_from_ssi():
    """Lấy dữ liệu VN-Index từ SSI iBoard API."""
    try:
        url = "https://iboard-query.ssi.com.vn/v2/stock/marketwatch?indexCode=VNINDEX"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        item = data.get("data", [{}])[0]
        return {
            "price": item.get("indexValue"),
            "change": item.get("indexChange"),
            "pct": item.get("percentChange"),
            "volume": item.get("totalVolume"),
            "value": item.get("totalValue"),
            "advances": item.get("advances"),
            "declines": item.get("declines"),
            "nochanges": item.get("nochanges"),
        }
    except Exception as e:
        print(f"[SSI iBoard] Lỗi: {e}")
        return {}


def fetch_cafef_news():
    """Lấy tin tức mới nhất từ CafeF."""
    try:
        url = "https://cafef.vn/thi-truong-chung-khoan.chn"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        news = []
        for item in soup.select("h3.title a, h2.title a")[:5]:
            title = item.text.strip()
            href = item.get("href", "")
            if not href.startswith("http"):
                href = "https://cafef.vn" + href
            if title:
                news.append({"title": title, "url": href})
        return news
    except Exception as e:
        print(f"[CafeF] Lỗi: {e}")
        return []


def fetch_vietstock_analysis():
    """Lấy nhận định thị trường từ Vietstock."""
    try:
        url = "https://vietstock.vn/chu-de/nhan-dinh-thi-truong.htm"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = []
        for a in soup.select("article h3 a, .title-news a")[:3]:
            title = a.text.strip()
            href = a.get("href", "")
            if not href.startswith("http"):
                href = "https://vietstock.vn" + href
            if title:
                items.append({"title": title, "url": href})
        return items
    except Exception as e:
        print(f"[Vietstock] Lỗi: {e}")
        return []


# ─── PHÂN TÍCH KỸ THUẬT ──────────────────────────────────────────────────────
def fibonacci_levels(low: float, high: float) -> dict:
    """Tính các mức Fibonacci Retracement từ đáy lên đỉnh."""
    diff = high - low
    levels = {
        "0.0% (Đỉnh)": round(high, 2),
        "23.6%": round(high - 0.236 * diff, 2),
        "38.2%": round(high - 0.382 * diff, 2),
        "50.0%": round(high - 0.500 * diff, 2),
        "61.8% 🔑": round(high - 0.618 * diff, 2),
        "78.6%": round(high - 0.786 * diff, 2),
        "100% (Đáy)": round(low, 2),
    }
    return levels


def get_fib_zone(price: float, fib: dict) -> str:
    """Xác định VN-Index đang nằm ở vùng Fibonacci nào."""
    levels = sorted(fib.items(), key=lambda x: x[1], reverse=True)
    for i in range(len(levels) - 1):
        name, val = levels[i]
        next_name, next_val = levels[i + 1]
        if next_val <= price <= val:
            return f"Đang ở giữa Fib {next_name} ({next_val}) và {name} ({val})"
    return "Ngoài vùng Fibonacci"


def support_resistance(price: float) -> dict:
    """Xác định vùng kháng cự/hỗ trợ theo vùng giá hiện tại."""
    zones = [
        (1700, 1740, "Hỗ trợ rất mạnh (đáy trung hạn)"),
        (1750, 1770, "Hỗ trợ mạnh (Fib 23.6% + MA200)"),
        (1800, 1820, "Hỗ trợ/kháng cự tâm lý 1.800"),
        (1830, 1870, "Kháng cự gần (MA50+MA100)"),
        (1900, 1935, "Kháng cự mạnh (vùng đỉnh lịch sử)"),
    ]
    result = {"support": [], "resistance": []}
    for low, high, label in zones:
        if price > high:
            result["support"].append(f"{low}–{high}: {label}")
        elif price < low:
            result["resistance"].append(f"{low}–{high}: {label}")
        else:
            result["support"].append(f"⚠️ Đang trong vùng: {low}–{high}: {label}")
    return result


def trend_analysis(price: float, change_pct: float, volume: float = None) -> dict:
    """Đánh giá xu hướng ngắn hạn."""
    # Xu hướng dựa trên vùng giá
    if price >= 1870:
        trend = "📈 TĂNG MẠNH — Trên vùng kháng cự cũ"
        bias = "bullish"
    elif price >= 1820:
        trend = "📈 TĂNG NHẸ — Hồi phục, cần xác nhận"
        bias = "neutral_bullish"
    elif price >= 1800:
        trend = "⚖️ GIẰNG CO — Kiểm định ngưỡng tâm lý 1.800"
        bias = "neutral"
    elif price >= 1760:
        trend = "📉 ĐIỀU CHỈNH — Cần giữ vùng hỗ trợ 1.760"
        bias = "neutral_bearish"
    else:
        trend = "📉 GIẢM MẠNH — Áp lực bán chiếm ưu thế"
        bias = "bearish"

    # Momentum
    if change_pct is not None:
        try:
            pct = float(str(change_pct).replace("%", "").replace("+", ""))
            if pct > 1.5:
                momentum = "🟢 Momentum tăng mạnh"
            elif pct > 0.3:
                momentum = "🟡 Momentum tăng nhẹ"
            elif pct > -0.3:
                momentum = "⚪ Momentum trung lập"
            elif pct > -1.5:
                momentum = "🟠 Momentum giảm nhẹ"
            else:
                momentum = "🔴 Momentum giảm mạnh — cảnh báo"
        except:
            momentum = "⚪ Không xác định"
    else:
        momentum = "⚪ Không có dữ liệu"

    return {"trend": trend, "momentum": momentum, "bias": bias}


def forecast_2weeks(price: float, bias: str) -> str:
    """Dự báo 2 tuần tới theo kịch bản."""
    now = datetime.now(VN_TZ)
    end = now + timedelta(weeks=2)
    date_range = f"{now.strftime('%d/%m')} – {end.strftime('%d/%m/%Y')}"

    if bias == "bullish":
        return (
            f"📅 Dự báo {date_range}\n"
            f"🟢 Kịch bản tích cực (xác suất ~60%): Tiếp tục tăng, hướng đến 1.920–1.935\n"
            f"🟡 Kịch bản trung lập (xác suất ~30%): Tích lũy 1.850–1.900\n"
            f"🔴 Kịch bản rủi ro (xác suất ~10%): Điều chỉnh về 1.810–1.830"
        )
    elif bias in ("neutral_bullish", "neutral"):
        return (
            f"📅 Dự báo {date_range}\n"
            f"🟢 Kịch bản tích cực (xác suất ~45%): Hồi phục về 1.850–1.870 nếu giữ được 1.800\n"
            f"🟡 Kịch bản trung lập (xác suất ~35%): Giằng co 1.780–1.830\n"
            f"🔴 Kịch bản rủi ro (xác suất ~20%): Mất 1.780, kiểm định 1.750–1.760"
        )
    elif bias == "neutral_bearish":
        return (
            f"📅 Dự báo {date_range}\n"
            f"🟢 Kịch bản tích cực (xác suất ~30%): Bật mạnh từ vùng hỗ trợ, hướng 1.820\n"
            f"🟡 Kịch bản trung lập (xác suất ~35%): Tích lũy vùng 1.750–1.800\n"
            f"🔴 Kịch bản rủi ro (xác suất ~35%): Phá 1.750, hướng về 1.700–1.740"
        )
    else:  # bearish
        return (
            f"📅 Dự báo {date_range}\n"
            f"🟢 Kịch bản tích cực (xác suất ~20%): Bật kỹ thuật mạnh về 1.780–1.800\n"
            f"🟡 Kịch bản trung lập (xác suất ~30%): Tích lũy giằng co 1.700–1.760\n"
            f"🔴 Kịch bản rủi ro (xác suất ~50%): Tiếp tục giảm về 1.650–1.700"
        )


def stock_advice(price: float, bias: str) -> str:
    """Lời khuyên cụ thể theo vùng giá và xu hướng."""
    if bias == "bullish":
        return (
            "💡 LỜI KHUYÊN\n"
            "✅ Có thể mua vào — ưu tiên cổ phiếu đầu ngành, thanh khoản cao\n"
            "📌 Ví dụ mã quan tâm: VIC, VHM (BĐS phục hồi), VCB, TCB (ngân hàng tăng trưởng), FPT (công nghệ)\n"
            "⚠️ Đặt stoploss dưới 1.850 cho giao dịch swing\n"
            "📊 Tỷ lệ giải ngân gợi ý: 60–70% danh mục"
        )
    elif bias in ("neutral_bullish", "neutral"):
        return (
            "💡 LỜI KHUYÊN\n"
            "⏳ Quan sát — chờ xác nhận xu hướng trước khi vào mạnh\n"
            "📌 Nếu mua: ưu tiên cổ phiếu phòng thủ — VCB, BID (ngân hàng), GAS, PLX (năng lượng)\n"
            "⚠️ Không mua đuổi — chờ pullback về vùng hỗ trợ\n"
            "📊 Tỷ lệ giải ngân gợi ý: 30–50%, cơ cấu dần"
        )
    elif bias == "neutral_bearish":
        return (
            "💡 LỜI KHUYÊN\n"
            "🛑 Thận trọng — giảm tỷ trọng hoặc giữ tiền mặt\n"
            "📌 Nếu nắm giữ: cân nhắc chốt lời một phần cổ phiếu yếu\n"
            "📌 Vùng mua thử nghiệm: 1.750–1.760 với 20–30% vốn, stoploss 1.730\n"
            "📊 Tỷ lệ giải ngân gợi ý: 20–30%, chia làm nhiều lần"
        )
    else:
        return (
            "💡 LỜI KHUYÊN\n"
            "🔴 KHÔNG MUA — Thị trường đang giảm mạnh\n"
            "📌 Ưu tiên bảo toàn vốn, tăng tỷ lệ tiền mặt lên 70–80%\n"
            "📌 Chỉ xem xét bắt đáy khi có tín hiệu đảo chiều rõ ràng (nến Hammer + khối lượng lớn)\n"
            "📊 Tỷ lệ giải ngân gợi ý: 0–10%, chờ xác nhận"
        )


# ─── BUILD BÁO CÁO ───────────────────────────────────────────────────────────
def build_report(session: str) -> str:
    now = datetime.now(VN_TZ)
    weekday = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"][now.weekday()]
    date_str = now.strftime(f"{weekday}, %d/%m/%Y %H:%M")

    emoji = "🌅" if session == "morning" else "🌆"
    title = "BÁO CÁO SÁNG" if session == "morning" else "BÁO CÁO CHIỀU"

    lines = [f"{emoji} <b>VN-INDEX {title}</b>", f"📆 {date_str}", ""]

    # ── Lấy dữ liệu
    ssi = fetch_vnindex_from_ssi()
    investing = fetch_vnindex_price()

    price = ssi.get("price") or investing.get("price")
    change = ssi.get("change") or investing.get("change")
    pct = ssi.get("pct") or investing.get("pct")
    volume = ssi.get("volume")
    value = ssi.get("value")
    advances = ssi.get("advances")
    declines = ssi.get("declines")
    nochanges = ssi.get("nochanges")

    if not price:
        lines.append("⚠️ Không lấy được dữ liệu giá. Vui lòng kiểm tra lại nguồn.")
        return "\n".join(lines)

    # ── Phần 1: Điểm số
    try:
        pct_val = float(str(pct).replace("%", "").replace("+", ""))
        pct_emoji = "🟢" if pct_val > 0 else ("🔴" if pct_val < 0 else "⚪")
    except:
        pct_val = 0
        pct_emoji = "⚪"

    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 <b>ĐIỂM SỐ HIỆN TẠI</b>",
        f"VN-Index: <b>{price:,.2f}</b> điểm",
        f"Thay đổi: {pct_emoji} {change} ({pct})",
    ]

    if volume:
        vol_fmt = f"{float(volume)/1e6:.1f}M CP"
        lines.append(f"Khối lượng: {vol_fmt}")
    if value:
        val_fmt = f"{float(value)/1e9:.0f} tỷ đồng"
        lines.append(f"Giá trị GD: {val_fmt}")
    if advances and declines:
        lines.append(f"Tăng/Giảm/Đứng: {advances} / {declines} / {nochanges or '–'}")

    # ── Phần 2: Xu hướng
    trend = trend_analysis(price, pct_val, volume)
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📈 <b>XU HƯỚNG</b>",
        trend["trend"],
        trend["momentum"],
    ]

    # ── Phần 3: Kháng cự / Hỗ trợ
    sr = support_resistance(price)
    lines += ["", "━━━━━━━━━━━━━━━━━━━━", "🧱 <b>KHÁNG CỰ / HỖ TRỢ</b>"]
    if sr["resistance"]:
        lines.append("🔴 Kháng cự phía trên:")
        for z in sr["resistance"][:2]:
            lines.append(f"  • {z}")
    if sr["support"]:
        lines.append("🟢 Hỗ trợ phía dưới:")
        for z in sr["support"][:2]:
            lines.append(f"  • {z}")

    # ── Phần 4: Fibonacci
    LOW = 1200.0   # Đáy tháng 4/2025 (swing lớn)
    HIGH = 1933.11  # Đỉnh lịch sử
    fib = fibonacci_levels(LOW, HIGH)
    fib_zone = get_fib_zone(price, fib)

    lines += ["", "━━━━━━━━━━━━━━━━━━━━", "📐 <b>FIBONACCI (Đáy 1.200 → Đỉnh 1.933)</b>"]
    for name, val in fib.items():
        marker = " ◀ BẠN ĐANG Ở ĐÂY" if abs(price - val) < 25 else ""
        lines.append(f"  • {name}: {val:,.2f}{marker}")
    lines.append(f"📍 {fib_zone}")

    # ── Phần 5: Phân tích ngày/tuần/tháng
    lines += ["", "━━━━━━━━━━━━━━━━━━━━", "🗓 <b>PHÂN TÍCH KHUNG THỜI GIAN</b>"]

    if session == "morning":
        lines += [
            "📌 <b>Hôm nay:</b> Phiên sáng — Chờ phản ứng vùng mở cửa, theo dõi khối lượng đầu phiên",
            f"📌 <b>Tuần này:</b> VN-Index cần giữ {1800 if price > 1800 else 1760:.0f} để giữ xu hướng",
            "📌 <b>Tháng 6:</b> Giai đoạn điều chỉnh sau đỉnh lịch sử — thị trường đang tìm vùng cân bằng mới",
        ]
    else:
        lines += [
            f"📌 <b>Hôm nay:</b> Đóng cửa {price:,.2f} — {'Tích cực' if pct_val > 0 else 'Tiêu cực' if pct_val < 0 else 'Trung lập'}",
            f"📌 <b>Tuần này:</b> {'Xu hướng tích lũy, chờ tín hiệu rõ hơn' if abs(pct_val) < 1 else 'Biến động mạnh, quản trị rủi ro là ưu tiên'}",
            "📌 <b>Tháng 6:</b> Rủi ro vĩ mô toàn cầu (Fed, căng thẳng địa chính trị) — khối ngoại vẫn bán ròng",
        ]

    # ── Phần 6: Dự báo 2 tuần
    lines += ["", "━━━━━━━━━━━━━━━━━━━━", "🔮 <b>DỰ BÁO 2 TUẦN TỚI</b>",
              forecast_2weeks(price, trend["bias"])]

    # ── Phần 7: Lời khuyên
    lines += ["", "━━━━━━━━━━━━━━━━━━━━", stock_advice(price, trend["bias"])]

    # ── Phần 8: Tin tức
    news = fetch_cafef_news()
    vietstock = fetch_vietstock_analysis()
    if news or vietstock:
        lines += ["", "━━━━━━━━━━━━━━━━━━━━", "📰 <b>TIN TỨC NỔI BẬT</b>"]
        for item in (news + vietstock)[:4]:
            lines.append(f"• <a href='{item['url']}'>{item['title']}</a>")

    # ── Phần 9: Nguồn dữ liệu
    lines += [
        "", "━━━━━━━━━━━━━━━━━━━━",
        "🔗 <b>NGUỒN DỮ LIỆU</b>",
        "• <a href='https://iboard.ssi.com.vn/'>SSI iBoard</a> — Giá real-time, khối lượng",
        "• <a href='https://vn.investing.com/indices/vn-index'>Investing.com VN</a> — Giá & biến động",
        "• <a href='https://cafef.vn/thi-truong-chung-khoan.chn'>CafeF</a> — Tin tức thị trường",
        "• <a href='https://vietstock.vn/chu-de/nhan-dinh-thi-truong.htm'>Vietstock</a> — Nhận định phân tích",
        "• <a href='https://vneconomy.vn/chung-khoan.htm'>VnEconomy</a> — Tin kinh tế vĩ mô",
        "• <a href='https://www.hsx.vn/'>HOSE Official</a> — Dữ liệu chính thức sàn",
    ]

    lines += ["", "━━━━━━━━━━━━━━━━━━━━",
              "⚠️ <i>Bot phân tích tự động — không phải tư vấn đầu tư chính thức. DYOR!</i>"]

    return "\n".join(lines)


# ─── GỬI TELEGRAM ────────────────────────────────────────────────────────────
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    r = requests.post(url, json=payload, timeout=15)
    if r.status_code == 200:
        print("✅ Đã gửi Telegram thành công!")
    else:
        print(f"❌ Lỗi Telegram: {r.status_code} — {r.text}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    now = datetime.now(VN_TZ)
    hour = now.hour

    # GitHub Actions sẽ trigger 2 lần:
    # 7:00 ICT = 00:00 UTC → session morning
    # 16:30 ICT = 09:30 UTC → session afternoon
    if hour < 12:
        session = "morning"
    else:
        session = "afternoon"

    # Bỏ qua cuối tuần (thị trường đóng)
    if now.weekday() >= 5:
        print(f"📅 Cuối tuần ({now.strftime('%A')}) — thị trường đóng, không gửi báo cáo.")
    else:
        print(f"🚀 Đang tạo báo cáo phiên {session.upper()}...")
        report = build_report(session)
        print(report)
        send_telegram(report)
