from __main__ import app
import csv
import json

DATA_PATH = "testing/test_imu.csv"

@app.route("/imu")
def imu_api():
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

        output_dict = {
            "timestamp_ns": data_dict["timestamp_ns"],
            "accel_x": data_dict["accel_x"]}
        return json.dumps(output_dict)