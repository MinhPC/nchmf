"""Sensor phụ trợ cho NCHMF: nhiệt độ, độ ẩm, gió hiện tại + mảng 10 ngày qua."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_URL, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NchmfTemp(coordinator, entry),
            NchmfHumidity(coordinator, entry),
            NchmfWind(coordinator, entry),
            NchmfPastTemps(coordinator, entry),
        ]
    )


class _Base(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator, entry: ConfigEntry, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "NCHMF",
            "model": "Web scrape",
            "configuration_url": entry.data.get(CONF_URL),
        }

    @property
    def _data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def _current(self) -> dict:
        return self._data.get("current", {}) or {}


class NchmfTemp(_Base):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "temperature", "Nhiệt độ")

    @property
    def native_value(self):
        return self._current.get("temp")


class NchmfHumidity(_Base):
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "humidity", "Độ ẩm")

    @property
    def native_value(self):
        return self._current.get("humidity")


class NchmfWind(_Base):
    _attr_device_class = SensorDeviceClass.WIND_SPEED
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfSpeed.METERS_PER_SECOND

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "wind_speed", "Gió")

    @property
    def native_value(self):
        return self._current.get("wind_speed")

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "wind_dir": self._current.get("wind_dir"),
            "wind_bearing": self._current.get("wind_bearing"),
        }


class NchmfPastTemps(_Base):
    """Mảng nhiệt độ 10 ngày qua (mỗi 3h) để vẽ chart (apexcharts data_generator)."""

    _attr_icon = "mdi:chart-line"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "past_temps", "Nhiệt độ 10 ngày qua")

    @property
    def native_value(self):
        temps = self._data.get("past_temps", [])
        return temps[-1] if temps else None

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "temperatures": self._data.get("past_temps", []),
            "times": self._data.get("past_times", []),
        }
