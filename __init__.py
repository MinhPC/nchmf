"""NCHMF weather integration (YAML setup, cố định Đà Nẵng)."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, SCAN_INTERVAL_MINUTES, URL, USER_AGENT
from .parser import parse_html

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["weather", "sensor"]


class NchmfCoordinator(DataUpdateCoordinator):
    """Fetch + parse trang nchmf, chia sẻ cho weather và sensor."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict:
        try:
            async with asyncio.timeout(30):
                # ssl=False: site .gov.vn lỗi chuỗi chứng chỉ, cần bỏ qua verify
                async with self._session.get(
                    URL, ssl=False, headers={"User-Agent": USER_AGENT}
                ) as resp:
                    resp.raise_for_status()
                    raw = await resp.read()
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Lỗi tải trang nchmf: {err}") from err

        try:
            return await self.hass.async_add_executor_job(parse_html, raw)
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Lỗi phân tích trang nchmf: {err}") from err


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Nạp integration khi có key `nchmf:` trong configuration.yaml."""
    if DOMAIN not in config:
        return True

    coordinator = NchmfCoordinator(hass)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        _LOGGER.error("Không lấy được dữ liệu nchmf lần đầu; sẽ thử lại theo lịch")

    hass.data[DOMAIN] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            discovery.async_load_platform(hass, platform, DOMAIN, {}, config)
        )

    return True
