"""Sensor phụ trợ cho NCHMF: nhiệt độ, độ ẩm, gió hiện tại + mảng 10 ngày qua."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
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
    async_add_entities(
        [
            NchmfTemp(coordinator),
            NchmfHumidity(coordinator),
            NchmfWind(coordinator),
            NchmfPastTemps(coordinator),
        ]
    )


class _Base(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = False

    def __init__(self, coordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_name = name

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

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "temperature", "NCHMF Đà Nẵng Nhiệt độ")

    @property
    def native_value(self):
        return self._current.get("temp")


class NchmfHumidity(_Base):
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "humidity", "NCHMF Đà Nẵng Độ ẩm")

    @property
    def native_value(self):
        return self._current.get("humidity")


class NchmfWind(_Base):
    _attr_device_class = SensorDeviceClass.WIND_SPEED
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfSpeed.METERS_PER_SECOND

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "wind_speed", "NCHMF Đà Nẵng Gió")

    @property
    def native_value(self):
        return self._current.get("wind_speed")

    @property
    def extra_state_attributes(self) -> dict:
        return {"wind_dir": self._current.get("wind_dir")}


class NchmfPastTemps(_Base):
    """Mảng nhiệt độ 10 ngày qua (mỗi 3h) để vẽ chart (apexcharts data_generator)."""

    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "past_temps", "NCHMF Đà Nẵng Nhiệt độ 10 ngày qua")

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
