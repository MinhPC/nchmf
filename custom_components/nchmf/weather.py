"""Weather entity cho NCHMF."""
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

from .const import ATTRIBUTION, CONF_URL, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NchmfWeather(coordinator, entry)])


class NchmfWeather(CoordinatorEntity, WeatherEntity):
    """Weather entity dựng từ dữ liệu scrape."""

    _attr_has_entity_name = True
    _attr_name = None  # entity chính -> lấy tên theo device
    _attr_attribution = ATTRIBUTION
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_weather"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "NCHMF",
            "model": "Web scrape",
            "configuration_url": entry.data.get(CONF_URL),
        }

    @property
    def _current(self) -> dict:
        return (self.coordinator.data or {}).get("current", {}) or {}

    @property
    def condition(self) -> str | None:
        return self._current.get("condition")

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
        return {
            "location": data.get("location"),
            "condition_text": self._current.get("condition_text"),
            "wind_dir": self._current.get("wind_dir"),
            "update_time": data.get("update_time"),
        }

    async def async_forecast_daily(self) -> list[Forecast]:
        out: list[Forecast] = []
        for d in (self.coordinator.data or {}).get("forecast", []):
            out.append(
                Forecast(
                    datetime=d["datetime"],
                    condition=d["condition"],
                    native_temperature=d["temperature"],
                    native_templow=d["templow"],
                )
            )
        return out

    @callback
    def _handle_coordinator_update(self) -> None:
        # Ghi state hiện tại + đẩy forecast tới các card đang subscribe.
        # WeatherEntity.async_update_listeners là COROUTINE và bắt buộc có
        # tham số forecast_types -> phải truyền None (mọi loại) và bọc trong
        # async_create_task (đang ở @callback đồng bộ nên không await được).
        super()._handle_coordinator_update()
        self.hass.async_create_task(self.async_update_listeners(None))
