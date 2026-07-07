"""Chuyển JSON của WeatherApiService (khituongvietnam.gov.vn) -> dữ liệu có cấu trúc.

`transform` là hàm THUẦN (pure), không đụng event loop và không phụ thuộc HA
ngoài `homeassistant.util.dt` -> test được ngoài Home Assistant (xem CLAUDE.md mục 9).
"""
from __future__ import annotations

import math
import re
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
    # "Mây thay đổi" = mây biến động, nắng ngắt quãng -> partlycloudy, KHÔNG phải
    # sunny (dù có chữ "nắng" đứng sau) -> phải xét trước nhánh "nắng".
    if "thay đổi" in c or "mây rải rác" in c:
        return "partlycloudy"
    if "ít mây" in c:
        return "sunny"
    if "quang" in c:  # "trời quang"
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


# Hướng gió TIẾNG VIỆT -> độ (la bàn 16 hướng), cho chuỗi Wind của quan trắc
# ("Gió nam đông nam - tốc độ: 1 m/s"). Xếp cụm 3 chữ trước 2 chữ trước 1 chữ.
_WIND_BEARINGS_VN = [
    ("bắc đông bắc", 22), ("đông đông bắc", 67), ("đông đông nam", 112),
    ("nam đông nam", 157), ("nam tây nam", 202), ("tây tây nam", 247),
    ("tây tây bắc", 292), ("bắc tây bắc", 337),
    ("đông bắc", 45), ("đông nam", 135), ("tây nam", 225), ("tây bắc", 315),
    ("bắc", 0), ("đông", 90), ("nam", 180), ("tây", 270),
]


def wind_bearing_vn(label: str):
    """'nam đông nam' -> 157. None nếu không nhận ra."""
    c = (label or "").lower()
    for phrase, deg in _WIND_BEARINGS_VN:
        if phrase in c:
            return deg
    return None


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
            "warning": (f.get("Weather_War") or "").strip() or None,
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
        "location": (station.get("Name") or "").strip() or "NCHMF",
        "province": (station.get("ProvinceName") or "").strip(),
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


def _wind_from_text(text: str):
    """'Gió nam đông nam - tốc độ: 1 m/s' -> (speed:float|None, dir_label, bearing)."""
    speed = None
    m = re.search(r"tốc\s*độ\s*:?\s*([\d.,]+)\s*m/s", text or "")
    if m:
        speed = float(m.group(1).replace(",", "."))
    dir_label = ""
    dm = re.search(r"[Gg]ió\s+(.+?)\s*-\s*tốc", text or "")
    if dm:
        dir_label = dm.group(1).strip()
    return speed, dir_label, wind_bearing_vn(dir_label)


def parse_obs(payload) -> dict:
    """JSON quan trắc thời gian thực (api/wetherlocal) -> dict 'current'.

    Trả {} nếu thiếu nhiệt độ (coi như không có quan trắc -> fallback forecast).
    Khoá khớp với điểm hourly để merge đè lên forecast.
    """
    o = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(o, dict):
        return {}
    temp = o.get("Current_Temp")
    if temp is None:
        return {}
    text = o.get("Weather_Text") or ""
    speed, wdir, bearing = _wind_from_text(o.get("Wind") or "")
    icon = o.get("Icon")
    return {
        "temp": _round_int(temp),
        "humidity": _round_int(o.get("Humidity")),
        "wind_speed": speed,
        "wind_dir": wdir,
        "wind_bearing": bearing,
        "precipitation": o.get("Rainfall"),
        "condition": map_condition(text) if text else None,
        "condition_text": text,
        "icon": (ICON_BASE + icon) if icon else None,
        "obs_station": (o.get("Name") or "").strip(),
        "obs_time": o.get("TimeObservation"),
    }


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Khoảng cách đường chim bay (km) giữa hai điểm lat/lon."""
    r1, r2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(r1) * math.cos(r2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def sample_points(lat: float, lon: float, rings=(2.0, 4.0)) -> list[tuple[float, float]]:
    """Điểm tâm + các vòng (bán kính km) theo 8 hướng, để dò trạm lân cận.

    API chỉ trả TRẠM GẦN NHẤT cho mỗi lat/lon, nên phải quét quanh tâm để lộ
    các trạm phường kế bên (mỗi phường ~2km). Trả list (lat, lon).
    """
    pts = [(lat, lon)]
    cos_lat = math.cos(math.radians(lat)) or 1e-9
    for r_km in rings:
        dlat = r_km / 111.0
        dlon = r_km / (111.0 * cos_lat)
        for ang in range(0, 360, 45):
            a = math.radians(ang)
            pts.append((lat + dlat * math.cos(a), lon + dlon * math.sin(a)))
    return pts


def rank_stations(lat: float, lon: float, stations: list[dict], limit: int = 5) -> list[dict]:
    """Gom trạm theo StationID (khử trùng), xếp theo khoảng cách tới (lat, lon).

    `stations` là list các dict Station thô từ API. Trả tối đa `limit` phần tử
    dạng {id, name, province, lat, lon, distance_km} đã sắp gần→xa.
    """
    seen: dict[str, dict] = {}
    for s in stations:
        if not s:
            continue
        sid = s.get("StationID")
        slat, slon = s.get("StationLat"), s.get("StationLon")
        if sid is None or slat is None or slon is None or sid in seen:
            continue
        seen[sid] = {
            "id": sid,
            "name": (s.get("Name") or "").strip(),
            "province": s.get("ProvinceName") or "",
            "lat": round(float(slat), 5),
            "lon": round(float(slon), 5),
            "distance_km": round(haversine_km(lat, lon, float(slat), float(slon)), 1),
        }
    return sorted(seen.values(), key=lambda x: x["distance_km"])[:limit]
