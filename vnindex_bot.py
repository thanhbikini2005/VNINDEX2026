"""
VN-Index Analysis Bot v2
Dùng thư viện vnstock (v4) để lấy dữ liệu chính xác.
Gửi báo cáo Telegram 7h sáng & 16h30 chiều mỗi ngày làm việc.
"""

import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# ─── LẤY DỮ LIỆU VNINDEX ─────────────────────────────────────────────────────
def fetch_vnindex():
    """Lấy dữ liệu VN-Index từ vnstock (nguồn KBS - không cần auth)."""
    try:
        from vnstock import Vnstock
        stock = Vnstock().stock(symbol='VNINDEX', source='KBS')
        # Lấy giá hiện tại / lịch sử gần nhất
        today = datetime.now(VN_TZ).strftime('%Y-%m-%d')
        week_ago = (datetime.now(VN_TZ) - timedelta(days=7)).strftime('%Y-%m-%d')
        df = stock.quote.history(start=week_ago, end=today, interval='1D')
        if df is not None and not df.empty:
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else None
            price = float(last['close'])
            change = price - float(prev['close']) if prev is not None else 0
            pct = (change / float(prev['close']) * 100) if prev is not None else 0
            volume = float(last.get('volume', 0))
            return {
                "price": price,
                "change": round(change, 2),
                "pct": round(pct, 2),
                "volume": volume,
                "high": float(last.get('high', price)),
                "low":  float(last.get('low', price)),
                "source": "vnstock/KBS"
            }
    except Exception as e:
        print(f"[vnstock/KBS] Lỗi: {e}")

    # Fallback 1: TCBS
    try:
        from vnstock import Vnstock
        stock = Vnstock().stock(symbol='VNINDEX', source='TCBS')
        today = datetime.now(VN_TZ).strftime('%Y-%m-%d')
        week_ago = (datetime.now(VN_TZ) - timedelta(days=7)).strftime('%Y-%m-%d')
        df = stock.quote.history(start=week_ago, end=today, interval='1D')
        if df is not None and not df.empty:
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else None
            price = float(last['close'])
            change = price - float(prev['close']) if prev is not None else 0
            pct = (change / float(prev['close']) * 100) if prev is not None else 0
            return {
                "price": price,
                "change": round(change, 2),
                "pct": round(pct, 2),
                "volume": float(last.get('volume', 0)),
                "high": float(last.get('high', price)),
                "low":  float(last.get('low', price)),
                "source": "vnstock/TCBS"
            }
    except Exception as e:
        print(f"[vnstock/TCBS] Lỗi: {e}")

    # Fallback 2: Scrape CafeF
    try:
        url = "https://cafef.vn/du-lieu/Ajax/PageNew/DataGradienVN30/BigTable.ashx?take=1&skip=0&filter=VNINDEX"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        item = data["Data"]["Data"][0]
        price = float(item["lastPrice"])
        change = float(item["priceChange"])
        pct = float(item["percentPriceChange"])
        return {
            "price": price, "change": change, "pct": pct,
            "volume": float(item.get("totalVolume", 0)),
            "high": float(item.get("highPrice", price)),
            "low":  float(item.get("lowPrice", price)),
            "source": "CafeF API"
        }
    except Exception as e:
        print(f"[CafeF API] Lỗi: {e}")

    return None


def fetch_breadth():
    """Lấy số mã tăng/giảm/đứng từ CafeF."""
    try:
        url = "https://cafef.vn/du-lieu/Ajax/PageNew/DataGradienVN30/BigTable.ashx?take=1&skip=0&filter=VNINDEX"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        item = data["Data"]["Data"][0]
        return {
            "advances":  item.get("advances", "?"),
            "declines":  item.get("declines", "?"),
            "nochanges": item.get("nochanges", "?"),
        }
    except:
        return {}


def fetch_weekly_data():
    """Lấy dữ liệu 1 tháng để tính tuần/tháng."""
    try:
        from vnstock import Vnstock
        stock = Vnstock().stock(symbol='VNINDEX', source='KBS')
        end = datetime.now(VN_TZ).strftime('%Y-%m-%d')
        start = (datetime.now(VN_TZ) - timedelta(days=30)).strftime('%Y-%m-%d')
        df = stock.quote.history(start=start, end=end, interval='1D')
        return df
    except Exception as e:
        print(f"[Weekly data] Lỗi: {e}")
        return None


def fetch_news():
    """Lấy tin tức từ CafeF."""
    try:
        r = requests.get("https://cafef.vn/thi-truong-chung-khoan.chn",
                         headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        news = []
        for a in soup.select("h3.title a, h2.title a")[:4]:
            title = a.text.strip()
            href  = a.get("href", "")
            if not href.startswith("http"):
                href = "https://cafef.vn" + href
            if title:
                news.append({"title": title, "url": href})
        return news
    except:
        return []


# ─── PHÂN TÍCH KỸ THUẬT ──────────────────────────────────────────────────────
FIB_LOW  = 1200.0    # Đáy tháng 4/2025
FIB_HIGH = 1933.11   # Đỉnh lịch sử

def fibonacci_levels():
    diff = FIB_HIGH - FIB_LOW
    return {
        "0.0% Đỉnh":   round(FIB_HIGH, 2),
        "23.6%":        round(FIB_HIGH - 0.236 * diff, 2),
        "38.2%":        round(FIB_HIGH - 0.382 * diff, 2),
        "50.0%":        round(FIB_HIGH - 0.500 * diff, 2),
        "61.8% 🔑":     round(FIB_HIGH - 0.618 * diff, 2),
        "78.6%":        round(FIB_HIGH - 0.786 * diff, 2),
        "100% Đáy":     round(FIB_LOW, 2),
    }


def fib_zone(price, fib):
    levels = sorted(fib.items(), key=lambda x: x[1], reverse=True)
    for i in range(len(levels) - 1):
        name, val = levels[i]
        next_name, next_val = levels[i + 1]
        if next_val <= price <= val:
            return f"Giữa Fib {next_name} ({next_val:,.0f}) ↔ {name} ({val:,.0f})"
    return "Ngoài vùng Fibonacci"


def support_resistance(price):
    zones = [
        (1700, 1740, "Hỗ trợ rất mạnh — đáy trung hạn"),
        (1750, 1770, "Hỗ trợ mạnh — Fib 23.6% + MA200"),
        (1800, 1820, "Vùng tâm lý 1.800 — S/R quan trọng"),
        (1830, 1870, "Kháng cự gần — MA50 + MA100"),
        (1900, 1935, "Kháng cự mạnh — vùng đỉnh lịch sử"),
    ]
    result = {"support": [], "resistance": []}
    for lo, hi, label in zones:
        if price > hi:
            result["support"].append(f"{lo:,.0f}–{hi:,.0f}: {label}")
        elif price < lo:
            result["resistance"].append(f"{lo:,.0f}–{hi:,.0f}: {label}")
        else:
            result["support"].append(f"⚠️ Đang trong vùng {lo:,.0f}–{hi:,.0f}: {label}")
    return result


def trend_bias(price, pct):
    if price >= 1870:
        return "📈 TĂNG MẠNH — Trên kháng cự cũ", "bullish"
    elif price >= 1820:
        return "📈 TĂNG NHẸ — Hồi phục, cần xác nhận", "neutral_bullish"
    elif price >= 1800:
        return "⚖️ GIẰNG CO — Kiểm định ngưỡng tâm lý 1.800", "neutral"
    elif price >= 1760:
        return "📉 ĐIỀU CHỈNH — Cần giữ vùng hỗ trợ 1.760", "neutral_bearish"
    else:
        return "📉 GIẢM MẠNH — Áp lực bán chiếm ưu thế", "bearish"


def momentum_label(pct):
    if pct > 1.5:   return "🟢 Momentum mạnh — dòng tiền tích cực"
    elif pct > 0.3: return "🟡 Momentum tăng nhẹ"
    elif pct > -0.3:return "⚪ Momentum trung lập"
    elif pct > -1.5:return "🟠 Momentum yếu — thận trọng"
    else:           return "🔴 Momentum giảm mạnh — cảnh báo bán"


def volume_label(volume):
    if not volume or volume == 0:
        return "Không có dữ liệu khối lượng"
    v = volume / 1e6
    if v > 600:   return f"🔥 Rất cao: {v:.0f}M CP — thị trường sôi động"
    elif v > 400: return f"🟢 Cao: {v:.0f}M CP — thanh khoản tốt"
    elif v > 250: return f"🟡 Trung bình: {v:.0f}M CP"
    else:         return f"🔴 Thấp: {v:.0f}M CP — dòng tiền co hẹp"


def weekly_summary(df):
    if df is None or len(df) < 5:
        return "Không đủ dữ liệu tuần"
    week = df.tail(5)
    w_open  = float(week.iloc[0]['close'])
    w_close = float(week.iloc[-1]['close'])
    w_high  = float(week['high'].max())
    w_low   = float(week['low'].min())
    w_chg   = w_close - w_open
    w_pct   = w_chg / w_open * 100
    emoji   = "🟢" if w_chg > 0 else "🔴"
    return (f"{emoji} Tuần: {w_open:,.2f} → {w_close:,.2f} "
            f"({'+' if w_chg>0 else ''}{w_chg:.2f} / {w_pct:+.2f}%)\n"
            f"   Cao nhất: {w_high:,.2f} | Thấp nhất: {w_low:,.2f}")


def monthly_summary(df):
    if df is None or df.empty:
        return "Không đủ dữ liệu tháng"
    m_open  = float(df.iloc[0]['close'])
    m_close = float(df.iloc[-1]['close'])
    m_high  = float(df['high'].max())
    m_low   = float(df['low'].min())
    m_chg   = m_close - m_open
    m_pct   = m_chg / m_open * 100
    emoji   = "🟢" if m_chg > 0 else "🔴"
    return (f"{emoji} Tháng: {m_open:,.2f} → {m_close:,.2f} "
            f"({'+' if m_chg>0 else ''}{m_chg:.2f} / {m_pct:+.2f}%)\n"
            f"   Cao nhất: {m_high:,.2f} | Thấp nhất: {m_low:,.2f}")


def forecast(price, bias):
    now = datetime.now(VN_TZ)
    end = now + timedelta(weeks=2)
    dr  = f"{now.strftime('%d/%m')}–{end.strftime('%d/%m/%Y')}"
    scenarios = {
        "bullish": [
            ("🟢 Tích cực ~60%", "Tiếp tục tăng, hướng đến 1.920–1.935"),
            ("🟡 Trung lập ~30%", "Tích lũy vùng 1.850–1.900"),
            ("🔴 Rủi ro ~10%",   "Điều chỉnh về 1.810–1.830"),
        ],
        "neutral_bullish": [
            ("🟢 Tích cực ~45%", "Hồi phục về 1.850–1.870 nếu giữ 1.800"),
            ("🟡 Trung lập ~35%", "Giằng co 1.780–1.830"),
            ("🔴 Rủi ro ~20%",   "Mất 1.780 → kiểm định 1.750–1.760"),
        ],
        "neutral": [
            ("🟢 Tích cực ~40%", "Bứt phá trên 1.820, hướng 1.850"),
            ("🟡 Trung lập ~35%", "Giằng co quanh 1.790–1.820"),
            ("🔴 Rủi ro ~25%",   "Mất 1.800 → kiểm định 1.760–1.780"),
        ],
        "neutral_bearish": [
            ("🟢 Tích cực ~30%", "Bật mạnh từ hỗ trợ, về 1.800–1.820"),
            ("🟡 Trung lập ~35%", "Tích lũy vùng 1.750–1.800"),
            ("🔴 Rủi ro ~35%",   "Phá 1.750 → hướng 1.700–1.740"),
        ],
        "bearish": [
            ("🟢 Tích cực ~20%", "Bật kỹ thuật về 1.780–1.800"),
            ("🟡 Trung lập ~30%", "Giằng co 1.700–1.760"),
            ("🔴 Rủi ro ~50%",   "Tiếp tục giảm về 1.650–1.700"),
        ],
    }
    lines = [f"📅 Dự báo {dr}"]
    for label, desc in scenarios.get(bias, scenarios["neutral"]):
        lines.append(f"  {label}: {desc}")
    return "\n".join(lines)


def advice(price, bias):
    tips = {
        "bullish": (
            "✅ Có thể mua — ưu tiên cổ phiếu đầu ngành thanh khoản cao\n"
            "📌 Ví dụ quan tâm: FPT, VCB, TCB, VIC, VHM\n"
            "⚠️ Stoploss dưới 1.850 | Tỷ lệ giải ngân: 60–70%"
        ),
        "neutral_bullish": (
            "⏳ Quan sát — chờ xác nhận trước khi vào mạnh\n"
            "📌 Ưu tiên cổ phiếu phòng thủ: VCB, BID, GAS, PLX\n"
            "⚠️ Không mua đuổi — chờ pullback | Tỷ lệ giải ngân: 30–50%"
        ),
        "neutral": (
            "🔍 Theo dõi vùng 1.800 — chưa nên vào mạnh\n"
            "📌 Nếu mua thử: VCB, FPT (cổ phiếu nền tảng)\n"
            "⚠️ Stoploss dưới 1.780 | Tỷ lệ giải ngân: 20–40%"
        ),
        "neutral_bearish": (
            "🛑 Thận trọng — giảm tỷ trọng hoặc giữ tiền mặt\n"
            "📌 Vùng mua thử: 1.750–1.760 với 20% vốn, stoploss 1.730\n"
            "⚠️ Ưu tiên bảo toàn | Tỷ lệ giải ngân: 10–20%"
        ),
        "bearish": (
            "🔴 KHÔNG MUA — Thị trường đang giảm mạnh\n"
            "📌 Bảo toàn vốn, nâng tiền mặt 70–80%\n"
            "⚠️ Chỉ mua khi có tín hiệu đảo chiều rõ ràng (Hammer + volume lớn)"
        ),
    }
    return "💡 LỜI KHUYÊN\n" + tips.get(bias, tips["neutral"])


# ─── BUILD BÁO CÁO ───────────────────────────────────────────────────────────
def build_report(session):
    now      = datetime.now(VN_TZ)
    weekday  = ["Thứ 2","Thứ 3","Thứ 4","Thứ 5","Thứ 6","Thứ 7","CN"][now.weekday()]
    date_str = now.strftime(f"{weekday}, %d/%m/%Y %H:%M")
    emoji    = "🌅" if session == "morning" else "🌆"
    title    = "BÁO CÁO SÁNG" if session == "morning" else "BÁO CÁO CHIỀU"

    L = [f"{emoji} <b>VN-INDEX {title}</b>", f"📆 {date_str}", ""]

    # ── Lấy dữ liệu
    d = fetch_vnindex()
    if not d:
        L.append("⚠️ Không lấy được dữ liệu. Vui lòng kiểm tra lại nguồn.")
        send_telegram("\n".join(L))
        return

    price  = d["price"]
    change = d["change"]
    pct    = d["pct"]
    volume = d.get("volume", 0)
    src    = d.get("source", "")
    pct_em = "🟢" if pct > 0 else ("🔴" if pct < 0 else "⚪")
    sign   = "+" if change > 0 else ""

    breadth = fetch_breadth()

    # ── Điểm số
    L += [
        "━━━━━━━━━━━━━━━━━━━━",
        "📊 <b>ĐIỂM SỐ</b>",
        f"VN-Index: <b>{price:,.2f}</b> điểm",
        f"Thay đổi: {pct_em} {sign}{change:.2f} ({sign}{pct:.2f}%)",
        volume_label(volume),
    ]
    if breadth:
        L.append(f"Tăng / Giảm / Đứng: {breadth.get('advances','?')} / {breadth.get('declines','?')} / {breadth.get('nochanges','?')}")
    if d.get("high") and d.get("low"):
        L.append(f"Cao: {d['high']:,.2f} | Thấp: {d['low']:,.2f}")
    L.append(f"<i>Nguồn: {src}</i>")

    # ── Xu hướng
    trend_txt, bias = trend_bias(price, pct)
    L += ["", "━━━━━━━━━━━━━━━━━━━━", "📈 <b>XU HƯỚNG</b>",
          trend_txt, momentum_label(pct)]

    # ── S/R
    sr = support_resistance(price)
    L += ["", "━━━━━━━━━━━━━━━━━━━━", "🧱 <b>KHÁNG CỰ / HỖ TRỢ</b>"]
    if sr["resistance"]:
        L.append("🔴 Kháng cự:")
        for z in sr["resistance"][:2]: L.append(f"  • {z}")
    if sr["support"]:
        L.append("🟢 Hỗ trợ:")
        for z in sr["support"][:2]: L.append(f"  • {z}")

    # ── Fibonacci
    fib = fibonacci_levels()
    L += ["", "━━━━━━━━━━━━━━━━━━━━",
          f"📐 <b>FIBONACCI</b> (Đáy {FIB_LOW:,.0f} → Đỉnh {FIB_HIGH:,.0f})"]
    for name, val in fib.items():
        marker = " ◀ BẠN ĐANG Ở ĐÂY" if abs(price - val) < 30 else ""
        L.append(f"  • {name}: {val:,.2f}{marker}")
    L.append(f"📍 {fib_zone(price, fib)}")

    # ── Ngày / Tuần / Tháng
    df_hist = fetch_weekly_data()
    L += ["", "━━━━━━━━━━━━━━━━━━━━", "🗓 <b>PHÂN TÍCH KHUNG THỜI GIAN</b>"]
    day_txt = ("Phiên sáng — theo dõi khối lượng đầu phiên"
               if session == "morning"
               else f"Đóng cửa {price:,.2f} — {'Tích cực' if pct > 0 else 'Tiêu cực' if pct < 0 else 'Trung lập'}")
    L.append(f"📌 <b>Hôm nay:</b> {day_txt}")
    L.append(f"📌 <b>Tuần:</b> {weekly_summary(df_hist)}")
    L.append(f"📌 <b>Tháng 6:</b> {monthly_summary(df_hist)}")

    # ── Dự báo
    L += ["", "━━━━━━━━━━━━━━━━━━━━", "🔮 <b>DỰ BÁO 2 TUẦN TỚI</b>",
          forecast(price, bias)]

    # ── Lời khuyên
    L += ["", "━━━━━━━━━━━━━━━━━━━━", advice(price, bias)]

    # ── Tin tức
    news = fetch_news()
    if news:
        L += ["", "━━━━━━━━━━━━━━━━━━━━", "📰 <b>TIN TỨC NỔI BẬT</b>"]
        for item in news:
            L.append(f"• <a href='{item['url']}'>{item['title']}</a>")

    # ── Nguồn
    L += [
        "", "━━━━━━━━━━━━━━━━━━━━", "🔗 <b>NGUỒN DỮ LIỆU</b>",
        "• <a href='https://github.com/thinh-vu/vnstock'>vnstock v4</a> — Dữ liệu giá chính (KBS/TCBS)",
        "• <a href='https://cafef.vn/thi-truong-chung-khoan.chn'>CafeF</a> — Breadth & Tin tức",
        "• <a href='https://vietstock.vn/chu-de/nhan-dinh-thi-truong.htm'>Vietstock</a> — Nhận định",
        "• <a href='https://vneconomy.vn/chung-khoan.htm'>VnEconomy</a> — Vĩ mô",
        "• <a href='https://www.hsx.vn/'>HOSE</a> — Sàn chính thức",
        "", "⚠️ <i>Bot phân tích tự động — không phải tư vấn đầu tư. DYOR!</i>",
    ]

    send_telegram("\n".join(L))


# ─── GỬI TELEGRAM ────────────────────────────────────────────────────────────
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }, timeout=15)
    if r.status_code == 200:
        print("✅ Đã gửi Telegram!")
    else:
        print(f"❌ Lỗi Telegram {r.status_code}: {r.text}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    now = datetime.now(VN_TZ)
    if now.weekday() >= 5:
        print(f"📅 Cuối tuần — thị trường đóng cửa.")
    else:
        session = "morning" if now.hour < 12 else "afternoon"
        print(f"🚀 Đang tạo báo cáo phiên {session.upper()}...")
        build_report(session)
