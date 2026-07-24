from flask import Flask
import threading
import json

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
        recording = True
        input(f"Recording: `{recording}`; Press [Enter] to toggle")
        recording = False
        input(f"Recording: `{recording}`; Press [Enter] to toggle")



if __name__ == "__main__":
    recording_toggler_thread = threading.Thread(target=recording_toggler)
    recording_toggler_thread.start()

    app.run(host="0.0.0.0", port=8050, debug=False)
