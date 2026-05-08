from flask import Flask, render_template
import json
import random
import threading
import collections
import requests
import time
import numpy as np

import constants as c
app = Flask(__name__)
running = True
running_lock = threading.Lock()

hub_polling_rate = 1

# temporary buffers
short_buffer_size = 120 * 60 # 120 seconds of data at 60hz
long_buffer_size = 60 * 24 # 24 hours of data at 1 sample

# graphing buffers
num_imu_fields = 3
imu_data = {
    "x_vals": collections.deque(maxlen=short_buffer_size),
    "y_data": [collections.deque(maxlen=short_buffer_size) for _ in range(num_imu_fields)] # buffer for each sensor
}
imu_data_lock = threading.Lock()

num_fsr_fields = 6
fsr_data = {
    "x_vals": collections.deque(maxlen=short_buffer_size),
    "y_data": [collections.deque(maxlen=short_buffer_size) for _ in range(num_fsr_fields)] # buffer for each sensor
}
fsr_data_lock = threading.Lock()


# Route for rendering dashboard html
@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/fsr")
def fsr_api():
    with fsr_data_lock:
        x_vals = list(fsr_data["x_vals"])
        y_data = [list(sensor_data) for sensor_data in fsr_data["y_data"]]

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
            "backgroundColor": "rgba(0,255,0,1.0)",
            "borderColor": "rgba(0,255,0,0.1)",
            "data": y_data[1]
        },
        {
            "fill": False,
            "lineTension": 0,
            "backgroundColor": "rgba(0,255,255,1.0)",
            "borderColor": "rgba(0,255,255,0.1)",
            "data": y_data[2]
        },
        {
            "fill": False,
            "lineTension": 0,
            "backgroundColor": "rgba(255,0,0,1.0)",
            "borderColor": "rgba(255,0,0,0.1)",
            "data": y_data[3]
        },
        {
            "fill": False,
            "lineTension": 0,
            "backgroundColor": "rgba(255,0,255,1.0)",
            "borderColor": "rgba(255,0,255,0.1)",
            "data": y_data[4]
        },
        {
            "fill": False,
            "lineTension": 0,
            "backgroundColor": "rgba(255,255,0,1.0)",
            "borderColor": "rgba(255,255,0,0.1)",
            "data": y_data[5]
        }
    ]

    return json.dumps({
        "data": {
            "labels": x_vals,
            "datasets": y_dataset
        }
    })

@app.route("/imu")
def imu_api():
    with imu_data_lock:
        x_vals = list(imu_data["x_vals"])
        y_data = [list(sensor_data) for sensor_data in imu_data["y_data"]]

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

if c.DEBUG:
    # simulators for tesitng purposes
    num_simulated_polls = 5
    @app.route("/debug/simulated_fsr")
    def simulated_fsr():
        simulated_timestamps = [time.time_ns() for _ in range(num_simulated_polls)]
        # really long shorthand for fake sensor data
        simulated_sensor_data = [[np.sin(current_simulated_time * sensor_number) for current_simulated_time in simulated_timestamps] for sensor_number in range(num_fsr_fields)]

        return json.dumps({
            "timestamps": simulated_timestamps,
            "sensors": simulated_sensor_data
        })

    @app.route("/debug/simulated_imu")
    def simulated_imu():
        simulated_timestamps = [time.time_ns() for _ in range(num_simulated_polls)]
        # really long shorthand for fake sensor data
        simulated_sensor_data = [[np.sin(current_simulated_time * sensor_number) for current_simulated_time in simulated_timestamps] for sensor_number in range(num_imu_fields)]

        return json.dumps({
            "timestamps": simulated_timestamps,
            "sensors": simulated_sensor_data
        })

    @app.route("/debug/get_fsr_data")
    def get_fsr_data():
        with fsr_data_lock:
            return json.dumps({
                "timestamps": list(fsr_data["x_vals"]),
                "sensors": [list(sensor_data) for sensor_data in fsr_data["y_data"]]
            })
        
    @app.route("/debug/get_imu_data")
    def get_imu_data():
        with imu_data_lock:
            return json.dumps({
                "timestamps": list(fsr_data["x_vals"]),
                "sensors": [list(sensor_data) for sensor_data in fsr_data["y_data"]]
            })

def update_fsr_buffer():
    currently_running = True
    fsr_url = "http://127.0.0.1:8080/debug/simulated_fsr"
    time.sleep(1)

    while currently_running:
        try:
            response = requests.get(fsr_url)
            data = response.json()
            timestamps = data["timestamps"]
            sensors = data["sensors"]

            with fsr_data_lock:
                    for data_entry in range(len(timestamps)):
                        fsr_data["x_vals"].append(timestamps[data_entry])
                        for sensor_number in range(num_fsr_fields):
                            fsr_data["y_data"][sensor_number].append(sensors[sensor_number][data_entry])
        except Exception as e:
            print(f"Error fetching FSR data: {e}")

        with running_lock:
            currently_running = running

        time.sleep(hub_polling_rate)

def update_imu_buffer():
    currently_running = True
    imu_url = "http://127.0.0.1:8080/debug/simulated_imu"
    time.sleep(1)

    while currently_running:
        try:
            response = requests.get(imu_url)
            data = response.json()
            timestamps = data["timestamps"]
            sensors = data["sensors"]

            with imu_data_lock:
                for data_entry in range(len(timestamps)):
                    imu_data["x_vals"].append(timestamps[data_entry])
                    for sensor_number in range(num_imu_fields):
                        imu_data["y_data"][sensor_number].append(sensors[sensor_number][data_entry])
        except Exception as e:
            print(f"Error fetching IMU data: {e}")

        with running_lock:
            currently_running = running
        
        time.sleep(hub_polling_rate)

def server_stopper():
    global running
    global fsr_data
    global imu_data

    input("Press Enter to stop the server...\n")
    with running_lock:
        running = False

    time.sleep(1)
    with fsr_data_lock:
        print(fsr_data)
        print(len(fsr_data["x_vals"]))
    with imu_data_lock:
        print(imu_data)
        print(len(imu_data["x_vals"]))

def main():
    # start threads
    server_stopper_thread = threading.Thread(target=server_stopper)
    server_stopper_thread.start()

    fsr_thread = threading.Thread(target=update_fsr_buffer)
    fsr_thread.start()

    imu_thread = threading.Thread(target=update_imu_buffer)
    imu_thread.start()

    # Starts server
    app.run(host="0.0.0.0", port=c.PORT, debug=c.DEBUG)

if __name__ == "__main__":
    main()