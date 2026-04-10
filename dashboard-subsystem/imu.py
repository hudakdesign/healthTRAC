from __main__ import app
import csv
import json

DATA_PATH = "testing/test_imu.csv"

# TODO: Update to take data from variable stored in memory. this current method will get slow over time
def get_imu_data():
    data_dict = {}
    with open(DATA_PATH, mode = "r") as file:
        csv_dict_reader = csv.DictReader(file)

        for idx, line in enumerate(csv_dict_reader):
            if idx == 0:
                for key in line.keys():
                    data_dict[key] = [line[key]]
            else:
                for key in line.keys():
                    data_dict[key].append(line[key])

    num_rows = 10
    last_n_item_dict = {}

    for key_, value_ in data_dict.items():
        last_n_item_dict[key_] = value_[-num_rows:]

    x_vals = last_n_item_dict["timestamp_hub"]       

    y_data = []
    y_data.append(last_n_item_dict["accel_x"])
    y_data.append(last_n_item_dict["accel_y"])
    y_data.append(last_n_item_dict["accel_z"])

    return x_vals, y_data

@app.route("/imu")
def imu_api():
    # Example of preparing data to send
    # x_vals = [0, 1, 2, 3, 4]
    # y_data = [
    #     [0, 1, 2, 3, 4],
    #     [4, 3, 2, 1, 0]
    # ]

    x_vals, y_data = get_imu_data()

    y_dataset = [
        {
            "fill": False,
            "lineTension": 0,
            "backgroundColor": "rgba(0,0,255,1.0)",
            "borderColor": "rgba(0,0,255,0.1)",
            "data": y_data[0]
        },
        {
            "fill": False,
            "lineTension": 0,
            "backgroundColor": "rgba(255,0,0,1.0)",
            "borderColor": "rgba(255,0,0,0.1)",
            "data": y_data[1]
        },
        {
            "fill": False,
            "lineTension": 0,
            "backgroundColor": "rgba(0,255,0,1.0)",
            "borderColor": "rgba(0,255,0,0.1)",
            "data": y_data[2]
        }
    ]

    return json.dumps({
        "data": {
            "labels": x_vals,
            "datasets": y_dataset
        }
    })