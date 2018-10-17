import datetime
from datetime import timedelta
import logging

import voluptuous as vol
import requests

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, ATTR_ATTRIBUTION,
    CONF_LATITUDE, CONF_LONGITUDE)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_DIRECTION = 'direction'
ATTR_LINE = 'line'
ATTR_BOARD = 'board'

CONF_PLANER_KEY = 'planer_key'
CONF_STOLP_KEY = 'stolp_key'
CONF_SITEID = 'siteid'
CONF_DIRECTION = 'direction'
CONF_PASSLIST = 'passlist'
CONF_MAXJOURNEYS = 'max_journeys'
CONF_ATTRIBUTION = "Powered by TRAFIKLAB"

UPDATE_FREQUENCY = timedelta(seconds=60)
FORCED_UPDATE_FREQUENCY = timedelta(seconds=5)

USER_AGENT = "Home Assistant Resrobot Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PLANER_KEY): cv.string,
    vol.Required(CONF_STOLP_KEY): cv.string,
    vol.Optional(CONF_SITEID, default="740070995"): cv.string,
    vol.Optional(CONF_DIRECTION, default="740000099"): cv.string,
    vol.Optional(CONF_NAME, default="tillberga"): cv.string,
    vol.Optional(CONF_PASSLIST, default="0"): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""

    data = DepartureBoardData(
        config.get(CONF_PLANER_KEY),
        config.get(CONF_STOLP_KEY),
        config.get(CONF_SITEID),
        config.get(CONF_DIRECTION),
        config.get(CONF_PASSLIST),
    )

    sensors = []
    sensors.append(
        ResrobotSensor(
            data,
            config.get(CONF_SITEID),
            config.get(CONF_NAME)
        )
    )

    add_devices(sensors)


class ResrobotSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, data, siteid, name):
        """Initialize the sensor."""
        self._siteid = siteid
        self._name = name or siteid
        self._data = data
        self._nextdeparture = 9999
        self._board = []

        #self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{}'.format(self._name)

    @property
    def icon(self):
        """ Return the icon for the frontend."""
        return 'mdi:bus'

    @property
    def state(self):
        """Return the state of the sensor."""
        if len(self._board) > 0:
            if (self._board[0]['diff'] == 0):
                return 'Nu'
            else:
                return self._board[0]['diff']

        return '?'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if not self._board:
            return

        for departure in self._board:
            params = {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_DIRECTION: departure.get('direction'),
                ATTR_LINE: departure.get('name'),
                ATTR_BOARD: self._board
            }
            return {k: v for k, v in params.items() if v}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "min"

    def get_time_to_departure(self, time, date):
        try:
            now = datetime.datetime.now()
            departure_string = '{} {}'.format(date, time)
            departure = datetime.datetime.strptime(departure_string, "%Y-%m-%d %H:%M:%S")
            time_diff = departure - now
            minutes = time_diff / datetime.timedelta(minutes=1)

            return int(minutes)

        except Exception:
            _LOGGER.error('Failed to parse departure time (%s) ', time)

        return 0

    def update(self):
        """Fetch new state data for the sensor.
        """
        self._data.update()

        board = []
        if len(self._data.data['Departure']) == 0:
            _LOGGER.error("No departures!!!")
        else:
            for idx, value in enumerate(self._data.data['Departure']):
                name = value['name'] or 'No name'
                stop = value['stop'] or 'Unknown stop'
                time = value['time'] or ''
                date = value['date'] or ''
                direction = value['direction'] or 'Unknown direction'
                diff = self.get_time_to_departure(time, date)

                board.append({"name": name, "time": time, "stop": stop, "date": date, "direction": direction, "diff": diff})

        self._board = sorted(board, key=lambda k: k['diff'])


class DepartureBoardData(object):
    """ Class for retrieving API data """

    def __init__(self, planerapikey, stolpapikey, siteid, direction, passlist):
        self._planerapikey = planerapikey
        self._stolpapikey = stolpapikey
        self._siteid = siteid
        self._direction = direction or 0
        self._passlist = passlist or 0
        self.data = {}

    @Throttle(UPDATE_FREQUENCY, FORCED_UPDATE_FREQUENCY)
    def update(self, **kwargs):
        """Get the latest data for this site from the API."""
        try:
            _LOGGER.info("Fetching Resrobot Data for '%s'", self._siteid)
            url = "https://api.resrobot.se/v2/departureBoard?key={}&id={}&direction={}&passlist={}&format=json". \
                format(self._stolpapikey, self._siteid, self._direction, self._passlist)

            req = requests.get(url, headers={"User-agent": USER_AGENT}, allow_redirects=True, timeout=5)

        except requests.exceptions.RequestException:
            _LOGGER.debug("failed fetching SL Data for '%s'", self._siteid)
            return

        if req.status_code == 200:
            self.data = req.json()

        else:
            _LOGGER.debug("failed fetching Resrobot Data for '%s'"
                          "(HTTP Status_code = %d)", self._siteid,
                          req.status_code)
