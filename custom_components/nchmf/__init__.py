"""NCHMF weather integration (config entry, chọn địa điểm qua UI)."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    ISSUE_NO_DATA,
    USER_AGENT,
)
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
        minutes = entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(minutes=minutes),
            config_entry=entry,
        )
        self._url = entry.data[CONF_URL]

    async def _async_update_data(self) -> dict:
        try:
            raw = await async_fetch_raw(self.hass, self._url)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Lỗi tải trang nchmf: {err}") from err

        try:
            data = await self.hass.async_add_executor_job(parse_html, raw)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Lỗi phân tích trang nchmf: {err}") from err

        self._check_health(data)
        return data

    def _check_health(self, data: dict) -> None:
        """Tạo/xoá repair issue: parse OK nhưng thiếu dữ liệu lõi = site đổi layout."""
        issue_id = f"{ISSUE_NO_DATA}_{self.config_entry.entry_id}"
        healthy = (
            data.get("current", {}).get("temp") is not None
            or bool(data.get("forecast"))
        )
        if healthy:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        else:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_NO_DATA,
                translation_placeholders={
                    "name": self.config_entry.title,
                    "url": self._url,
                },
            )


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
