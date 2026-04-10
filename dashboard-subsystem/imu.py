from __main__ import app
import csv
import json

DATA_PATH = "testing/test_imu.csv"

def get_imu_data():
    with open(DATA_PATH, mode = "r") as file:
        csv_dict_reader = csv.DictReader(file)

        data_dict = {}
        for idx, line in enumerate(csv_dict_reader):
            if idx == 0:
                for key in line.keys():
                    data_dict[key] = [line[key]]
            else:
                for key in line.keys():
                    data_dict[key].append(line[key])
                
            if idx == 9:
                break

        print(data_dict)

        # output_dict = {
        #     "timestamp_ns": data_dict["timestamp_ns"],
        #     "accel_x": data_dict["accel_x"]}

        x_vals = data_dict["timestamp_hub"]       

        y_data = []
        y_data.append(data_dict["accel_x"])
        y_data.append(data_dict["accel_y"])
        y_data.append(data_dict["accel_z"])

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