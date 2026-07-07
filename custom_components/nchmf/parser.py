"""Chuyển JSON của WeatherApiService (khituongvietnam.gov.vn) -> dữ liệu có cấu trúc.

`transform` là hàm THUẦN (pure), không đụng event loop và không phụ thuộc HA
ngoài `homeassistant.util.dt` -> test được ngoài Home Assistant (xem CLAUDE.md mục 9).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

from .const import ICON_BASE

# ForecastHour == 99 là bản ghi TỔNG HỢP THEO NGÀY (Tmax/Tmin);
# các giá trị khác (1/7/13/19) là điểm dự báo TRONG NGÀY (T2m).
DAILY_HOUR = 99


def map_condition(text: str) -> str:
    """Map mô tả tiếng Việt (Weather_Text) -> mã điều kiện chuẩn của Home Assistant."""
    c = (text or "").lower()
    # "không mưa" = KHÔNG có mưa -> đừng để chuỗi con "mưa" kích hoạt nhánh rainy.
    # (API mô tả "Nhiều mây, không mưa" -> phải ra cloudy, không phải rainy)
    has_rain = "mưa" in c and "không mưa" not in c
    if has_rain and ("dông" in c or "dong" in c):
        return "lightning-rainy"
    if has_rain:
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


# 8 hướng la bàn tiếng Việt (từ Direction theo độ) để hiển thị.
_DIRS = ["Bắc", "Đông bắc", "Đông", "Đông nam", "Nam", "Tây nam", "Tây", "Tây bắc"]


def wind_direction(deg) -> str:
    """Đổi Direction (độ) -> nhãn hướng tiếng Việt. '' nếu None."""
    if deg is None:
        return ""
    return _DIRS[round(float(deg) / 45) % 8]


def _round_int(v):
    """None-safe: làm tròn về int, giữ None nếu thiếu."""
    return int(round(float(v))) if v is not None else None


def _iso_day(date_str: str | None) -> datetime | None:
    """'2026-07-07T00:00:00' -> đầu ngày theo giờ địa phương."""
    if not date_str:
        return None
    try:
        d = datetime.fromisoformat(date_str)
    except ValueError:
        return None
    return dt_util.start_of_local_day(d)


def transform(payload: dict) -> dict:
    """JSON API -> dict `coordinator.data` (xem CLAUDE.md mục 5)."""
    station = payload.get("Station") or {}
    forecasts = payload.get("Forecasts") or []

    hourly: list[dict] = []
    daily: list[dict] = []
    for f in forecasts:
        hour = f.get("ForecastHour")
        text = f.get("Weather_Text") or ""
        icon = f.get("Icon")
        base_day = _iso_day(f.get("ForecastDate"))
        common = {
            "humidity": _round_int(f.get("RH")),
            "wind_speed": f.get("Speed"),
            "wind_bearing": f.get("Direction"),
            "wind_dir": wind_direction(f.get("Direction")),
            "pop": _round_int(f.get("PoP")),
            "precipitation": f.get("Prec"),
            "cloud": f.get("Cloud"),
            "condition_text": text,
            "condition": map_condition(text),
            "icon": (ICON_BASE + icon) if icon else None,
        }
        if hour == DAILY_HOUR:
            daily.append(
                {
                    "datetime": base_day.isoformat() if base_day else None,
                    "temperature": _round_int(f.get("Tmax")),
                    "templow": _round_int(f.get("Tmin")),
                    **common,
                }
            )
        else:
            when = base_day + timedelta(hours=hour) if base_day and hour is not None else None
            hourly.append(
                {
                    "datetime": when.isoformat() if when else None,
                    "hour": hour,
                    "temp": _round_int(f.get("T2m")),
                    **common,
                }
            )

    daily.sort(key=lambda d: d["datetime"] or "")
    hourly.sort(key=lambda h: h["hour"] if h["hour"] is not None else 0)

    return {
        "location": station.get("Name") or "NCHMF",
        "province": station.get("ProvinceName") or "",
        "station_id": station.get("StationID"),
        "lat": station.get("StationLat"),
        "lon": station.get("StationLon"),
        "hourly": hourly,
        "daily": daily,
    }


def pick_current(hourly: list[dict], now_hour: int) -> dict:
    """Chọn điểm trong ngày gần giờ hiện tại nhất làm 'hiện tại'. {} nếu rỗng."""
    if not hourly:
        return {}
    return min(hourly, key=lambda h: abs((h.get("hour") or 0) - now_hour))
