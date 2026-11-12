# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "flask>=3.1.3",
# ]
# ///

import argparse
import json
import threading

from flask import Flask

# Globals
app = Flask(__name__)
running = True
recording = True


@app.route("/")
def recording_flag():
    if recording:
        return json.dumps("True")
    else:
        return json.dumps("False")


def recording_toggler():
    global recording

    while running:
        input(f"Recording: `{recording}`; Press [Enter] to toggle")
        recording = not recording


if __name__ == "__main__":
    # parse arguments to check for specified port
    parser = argparse.ArgumentParser(
        prog="Microphone Controller",
        description="Basic script for controlling satellite mics for debugging purposes",
    )
    parser.add_argument("-p", "--port")
    args = parser.parse_args()

    # starts a thread for letting the user control the recording status
    recording_toggler_thread = threading.Thread(target=recording_toggler)
    recording_toggler_thread.start()

    # configures port number and starts server
    if args.port is None:
        port = 8080
    else:
        port = args.port
    app.run(host="0.0.0.0", port=port, debug=False)

    # stops user input thread
    running = False
