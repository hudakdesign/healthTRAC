import time

from flask import Flask, render_template

app = Flask(__name__)

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
    
    # Initialize subsystems
    
    # Start flask server
    
    app.run(host="0.0.0.0", port=8080)