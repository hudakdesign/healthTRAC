#!/usr/bin/env python3
import argparse
from flask import Flask, render_template

# importing the html template

def main():
    parser = argparse.ArgumentParser(description='Combined Sensor Dashboard')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the dashboard on')
    args = parser.parse_args()

    app = Flask(__name__)

    @app.route('/')
    def dashboard():
        return render_template('dashboard.html')

    print(f"Starting dashboard at http://localhost:{args.port}")
    app.run(host='0.0.0.0', port=args.port, debug=False)


if __name__ == "__main__":
    main()
