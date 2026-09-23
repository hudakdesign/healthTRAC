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

    subsystem.raw_data_polls = pd.DataFrame(initial_raw_data)
    subsystem._update_aggregate_data()
    assert len(subsystem.aggregate_data_polls_short) == initial_last_index // 25

    subsystem._update_raw_data(pd.DataFrame(next_raw_data))
    subsystem._update_aggregate_data()
    assert len(subsystem.aggregate_data_polls_short) == 120
