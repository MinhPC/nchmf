"""NCHMF weather integration (config entry, chọn địa điểm qua UI)."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_URL, DOMAIN, SCAN_INTERVAL_MINUTES, USER_AGENT
from .parser import parse_html

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["weather", "sensor"]


async def async_fetch_raw(hass: HomeAssistant, url: str) -> bytes:
    """Tải HTML thô của trang nchmf (cert hợp lệ nên verify SSL bình thường)."""
    session = async_get_clientsession(hass)
    async with asyncio.timeout(30):
        async with session.get(
            url, headers={"User-Agent": USER_AGENT}
        ) as resp:
            resp.raise_for_status()
            return await resp.read()


class NchmfCoordinator(DataUpdateCoordinator):
    """Fetch + parse trang nchmf, chia sẻ cho weather và sensor."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
            config_entry=entry,
        )
        self._url = entry.data[CONF_URL]

    async def _async_update_data(self) -> dict:
        try:
            raw = await async_fetch_raw(self.hass, self._url)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Lỗi tải trang nchmf: {err}") from err

        try:
            return await self.hass.async_add_executor_job(parse_html, raw)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Lỗi phân tích trang nchmf: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Nạp một config entry (một địa điểm)."""
    coordinator = NchmfCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Gỡ config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload khi entry đổi (ví dụ đổi tên)."""
    await hass.config_entries.async_reload(entry.entry_id)
