"""Config flow for Marstek CT Meter integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, MIN_SCAN_INTERVAL
from .api import MarstekCtApi, CannotConnect, InvalidAuth

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Optional("battery_mac", default="001122334455"): str,
        vol.Required("ct_mac"): str,
        vol.Required("device_type_prefix", default="HMG"): vol.In(["HMG", "HMB", "HMA", "HMK"]),
        vol.Required("device_type_number", default="50"): str,
        vol.Required("ct_type", default="HME-4"): vol.In(["HME-4", "HME-3"]),
    }
)

async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, any]:
    """Prüft die Benutzereingaben auf Gültigkeit."""
    api = MarstekCtApi(
        host=data["host"],
        device_type=data["device_type"],
        battery_mac=data["battery_mac"],
        ct_mac=data["ct_mac"],
        ct_type=data["ct_type"],
    )
    result = await hass.async_add_executor_job(api.test_connection)
    if "error" in result:
        error_msg = result["error"]
        if "Timeout" in error_msg:
            raise CannotConnect(error_msg)
        else:
            raise InvalidAuth(error_msg)
    return {"title": f"Marstek CT {data['host']}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Verwaltet den Konfigurations-Flow."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Behandelt den ersten Schritt des Flows."""
        errors = {}
        if user_input is not None:
            clean_ct_mac = user_input["ct_mac"].replace(":", "").replace("-", "").strip()
            clean_battery_mac = user_input.get("battery_mac", "").replace(":", "").replace("-", "").strip()
            if not clean_battery_mac:
                clean_battery_mac = "001122334455"

            final_data = user_input.copy()
            final_data["ct_mac"] = clean_ct_mac
            final_data["battery_mac"] = clean_battery_mac
            final_data["device_type"] = f"{user_input['device_type_prefix']}-{user_input['device_type_number']}"

            del final_data["device_type_prefix"]
            del final_data["device_type_number"]

            # Unique ID gebildet aus beiden bereinigten MACs
            unique_id = f'{clean_ct_mac.lower()}_{clean_battery_mac.upper()}'
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, final_data)
                return self.async_create_entry(title=info["title"], data=final_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unerwarteter Fehler bei der Validierung")
                errors["base"] = "unknown"
        
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return MarstekCtOptionsFlow(config_entry)


class MarstekCtOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Marstek CT Meter."""

    #def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
    #    """Initialize options flow."""
    #    self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> dict:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        options_schema = vol.Schema({
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=current_interval,
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=300)),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema
        )
