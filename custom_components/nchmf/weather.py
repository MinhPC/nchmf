"""Weather entity cho NCHMF (dữ liệu từ API KTTV theo lat/lon)."""
from __future__ import annotations

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    # Daily (10 ngày) + Hourly (4 mốc 1/7/13/19h HÔM NAY). Spinner của tab Hourly
    # chỉ xảy ra khi forecast RỖNG -> async_forecast_hourly LUÔN trả đủ 4 mốc
    # (KHÔNG lọc mốc quá khứ) nên không bao giờ rỗng -> không quay vòng. (Lỗi cũ
    # ở 2.6.0 do _future_only lọc hết mốc cuối ngày -> rỗng -> spinner.)
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )
    # Mảng 4 mốc trong ngày (today_points) cho card tự render -> đừng ghi recorder.
    _unrecorded_attributes = frozenset({"today_points"})

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
    def native_visibility(self):
        # Tầm nhìn xa (km) từ quan trắc; None khi API không có -> HA ẩn trường này.
        return self._current.get("visibility")

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
            # Phường thật của điểm quan trắc (StationName), tách với tên trạm gần nhất.
            "observation_ward": cur.get("obs_ward"),
            "observation_time": cur.get("obs_time"),
            "visibility": cur.get("visibility"),
            # 4 mốc trong ngày (1/7/13/19h) của KTTV để card TỰ render diễn biến
            # hôm nay — KHÔNG đẩy vào tab Hourly của HA (tránh spinner khi mốc đã qua).
            "today_points": self._today_points(),
        }

    def _today_points(self) -> list[dict]:
        """4 mốc dự báo trong ngày (giờ 1/7/13/19) rút gọn cho card hiển thị.

        Kèm đủ độ ẩm/gió/mưa/mây để card hiện diễn biến hôm nay chi tiết.
        """
        out: list[dict] = []
        for h in (self.coordinator.data or {}).get("hourly", []):
            out.append(
                {
                    "hour": h.get("hour"),
                    "datetime": h.get("datetime"),
                    "temp": h.get("temp"),
                    "condition": h.get("condition"),
                    "condition_text": h.get("condition_text"),
                    "humidity": h.get("humidity"),
                    "pop": h.get("pop"),
                    "precipitation": h.get("precipitation"),
                    "wind_speed": h.get("wind_speed"),  # m/s thô
                    "wind_dir": h.get("wind_dir"),  # nhãn VN
                    "wind_bearing": h.get("wind_bearing"),  # độ
                    "cloud": h.get("cloud"),
                    "icon": h.get("icon"),
                }
            )
        return out

    def _forecast(self, key: str) -> list[Forecast]:
        records = (self.coordinator.data or {}).get(key, [])
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
        # LUÔN trả đủ 4 mốc 1/7/13/19h (kể cả mốc đã qua) -> không bao giờ rỗng
        # -> tab Hourly không quay vòng. KHÔNG lọc mốc quá khứ (đó là lỗi 2.6.0).
        return self._forecast("hourly")

    @callback
    def _handle_coordinator_update(self) -> None:
        # Ghi state hiện tại + đẩy forecast tới các card đang subscribe.
        # WeatherEntity.async_update_listeners là COROUTINE và bắt buộc có
        # tham số forecast_types -> phải truyền None (mọi loại) và bọc trong
        # async_create_task (đang ở @callback đồng bộ nên không await được).
        super()._handle_coordinator_update()
        self.hass.async_create_task(self.async_update_listeners(None))
