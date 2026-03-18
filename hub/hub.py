from flask import Flask
import json
import subprocess
import time

flag_directory = "data/"
flag_file = "recording_flag"
flag_path = f"{flag_directory}{flag_file}"

app = Flask(__name__)


@app.route("/")
def index():
    if check_recording_flag():
        return create_json(True)
    else:
        return create_json(False)


# Placeholder function prior to button implementation
def check_recording_flag():
    flag = subprocess.run(
        ["cat", flag_path], capture_output=True, text=True
    ).stdout.strip()

    print(flag)

    if flag == "1":
        return True
    else:
        return False


# TODO: check button via gpio
def check_button():
    return True


def create_json(recording):
    data = {"time_ns": time.time_ns(), "recording": recording}
    return json.dumps(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
