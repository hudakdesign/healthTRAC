from flask import Flask
import json
import time
import threading

flag_directory = "data/"
flag_file = "recording_flag"
flag_path = f"{flag_directory}{flag_file}"

recording_flag = False
recording_flag_lock = threading.Lock()

app = Flask(__name__)


@app.route("/")
def index():
    with recording_flag_lock:
        return create_json(recording_flag)


@app.route("/toggle_recording")
def toggle_recording():
    global recording_flag
    with recording_flag_lock:
        recording_flag = not recording_flag
        return str(recording_flag)


# Creates json file to return via the api
# takes in if the satellites should record or not
def create_json(recording):
    data = {"time_ns": time.time_ns(), "recording": recording}
    return json.dumps(data)


# TODO: check button via gpio
def check_button():
    return True


if __name__ == "__main__":
    # Runs api server on all interfaces on port 5000
    app.run(host="0.0.0.0", port=5001, debug=True)
