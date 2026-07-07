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
    EntityCategory,
    UnitOfPrecipitationDepth,
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
            NchmfPrecip(coordinator, entry),
            NchmfCloud(coordinator, entry),
            NchmfWindDir(coordinator, entry),
            NchmfCondition(coordinator, entry),
            NchmfObsStation(coordinator, entry),
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
            "manufacturer": "Minh Phan",
            "model": "Vietnam Weather",
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


class NchmfPrecip(_Base):
    """Lượng mưa (mm) — quan trắc (Rainfall) nếu có, else forecast (Prec)."""

    _attr_device_class = SensorDeviceClass.PRECIPITATION
    # Lượng mưa TÍCH LUỸ (mm), không phải giá trị tức thời -> TOTAL cho đúng ngữ
    # nghĩa long-term statistics (device_class precipitation khuyến nghị TOTAL).
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfPrecipitationDepth.MILLIMETERS

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "precipitation")

    @property
    def native_value(self):
        return self._current.get("precipitation")


class NchmfCloud(_Base):
    """Lượng mây (%) — Cloud (0..1) quy đổi sang phần trăm."""

    _attr_translation_key = "cloud"
    _attr_icon = "mdi:weather-cloudy"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "cloud")

    @property
    def native_value(self):
        c = self._current.get("cloud")
        if c is None:
            return None
        # Cloud thường là 0..1; nếu đã là % (>1) thì giữ nguyên.
        return round(c * 100) if c <= 1 else round(c)


class NchmfWindDir(_Base):
    """Hướng gió (nhãn tiếng Việt); độ ở attr wind_bearing."""

    _attr_translation_key = "wind_direction"
    _attr_icon = "mdi:compass-outline"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "wind_direction")

    @property
    def native_value(self):
        return self._current.get("wind_dir") or None

    @property
    def extra_state_attributes(self) -> dict:
        return {"wind_bearing": self._current.get("wind_bearing")}


class NchmfCondition(_Base):
    """Điều kiện thời tiết (mô tả tiếng Việt của KTTV)."""

    _attr_translation_key = "condition"
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "condition")

    @property
    def native_value(self):
        return self._current.get("condition_text") or None

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "condition": self._current.get("condition"),  # mã HA
            "icon_url": self._current.get("icon"),  # icon KTTV thật
        }


class NchmfObsStation(_Base):
    """Trạm quan trắc gần nhất (nguồn 'hiện tại'). Sensor chẩn đoán."""

    _attr_translation_key = "observation_station"
    _attr_icon = "mdi:map-marker-radius-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "observation_station")

    @property
    def native_value(self):
        return self._current.get("obs_station") or None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "observation_time": self._current.get("obs_time"),
            "current_source": data.get("current_source"),
            # Phường thật của điểm quan trắc (StationName), khác tên trạm gần nhất.
            "observation_ward": self._current.get("obs_ward"),
        }
