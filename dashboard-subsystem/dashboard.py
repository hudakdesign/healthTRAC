from flask import Flask, render_template
import json
import random
import threading

import constants as c
app = Flask(__name__)
import imu


def main():
    # Route for rendering dashboard html
    @app.route("/")
    def index():
        return render_template("dashboard.html")

    @app.route("/fsr")
    def fsr_api():
        # Example of preparing data to send
        x_vals = [0, 1, 2, 3, 4]
        y_data = [
            [0, 1, 2, 3, 4],
            [4, 3, 2, 1, 0]
        ]

        y_dataset = [
            {
                "fill": False,
                "lineTension": 0,
                "backgroundColor": "rgba(0,0,255,1.0)",
                "borderColor": "rgba(0,0,255,0.1)",
                "data": y_data[0]
            },
            {
                "fill": False,
                "lineTension": 0,
                "backgroundColor": "rgba(255,0,0,1.0)",
                "borderColor": "rgba(255,0,0,0.1)",
                "data": y_data[1]
            }
        ]

        return json.dumps({
            "data": {
                "labels": x_vals,
                "datasets": y_dataset
            }
        })

    # Starts server
    app.run(host="0.0.0.0", port=c.PORT, debug=c.DEBUG)

if __name__ == "__main__":
    main()