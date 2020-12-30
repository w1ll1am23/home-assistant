"""Support for EcoNet products."""
import asyncio
from datetime import timedelta
import logging

from pyeconet import EcoNetApiInterface
from pyeconet.equipment import EquipmentType
from pyeconet.errors import InvalidCredentialsError, PyeconetError

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import API_CLIENT, DOMAIN, EQUIPMENT

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["water_heater", "binary_sensor", "sensor"]
PUSH_UPDATE = "econet.push_update"

INTERVAL = timedelta(minutes=60)


async def async_setup(hass, config):
    """Set up the EcoNet component."""

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][API_CLIENT] = {}
    hass.data[DOMAIN][EQUIPMENT] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_EMAIL: conf[CONF_EMAIL],
                CONF_PASSWORD: conf[CONF_PASSWORD],
            },
        )
    )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up EcoNet as config entry."""
    entry_updates = {}
    if entry_updates:
        hass.config_entries.async_update_entry(config_entry, **entry_updates)

    email = config_entry.data.get(CONF_EMAIL)
    password = config_entry.data.get(CONF_PASSWORD)

    try:
        api = await EcoNetApiInterface.login(email, password=password)
    except InvalidCredentialsError:
        _LOGGER.error("Invalid credentials provided")
        return False
    except PyeconetError as err:
        _LOGGER.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    equipment = await api.get_equipment_by_type([EquipmentType.WATER_HEATER])
    hass.data[DOMAIN][API_CLIENT][config_entry.entry_id] = api
    hass.data[DOMAIN][EQUIPMENT][config_entry.entry_id] = equipment

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    api.subscribe()

    def update_published():
        """Handle a push update."""
        async_dispatcher_send(hass, PUSH_UPDATE)

    for _eqip in equipment[EquipmentType.WATER_HEATER]:
        _eqip.set_update_callback(update_published)

    async def resubscribe(now):
        """Resubscribe to the MQTT updates."""
        await hass.async_add_executor_job(api.unsubscribe)
        api.subscribe()

    async def fetch_update(now):
        """Fetch the latest changes from the API."""
        await api.refresh_equipment()

    async_track_time_interval(hass, resubscribe, INTERVAL)
    async_track_time_interval(hass, fetch_update, INTERVAL + timedelta(minutes=1))

    return True


async def async_unload_entry(hass, entry):
    """Unload a EcoNet config entry."""
    tasks = [
        hass.config_entries.async_forward_entry_unload(entry, component)
        for component in PLATFORMS
    ]

    await asyncio.gather(*tasks)

    hass.data[DOMAIN][API_CLIENT].pop(entry.entry_id)
    hass.data[DOMAIN][EQUIPMENT].pop(entry.entry_id)

    return True


class EcoNetEntity(Entity):
    """Define a base EcoNet entity."""

    def __init__(self, econet):
        """Initialize."""
        self._econet = econet

    async def async_added_to_hass(self):
        """Subscribe to device events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                PUSH_UPDATE, self.on_update_received
            )
        )

    @callback
    def on_update_received(self):
        """Update was pushed from the ecoent API."""
        self.schedule_update_ha_state()

    @property
    def available(self):
        """Return if the the device is online or not."""
        return self._econet.connected

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._econet.device_id)},
            "manufacturer": "Rheem",
            "name": self._econet.device_name,
        }

    @property
    def name(self):
        """Return the name of the entity."""
        return self._econet.device_name

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._econet.device_id}_{self._econet.device_name}"

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False
