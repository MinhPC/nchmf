"""Diagnostics cho NCHMF (Settings -> ... -> Download diagnostics)."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_URL, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Xuất trạng thái coordinator + dữ liệu đã parse để chẩn đoán."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry": {
            "title": entry.title,
            "url": entry.data.get(CONF_URL),
            "options": dict(entry.options),
        },
        "last_update_success": coordinator.last_update_success,
        "update_interval_seconds": (
            coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None
        ),
        "data": coordinator.data,
    }
