"""Binary sensor cảnh báo thời tiết (Weather_War) cho NCHMF.

Bật (on) khi điểm hiện tại có cảnh báo (`warning`), tắt (off) khi không. Cho phép
tạo automation bắn thông báo khi KTTV phát cảnh báo — dữ liệu vốn đã có ở
`current["warning"]` (từ trường Weather_War của API).
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    async_add_entities([NchmfWarning(coordinator, entry)])


class NchmfWarning(CoordinatorEntity, BinarySensorEntity):
    """Cảnh báo thời tiết KTTV (on = có cảnh báo)."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_translation_key = "warning"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_warning"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "KTTV / NCHMF",
            "model": "khituongvietnam.gov.vn API",
        }

    @property
    def _current(self) -> dict:
        return (self.coordinator.data or {}).get("current", {}) or {}

    @property
    def is_on(self) -> bool:
        return bool(self._current.get("warning"))

    @property
    def extra_state_attributes(self) -> dict:
        return {"warning": self._current.get("warning")}
