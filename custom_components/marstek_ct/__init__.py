"""The Marstek CT Meter integration."""
from __future__ import annotations
from datetime import timedelta
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import MarstekCtApi
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
# Die BINARY_SENSOR-Plattform wird hier wieder entfernt
PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Marstek CT Meter from a config entry."""
    api = MarstekCtApi(
        host=entry.data["host"],
        device_type=entry.data.get("device_type", "HMG-50"),
        battery_mac=entry.data.get("battery_mac", "001122334455"),
        ct_mac=entry.data["ct_mac"],
        ct_type=entry.data.get("ct_type", "HME-4"),
    )

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            data = await hass.async_add_executor_job(api.fetch_data)
            if "error" in data:
                raise UpdateFailed(f"API error: {data['error']}")
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="marstek_ct_sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
