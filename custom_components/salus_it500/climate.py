"""
Adds support for the Salus Thermostat units.
"""
import datetime
import time
import logging
import re
import requests
import json
import asyncio
import aiohttp

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.const import UnitOfTemperature

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.climate.const import HVACMode

# Add new constants for additional features
SUPPORT_PRESETS = ["schedule", "manual", "holiday"]
SUPPORT_HVAC_MODES = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
SUPPORT_HOLIDAY_MODE = "holiday"
SUPPORT_SCHEDULE_PROGRAM = "schedule_program"
FROST_PROTECTION_MODE = "frost_protection"

URL_LOGIN = "https://salus-it500.com/public/login.php"
URL_GET_TOKEN = "https://salus-it500.com/public/control.php"
URL_GET_DATA = "https://salus-it500.com/public/ajax_device_values.php"
URL_SET_DATA = "https://salus-it500.com/includes/set.php"

DEFAULT_NAME = "Salus Thermostat"

CONF_NAME = "name"
MIN_TEMP = 5
MAX_TEMP = 34.5
SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    # | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)
SUPPORT_PRESET = ["schedule", "manual", "holiday"]

__version__ = "1.0.0"

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Salus iT500 climate platform."""
    # Retrieve the configuration from __init__.py
    username = hass.data["salus_it500"]["username"]
    password = hass.data["salus_it500"]["password"]
    name = hass.data["salus_it500"]["name"]
    device_id = hass.data["salus_it500"]["device_id"]
    session = aiohttp.ClientSession()  # Create the session here

    # Create the climate and sensor entities
    thermostat = SalusThermostat(
        email=username,
        password=password,
        name=name,
        device_id=device_id,
        session=session,
    )
    temperature_sensor = SalusTemperatureSensor(thermostat)
    target_temperature = SalusTargetTemperatureSensor(thermostat)
    online_status = SalusOnlineBinarySensor(thermostat)
    autoOff = SalusCH1autoOff(thermostat)
    manual = SalusCH1manual(thermostat)
    schedType = SalusCH1schedType(thermostat)
    heatOnOffStatus = SalusCH1heatOnOffStatus(thermostat)
    autoMode = SalusCH1autoMode(thermostat)
    heatOnOff = SalusCH1heatOnOff(thermostat)
    frostActive = SalusCH1frostActive(thermostat)

    # Create climate entity with the retrieved data
    async_add_entities(
        [
            thermostat,
            # temperature_sensor,
            # target_temperature,
            # online_status,
            # autoOff,
            # manual,
            # schedType,
            # heatOnOffStatus,
            # autoMode,
            # heatOnOff,
            # frostActive,
        ],
        update_before_add=True,
    )


class SalusThermostat(ClimateEntity):
    def __init__(self, email, password, name=None, device_id=None, session=None):
        """Initialize the thermostat."""
        self._online = None
        self._target_temp = None
        self._current_temp = None
        self._hvac_mode = None
        self._preset_mode = None
        self._name = name
        self._username = email
        self._password = password
        self._device_id = device_id
        self._current_temperature = None
        self._target_temperature = None
        self._frost = None
        self._status = None
        self._current_operation_mode = None
        self._token = None
        self._session = session
        self._unique_id = self.name.lower() + "_" + self._device_id.lower()
        self._attr_unique_id = self._unique_id.lower()
        self._attr_supported_features = SUPPORT_FLAGS
        # Explicitly set the entity ID if needed
        self.entity_id = f"climate.{self._unique_id.lower().replace(" ", "")}"
        self._CH1autoOff = None
        self._CH1manual = None
        self._CH1autoOff = None
        self._CH1schedType = None
        self._CH1heatOnOffStatus = None
        self._CH1autoMode = None
        self._CH1heatOnOff = None
        self._CH1frostActive = None

        # Schedule an initial data fetch
        asyncio.create_task(self._get_data())

    @property
    def device_info(self):
        """Return device-specific attributes for this entity."""
        return DeviceInfo(identifiers={(self._unique_id,)}, name=self._name)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return SUPPORT_HVAC_MODES

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        return self._preset_mode

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return SUPPORT_PRESETS

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this thermostat."""
        return self._unique_id

    @property
    def should_poll(self):
        """Return if polling is required."""
        return True

    @property
    def min_temperature(self):
        """Return the minimum temperature."""
        return MIN_TEMP

    @property
    def max_temperature(self):
        """Return the maximum temperature."""
        return MAX_TEMP

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        """return current temperature"""
        return self._current_temperature

    @property
    def target_temperature(self):
        """return target temperature"""
        return self._target_temperature

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            # ... [other attributes] ...
            "online": self._online,
            "CH1autoOff": self._CH1autoOff,
            "CH1manual": self._CH1manual,
            "CH1schedType": self._CH1schedType,
            "CH1heatOnOffStatus": self._CH1heatOnOffStatus,
            "CH1autoMode": self._CH1autoMode,
            "CH1heatOnOff": self._CH1heatOnOff,
            "CH1frostActive": self._CH1frostActive,
            "operation_mode": self._current_operation_mode,
        }

    async def async_turn_on(self):
        """Turn the entity on."""        
        self._hvac_mode = HVACMode.AUTO
        headers = {"content-type": "application/x-www-form-urlencoded"}
        payload = {
            "token": self._token,
            "devId": self._device_id,
            "auto": "0",
            "auto_setZ1": "1",
        }
        try:
            async with self._session.post(URL_SET_DATA, data=payload, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.error(f"async_turn_on: Failed to post data to Salus. HTTP status code: {response.status}")
                    return
                
                _LOGGER.debug("Successfull set cmd TURN ON")
                self._current_operation_mode = "AUTO"
                
        except Exception as e:
            _LOGGER.error(f"Error Setting TURN ON. error: {e}")

    async def async_turn_off(self):
        """Turn the entity off."""
        self._hvac_mode = HVACMode.OFF        
        headers = {"content-type": "application/x-www-form-urlencoded"}
        payload = {
            "token": self._token,
            "devId": self._device_id,
            "auto": "1",
            "auto_setZ1": "1",
        }
        try:
            async with self._session.post(URL_SET_DATA, data=payload, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.error(f"async_turn_off: Failed to post data to Salus. HTTP status code: {response.status}")
                    return

                _LOGGER.debug("Successfull set cmd to TURN OFF")
                self._current_operation_mode = "OFF"

        except Exception as e:
            _LOGGER.error(f"Error Setting TURN OFF. error: {e}")

    async def async_toggle(self):
        """Toggle the entity."""
        if self._current_operation_mode == "OFF":
            await self.async_turn_on()
        elif self._current_operation_mode in ["HEAT", "OFF"]:
            await self.async_turn_off()


    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temperature = temperature
        if self._hvac_mode in [HVACMode.HEAT]:
            await self._set_temperature(temperature)
        
        if self.entity_id:  # Only call if entity is initialized
            self.async_write_ha_state()

        await self.async_update()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode, via URL commands."""        
        _LOGGER.debug(f"Setting the HVAC mode: {hvac_mode}")

        self._hvac_mode = hvac_mode
        headers = {"content-type": "application/x-www-form-urlencoded"}
        if hvac_mode == HVACMode.OFF:
            payload = {
                "token": self._token,
                "devId": self._device_id,
                "auto": "1",
                "auto_setZ1": "1",
            }
            try:
                async with self._session.post(URL_SET_DATA, data=payload, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error(f"async_set_hvac_mode: {hvac_mode} - Failed to post data to Salus. HTTP status code: {response.status}")
                        return

                    _LOGGER.debug(f"Successfull set cmd HVAC mode: {hvac_mode}")
                    self._current_operation_mode = "OFF"

            except Exception as e:
                _LOGGER.error(f"Error Setting HVAC mode. error: {e}")
        
        elif hvac_mode == HVACMode.HEAT:    # MAN mode
            payload = {
                "token": self._token,
                "devId": self._device_id,
                "tempUnit": "0",
                "current_tempZ1_set": "1",
                "current_tempZ1": self._target_temperature,
            }
            headers = {"content-type": "application/x-www-form-urlencoded"}
            try:
                async with self._session.post(URL_SET_DATA, data=payload, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error(f"async_set_hvac_mode: {hvac_mode} - Failed to post data to Salus. HTTP status code: {response.status}")
                        return
                                   
                    _LOGGER.debug(f"Successfull set cmd HVAC mode: {hvac_mode}")
                    self._current_operation_mode = "MAN"

            except Exception as e:
                _LOGGER.error(f"Error getting data: {e}")
        
        elif hvac_mode == HVACMode.AUTO:
            payload = {
                "token": self._token,
                "devId": self._device_id,
                "auto": "0",
                "auto_setZ1": "1",
            }
            try:
                async with self._session.post(URL_SET_DATA, data=payload, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error(f"async_set_hvac_mode: {hvac_mode} - Failed to post data to Salus. HTTP status code: {response.status}")
                        return
                    
                    _LOGGER.debug(f"Successfull set cmd HVAC mode: {hvac_mode}")
                    self._current_operation_mode = "AUTO"
                    
            except Exception as e:
                _LOGGER.error(f"Error Setting HVAC AUTO mode. error: {e}")

        _LOGGER.debug("HVAC mode is set.")

        # # Call async_write_ha_state() to notify HA of the new state
        if self.entity_id:  # Only call if entity is initialized
            self.async_write_ha_state()

        await self.async_update()

    async def async_set_preset_mode(self, preset_mode):
        self._preset_mode = preset_mode
        if preset_mode not in SUPPORT_PRESET:
            raise ValueError(f"Invalid preset mode: {preset_mode}")
        if preset_mode == "schedule":
            self._set_preset_schedule()
        elif preset_mode == "manual":
            self._set_preset_manual()
        elif preset_mode == "holiday":
            self._set_preset_holiday()
        elif preset_mode == "off":
            self._set_preset_off()
        self.schedule_update_ha_state(force_refresh=True)

    def set_holiday_mode(self, start_date, end_date):
        """Set the holiday mode with start and end dates."""
        # Implement the logic to set holiday mode using Salus API
        # ...

    def set_schedule_program(self, program_type, schedule=None):
        """Set the schedule program.

        :param program_type: Type of the program ('all', '5/2', 'individual')
        :param schedule: The schedule data, format depends on program_type
        """
        if program_type not in ["all", "5/2", "individual"]:
            _LOGGER.error(
                "Invalid program type. Must be 'all', '5/2', or 'individual'."
            )
            return

        if program_type == "all":
            self._set_all_days_schedule(schedule)
        elif program_type == "5/2":
            self._set_5_2_schedule(schedule)
        elif program_type == "individual":
            self._set_individual_schedule(schedule)

    def _set_all_days_schedule(self, schedule):
        """Set the same schedule for all days."""
        # Implement the logic to set the same schedule for all days using Salus API
        # ...

    def _set_5_2_schedule(self, schedule):
        """Set one schedule for weekdays and another for the weekend."""
        # Implement the logic to set a 5/2 schedule using Salus API
        # ...

    def _set_individual_schedule(self, schedule):
        """Set individual schedules for each day."""
        # Implement the logic to set individual schedules for each day using Salus API
        # ...

    def override_target_temperature(self, temperature):
        """Override the current target temperature."""
        # Implement the logic to override target temperature using Salus API
        # ...

    def set_frost_protection(self, enabled, temperature=None):
        """Enable or disable frost protection mode.

        :param enabled: Boolean indicating whether to enable or disable frost protection.
        :param temperature: The temperature to maintain when frost protection is enabled.
        """
        if enabled and temperature is not None:
            # Validate the temperature
            if temperature < MIN_TEMP or temperature > MAX_TEMP:
                _LOGGER.error(
                    "Temperature for frost protection must be between %s and %s",
                    MIN_TEMP,
                    MAX_TEMP,
                )
                return

            # Implement the logic to enable frost protection with the specified temperature using Salus API
            # ...

        elif not enabled:
            # Implement the logic to disable frost protection using Salus API
            # ...
            pass
        else:
            _LOGGER.error("Temperature must be provided to enable frost protection.")

    async def _set_temperature(self, temperature):
        """Set new target temperature, via URL commands."""
        payload = {
            "token": self._token,
            "devId": self._device_id,
            "tempUnit": "0",
            "current_tempZ1_set": "1",
            "current_tempZ1": temperature,
        }
        headers = {"content-type": "application/x-www-form-urlencoded"}
        try:
            async with self._session.post(URL_SET_DATA, data=payload, headers=headers) as response:
                if response.status != 200:
                    _LOGGER.error(
                        f"_set_temperature - Failed to post data to Salus. HTTP status code: {response.status}"
                    )
                    return
                self._target_temperature = temperature
                # self.schedule_update_ha_state(force_refresh=True)
                _LOGGER.debug("Salusfy set_temperature OK")
        except Exception as e:
            _LOGGER.error(f"Error getting data: {e}")

        await self.async_update()

    def _set_preset_schedule(self):
        """Set the thermostat to the home preset."""
        # Set the temperature and other settings for the home preset
        # using the Salus API

    def _set_preset_manual(self):
        """Set the thermostat to the away preset."""
        # Set the temperature and other settings for the away preset
        # using the Salus API

    def _set_preset_holiday(self):
        """Set the thermostat to the sleep preset."""
        # Set the temperature and other settings for the sleep preset
        # using the Salus API

    def _set_preset_off(self):
        """Set the thermostat to the off preset."""
        # Set the temperature and other settings for the sleep preset
        # using the Salus API

    async def get_token(self):
        """Get the Session Token of the Thermostat."""
        payload = {
            "IDemail": self._username,
            "password": self._password,
            "login": "Login",
            "keep_logged_in": "1",
        }
        headers = {"content-type": "application/x-www-form-urlencoded"}
        _LOGGER.debug(
            f"get_token --url_login: {URL_LOGIN}, payload: {payload}, headers: {headers}"
        )

        try:
            # Make the POST request to login and handle the response asynchronously
            async with self._session.post(
                URL_LOGIN, data=payload, headers=headers
            ) as response:
                if response.status != 200:
                    _LOGGER.error(
                        f"Failed to login to Salus iT500. HTTP status code: {response.status}"
                    )
                    return
                _LOGGER.debug("Login successful. Proceeding to fetch the token.")

                # Fetch the token using a GET request
                params = {"devId": self._device_id}
                async with self._session.get(
                    URL_GET_TOKEN, params=params
                ) as token_response:
                    if token_response.status != 200:
                        _LOGGER.error(
                            f"Failed to fetch the token. HTTP status code: {token_response.status}"
                        )
                        return

                    token_text = await token_response.text()

                    # Check if token_text is a valid string before using regex search
                    if token_text and isinstance(token_text, str):
                        result = re.search(
                            r'<input id="token" type="hidden" value="(.*)" />',
                            token_text,
                        )
                        if result:
                            self._token = result.group(1)
                            _LOGGER.debug("Successfully retrieved the token.")
                        else:
                            _LOGGER.error(
                                "Token not found in the response. Check the HTML structure."
                            )
                    else:
                        _LOGGER.error(
                            "Unexpected response format when getting the token. Expected a string."
                        )

        except aiohttp.ClientError as e:
            _LOGGER.error(f"HTTP request failed: {e}")
        except Exception as e:
            _LOGGER.error(f"Unexpected error while getting the token: {e}")

    async def _get_data(self):
        """Fetch the latest data from the Salus Thermostat."""
        # Refresh token if it's not available
        if self._token is None:
            await self.get_token()

        params = {
            "devId": self._device_id,
            "token": self._token,
            "&_": str(int(round(time.time() * 1000))),
        }

        try:
            # Make the GET request to fetch data asynchronously
            async with self._session.get(URL_GET_DATA, params=params) as response:
                if response.status != 200:
                    _LOGGER.error(
                        f"Failed to fetch data from Salus. HTTP status code: {response.status}"
                    )
                    return

                data_text = await response.text()

                # Check if data_text is a valid JSON string before attempting to parse
                if data_text:
                    try:
                        data = json.loads(data_text)
                        _LOGGER.debug(f"Salusfy get_data output: {data_text}")

                        # Check valid data
                        if data.get("CH1autoOff") != "":
                            self._online = True
                            # Parse and update device data
                            self._target_temperature = float(
                                data.get("CH1currentSetPoint", 0)
                            )
                            self._current_temperature = float(
                                data.get("CH1currentRoomTemp", 0)
                            )
                            self._frost = float(data.get("frost", 0))

                            self._CH1autoOff = data.get("CH1autoOff", 0)
                            self._CH1manual = data.get("CH1manual", 0)
                            self._CH1schedType = data.get("CH1schedType", 0)
                            self._CH1heatOnOffStatus = data.get("CH1heatOnOffStatus", 0)
                            self._CH1autoMode = data.get("CH1autoMode", 0)
                            self._CH1heatOnOff = data.get("CH1heatOnOff", 0)
                            self._CH1frostActive = data.get("CH1frostActive", 0)

                            # Update the status and operation mode
                            self._status = (
                                "ON" if data.get("CH1heatOnOffStatus") == "1" else "OFF"
                            )

                            _LOGGER.debug(f"self._CH1autoOff: {self._CH1autoOff}, self._CH1heatOnOff: {self._CH1heatOnOff}, self._CH1autoMode: {self._CH1autoMode}, self._CH1manual: {self._CH1manual}")

                            # Set HVACmode
                            if self._CH1autoOff == "1" and self._CH1heatOnOff == "1":
                                self._hvac_mode = HVACMode.OFF
                                self._current_operation_mode = "OFF"
                            
                            elif self._CH1autoOff == "0" and self._CH1heatOnOff == "0":
                                self._hvac_mode = HVACMode.AUTO                            
                                self._current_operation_mode = "AUTO"

                            elif self._CH1autoMode == "1" and self._CH1manual == "1":
                                self._hvac_mode = HVACMode.HEAT                            
                                self._current_operation_mode = "HEAT"

                            _LOGGER.debug(f"Set HVACMode: {self._hvac_mode}")

                        else:                            
                            self._online = False
                            _LOGGER.debug("Request ok, but get invalid data")
                            _LOGGER.debug(f"self._CH1autoOff: {self._CH1autoOff}, self._CH1heatOnOff: {self._CH1heatOnOff}, self._CH1autoMode: {self._CH1autoMode}, self._CH1manual: {self._CH1manual}")

                    except json.JSONDecodeError as json_err:
                        _LOGGER.error(
                            f"Failed to parse JSON data from Salus response: {json_err}"
                        )
                else:
                    _LOGGER.error(
                        "Received an empty response when fetching data from Salus."
                    )

        except aiohttp.ClientError as http_err:
            self._online = False
            _LOGGER.error(
                f"HTTP request error while getting data from Salus: {http_err}"
            )
        except Exception as e:
            _LOGGER.error(f"Unexpected error while getting data from Salus: {e}")

        # Call async_write_ha_state() to notify HA of the new state
        # if self.entity_id:  # Only call if entity is initialized
        #     self.async_write_ha_state()

    async def async_update(self):
        """Get the latest data."""
        await self._get_data()

        if self.entity_id:  # Only call if entity is initialized
            self.async_write_ha_state()



class SalusTemperatureSensor(SensorEntity):
    """Representation of a Salus Temperature Sensor."""

    def __init__(self, thermostat):
        """Initialize the sensor."""
        self._thermostat = thermostat
        self._attr_name = f"{thermostat.name} Current Temperature"
        self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = "temperature"
        self._attr_unique_id = f"{thermostat.unique_id}_current_temperature"

    @property
    def state(self):
        """Return the current temperature."""
        return self._thermostat._current_temperature

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {(self._attr_unique_id,)},
            "name": self._attr_name,
            "manufacturer": "Salus",
            "model": "iT500",
        }

class SalusTargetTemperatureSensor(SensorEntity):
    """Representation of a Salus Temperature Sensor."""

    def __init__(self, thermostat):
        """Initialize the sensor."""
        self._thermostat = thermostat
        self._attr_name = f"{thermostat.name} Target Temperature"
        self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = "temperature"
        self._attr_unique_id = f"{thermostat.unique_id}_target_temperature"

    @property
    def state(self):
        """Return the current temperature."""
        return self._thermostat._target_temperature

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {(self._attr_unique_id,)},
            "name": self._attr_name,
            "manufacturer": "Salus",
            "model": "iT500",
        }

class SalusOnlineBinarySensor(BinarySensorEntity):
    """Representation of a Online Status."""

    def __init__(self, thermostat):
        """Initialize the binary sensor."""
        self._thermostat = thermostat
        self._attr_name = f"{thermostat.name} Online Status"
        self._attr_unique_id = f"{thermostat.unique_id}_online_status"

    @property
    def is_on(self):
        return self._thermostat._online

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {(self._attr_unique_id,)},
            "name": self._attr_name,
            "manufacturer": "Salus",
            "model": "iT500",
        }

class SalusCH1autoOff(BinarySensorEntity):
    """Representation of a CH1autoOff."""

    def __init__(self, thermostat):
        """Initialize the binary sensor."""
        self._thermostat = thermostat
        self._attr_name = f"{thermostat.name} CH1autoOff"
        self._attr_unique_id = f"{thermostat.unique_id}_CH1autoOff"

    @property
    def is_on(self):
        return self._thermostat._CH1autoOff == "1"

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {(self._attr_unique_id,)},
            "name": self._attr_name,
            "manufacturer": "Salus",
            "model": "iT500",
        }

class SalusCH1manual(BinarySensorEntity):
    """Representation of a CH1manual."""

    def __init__(self, thermostat):
        """Initialize the binary sensor."""
        self._thermostat = thermostat
        self._attr_name = f"{thermostat.name} CH1manual"
        self._attr_unique_id = f"{thermostat.unique_id}_CH1manual"

    @property
    def is_on(self):
        return self._thermostat._CH1manual == "1"

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {(self._attr_unique_id,)},
            "name": self._attr_name,
            "manufacturer": "Salus",
            "model": "iT500",
        }

class SalusCH1schedType(BinarySensorEntity):
    """Representation of a CH1schedType."""

    def __init__(self, thermostat):
        """Initialize the binary sensor."""
        self._thermostat = thermostat
        self._attr_name = f"{thermostat.name} CH1schedType"
        self._attr_unique_id = f"{thermostat.unique_id}_CH1schedType"

    @property
    def is_on(self):
        return self._thermostat._CH1schedType == "1"

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {(self._attr_unique_id,)},
            "name": self._attr_name,
            "manufacturer": "Salus",
            "model": "iT500",
        }

class SalusCH1heatOnOffStatus(BinarySensorEntity):
    """Representation of a CH1heatOnOffStatus."""

    def __init__(self, thermostat):
        """Initialize the binary sensor."""
        self._thermostat = thermostat
        self._attr_name = f"{thermostat.name} CH1heatOnOffStatus"
        self._attr_unique_id = f"{thermostat.unique_id}_CH1heatOnOffStatus"

    @property
    def is_on(self):
        return self._thermostat._CH1heatOnOffStatus == "1"

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {(self._attr_unique_id,)},
            "name": self._attr_name,
            "manufacturer": "Salus",
            "model": "iT500",
        }

class SalusCH1autoMode(BinarySensorEntity):
    """Representation of a CH1autoMode."""

    def __init__(self, thermostat):
        """Initialize the binary sensor."""
        self._thermostat = thermostat
        self._attr_name = f"{thermostat.name} CH1autoMode"
        self._attr_unique_id = f"{thermostat.unique_id}_CH1autoMode"

    @property
    def is_on(self):
        return self._thermostat._CH1autoMode == "1"

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {(self._attr_unique_id,)},
            "name": self._attr_name,
            "manufacturer": "Salus",
            "model": "iT500",
        }

class SalusCH1heatOnOff(BinarySensorEntity):
    """Representation of a CH1heatOnOff."""

    def __init__(self, thermostat):
        """Initialize the binary sensor."""
        self._thermostat = thermostat
        self._attr_name = f"{thermostat.name} CH1heatOnOff"
        self._attr_unique_id = f"{thermostat.unique_id}_CH1heatOnOff"

    @property
    def is_on(self):
        return self._thermostat._CH1heatOnOff == "1"

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {(self._attr_unique_id,)},
            "name": self._attr_name,
            "manufacturer": "Salus",
            "model": "iT500",
        }

class SalusCH1frostActive(BinarySensorEntity):
    """Representation of a CH1frostActive."""

    def __init__(self, thermostat):
        """Initialize the binary sensor."""
        self._thermostat = thermostat
        self._attr_name = f"{thermostat.name} CH1frostActive"
        self._attr_unique_id = f"{thermostat.unique_id}_CH1frostActive"

    @property
    def is_on(self):
        return self._thermostat._CH1frostActive == "1"

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {(self._attr_unique_id,)},
            "name": self._attr_name,
            "manufacturer": "Salus",
            "model": "iT500",
        }
