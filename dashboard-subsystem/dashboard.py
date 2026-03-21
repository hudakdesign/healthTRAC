from flask import Flask, render_template
import json
import random
import threading

import constants as c

app = Flask(__name__)


def main():
    # Route for rendering dashboard html
    @app.route("/")
    def index():
        return render_template("dashboard.html")

    @app.route("/imu")
    def imu_api():
        # Example of preparing data to send
        x_vals = [0, 1, 2, 3, 4]
        y_vals = [0, 1, 4, 9, 16]
        

        return json.dumps({
            "x_vals": x_vals,
            "y_vals": y_vals
        })
    

    @app.route("/fsr")
    def fsr_api():
        # Example of preparing data to send
        x_vals = [0, 1, 2, 3, 4]
        y_vals = [0, 8, 16, 8, 0]

        return json.dumps({
            "x_vals": x_vals,
            "y_vals": y_vals
        })

    # Starts server
    app.run(host="0.0.0.0", port=c.PORT, debug=c.DEBUG)

if __name__ == "__main__":
    main()