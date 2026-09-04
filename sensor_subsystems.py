"""Module containing classes for interfacing with all sensor subsystems in healthTRAC"""

# Imports:
import collections

import requests
import pandas as pd

# Constants:
DATA_POLL_QUEUE_LENGTH = 1000
REQUEST_TIMEOUT_SECONDS = 1


# Classes:
class Sensor_Subsystem:
    """Generic parent class for retrieving data from sensor subsystems

    Attributes:
        subsystem_url: The URL for accessing the microphone array.
        raw_data_polls: A dataframe for containing received raw data polls.
        aggregate_data_polls_short: A ring buffer of aggregate datapoints
            used for display and debugging on the dashboard.
        aggregate_data_polls_long: A ring buffer of very low frequency
            aggregate datapoints for display and debugging on the dashboard.
        is_connected: A boolean value for if the subsystem is connected.
            this is set if the request succeeds or not.
    """

    def __init__(self, subsystem_url):
        self.subsystem_url = subsystem_url
        self.raw_data_polls = None
        self.aggregate_data_polls_short = collections.deque(
            maxlen=DATA_POLL_QUEUE_LENGTH
        )
        self.aggregate_data_polls_long = collections.deque(
            maxlen=DATA_POLL_QUEUE_LENGTH
        )
        self.is_connected = False

    def _poll_subsystem(self):
        """Request data from `subsystem_url` and return it as a dict

        Attempts to request data from `subsystem_url` and parses the json into
        a dict before returning it. If the request times out then
        `is_connected` is set to `False` and returns `False`; otherwise, it is
        set to `True`.
        """

        try:
            # tries to get the data from the `subsystem_url`
            response = requests.get(self.subsystem_url, timeout=REQUEST_TIMEOUT_SECONDS)
        except:
            # if something goes wrong, then `is_connected` should be `False`
            self.is_connected = False
            # and return `False`
            return False
        # if the response came though then
        self.is_connected = True
        return response.json()

    def update_raw_data(self):
        """Updates `raw_data_polls` with response data from subsystem

        Polls the subsystem, takes the dictionary and uses it to update
        `raw_data_polls`. Returns `True` if successful, and `False` if anything
        went wrong.
        """

        # poll the subsystem
        response = self._poll_subsystem()

        # check that the poll was successful
        if response:
            incoming_raw_data = pd.DataFrame(response["dataPolls"])

            # updates the dataframe with the incoming data
            # special case for if this is the first poll
            if self.raw_data_polls == None:
                self.raw_data_polls = incoming_raw_data
            else:
                self.raw_data_polls = pd.concat(
                    [self.raw_data_polls, incoming_raw_data], ignore_index=True
                )
            return True
        else:
            return False


class Microphone_Array(Sensor_Subsystem):
    """Handles retrieving data from microphone array subsystems

    Attributes:
        subsystem_url: The URL for accessing the microphone array.
        raw_data_polls: A list for containing received raw data polls.
        aggregate_data_polls_short: A ring buffer of aggregate datapoints
            used for display and debugging on the dashboard.
        aggregate_data_polls_long: A ring buffer of very low frequency
            aggregate datapoints for display and debugging on the dashboard.
        is_connected: A boolean value for if the subsystem is connected.
            this is set if the request succeeds or not.
        is_muted: A boolean value for if the mic is currently muted.
    """

    pass


class Force_Sensitive_Resistor(Sensor_Subsystem):
    """Handles retrieving data from force sensitive resistor subsystems

    Attributes:
        subsystem_url: The URL for accessing the microphone array.
        raw_data_polls: A list for containing received raw data polls.
        aggregate_data_polls_short: A ring buffer of aggregate datapoints
            used for display and debugging on the dashboard.
        aggregate_data_polls_long: A ring buffer of very low frequency
            aggregate datapoints for display and debugging on the dashboard.
        is_connected: A boolean value for if the subsystem is connected.
            this is set if the request succeeds or not.
    """

    pass


class Inertial_Measurement_Unit(Sensor_Subsystem):
    """Handles retrieving data from microphone array subsystems

    Attributes:
        subsystem_url: The URL for accessing the microphone array.
        raw_data_polls: A list for containing received raw data polls.
        aggregate_data_polls_short: A ring buffer of aggregate datapoints
            used for display and debugging on the dashboard.
        aggregate_data_polls_long: A ring buffer of very low frequency
            aggregate datapoints for display and debugging on the dashboard.
        is_connected: A boolean value for if the subsystem is connected.
            this is set if the request succeeds or not.
        toothbrush_is_connected: A boolean value for if the toothbrush is
            currently connected or not.
        toothbrush_battery_percent: An integer value for how much charge is
            left on the toothbrush out of 100
    """

    pass
