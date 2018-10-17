import datetime
from datetime import timedelta
import logging

import voluptuous as vol
import requests

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_utc_time, async_track_utc_time_change)
from homeassistant.util import dt as dt_util

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_PLANER_KEY = 'planer_key'
CONF_STOLP_KEY = 'stolp_key'
CONF_SITE_ID = 'site_id',
CONF_DIRECTION = 'direction'

UPDATE_FREQUENCY = timedelta(seconds=60)
FORCED_UPDATE_FREQUENCY = timedelta(seconds=5)

USER_AGENT = "Home Assistant Resrobot Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_PLANER_KEY): cv.string,
    vol.Optional(CONF_STOLP_KEY): cv.string,
    vol.Optional(CONF_SITE_ID): cv.string,
    vol.Optional(CONF_DIRECTION): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""

    data = DepartureBoardData(
        config.get(CONF_PLANER_KEY),
        config.get(CONF_STOLP_KEY),
        config.get(CONF_SITE_ID),
        config.get(CONF_DIRECTION)
    )

    add_devices([ResrobotSensor()])


class ResrobotSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Example Temperature'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "min"

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._state = 23


class DepartureBoardData(object):
    """ Class for retrieving API data """

    def __init__(self, planerapikey, stolpapikey, siteid, direction):
        self._planerapikey = planerapikey
        self._stolpapikey = stolpapikey
        self._siteid = siteid
        self._direction = direction or 0
        self.data = {}

    @Throttle(UPDATE_FREQUENCY, FORCED_UPDATE_FREQUENCY)
    def update(self, **kwargs):
        """Get the latest data for this site from the API."""
        try:
            _LOGGER.info("fetching Resrobot Data for '%s'", self._siteid)
            url = "https://api.resrobot.se/v2/departureBoard?key={}&siteid={}". \
                format(self._planerapikey, self._siteid)

            req = requests.get(url, headers={"User-agent": USER_AGENT}, allow_redirects=True, timeout=5)

        except requests.exceptions.RequestException:
            _LOGGER.error("failed fetching SL Data for '%s'", self._siteid)
            return

        if req.status_code == 200:
            self.data = req.json()

        else:
            _LOGGER.error("failed fetching SL Data for '%s'"
                          "(HTTP Status_code = %d)", self._siteid,
                          req.status_code)
