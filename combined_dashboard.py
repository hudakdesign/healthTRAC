#!/usr/bin/env python3
import argparse
from flask import Flask, render_template



def main():
    parser = argparse.ArgumentParser(description='Combined Sensor Dashboard')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the dashboard on')
    args = parser.parse_args()

    app = Flask(__name__)

    # Routes
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/audio')
    def dashboard():
        return render_template('audio_dashboard.html')
    
    @app.route('/imu')
    def imu_dashboard():
        return render_template('imu_dashboard.html')

    print(f"Starting dashboard at http://localhost:{args.port}")
    app.run(host='0.0.0.0', port=args.port, debug=False)


if __name__ == "__main__":
    main()
