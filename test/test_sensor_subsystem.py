import json
from unittest.mock import Mock

import pytest


@pytest.fixture
def valid_fsr_response():
    with open("valid_fsr_response.json", "r") as f:
        return json.load(f)


@pytest.fixture
def invalid_fsr_response():
    response = {
        "adsf": [2, 3, 4, 6, 21, 5, 23],
        "sfdkfjew": [23, 3425, 342, 65],
        "dhfgfje": "test",
    }


@pytest.fixture
def empty_fsr_response():
    pass


# Parent class tests
def test_sensor_subsystem():
    pass


# _poll_subsystem()
def test_polling_online_subsystem():
    pass


def test_polling_offline_subsystem():
    pass


def test_is_connected():
    pass


# _load_response_to_df()
def test_load_valid_response_to_df():
    pass


def load_invalid_response_to_df():
    pass


# _save_data_to_database()
def test_save_data_to_new_database():
    pass


def test_save_data_to_existing_database():
    pass


# _update_aggregate_data()
def test_update_small_amount_aggregate_data():
    pass


def test_update_large_amount_aggregate_data():
    pass


def test_update_invalid_aggregate_data():
    pass


# _update_raw_data()
def test_update_valid_raw_data():
    pass


def test_update_invalid_raw_data():
    pass


# _update_data()
def test_update_valid_data():
    pass


def test_update_invalid_data():
    pass


# _data_updater()
def test_data_updater_frequency():
    pass


# get_raw_data()
def test_get_raw_data():
    pass


# get_notes()
def test_get_notes():
    pass


# get_time_since_online_ms()
def test_get_time_since_online_ms():
    pass


# get_aggregate_data_short()
def test_get_aggregate_data_short():
    pass


# start_updating()
def test_start_updating():
    pass


# stop_updating()
def test_stop_updating():
    pass


# Fsr child tests
def test_force_sensitive_resistor():
    pass


# Imu child tests
def test_inertial_measurement_unit():
    pass


# Mic child tests
def test_microphone_array():
    pass
