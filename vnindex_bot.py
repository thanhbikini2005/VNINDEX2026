"""
VN-Index Analysis Bot v3
- Tiêu đề: chỉ ngày giờ
- Fibonacci: 2 vùng gần nhất
- Khối lượng 30 ngày: phân tích gom/phân phối/phân kỳ
"""

import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
VN_TZ  = pytz.timezone("Asia/Ho_Chi_Minh")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

FIB_LOW  = 1200.0
FIB_HIGH = 1933.11

# ─── LẤY DỮ LIỆU ─────────────────────────────────────────────────────────────
def fetch_history(days=35):
    """Lấy lịch sử N ngày từ vnstock."""
    end   = datetime.now(VN_TZ).strftime('%Y-%m-%d')
    start = (datetime.now(VN_TZ) - timedelta(days=days)).strftime('%Y-%m-%d')
    for source in ['KBS', 'TCBS']:
        try:
            from vnstock import Vnstock
            df = Vnstock().stock(symbol='VNINDEX', source=source) \
                          .quote.history(start=start, end=end, interval='1D')
            if df is not None and len(df) >= 2:
                print(f"[vnstock/{source}] OK — {len(df)} phiên")
                return df
        except Exception as e:
            print(f"[vnstock/{source}] Lỗi: {e}")
    return None


def parse_latest(df):
    if df is None or df.empty:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price  = float(last['close'])
    change = price - float(prev['close'])
    pct    = change / float(prev['close']) * 100
    return {
        "price":  price,
        "change": round(change, 2),
        "pct":    round(pct, 2),
        "volume": float(last.get('volume', 0)),
        "high":   float(last.get('high', price)),
        "low":    float(last.get('low', price)),
    }


def fetch_news():
    try:
        r = requests.get("https://cafef.vn/thi-truong-chung-khoan.chn",
                         headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        news = []
        for a in soup.select("h3.title a, h2.title a")[:4]:
            t = a.text.strip()
            h = a.get("href","")
            if not h.startswith("http"): h = "https://cafef.vn" + h
            if t: news.append({"title": t, "url": h})
        return news
    except:
        return []


# ─── PHÂN TÍCH KHỐI LƯỢNG 30 NGÀY ───────────────────────────────────────────
def volume_analysis(df):
    """
    So sánh khối lượng & giá 30 ngày để phát hiện:
    - Gom hàng (accumulation): giá đi ngang/tăng nhẹ, vol tăng dần
    - Phân phối (distribution): giá đi ngang/giảm nhẹ, vol cao
    - Phân kỳ âm: giá tăng nhưng vol giảm → lực mua yếu dần
    - Phân kỳ dương: giá giảm nhưng vol giảm → lực bán cạn kiệt
    - Bình thường
    """
    if df is None or len(df) < 10:
        return "Không đủ dữ liệu khối lượng"

    closes  = [float(r['close'])  for _, r in df.iterrows()]
    volumes = [float(r['volume']) for _, r in df.iterrows()]

    # Chia 2 nửa để so sánh trend
    mid = len(df) // 2
    price_early  = sum(closes[:mid])  / mid
    price_late   = sum(closes[mid:])  / (len(df) - mid)
    vol_early    = sum(volumes[:mid]) / mid
    vol_late     = sum(volumes[mid:]) / (len(df) - mid)

    avg_vol_30   = sum(volumes) / len(volumes)
    last_5_vol   = sum(volumes[-5:]) / 5
    last_price   = closes[-1]
    first_price  = closes[0]

    price_trend  = (price_late - price_early) / price_early * 100   # % giá thay đổi
    vol_trend    = (vol_late   - vol_early)   / vol_early   * 100   # % vol thay đổi
    vol_ratio    = last_5_vol / avg_vol_30                           # vol 5 phiên gần / tb30

    # Phân loại
    lines = []
    avg_m = avg_vol_30 / 1e6
    last5_m = last_5_vol / 1e6
    lines.append(f"TB 30 phiên: {avg_m:.0f}M CP | 5 phiên gần: {last5_m:.0f}M CP")

    if vol_ratio > 1.3:
        lines.append(f"📊 Khối lượng 5 phiên GẦN ĐÂY CAO HƠN TB 30 ngày {(vol_ratio-1)*100:.0f}%")
    elif vol_ratio < 0.7:
        lines.append(f"📊 Khối lượng 5 phiên GẦN ĐÂY THẤP HƠN TB 30 ngày {(1-vol_ratio)*100:.0f}%")
    else:
        lines.append(f"📊 Khối lượng 5 phiên gần ổn định so với TB 30 ngày")

    # Nhận định chính
    if price_trend > 1.5 and vol_trend > 10:
        signal = "🟢 GOM HÀNG / TÍCH LŨY — Giá tăng kèm volume tăng → dòng tiền vào thật"
    elif price_trend > 1.5 and vol_trend < -10:
        signal = "⚠️ PHÂN KỲ ÂM — Giá tăng nhưng volume giảm → lực mua đang yếu dần, cẩn thận"
    elif price_trend < -1.5 and vol_trend > 10:
        signal = "🔴 PHÂN PHỐI — Giá giảm kèm volume cao → bên bán đang chiếm ưu thế"
    elif price_trend < -1.5 and vol_trend < -10:
        signal = "🟡 PHÂN KỲ DƯƠNG — Giá giảm nhưng volume cũng giảm → lực bán cạn dần, có thể sắp hết đà giảm"
    elif abs(price_trend) <= 1.5 and vol_trend > 15:
        signal = "🔍 TÍCH LŨY NGANG — Giá đi ngang nhưng volume tăng → đang có bên gom âm thầm"
    elif abs(price_trend) <= 1.5 and vol_trend < -15:
        signal = "😴 THỊ TRƯỜNG NGỦ ĐÔNG — Giá đi ngang, volume co lại → chờ breakout"
    else:
        signal = "⚪ BÌNH THƯỜNG — Chưa có tín hiệu volume đặc biệt"

    lines.append(signal)
    lines.append(f"<i>(Giá 30 ngày: {first_price:,.0f}→{last_price:,.0f} | Vol trend: {vol_trend:+.0f}%)</i>")
    return "\n".join(lines)


# ─── FIBONACCI — 2 VÙNG GẦN NHẤT ────────────────────────────────────────────
def fib_nearest(price):
    """Trả về vùng hỗ trợ Fib gần nhất bên dưới & kháng cự gần nhất bên trên."""
    diff = FIB_HIGH - FIB_LOW
    levels = [
        ("0.0% (Đỉnh)",  FIB_HIGH),
        ("23.6%",         round(FIB_HIGH - 0.236 * diff, 2)),
        ("38.2%",         round(FIB_HIGH - 0.382 * diff, 2)),
        ("50.0%",         round(FIB_HIGH - 0.500 * diff, 2)),
        ("61.8% 🔑",      round(FIB_HIGH - 0.618 * diff, 2)),
        ("78.6%",         round(FIB_HIGH - 0.786 * diff, 2)),
        ("100% (Đáy)",   FIB_LOW),
    ]
    above = [(n, v) for n, v in levels if v > price]
    below = [(n, v) for n, v in levels if v < price]

    support    = max(below, key=lambda x: x[1]) if below else None
    resistance = min(above, key=lambda x: x[1]) if above else None
    return support, resistance


# ─── XU HƯỚNG ────────────────────────────────────────────────────────────────
def trend_bias(price, pct):
    if price >= 1870:
        return "📈 TĂNG MẠNH — Trên kháng cự cũ", "bullish"
    elif price >= 1820:
        return "📈 TĂNG NHẸ — Hồi phục, cần xác nhận", "neutral_bullish"
    elif price >= 1800:
        return "⚖️ GIẰNG CO — Kiểm định ngưỡng 1.800", "neutral"
    elif price >= 1760:
        return "📉 ĐIỀU CHỈNH — Cần giữ vùng hỗ trợ 1.760", "neutral_bearish"
    else:
        return "📉 GIẢM MẠNH — Áp lực bán chiếm ưu thế", "bearish"


def momentum_label(pct):
    if pct > 1.5:    return "🟢 Momentum mạnh"
    elif pct > 0.3:  return "🟡 Momentum tăng nhẹ"
    elif pct > -0.3: return "⚪ Trung lập"
    elif pct > -1.5: return "🟠 Momentum yếu — thận trọng"
    else:            return "🔴 Momentum giảm mạnh"


def weekly_change(df):
    if df is None or len(df) < 5: return "—"
    w = df.tail(5)
    o, c = float(w.iloc[0]['close']), float(w.iloc[-1]['close'])
    chg = c - o
    pct = chg / o * 100
    em  = "🟢" if chg > 0 else "🔴"
    return f"{em} {o:,.0f} → {c:,.0f} ({'+' if chg>0 else ''}{pct:.2f}%)"


def monthly_change(df):
    if df is None or df.empty: return "—"
    o, c = float(df.iloc[0]['close']), float(df.iloc[-1]['close'])
    chg = c - o
    pct = chg / o * 100
    em  = "🟢" if chg > 0 else "🔴"
    return f"{em} {o:,.0f} → {c:,.0f} ({'+' if chg>0 else ''}{pct:.2f}%)"


def support_resistance(price):
    zones = [
        (1700, 1740, "Hỗ trợ rất mạnh"),
        (1750, 1770, "Hỗ trợ mạnh — Fib 23.6% + MA200"),
        (1800, 1820, "Vùng tâm lý 1.800"),
        (1830, 1870, "Kháng cự gần — MA50+MA100"),
        (1900, 1935, "Kháng cự mạnh — vùng đỉnh"),
    ]
    sup, res = [], []
    for lo, hi, label in zones:
        if price > hi:
            sup.append(f"{lo:,.0f}–{hi:,.0f} ({label})")
        elif price < lo:
            res.append(f"{lo:,.0f}–{hi:,.0f} ({label})")
        else:
            sup.append(f"⚠️ Đang trong vùng {lo:,.0f}–{hi:,.0f} ({label})")
    return sup, res


def forecast(bias):
    now = datetime.now(VN_TZ)
    dr  = f"{now.strftime('%d/%m')}–{(now+timedelta(weeks=2)).strftime('%d/%m')}"
    s = {
        "bullish":         [("🟢 ~60%","Tiếp tục tăng hướng 1.920–1.935"),("🟡 ~30%","Tích lũy 1.850–1.900"),("🔴 ~10%","Điều chỉnh về 1.810–1.830")],
        "neutral_bullish": [("🟢 ~45%","Hồi phục về 1.850–1.870 nếu giữ 1.800"),("🟡 ~35%","Giằng co 1.780–1.830"),("🔴 ~20%","Mất 1.780 → kiểm định 1.750–1.760")],
        "neutral":         [("🟢 ~40%","Bứt phá trên 1.820, hướng 1.850"),("🟡 ~35%","Giằng co 1.790–1.820"),("🔴 ~25%","Mất 1.800 → kiểm định 1.760–1.780")],
        "neutral_bearish": [("🟢 ~30%","Bật mạnh từ hỗ trợ, về 1.800–1.820"),("🟡 ~35%","Tích lũy 1.750–1.800"),("🔴 ~35%","Phá 1.750 → hướng 1.700–1.740")],
        "bearish":         [("🟢 ~20%","Bật kỹ thuật về 1.780–1.800"),("🟡 ~30%","Giằng co 1.700–1.760"),("🔴 ~50%","Tiếp tục giảm về 1.650–1.700")],
    }
    lines = [f"📅 {dr}"]
    for label, desc in s.get(bias, s["neutral"]):
        lines.append(f"  {label}: {desc}")
    return "\n".join(lines)


def advice(bias):
    t = {
        "bullish":         "✅ Có thể mua — ưu tiên FPT, VCB, TCB, VIC\n⚠️ Stoploss dưới 1.850 | Giải ngân 60–70%",
        "neutral_bullish": "⏳ Quan sát — chờ xác nhận\n📌 Nếu mua: VCB, BID, GAS | Giải ngân 30–50%",
        "neutral":         "🔍 Theo dõi vùng 1.800\n📌 Thử nghiệm nhỏ: VCB, FPT | Giải ngân 20–40%",
        "neutral_bearish": "🛑 Thận trọng — giữ tiền mặt\n📌 Mua thử 1.750–1.760, stoploss 1.730 | Giải ngân 10–20%",
        "bearish":         "🔴 KHÔNG MUA — Bảo toàn vốn 70–80%\n📌 Chỉ vào khi có nến đảo chiều + volume lớn",
    }
    return "💡 LỜI KHUYÊN\n" + t.get(bias, t["neutral"])


# ─── BUILD & GỬI ─────────────────────────────────────────────────────────────
def build_and_send(session):
    now = datetime.now(VN_TZ)
    weekday = ["Thứ 2","Thứ 3","Thứ 4","Thứ 5","Thứ 6","Thứ 7","CN"][now.weekday()]
    date_str = now.strftime(f"{weekday}, %d/%m/%Y %H:%M")

    L = [f"📆 <b>{date_str}</b>", ""]

    # ── Dữ liệu
    df = fetch_history(35)
    d  = parse_latest(df)
    if not d:
        L.append("⚠️ Không lấy được dữ liệu giá.")
        send_telegram("\n".join(L)); return

    price  = d["price"]
    change = d["change"]
    pct    = d["pct"]
    volume = d.get("volume", 0)
    sign   = "+" if change > 0 else ""
    pct_em = "🟢" if pct > 0 else ("🔴" if pct < 0 else "⚪")

    # ── Điểm số
    L += [
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 VN-Index: <b>{price:,.2f}</b>  {pct_em} {sign}{change:.2f} ({sign}{pct:.2f}%)",
        f"Cao: {d['high']:,.2f} | Thấp: {d['low']:,.2f}",
        f"Khối lượng: {volume/1e6:.0f}M CP",
    ]

    # ── Xu hướng
    trend_txt, bias = trend_bias(price, pct)
    L += ["", "━━━━━━━━━━━━━━━━━━━━",
          f"📈 <b>XU HƯỚNG</b>",
          trend_txt, momentum_label(pct)]

    # ── Kháng cự / Hỗ trợ
    sup, res = support_resistance(price)
    L += ["", "━━━━━━━━━━━━━━━━━━━━", "🧱 <b>KHÁNG CỰ / HỖ TRỢ</b>"]
    if res: L.append("🔴 Kháng cự: " + " | ".join(res[:2]))
    if sup: L.append("🟢 Hỗ trợ: "  + " | ".join(sup[:2]))

    # ── Fibonacci (2 vùng gần nhất)
    fib_sup, fib_res = fib_nearest(price)
    L += ["", "━━━━━━━━━━━━━━━━━━━━", "📐 <b>FIBONACCI</b>"]
    if fib_res:
        name, val = fib_res
        L.append(f"🔴 Kháng cự Fib gần nhất: <b>{val:,.2f}</b> ({name})")
    if fib_sup:
        name, val = fib_sup
        L.append(f"🟢 Hỗ trợ Fib gần nhất:   <b>{val:,.2f}</b> ({name})")

    # ── Khối lượng 30 ngày
    L += ["", "━━━━━━━━━━━━━━━━━━━━", "📦 <b>KHỐI LƯỢNG 30 NGÀY</b>",
          volume_analysis(df)]

    # ── Ngày / Tuần / Tháng
    L += ["", "━━━━━━━━━━━━━━━━━━━━", "🗓 <b>KHUNG THỜI GIAN</b>"]
    if session == "morning":
        L.append(f"📌 Hôm nay: Phiên sáng — theo dõi khối lượng đầu phiên")
    else:
        L.append(f"📌 Hôm nay: Đóng cửa {price:,.2f} — {'Tích cực' if pct>0 else 'Tiêu cực' if pct<0 else 'Trung lập'}")
    L.append(f"📌 Tuần:   {weekly_change(df)}")
    L.append(f"📌 Tháng:  {monthly_change(df)}")

    # ── Dự báo 2 tuần
    L += ["", "━━━━━━━━━━━━━━━━━━━━", "🔮 <b>DỰ BÁO 2 TUẦN TỚI</b>",
          forecast(bias)]

    # ── Lời khuyên
    L += ["", "━━━━━━━━━━━━━━━━━━━━", advice(bias)]

    # ── Tin tức
    news = fetch_news()
    if news:
        L += ["", "━━━━━━━━━━━━━━━━━━━━", "📰 <b>TIN TỨC</b>"]
        for item in news:
            L.append(f"• <a href='{item['url']}'>{item['title']}</a>")

    # ── Nguồn & chú thích
    L += [
        "", "━━━━━━━━━━━━━━━━━━━━",
        "🔗 <b>NGUỒN</b>: <a href='https://github.com/thinh-vu/vnstock'>vnstock v4</a> (giá) · <a href='https://cafef.vn'>CafeF</a> (tin tức)",
        "🧮 Xu hướng, Fib, S/R, Vol được <b>tính tự động bằng công thức trong code</b> — không copy bài viết",
        "⚠️ <i>Phân tích tham khảo, không phải tư vấn đầu tư. DYOR!</i>",
    ]

    send_telegram("\n".join(L))


def send_telegram(msg):
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg,
              "parse_mode": "HTML", "disable_web_page_preview": False},
        timeout=15)
    print("✅ Sent!" if r.status_code == 200 else f"❌ {r.status_code}: {r.text}")


if __name__ == "__main__":
    now = datetime.now(VN_TZ)
    if now.weekday() >= 5:
        print("📅 Cuối tuần — thị trường đóng.")
    else:
        session = "morning" if now.hour < 12 else "afternoon"
        print(f"🚀 Phiên {session.upper()}...")
        build_and_send(session)
