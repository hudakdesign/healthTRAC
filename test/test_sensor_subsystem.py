import sensor_subsystem
import json
from unittest.mock import Mock

import pytest
import pandas as pd


def test_update_aggregate_drops_right_amount():
    subsystem = sensor_subsystem.Sensor_Subsystem("test_db", "test_url", "test_notes")

    initial_last_index = 100 * 24
    next_last_index = 200 * 24

    initial_raw_data = {
        "timestamps": [i for i in range(initial_last_index)],
        "sensor0": [i * 2 for i in range(initial_last_index)],
        "sensor2": [i / 2 for i in range(initial_last_index)],
    }

    next_raw_data = {
        "timestamps": [i for i in range(initial_last_index, next_last_index)],
        "sensor0": [i * 2 for i in range(initial_last_index, next_last_index)],
        "sensor2": [i / 2 for i in range(initial_last_index, next_last_index)],
    }

    # add the first set of data polls and check right amount aggregated
    subsystem.raw_data_polls = pd.DataFrame(initial_raw_data)
    subsystem._update_aggregate_data()
    assert len(subsystem.aggregate_data_polls_short) == initial_last_index // 25

    # add another set and check that the right amount were kept / dropped
    subsystem._update_raw_data(pd.DataFrame(next_raw_data))
    subsystem._update_aggregate_data()
    assert len(subsystem.aggregate_data_polls_short) == 120


def test_imu_get_peripheral_data():
    subsystem = sensor_subsystem.Inertial_Measurement_Unit(
        "test.db", "test_url", "test_notes"
    )

    initial_last_index = 107
    raw_data_range = range(initial_last_index)

    initial_raw_data = {
        "timestamps": [i for i in raw_data_range],
        "accelX": [i * -1 for i in raw_data_range],
        "accelY": [i * 2 for i in raw_data_range],
        "accelZ": [i * 3 for i in raw_data_range],
        "batteryPercent": [i for i in raw_data_range],
    }

    # set up an imu subsystem with some data
    subsystem.raw_data_polls = pd.DataFrame(initial_raw_data)
    subsystem.peripheral_last_connect_time_ms = 12345
    subsystem.peripheral_signal_strength_dbm = -82
    subsystem._update_aggregate_data()

    # make sure that battery percent was dropped from the normal aggregate data
    assert "batteryPercent" not in subsystem.get_aggregate_data_short()

    # check that the correct peripheral data is returned
    subsystem_peripheral_data = subsystem.get_peripheral_data()
    assert subsystem_peripheral_data["batteryPercent"] == (0 + 25 + 50 + 75) / 4
    assert subsystem_peripheral_data["lastConnectTimeMs"] == 12345
    assert subsystem_peripheral_data["signalStrengthDbm"] == -82
