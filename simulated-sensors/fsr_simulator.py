from flask import Flask
import json
import numpy as np
import threading
import time

app = Flask(__name__)

# NOTE: change these to change what sensor you're simulating
device_name = "FSR"
num_sensors = 8
port = 8081  # make sure this port isnt in use


update_frequency = 1 / 60
# simulated buffer of sensor data (whats on the device)
data = {
    "device_name": device_name,
    "timestamps": [],
    "sensors": [[] for _ in range(num_sensors)],
}
data_lock = threading.Lock()


# simulates getting data from each sub-sensor on the device
# saves the data to the buffer
def get_sensor_data(t):
    data["timestamps"].append(t)
    for i in range(num_sensors):
        value = np.sin(t * (i + 1) * 0.001)
        data["sensors"][i].append(value)


# thread for simulating the device gathering data regardless of
# if its being called
def update_loop():
    t = 0
    while True:
        data_lock.acquire()
        get_sensor_data(t)
        data_lock.release()
        t += 1
        time.sleep(update_frequency)


# api endpoint for getting the data off the device
# clears the buffer after getting the data
@app.route("/data")
def fsr_api():
    data_lock.acquire()
    response = json.dumps(data)
    data["timestamps"] = []
    data["sensors"] = [[] for _ in range(num_sensors)]
    data_lock.release()
    return response


def main():
    update_thread = threading.Thread(target=update_loop)
    update_thread.start()
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
