"""Config flow cho NCHMF: chọn tỉnh (dropdown) hoặc dán URL, tự kiểm tra."""
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
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import async_fetch_raw
from .const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_URL,
    DOMAIN,
    INDEX_URL,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
)
from .parser import parse_html, parse_provinces

_LOGGER = logging.getLogger(__name__)


async def _validate(hass, url: str) -> str:
    """Fetch + parse URL. Trả về tên địa điểm. Raise nếu không hợp lệ."""
    raw = await async_fetch_raw(hass, url)
    data = await hass.async_add_executor_job(parse_html, raw)
    return data.get("location") or "NCHMF"


async def _fetch_provinces(hass) -> dict[str, str]:
    """{url: tên tỉnh} từ trang index. Rỗng nếu tải/parse lỗi (sẽ fallback nhập URL)."""
    try:
        raw = await async_fetch_raw(hass, INDEX_URL)
        return await hass.async_add_executor_job(parse_provinces, raw)
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Không tải được danh sách tỉnh, dùng ô nhập URL")
        return {}


def _url_field(provinces: dict[str, str], default: str):
    """Dropdown tỉnh (cho phép dán URL) nếu có danh sách, ngược lại ô text."""
    if not provinces:
        return str
    options = [
        SelectOptionDict(value=url, label=name)
        for url, name in sorted(provinces.items(), key=lambda kv: kv[1])
    ]
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            custom_value=True,  # vẫn cho phép dán URL tỉnh không có trong list
            sort=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _schema(provinces, url_default=DEFAULT_URL, name_default=""):
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=url_default): _url_field(
                provinces, url_default
            ),
            vol.Optional(CONF_NAME, default=name_default): str,
        }
    )


class NchmfConfigFlow(ConfigFlow, domain=DOMAIN):
    """Xử lý luồng thêm / cấu hình lại địa điểm qua UI."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NchmfOptionsFlow()

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

        provinces = await _fetch_provinces(self.hass)
        return self.async_show_form(
            step_id="user", data_schema=_schema(provinces), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Đổi URL / tên của một entry đã có."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].strip()
            if any(
                e.entry_id != entry.entry_id and e.data.get(CONF_URL) == url
                for e in self._async_current_entries()
            ):
                errors["base"] = "already_configured"
            else:
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

        provinces = await _fetch_provinces(self.hass)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(
                provinces, entry.data[CONF_URL], entry.data.get(CONF_NAME, "")
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
