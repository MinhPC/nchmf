"""NCHMF weather integration (config entry, chọn địa điểm theo lat/lon qua UI)."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .const import (
    API_URL,
    CONF_LAT,
    CONF_LON,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    ISSUE_NO_DATA,
    OBS_URL,
    USER_AGENT,
)
from .parser import parse_obs, pick_current, rank_stations, sample_points, transform

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["weather", "sensor", "binary_sensor"]


async def async_fetch_json(hass: HomeAssistant, lat, lon) -> dict:
    """Gọi API dự báo theo lat/lon (cert hợp lệ -> verify SSL bình thường)."""
    session = async_get_clientsession(hass)
    async with asyncio.timeout(30):
        async with session.get(
            API_URL,
            params={"lat": lat, "lon": lon},
            headers={"User-Agent": USER_AGENT},
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


async def async_fetch_obs(hass: HomeAssistant, lat, lon):
    """Gọi API quan trắc thời gian thực (trạm gần nhất). Param 'Lat'/'Lon' viết hoa."""
    session = async_get_clientsession(hass)
    async with asyncio.timeout(30):
        async with session.get(
            OBS_URL,
            params={"Lat": lat, "Lon": lon},
            headers={"User-Agent": USER_AGENT},
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


async def async_discover_stations(
    hass: HomeAssistant, lat, lon, limit: int = 5
) -> list[dict]:
    """Dò các trạm/phường gần (lat, lon) để người dùng chọn trong config flow.

    API chỉ trả trạm gần nhất mỗi lần gọi -> quét đồng thời tâm + 2 vòng quanh
    tâm, khử trùng theo StationID, xếp theo khoảng cách. Trả tối đa `limit` trạm
    dạng {id, name, province, lat, lon, distance_km}.
    """
    session = async_get_clientsession(hass)

    async def _one(la, lo):
        try:
            async with asyncio.timeout(15):
                async with session.get(
                    API_URL,
                    params={"lat": la, "lon": lo},
                    headers={"User-Agent": USER_AGENT},
                ) as resp:
                    resp.raise_for_status()
                    return (await resp.json()).get("Station")
        except Exception:  # noqa: BLE001
            return None

    points = sample_points(lat, lon)
    results = await asyncio.gather(*(_one(la, lo) for la, lo in points))
    return rank_stations(lat, lon, [s for s in results if s], limit)


class NchmfCoordinator(DataUpdateCoordinator):
    """Gọi + chuẩn hoá JSON API, chia sẻ cho weather và sensor."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        minutes = entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(minutes=minutes),
            config_entry=entry,
        )
        self._lat = entry.data[CONF_LAT]
        self._lon = entry.data[CONF_LON]

    async def _async_update_data(self) -> dict:
        # Forecast (bắt buộc) + quan trắc thời gian thực (tuỳ chọn) gọi SONG SONG.
        forecast_payload, obs_payload = await asyncio.gather(
            async_fetch_json(self.hass, self._lat, self._lon),
            async_fetch_obs(self.hass, self._lat, self._lon),
            return_exceptions=True,
        )

        if isinstance(forecast_payload, Exception):
            raise UpdateFailed(f"Lỗi gọi API KTTV: {forecast_payload}")

        try:
            data = transform(forecast_payload)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Lỗi chuẩn hoá JSON KTTV: {err}") from err

        # 'current': ưu tiên QUAN TRẮC thật (trạm gần nhất); nếu thiếu -> dùng điểm
        # dự báo gần giờ hiện tại. PoP/giờ luôn lấy từ forecast (quan trắc không có).
        now = dt_util.now()
        fc_current = pick_current(data["hourly"], now.hour)
        obs: dict = {}
        if not isinstance(obs_payload, Exception):
            try:
                obs = parse_obs(obs_payload)
            except Exception:  # noqa: BLE001
                obs = {}
        # Chỉ đè field CÓ giá trị của quan trắc lên forecast: field quan trắc bị
        # thiếu (vd gió "lặng" không parse ra tốc độ, Weather_Text rỗng) sẽ KHÔNG
        # xoá mất giá trị forecast hợp lệ (tránh gió/điều kiện hiện tại về None).
        if obs:
            data["current"] = {
                **fc_current,
                **{k: v for k, v in obs.items() if v is not None},
            }
            data["current_source"] = "observation"
        else:
            data["current"] = fc_current
            data["current_source"] = "forecast"
        data["update_time"] = self._current_time(now, obs, data["current"])
        self._check_health(data)
        return data

    @staticmethod
    def _current_time(now, obs: dict, current: dict) -> str | None:
        """Thời điểm của 'current': giờ QUAN TRẮC thật nếu có (obs_time là giờ trong
        ngày), ngược lại datetime của điểm dự báo gần giờ hiện tại."""
        obs_time = obs.get("obs_time") if obs else None
        if obs_time is not None:
            try:
                return now.replace(
                    hour=int(obs_time), minute=0, second=0, microsecond=0
                ).isoformat()
            except (ValueError, TypeError):
                pass
        return current.get("datetime")

    def _check_health(self, data: dict) -> None:
        """Tạo/xoá repair issue: gọi OK nhưng thiếu dữ liệu lõi = API đổi schema."""
        issue_id = f"{ISSUE_NO_DATA}_{self.config_entry.entry_id}"
        healthy = (
            bool(data.get("daily"))
            or data.get("current", {}).get("temp") is not None
        )
        if healthy:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        else:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_NO_DATA,
                translation_placeholders={
                    "name": self.config_entry.title,
                    "coords": f"{self._lat}, {self._lon}",
                },
            )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Chuyển entry bản cũ (v1, lưu CONF_URL scrape) sang v2 (lat/lon).

    Không suy ra được toạ độ từ URL tỉnh cũ -> dùng toạ độ nhà HA làm mặc định;
    người dùng dùng Reconfigure (bản đồ) để chỉnh đúng phường. Nhờ vậy sau khi
    cập nhật code, entry cũ TỰ nạp được thay vì crash (thiếu CONF_LAT).
    """
    if entry.version >= 2:
        return True

    lat = round(float(hass.config.latitude), 5)
    lon = round(float(hass.config.longitude), 5)
    hass.config_entries.async_update_entry(
        entry,
        data={CONF_LAT: lat, CONF_LON: lon, CONF_NAME: entry.title},
        unique_id=f"{lat},{lon}",
        version=2,
    )
    _LOGGER.warning(
        "Đã chuyển entry NCHMF '%s' sang toạ độ nhà HA (%s, %s) do đổi sang API "
        "theo lat/lon. Dùng Reconfigure (bản đồ) để chọn đúng phường.",
        entry.title,
        lat,
        lon,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Nạp một config entry (một địa điểm)."""
    coordinator = NchmfCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Gỡ config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload khi entry đổi (ví dụ đổi tên / toạ độ / scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)
