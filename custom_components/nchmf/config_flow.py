"""Config flow cho NCHMF: chọn tâm trên bản đồ (mặc định nhà HA) -> chọn trạm gần."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import async_discover_stations
from .const import (
    CONF_LAT,
    CONF_LON,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

CONF_LOCATION = "location"
CONF_STATION = "station"


def _center_schema(hass: HomeAssistant, lat=None, lon=None, name_default=""):
    """Bước 1: bản đồ chọn tâm (mặc định nhà HA) + tên tuỳ chọn."""
    lat = lat if lat is not None else hass.config.latitude
    lon = lon if lon is not None else hass.config.longitude
    return vol.Schema(
        {
            vol.Required(
                CONF_LOCATION,
                default={"latitude": lat, "longitude": lon},
            ): LocationSelector(),
            vol.Optional(CONF_NAME, default=name_default): str,
        }
    )


def _station_schema(stations: list[dict], default: str | None = None):
    """Bước 2: dropdown các trạm gần nhất (value = 'lat,lon')."""
    options = [
        SelectOptionDict(
            value=f"{s['lat']},{s['lon']}",
            label=f"{s['name']} ({s['distance_km']} km)",
        )
        for s in stations
    ]
    return vol.Schema(
        {
            vol.Required(
                CONF_STATION,
                default=default or options[0]["value"],
            ): SelectSelector(
                SelectSelectorConfig(
                    options=options, mode=SelectSelectorMode.LIST
                )
            )
        }
    )


class NchmfConfigFlow(ConfigFlow, domain=DOMAIN):
    """Xử lý luồng thêm / cấu hình lại địa điểm qua UI."""

    VERSION = 2

    def __init__(self) -> None:
        self._name: str = ""
        self._stations: list[dict] = []
        self._reconfigure_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NchmfOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_center_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._reconfigure_entry = self._get_reconfigure_entry()
        return await self._async_center_step("reconfigure", user_input)

    async def _async_center_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Bước 1 (dùng chung user + reconfigure): chọn tâm rồi dò trạm gần."""
        errors: dict[str, str] = {}
        entry = self._reconfigure_entry

        if user_input is not None:
            loc = user_input[CONF_LOCATION]
            lat = round(float(loc["latitude"]), 5)
            lon = round(float(loc["longitude"]), 5)
            self._name = user_input.get(CONF_NAME, "").strip()
            try:
                self._stations = await async_discover_stations(self.hass, lat, lon)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Không dò được trạm gần %s,%s", lat, lon)
                errors["base"] = "cannot_connect"
            else:
                if not self._stations:
                    errors["base"] = "no_stations"
                else:
                    return await self.async_step_station()

        lat_def = entry.data.get(CONF_LAT) if entry else None
        lon_def = entry.data.get(CONF_LON) if entry else None
        name_def = entry.data.get(CONF_NAME, "") if entry else ""
        return self.async_show_form(
            step_id=step_id,
            data_schema=_center_schema(self.hass, lat_def, lon_def, name_def),
            errors=errors,
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Bước 2: chọn trạm gần nhất -> lưu toạ độ trạm."""
        entry = self._reconfigure_entry

        if user_input is not None:
            lat_s, lon_s = user_input[CONF_STATION].split(",")
            lat, lon = round(float(lat_s), 5), round(float(lon_s), 5)
            station = next(
                (s for s in self._stations if s["lat"] == lat and s["lon"] == lon),
                None,
            )
            title = self._name or (station["name"] if station else "NCHMF")
            unique_id = f"{lat},{lon}"
            data = {CONF_LAT: lat, CONF_LON: lon, CONF_NAME: title}

            if entry is not None:
                if any(
                    e.entry_id != entry.entry_id and e.unique_id == unique_id
                    for e in self._async_current_entries()
                ):
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry, title=title, unique_id=unique_id, data=data
                )

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="station", data_schema=_station_schema(self._stations)
        )


class NchmfOptionsFlow(OptionsFlow):
    """Đổi chu kỳ cập nhật."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_MINUTES,
                        max=MAX_SCAN_INTERVAL_MINUTES,
                        step=5,
                        unit_of_measurement="phút",
                        mode=NumberSelectorMode.BOX,
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
