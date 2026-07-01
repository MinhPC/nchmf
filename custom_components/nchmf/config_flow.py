"""Config flow cho NCHMF: nhập URL tỉnh, tự kiểm tra bằng cách fetch + parse."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from . import async_fetch_raw
from .const import CONF_NAME, CONF_URL, DEFAULT_URL, DOMAIN
from .parser import parse_html

_LOGGER = logging.getLogger(__name__)


async def _validate(hass, url: str) -> str:
    """Fetch + parse URL. Trả về tên địa điểm. Raise nếu không hợp lệ."""
    raw = await async_fetch_raw(hass, url)
    data = await hass.async_add_executor_job(parse_html, raw)
    return data.get("location") or "NCHMF"


def _schema(url: str = DEFAULT_URL, name: str = "") -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=url): str,
            vol.Optional(CONF_NAME, default=name): str,
        }
    )


class NchmfConfigFlow(ConfigFlow, domain=DOMAIN):
    """Xử lý luồng thêm / cấu hình lại địa điểm qua UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].strip()
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            try:
                location = await _validate(self.hass, url)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Không kiểm tra được URL nchmf: %s", url)
                errors["base"] = "cannot_connect"
            else:
                title = user_input.get(CONF_NAME, "").strip() or location
                return self.async_create_entry(
                    title=title, data={CONF_URL: url, CONF_NAME: title}
                )

        return self.async_show_form(
            step_id="user", data_schema=_schema(), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Đổi URL / tên của một entry đã có."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].strip()
            try:
                location = await _validate(self.hass, url)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Không kiểm tra được URL nchmf: %s", url)
                errors["base"] = "cannot_connect"
            else:
                title = user_input.get(CONF_NAME, "").strip() or location
                return self.async_update_reload_and_abort(
                    entry,
                    title=title,
                    unique_id=url,
                    data={CONF_URL: url, CONF_NAME: title},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(
                entry.data[CONF_URL], entry.data.get(CONF_NAME, "")
            ),
            errors=errors,
        )
