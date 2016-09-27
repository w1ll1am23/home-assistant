"""
Support for Wink hubs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/wink/
"""
import logging
import json

import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import CONF_ACCESS_TOKEN, ATTR_BATTERY_LEVEL, \
                                CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from pubnub.pubnub import SubscribeCallback, PNOperationType, PNStatusCategory

REQUIREMENTS = ['python-wink==0.10.0']

_LOGGER = logging.getLogger(__name__)

CHANNELS = []

DOMAIN = 'wink'

SUBSCRIPTION_HANDLER = None
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_USER_AGENT = 'user_agent'
CONF_OATH = 'oath'
CONF_DEFINED_BOTH_MSG = 'Remove access token to use oath2.'
CONF_MISSING_OATH_MSG = 'Missing oath2 credentials.'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Inclusive(CONF_EMAIL, CONF_OATH,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Inclusive(CONF_PASSWORD, CONF_OATH,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Inclusive(CONF_CLIENT_ID, CONF_OATH,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Inclusive(CONF_CLIENT_SECRET, CONF_OATH,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Exclusive(CONF_EMAIL, CONF_OATH,
                      msg=CONF_DEFINED_BOTH_MSG): cv.string,
        vol.Exclusive(CONF_ACCESS_TOKEN, CONF_OATH,
                      msg=CONF_DEFINED_BOTH_MSG): cv.string,
        vol.Optional(CONF_USER_AGENT, default=None): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

WINK_COMPONENTS = [
    'binary_sensor', 'sensor', 'light', 'switch', 'lock', 'cover', 'climate'
]


def setup(hass, config):
    """Setup the Wink component."""
    import pywink

    user_agent = config[DOMAIN][CONF_USER_AGENT]

    if user_agent:
        pywink.set_user_agent(user_agent)

    access_token = config[DOMAIN].get(CONF_ACCESS_TOKEN)

    if access_token:
        pywink.set_bearer_token(access_token)
    else:
        email = config[DOMAIN][CONF_EMAIL]
        password = config[DOMAIN][CONF_PASSWORD]
        client_id = config[DOMAIN]['client_id']
        client_secret = config[DOMAIN]['client_secret']
        pywink.set_wink_credentials(email, password, client_id,
                                    client_secret)

    from pubnub.pnconfiguration import PNConfiguration
    from pubnub.pubnub import PubNub
    pywink.set_bearer_token(config[DOMAIN][CONF_ACCESS_TOKEN])
    pnconfig = PNConfiguration()
    pnconfig.subscribe_key = pywink.get_subscription_key()
    pnconfig.ssl = True
    global SUBSCRIPTION_HANDLER
    SUBSCRIPTION_HANDLER = PubNub(pnconfig)

    # Load components for the devices in Wink that we support
    for component in WINK_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)
    return True


class WinkDevice(Entity):
    """Representation a base Wink device."""

    def __init__(self, wink):
        """Initialize the Wink device."""
        from pubnub.pnconfiguration import PNConfiguration
        from pubnub.pubnub import PubNub

        self.wink = wink
        self._battery = self.wink.battery_level
        if self.wink.pubnub_channel in CHANNELS:
            pnconfig = PNConfiguration()
            pnconfig.subscribe_key = self.wink.pubnub_key
            pnconfig.ssl = True
            pubnub = PubNub(pnconfig)
            pubnub_listener = PubNubCallback(self)
            pubnub.add_listener(pubnub_listener)
            pubnub.subscribe().channels(self.wink.pubnub_channel).execute()
        else:
            CHANNELS.append(self.wink.pubnub_channel)

    @property
    def unique_id(self):
        """Return the ID of this Wink device."""
        return '{}.{}'.format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """Return the name of the device."""
        return self.wink.name()

    @property
    def available(self):
        """True if connection == True."""
        return self.wink.available

    def update(self):
        """Update state of the device."""
        self.wink.update_state()

    @property
    def should_poll(self):
        """Only poll if we are not subscribed to pubnub."""
        return self.wink.pubnub_channel is None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._battery:
            return {
                ATTR_BATTERY_LEVEL: self._battery_level,
            }

    @property
    def _battery_level(self):
        """Return the battery level."""
<<<<<<< HEAD
        if self.wink.battery_level is not None:
            return self.wink.battery_level * 100
=======
        return self.wink.battery_level * 100

class PubNubCallback(SubscribeCallback):
    def __init__(self, entity):
        self.entity = entity

    def status(self, pubnub, status):
        if status.operation == PNOperationType.PNSubscribeOperation \
                and status.category == PNStatusCategory.PNConnectedCategory:
            print("connected")

    def presence(self, pubnub, presence):
        pass

    def message(self, pubnub, message):
        if 'data' in message.message:
            json_data = json.dumps(message.message.get('data'))
        else:
            json_data = message.message
        self.entity.wink.pubnub_update(json.loads(json_data))
        self.entity.update_ha_state()
>>>>>>> idk
