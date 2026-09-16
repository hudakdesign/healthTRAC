import json

from flask import Flask, render_template
import sensor_subsystems

# Constants
CONFIG_FILE_PATH = "config_test.json"

# Globals
app = Flask(__name__)


# Helpers
def load_configuration(config_file_path):
    """Returns hub configuration from file at provided path"""

    with open(config_file_path, "r") as f:
        return json.load(f)


# Routes
@app.route("/")
def index():
    """Route for getting the webpage for the dashboard"""

    return render_template("new_dashboard.html")


@app.route("/data")
def get_data():
    """Route for getting all of the aggregate data for the dashboard"""

    return "Not yet implemented"


@app.route("/recording")
def recording_status():
    """Route for checking if microphones should be recording or not"""

    return "Not yet implemented"


if __name__ == "__main__":
    # Load config file
    hub_config = load_configuration(CONFIG_FILE_PATH)

    # Initialize subsystems
    subsystems = {}
    for subsystem_config in hub_config["subsystems"]:
        # load in attributes
        subsystem_name = subsystem_config["name"]
        subsystem_address = subsystem_config["address"]
        # this is unused for now
        # later use it for selecting type of subsystem object
        subsystem_type = subsystem_config["type"]
        # also unused for now
        # include it in data sent to hub
        subsystem_notes = subsystem_config["notes"]

        subsystems[subsystem_name] = sensor_subsystems.Sensor_Subsystem(
            f"{subsystem_name}.db", subsystem_address
        )

    # Start the subsystems
    for subsystem_name in subsystems.keys():
        subsystems[subsystem_name].start_updating()

    # Run flask server
    app.run(host="0.0.0.0", port=8080)

    # Stop the subsystems
    for subsystem_name in subsystems.keys():
        subsystems[subsystem_name].stop_updating()
