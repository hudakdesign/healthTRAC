import collections
import json
import threading
import time

import constants as c
import requests
from flask import Flask, render_template

app = Flask(__name__)
running = True
running_lock = threading.Lock()

# How often in between times that hub requests data from microcontrollers
hub_polling_rate = 1

# temporary buffers
short_buffer_size = 120 * 60  # 120 seconds of data at 60hz
long_buffer_size = 60 * 24  # 24 hours of data at 1 sample

# graphing buffers
num_imu_fields = 3
imu_data = {
    "x_vals": collections.deque(maxlen=short_buffer_size),
    "y_data": [
        collections.deque(maxlen=short_buffer_size) for _ in range(num_imu_fields)
    ],  # buffer for each sensor
}
imu_data_lock = threading.Lock()

num_fsr_fields = 8
fsr_data = {
    "x_vals": collections.deque(maxlen=short_buffer_size),
    "y_data": [
        collections.deque(maxlen=short_buffer_size) for _ in range(num_fsr_fields)
    ],  # buffer for each sensor
}
fsr_data_lock = threading.Lock()

num_audio_fields = 1
audio_data = {
    "x_vals": collections.deque(maxlen=short_buffer_size),
    "y_data": [
        collections.deque(maxlen=short_buffer_size) for _ in range(num_audio_fields)
    ],  # buffer for each sensor
}
audio_data_lock = threading.Lock()

# Recording flag for controlling satellite recording
recording_flag = True
recording_flag_lock = threading.Lock()


# Route for rendering dashboard html
@app.route("/")
def index():
    return render_template("dashboard.html")


# Route for getting recording flag status
# (if the satellite should be recording)
@app.route("/recording_flag")
def recording_flag_api():
    global recording_flag
    with recording_flag_lock:
        data = {"time_ns": time.time_ns(), "recording": recording_flag}
        return json.dumps(data)


# Route for toggling recording flag
@app.route("/toggle_recording_flag")
def toggle_recording_flag():
    global recording_flag
    with recording_flag_lock:
        recording_flag = not recording_flag
        return str(recording_flag)


@app.route("/fsr_data")
def fsr_data_api():
    with fsr_data_lock:
        return json.dumps(
            {
                "timestamps": list(fsr_data["x_vals"]),
                "sensors": [list(sensor_data) for sensor_data in fsr_data["y_data"]],
            }
        )


@app.route("/imu_data")
def imu_data_api():
    with imu_data_lock:
        return json.dumps(
            {
                "timestamps": list(imu_data["x_vals"]),
                "sensors": [list(sensor_data) for sensor_data in imu_data["y_data"]],
            }
        )


@app.route("/audio_data")
def audio_data_api():
    with audio_data_lock:
        return json.dumps(
            {
                "timestamps": list(audio_data["x_vals"]),
                "sensors": [list(sensor_data) for sensor_data in audio_data["y_data"]],
            }
        )


# Threads:
# Thread for requesting data from fsr.
# Requests data from microcontroller, uses it to update short term data buffers
def update_fsr_buffer():
    currently_running = True
    fsr_url = c.fsr_url
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
                        fsr_data["y_data"][sensor_number].append(
                            sensors[sensor_number][data_entry]
                        )
        except Exception as e:
            print(f"Error fetching FSR data: {e}")

        with running_lock:
            currently_running = running

        time.sleep(hub_polling_rate)


# Thread for requesting data from imu.
# Requests data from microcontroller, uses it to update short term data buffers
def update_imu_buffer():
    currently_running = True
    imu_url = c.imu_url
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
                        imu_data["y_data"][sensor_number].append(
                            sensors[sensor_number][data_entry]
                        )
        except Exception as e:
            print(f"Error fetching IMU data: {e}")

        with running_lock:
            currently_running = running

        time.sleep(hub_polling_rate)


# Thread for requesting data from satellite
# Requests data from satellite, uses it to update short term data buffers
def update_audio_buffer():
    currently_running = True
    audio_url = c.audio_url
    time.sleep(1)

    while currently_running:
        try:
            response = requests.get(audio_url)
            print(f"response: {response}")
            data = response.json()
            timestamps = data["timestamps"]
            sensors = data["sensors"]

            print(f"audio response: {data}")

            with audio_data_lock:
                audio_data["x_vals"].append(timestamps)
                for sensor_number in range(num_audio_fields):
                    audio_data["y_data"][sensor_number].append(sensors[sensor_number])
        except Exception as e:
            print(f"Error fetching Audio data: {e}")

        with running_lock:
            currently_running = running

        time.sleep(hub_polling_rate)


# Thread for stopping the server. If the user pressed enter, all threads are told to stop looping
def server_stopper():
    global running
    global fsr_data
    global imu_data
    global audio_data

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
    with audio_data_lock:
        print(audio_data)
        print(len(audio_data["x_vals"]))


# Threads/


def main():
    # start threads
    server_stopper_thread = threading.Thread(target=server_stopper)
    server_stopper_thread.start()

    fsr_thread = threading.Thread(target=update_fsr_buffer)
    fsr_thread.start()

    imu_thread = threading.Thread(target=update_imu_buffer)
    imu_thread.start()

    audio_thread = threading.Thread(target=update_audio_buffer)
    audio_thread.start()

    # start server
    app.run(host="0.0.0.0", port=c.PORT, debug=c.DEBUG)


if __name__ == "__main__":
    main()
