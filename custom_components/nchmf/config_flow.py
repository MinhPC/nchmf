"""Config flow cho NCHMF: chọn địa điểm trên bản đồ (lat/lon), tự kiểm tra API."""
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
)

from . import async_fetch_json
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
from .parser import transform

_LOGGER = logging.getLogger(__name__)

CONF_LOCATION = "location"


async def _validate(hass: HomeAssistant, lat, lon) -> str:
    """Gọi API tại lat/lon. Trả tên phường/trạm. Raise nếu không hợp lệ."""
    payload = await async_fetch_json(hass, lat, lon)
    data = transform(payload)
    return data.get("location") or "NCHMF"


def _schema(hass: HomeAssistant, lat=None, lon=None, name_default=""):
    """Bản đồ chọn toạ độ (mặc định nhà HA) + tên tuỳ chọn."""
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


def _coords(user_input: dict) -> tuple[float, float]:
    """Lấy (lat, lon) làm tròn 5 chữ số từ LocationSelector."""
    loc = user_input[CONF_LOCATION]
    return round(float(loc["latitude"]), 5), round(float(loc["longitude"]), 5)


class NchmfConfigFlow(ConfigFlow, domain=DOMAIN):
    """Xử lý luồng thêm / cấu hình lại địa điểm qua UI."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NchmfOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            lat, lon = _coords(user_input)
            await self.async_set_unique_id(f"{lat},{lon}")
            self._abort_if_unique_id_configured()
            try:
                location = await _validate(self.hass, lat, lon)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Không gọi được API KTTV: %s,%s", lat, lon)
                errors["base"] = "cannot_connect"
            else:
                title = user_input.get(CONF_NAME, "").strip() or location
                return self.async_create_entry(
                    title=title,
                    data={CONF_LAT: lat, CONF_LON: lon, CONF_NAME: title},
                )

        return self.async_show_form(
            step_id="user", data_schema=_schema(self.hass), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Đổi toạ độ / tên của một entry đã có."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            lat, lon = _coords(user_input)
            unique_id = f"{lat},{lon}"
            if any(
                e.entry_id != entry.entry_id and e.unique_id == unique_id
                for e in self._async_current_entries()
            ):
                errors["base"] = "already_configured"
            else:
                try:
                    location = await _validate(self.hass, lat, lon)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Không gọi được API KTTV: %s,%s", lat, lon)
                    errors["base"] = "cannot_connect"
                else:
                    title = user_input.get(CONF_NAME, "").strip() or location
                    return self.async_update_reload_and_abort(
                        entry,
                        title=title,
                        unique_id=unique_id,
                        data={CONF_LAT: lat, CONF_LON: lon, CONF_NAME: title},
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(
                self.hass,
                entry.data.get(CONF_LAT),
                entry.data.get(CONF_LON),
                entry.data.get(CONF_NAME, ""),
            ),
            errors=errors,
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
