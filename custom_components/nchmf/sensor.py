"""Sensor phụ trợ cho NCHMF: nhiệt độ, độ ẩm, gió, xác suất mưa (hiện tại)."""
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

from .const import ATTRIBUTION, DOMAIN


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
            NchmfPop(coordinator, entry),
        ]
    )


class _Base(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "KTTV / NCHMF",
            "model": "khituongvietnam.gov.vn API",
        }

    @property
    def _current(self) -> dict:
        return (self.coordinator.data or {}).get("current", {}) or {}


# Nhiệt độ / độ ẩm / gió: KHÔNG đặt name -> HA lấy tên theo device_class (đã
# dịch sẵn en/vi). entity_id của bản đã cài giữ nguyên (nằm trong registry).
class NchmfTemp(_Base):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "temperature")

    @property
    def native_value(self):
        return self._current.get("temp")


class NchmfHumidity(_Base):
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "humidity")

    @property
    def native_value(self):
        return self._current.get("humidity")


class NchmfWind(_Base):
    _attr_device_class = SensorDeviceClass.WIND_SPEED
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfSpeed.METERS_PER_SECOND

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "wind_speed")

    @property
    def native_value(self):
        return self._current.get("wind_speed")

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "wind_dir": self._current.get("wind_dir"),
            "wind_bearing": self._current.get("wind_bearing"),
        }


class NchmfPop(_Base):
    """Xác suất mưa (PoP) của điểm dự báo gần giờ hiện tại."""

    _attr_translation_key = "precipitation_probability"
    _attr_icon = "mdi:weather-rainy"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "pop")

    @property
    def native_value(self):
        return self._current.get("pop")

    @property
    def extra_state_attributes(self) -> dict:
        return {"precipitation": self._current.get("precipitation")}
