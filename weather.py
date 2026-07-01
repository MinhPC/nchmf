"""Weather entity cho NCHMF."""
from __future__ import annotations

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    coordinator = hass.data[DOMAIN]
    async_add_entities([NchmfWeather(coordinator)])


class NchmfWeather(CoordinatorEntity, WeatherEntity):
    """Weather entity dựng từ dữ liệu scrape."""

    _attr_has_entity_name = False
    _attr_name = "NCHMF Đà Nẵng"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_weather"

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
        # async_update_listeners là @callback đồng bộ -> gọi trực tiếp,
        # KHÔNG bọc trong async_create_task (nó không phải coroutine).
        super()._handle_coordinator_update()
        self.async_update_listeners()
