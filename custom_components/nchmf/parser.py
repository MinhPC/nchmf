"""Parse HTML thô của trang nchmf thành dữ liệu có cấu trúc.

Hàm parse_html chạy trong executor (đồng bộ, không đụng event loop).
"""
from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from homeassistant.util import dt as dt_util


def map_condition(text: str) -> str:
    """Map mô tả tiếng Việt của nchmf -> mã điều kiện chuẩn của Home Assistant."""
    c = (text or "").lower()
    if "dông" in c or "dong" in c:
        return "lightning-rainy"
    if "mưa" in c:
        return "rainy"
    if "sương mù" in c or "mù" in c:
        return "fog"
    if "nhiều mây" in c:
        return "cloudy"
    if "ít mây" in c:
        return "sunny"
    if "nắng" in c:
        return "sunny"
    if "mây" in c:
        return "partlycloudy"
    return "partlycloudy"


# Hướng gió tiếng Việt -> độ (0-360, hướng gió THỔI TỪ, theo la bàn).
# Xếp tổ hợp 2 chữ trước để "đông bắc" khớp trước "đông"/"bắc".
_WIND_BEARINGS = [
    ("đông bắc", 45),
    ("đông nam", 135),
    ("tây bắc", 315),
    ("tây nam", 225),
    ("bắc", 0),
    ("đông", 90),
    ("nam", 180),
    ("tây", 270),
]


def wind_bearing(text: str) -> int | None:
    """Map 'Gió đông bắc' -> 45. None nếu không nhận ra hướng."""
    c = (text or "").lower()
    for name, deg in _WIND_BEARINGS:
        if name in c:
            return deg
    return None


def _int(text: str) -> int | None:
    m = re.search(r"-?\d+", text or "")
    return int(m.group()) if m else None


def _wind_speed(text: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*m/s", text or "")
    return float(m.group(1).replace(",", ".")) if m else None


def _parse_block(block) -> dict:
    """Đọc một khối (hiện tại / hôm nay / đêm nay)."""
    values: dict[str, str] = {}
    for li in block.select("ul.list-info-wt li"):
        label_el = li.select_one(".uk-width-1-4")
        value_el = li.select_one(".uk-width-3-4")
        if not label_el or not value_el:
            continue
        label = label_el.get_text(" ", strip=True)
        value = value_el.get_text(" ", strip=True).lstrip(":").strip()
        values[label] = value

    time_el = block.select_one(".time-update")
    update_time = ""
    if time_el:
        update_time = (
            time_el.get_text(" ", strip=True).replace("Cập nhật:", "").strip()
        )

    cond_text = values.get("Thời tiết", "")
    wind_raw = values.get("Hướng gió", "")
    wind_dir = ""
    dir_match = re.search(r"(Gió[^-]+?)\s*-", wind_raw)
    if dir_match:
        wind_dir = dir_match.group(1).strip()

    return {
        "temp": _int(values.get("Nhiệt độ", "")),
        "humidity": _int(values.get("Độ ẩm", "")),
        "wind_speed": _wind_speed(wind_raw),
        "wind_dir": wind_dir,
        "wind_bearing": wind_bearing(wind_dir or wind_raw),
        "condition_text": cond_text,
        "condition": map_condition(cond_text) if cond_text else None,
        "update_time": update_time,
    }


def parse_html(raw: bytes | str) -> dict:
    """Trả về dict dữ liệu thời tiết đã cấu trúc hoá."""
    if isinstance(raw, bytes):
        html = raw.decode("utf-8", "replace")
    else:
        html = raw

    soup = BeautifulSoup(html, "html.parser")

    loc_el = soup.select_one(".tt-news")
    location = loc_el.get_text(" ", strip=True) if loc_el else "Đà Nẵng"

    content = soup.select_one(".content-news")
    if content is None:
        raise ValueError("Không tìm thấy .content-news trong trang")

    blocks = content.select(".text-weather-location")
    parsed_blocks = [_parse_block(b) for b in blocks[:3]]
    while len(parsed_blocks) < 3:
        parsed_blocks.append({})

    current, today, night = parsed_blocks[0], parsed_blocks[1], parsed_blocks[2]

    # ---- Dự báo 10 ngày ----
    # Tìm trên TOÀN soup, KHÔNG scope vào .content-news: trang không đóng thẻ
    # chuẩn nên html.parser đẩy các .item-days-wt ra ngoài .content-news
    # (scope vào content sẽ ra rỗng -> forecast trống -> card quay vòng mãi).
    forecast: list[dict] = []
    for item in soup.select(".item-days-wt"):
        date_el = item.select_one(".date-wt")
        hi_el = item.select_one(".large-temp")
        lo_el = item.select_one(".small-temp")  # phần tử đầu = nhiệt độ thấp
        text_el = item.select_one(".text-temp")
        if not date_el or not hi_el:
            continue

        span = date_el.select_one("span")
        date_str = span.get_text(strip=True) if span else ""
        weekday = date_el.get_text(" ", strip=True)
        if date_str:
            weekday = weekday.replace(date_str, "").strip()

        try:
            d = datetime.strptime(date_str, "%d/%m/%Y")
            iso = dt_util.start_of_local_day(d).isoformat()
        except ValueError:
            continue

        cond_text = text_el.get_text(" ", strip=True) if text_el else ""
        forecast.append(
            {
                "datetime": iso,
                "weekday": weekday,
                "date": date_str,
                "temperature": _int(hi_el.get_text(strip=True)),
                "templow": _int(lo_el.get_text(strip=True)) if lo_el else None,
                "condition": map_condition(cond_text),
                "condition_text": cond_text,
            }
        )

    # ---- Mảng nhiệt độ 10 ngày qua (từ script Highcharts) ----
    past_temps: list[int] = []
    past_times: list[str] = []
    data_match = re.search(r"data:\s*\[([-\d,\s]+)\]", html)
    if data_match:
        past_temps = [
            int(x) for x in re.findall(r"-?\d+", data_match.group(1))
        ]
    cats_match = re.search(r"categories:\s*\[([^\]]+)\]", html)
    if cats_match:
        past_times = re.findall(r"'([^']+)'", cats_match.group(1))

    return {
        "location": location,
        "update_time": current.get("update_time", ""),
        "current": current,
        "today": today,
        "night": night,
        "forecast": forecast,
        "past_temps": past_temps,
        "past_times": past_times,
    }
