"""Weather entity cho NCHMF (dữ liệu từ API KTTV theo lat/lon)."""
from __future__ import annotations

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NchmfWeather(coordinator, entry)])


class NchmfWeather(CoordinatorEntity, WeatherEntity):
    """Weather entity dựng từ JSON API KTTV."""

    _attr_has_entity_name = True
    _attr_name = None  # entity chính -> lấy tên theo device
    _attr_attribution = ATTRIBUTION
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_weather"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Minh Phan",
            "model": "Vietnam Weather",
        }

    @property
    def _current(self) -> dict:
        return (self.coordinator.data or {}).get("current", {}) or {}

    @property
    def condition(self) -> str | None:
        cond = self._current.get("condition")
        # Trời quang ban đêm -> clear-night để ra icon mặt trăng (HA không tự đổi).
        if cond == "sunny" and self._is_night():
            return "clear-night"
        return cond

    def _is_night(self) -> bool:
        sun = self.hass.states.get("sun.sun")
        return sun is not None and sun.state == "below_horizon"

    @property
    def native_temperature(self):
        return self._current.get("temp")

    @property
    def humidity(self):
        return self._current.get("humidity")

    @property
    def native_wind_speed(self):
        return self._current.get("wind_speed")

    @property
    def native_wind_bearing(self):
        return self._current.get("wind_bearing")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        cur = self._current
        return {
            "location": data.get("location"),
            "province": data.get("province"),
            "condition_text": cur.get("condition_text"),
            "wind_dir": cur.get("wind_dir"),
            # Tốc độ gió THÔ (m/s) — HA quy đổi native_wind_speed sang đơn vị hệ thống
            # (thường km/h) ở attr wind_speed; attr này giữ m/s như nguồn/trang chủ.
            "wind_speed_ms": cur.get("wind_speed"),
            "precipitation_probability": cur.get("pop"),
            "precipitation": cur.get("precipitation"),
            "cloud": cur.get("cloud"),
            "icon_url": cur.get("icon"),  # icon thật của KTTV cho hiện tại
            "warning": cur.get("warning"),  # cảnh báo (Weather_War), None nếu không có
            "update_time": data.get("update_time"),
            # Nguồn 'hiện tại': quan trắc thật (trạm gần nhất) hay dự báo.
            "current_source": data.get("current_source"),
            "observation_station": cur.get("obs_station"),
            "observation_time": cur.get("obs_time"),
        }

    def _forecast(self, key: str, drop_past: bool = False) -> list[Forecast]:
        records = (self.coordinator.data or {}).get(key, [])
        if drop_past:
            records = self._future_only(records)
        out: list[Forecast] = []
        for d in records:
            if not d.get("datetime"):
                continue
            out.append(
                Forecast(
                    datetime=d["datetime"],
                    condition=d.get("condition"),
                    native_temperature=d.get("temperature", d.get("temp")),
                    native_templow=d.get("templow"),
                    humidity=d.get("humidity"),
                    native_wind_speed=d.get("wind_speed"),
                    wind_bearing=d.get("wind_bearing"),
                    precipitation_probability=d.get("pop"),
                    native_precipitation=d.get("precipitation"),
                )
            )
        return out

    async def async_forecast_daily(self) -> list[Forecast]:
        return self._forecast("daily")

    async def async_forecast_hourly(self) -> list[Forecast]:
        # Nguồn chỉ có 4 điểm 1/7/13/19 của HÔM NAY -> bỏ điểm đã qua để card
        # không hiển thị giờ quá khứ. Giữ điểm của giờ hiện tại (mốc >= đầu giờ).
        return self._forecast("hourly", drop_past=True)

    @staticmethod
    def _future_only(records: list[dict]) -> list[dict]:
        """Lọc bỏ điểm có datetime trước giờ hiện tại; nếu lọc hết (cuối ngày mọi
        điểm đã qua) thì GIỮ NGUYÊN để tránh forecast rỗng làm card quay vòng."""
        floor = dt_util.now().replace(minute=0, second=0, microsecond=0)
        future = []
        for d in records:
            when = dt_util.parse_datetime(d.get("datetime") or "")
            if when is None or when >= floor:
                future.append(d)
        return future or records

    @callback
    def _handle_coordinator_update(self) -> None:
        # Ghi state hiện tại + đẩy forecast tới các card đang subscribe.
        # WeatherEntity.async_update_listeners là COROUTINE và bắt buộc có
        # tham số forecast_types -> phải truyền None (mọi loại) và bọc trong
        # async_create_task (đang ở @callback đồng bộ nên không await được).
        super()._handle_coordinator_update()
        self.hass.async_create_task(self.async_update_listeners(None))
