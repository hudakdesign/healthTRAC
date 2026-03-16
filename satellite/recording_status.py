import random
import time
import json
from flask import Flask

POLL_RATE = 1.0

app = Flask(__name__)

@app.route("/")
def index():
    recording_data = get_recording_data()
    time.sleep(POLL_RATE)
    return json.dumps(recording_data)

# returns dictionary of recording debug info
def get_recording_data():
    dummy_data = {"time_ns": time.time_ns(),
                  "channels": 2,
                  "frequency": 41000,
                  "amplitude": random.random()}
    return dummy_data

if __name__ == "__main__":
    app.run(debug=True)