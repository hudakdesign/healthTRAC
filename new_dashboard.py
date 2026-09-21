import time
import json

from flask import Flask, render_template
import sensor_subsystems

# Constants
CONFIG_FILE_PATH = "config_test.json"
SYSTEM_ID = "hub-alpha"
NOTES = "In the CBI"

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
    """Route for getting all of the data needed for the dashboard"""

    dashboard_data = {}

    dashboard_data["systemId"] = SYSTEM_ID
    dashboard_data["uptimeMs"] = int((time.time_ns() - start_time) // 1e6)
    dashboard_data["notes"] = NOTES

    subsystems_data = {}
    # loop through all subsystems getting and saving aggregate data to send
    for subsystem_name, subsystem in subsystems.items():
        # create dict for data about the subsystem for the dashboard
        subsystem_data = {}

        subsystem_data["type"] = subsystem.get_subsystem_type()
        subsystem_data["notes"] = subsystem.get_notes()
        subsystem_data["timeSinceOnlineMs"] = subsystem.get_time_since_online_ms()

        # get the aggregate data for the subsystem and add it to the dict
        subsystem_aggregate_data = subsystem.get_aggregate_data_short()
        subsystem_data["data"] = subsystem_aggregate_data

        # subsystem type specific steps
        match subsystem_data["type"]:
            case "imu":
                subsystem_data["peripheral"] = subsystem.get_peripheral_data()
            case "mic":
                subsystem_data["isRecording"] = subsystem.get_recording_status()

        subsystems_data[subsystem_name] = subsystem_data

    dashboard_data["subsystems"] = subsystems_data

    return json.dumps(dashboard_data)


@app.route("/recording")
def recording_status():
    """Route for checking if microphones should be recording or not"""

    return "Not yet implemented"


if __name__ == "__main__":
    start_time = time.time_ns()

    # Load config file
    hub_config = load_configuration(CONFIG_FILE_PATH)

    # Initialize subsystems
    subsystems = {}
    for subsystem_name, subsystem_config in hub_config["subsystems"].items():
        # load in attributes
        subsystem_address = subsystem_config["address"]
        # this is unused for now
        # later use it for selecting type of subsystem object
        subsystem_type = subsystem_config["type"]
        # also unused for now
        # include it in data sent to hub
        subsystem_notes = subsystem_config["notes"]

        # use the correct object for each type
        match subsystem_type:
            case "fsr":
                subsystems[subsystem_name] = sensor_subsystems.Force_Sensitive_Resistor(
                    subsystem_name, subsystem_address, subsystem_notes
                )
            case "imu":
                subsystems[subsystem_name] = (
                    sensor_subsystems.Inertial_Measurement_Unit(
                        subsystem_name, subsystem_address, subsystem_notes
                    )
                )
            case "mic":
                subsystems[subsystem_name] = sensor_subsystems.Microphone_Array(
                    subsystem_name, subsystem_address, subsystem_notes
                )
            case _:
                print(f"ERROR: {subsystem_name} isn't a valid type.")

    # Start the subsystems
    for subsystem_name in subsystems.keys():
        subsystems[subsystem_name].start_updating()

    # Run flask server
    app.run(host="0.0.0.0", port=8080)

    # Stop the subsystems
    for subsystem_name in subsystems.keys():
        subsystems[subsystem_name].stop_updating()
