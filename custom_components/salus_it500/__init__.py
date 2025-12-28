"""The Salus iT500 integration."""
import logging
import voluptuous as vol
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery

# The DOMAIN should match the domain in your `configuration.yaml`
DOMAIN = "salus_it500"
_LOGGER = logging.getLogger(__name__)

# Configuration constants
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_NAME = "name"
CONF_DEVICEID = "device_id"

# Define the configuration schema
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_NAME): cv.string,                
                vol.Required(CONF_DEVICEID): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Salus iT500 integration from configuration.yaml."""
    # Extract the configuration
    conf = config.get(DOMAIN)
    if conf is None:
        _LOGGER.error("Salus iT500 configuration not found in configuration.yaml")
        return False

    # Retrieve username, password, and name
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    name = conf[CONF_NAME]
    device_id = conf[CONF_DEVICEID]

    _LOGGER.debug("Setting up Salus iT500 with username: %s, name: %s, device_id: %s", username, name, device_id)

    # Create an instance of the climate integration from the file
    # Assuming that you will import the climate integration from the file you've provided
    hass.data[DOMAIN] = {
        "username": username,
        "password": password,
        "name": name,
        "device_id": device_id,
        # You can initialize the integration here, e.g.:
        # "client": SalusIT500(username, password, name),
    }

    # Forward the device setup to the climate platform
    hass.async_create_task(
        discovery.async_load_platform(
            hass, "climate", DOMAIN, {"device_id": device_id}, config
        )
    )

    # Any other setup logic goes here

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Salus iT500 from a config entry (for future use with UI-based config)."""
    return await async_setup(hass, entry.data)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.info("Unloading Salus iT500 integration")
    return True
