"""Module containing classes for interfacing with all sensor subsystems in healthTRAC"""

# Imports:
import collections
import sqlite3
import subprocess
import threading
import time

import requests
import pandas as pd

# Constants:
REQUEST_TIMEOUT_SECONDS = 1
SUBSYSTEM_POLL_FREQUENCY_SECONDS = 1
AGGREGATE_SHORT_LENGTH = 120
AGGREGATE_SHORT_FREQUENCY_INDICES = 25  # every n indices


# Classes:
class Sensor_Subsystem:
    """Generic parent class for retrieving data from sensor subsystems

    Attributes:
        database_name: The filename for the database.
        con: The database connection object.
        subsystem_url: The URL for accessing the microphone array.
        raw_data_polls: A dataframe for containing received raw data polls.
        raw_data_polls_lock: A lock for protecting raw_data_polls.
        aggregate_data_polls_short: A short term dataframe of aggregate data
            polls.
        aggregate_data_polls_short_lock: A lock for protecting the short term
            dataframe.
        aggregate_data_polls_long: A long term dataframe of aggregate data
            polls.
        updater_thread: A thread which is used for continuously updating the
            data at a given frequency.
        is_connected: A boolean value for if the subsystem is connected.
            this is set if the request succeeds or not.
    """

    def __init__(self, database_name, subsystem_url):
        # Check that the data directory exists
        subprocess.run(["mkdir", "-p", "data"])

        self.database_name = database_name
        self.con = None  # this should get set on first save to db
        self.subsystem_url = subsystem_url
        self.raw_data_polls = None
        self.raw_data_polls_lock = threading.Lock()
        self.aggregate_data_polls_short = None
        self.aggregate_data_polls_short_lock = threading.Lock()
        self.aggregate_data_polls_long = None
        self.updater_thread = None
        self.is_updating = False
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

    def _load_response_to_df(self, response):
        """Loads response into a dataframe and returns it"""

        poll_df = pd.DataFrame(response["dataPolls"])
        return poll_df

    def _save_data_to_database(self, poll_df):
        """Inserts the incoming poll dataframe into the database"""

        if self.con is None:
            self.con = sqlite3.connect(f"data/{self.database_name}")

        poll_df.to_sql(name="data_polls", con=self.con, if_exists="append")

    def _update_aggregate_data(self):
        """Updates aggregate data buffers using data from `raw_data_polls`

        Takes every set number of data polls and puts them into
        `raw_data_polls`. Drops oldest rows that are outside of the allowed
        length. Also consume / remove the rows of `raw_data_polls` that have
        been aggregated.
        """

        # takes out the data to be aggregated from raw_data_polls
        with self.raw_data_polls_lock:
            # number of polls that cant yet be aggregated
            num_polls_outside_bin = (
                len(self.raw_data_polls) % AGGREGATE_SHORT_FREQUENCY_INDICES
            )
            # the length of the data that will be aggregated
            data_to_aggregate_len = len(self.raw_data_polls) - num_polls_outside_bin

            # make sure all of the polls fit into the bin
            data_to_aggregate = self.raw_data_polls.iloc[:data_to_aggregate_len]

            # remove the polls that have been taken out to aggregate
            self.raw_data_polls = self.raw_data_polls.iloc[len(data_to_aggregate) :]

            # reset the index and get rid of the old one
            self.raw_data_polls = self.raw_data_polls.reset_index()
            self.raw_data_polls = self.raw_data_polls.drop(columns=["index"])

        # take out every n polls to use as aggregate values
        new_aggregate_data = data_to_aggregate.iloc[::AGGREGATE_SHORT_FREQUENCY_INDICES]

        # lock the aggregate data polls
        # add this aggregate data to the existing data if it exists
        # if it exists then concatenate
        with self.aggregate_data_polls_short_lock:
            if self.aggregate_data_polls_short is not None:
                new_aggregate_data = pd.concat(
                    [self.aggregate_data_polls_short, new_aggregate_data],
                    ignore_index=True,
                )
            # if it doesnt then just use it as is
            # and reset the indices either way
            new_aggregate_data = new_aggregate_data.reset_index()
            new_aggregate_data = new_aggregate_data.drop(columns=["index"])

            # remove old data to make it the correct size
            num_polls_to_drop = len(new_aggregate_data) - AGGREGATE_SHORT_LENGTH
            new_aggregate_data = new_aggregate_data.iloc[num_polls_to_drop:]
            new_aggregate_data = new_aggregate_data.reset_index()
            new_aggregate_data = new_aggregate_data.drop(columns=["index"])

            # set aggregate data polls to the new dataframe
            self.aggregate_data_polls_short = new_aggregate_data

    def _update_raw_data(self, poll_df):
        """Updates `raw_data_polls` with poll data

        Updates raw data buffer with the contents of the received poll
        dataframe.
        """
        # updates the dataframe with the incoming data
        # uses lock to prevent race condition
        with self.raw_data_polls_lock:
            # special case for if this is the first poll
            if self.raw_data_polls is None:
                self.raw_data_polls = poll_df
            else:
                self.raw_data_polls = pd.concat(
                    [self.raw_data_polls, poll_df], ignore_index=True
                )

    def _update_data(self):
        """Handles polling, storing, and aggregating data

        1. Polls the subsystem, checks if it was successful.
        2. Parses it into a dataframe.
        3. Saves the raw data to the database.
        4. Updates the raw data buffer
        5. Aggregates the data with bins for short and long buffers.
        """

        response = self._poll_subsystem()

        # return False if the poll failed
        if not response:
            return False

        poll_df = self._load_response_to_df(response)

        self._save_data_to_database(poll_df)

        self._update_raw_data(poll_df)

        self._update_aggregate_data()

    def _data_updater(self):
        """Updater thread which polls subsystem every fixed amount of time"""

        while self.is_updating:
            self._update_data()
            time.sleep(SUBSYSTEM_POLL_FREQUENCY_SECONDS)

    def get_raw_data(self):
        """Handles getting raw data in a thread-safe manner"""

        with self.raw_data_polls_lock:
            return self.raw_data_polls
        
    def get_aggregate_data_polls_short(self):
        """Safely gets aggregate data from the short term dataframe"""
        
        with self.aggregate_data_polls_short_lock:
            return self.aggregate_data_polls_short

    def start_updating(self):
        """Starts the updater thread for polling the subsystem"""

        if self.updater_thread is not None and self.is_updating:
            print("Subsystem is already updating")
        else:
            self.is_updating = True
            self.updater_thread = threading.Thread(target=self._data_updater)
            self.updater_thread.start()

    def stop_updating(self):
        """Signals the updater thread to stop"""

        self.is_updating = False


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
