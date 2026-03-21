from flask import Flask, render_template
import threading

import constants as c

app = Flask(__name__)


def main():
    # Route for rendering dashboard html
    @app.route("/")
    def index():
        return render_template("dashboard.html")
    

    # Starts server
    app.run(host="0.0.0.0", port=5000, debug=c.DEBUG)