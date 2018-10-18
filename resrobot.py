import datetime
from datetime import timedelta
import logging
import math

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

ATTR_BOARD = 'board'
ATTR_THIS_DIRECTION = 'direction'
ATTR_THIS_LINE = 'name'
ATTR_THIS_LINE_NUMBER = 'line'
ATTR_THIS_TIME = 'time'
ATTR_THIS_DIFF = 'diff'
ATTR_NEXT_DIRECTION = 'next_direction'
ATTR_NEXT_LINE = 'next_name'
ATTR_NEXT_LINE_NUMBER = 'next_line'
ATTR_NEXT_TIME = 'next_time'
ATTR_NEXT_DIFF = 'next_diff'

CONF_STOLP_KEY = 'stolp_key'
CONF_SITEID = 'siteid'
CONF_DIRECTION = 'direction'
CONF_PASSLIST = 'passlist'
CONF_MAXJOURNEYS = 'max_journeys'
CONF_ATTRIBUTION = "Powered by TRAFIKLAB"

UPDATE_FREQUENCY = timedelta(seconds=15)
FORCED_UPDATE_FREQUENCY = timedelta(seconds=5)

USER_AGENT = "Home Assistant Resrobot Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOLP_KEY): cv.string,
    vol.Required(CONF_SITEID): cv.string,
    vol.Required(CONF_DIRECTION): cv.string,
    vol.Optional(CONF_NAME, default=""): cv.string,
    vol.Optional(CONF_PASSLIST, default="0"): cv.string,
})

global_diff = None

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""

    data = DepartureBoardData(
        config.get(CONF_STOLP_KEY),
        config.get(CONF_SITEID),
        config.get(CONF_DIRECTION),
        config.get(CONF_PASSLIST),
    )

    sensors = [ResrobotSensor(
        data,
        config.get(CONF_SITEID),
        config.get(CONF_NAME)
    )]

    add_devices(sensors)

    data.update()


class ResrobotSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, data, siteid, name):
        """Initialize the sensor."""
        self._siteid = siteid
        self._name = name or siteid
        self._data = data
        self._nextdeparture = '?'
        self._board = []

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
            self._name = self._board[0]['name']
            if self._board[0]['diff'] == 0:
                return 'Nu'
            else:
                return self._board[0]['diff']

        return '?'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if not self._board:
            return

        params = {}
        for idx, departure in enumerate(self._board):
            if idx == 0:
                params.update({
                    ATTR_THIS_DIRECTION: departure.get('direction'),
                    ATTR_THIS_LINE: departure.get('name'),
                    ATTR_THIS_LINE_NUMBER: departure.get('line'),
                    ATTR_THIS_TIME: departure.get('time'),
                    ATTR_THIS_DIFF: departure.get('diff')
                })
            elif idx == 1:
                params.update({
                    ATTR_NEXT_DIRECTION: departure.get('direction'),
                    ATTR_NEXT_LINE: departure.get('name'),
                    ATTR_NEXT_LINE_NUMBER: departure.get('line'),
                    ATTR_NEXT_TIME: departure.get('time'),
                    ATTR_NEXT_DIFF: departure.get('diff')
                })
            else:
                break

        params.update({
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_BOARD: self._board
        })

        return {k: v for k, v in params.items() if v}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "min"

    def get_time_to_departure(self, time, date):
        try:
            now = datetime.datetime.now()
            departure_string = '{} {}'.format(date, time)
            departure = datetime.datetime.strptime(departure_string, "%Y-%m-%d %H:%M")
            time_diff = departure - now
            minutes = time_diff / datetime.timedelta(minutes=1)

            return math.ceil(minutes)

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
                line = value['transportNumber'] or ''
                stop = value['stop'] or 'Unknown stop'
                time = value['time'][:-3] or ''
                date = value['date'] or ''
                direction = value['direction'] or 'Unknown direction'
                diff = self.get_time_to_departure(time, date)

                board.append({"name": name, "line": line, "time": time, "stop": stop, "date": date, "direction": direction, "diff": diff})

                global global_diff
                global_diff = board[0]['diff']

        self._board = sorted(board, key=lambda k: k['diff'])


class DepartureBoardData(object):
    """ Class for retrieving API data """

    def __init__(self, stolpapikey, siteid, direction, passlist):
        self._stolpapikey = stolpapikey
        self._siteid = siteid
        self._direction = direction or 0
        self._passlist = passlist or 0
        self.data = {}

    @Throttle(UPDATE_FREQUENCY, FORCED_UPDATE_FREQUENCY)
    def update(self, **kwargs):
        """Get the latest data for this site from the API."""
        global global_diff

        if global_diff and global_diff > 0:
            return

        try:
            _LOGGER.info("Fetching Resrobot Data for '%s'", self._siteid)
            url = "https://api.resrobot.se/v2/departureBoard?key={}&id={}&direction={}&passlist={}&format=json". \
                format(self._stolpapikey, self._siteid, self._direction, self._passlist)

            req = requests.get(url, headers={"User-agent": USER_AGENT}, allow_redirects=True, timeout=5)

        except requests.exceptions.RequestException:
            _LOGGER.error("failed fetching Resrobot Data for '%s'", self._siteid)
            return

        if req.status_code == 200:
            self.data = req.json()

        else:
            _LOGGER.error("failed fetching Resrobot Data for '%s'"
                          "(HTTP Status_code = %d)", self._siteid,
                          req.status_code)
