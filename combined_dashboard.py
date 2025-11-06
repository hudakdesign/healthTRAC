#!/usr/bin/env python3
import argparse
from flask_socketio import SocketIO
from flask import Flask, render_template
import pandas as pd
from collections import deque
import threading
from datetime import datetime
import matplotlib.pyplot as plt
import io
import base64
import time
import eventlet
from pathlib import Path

eventlet.monkey_patch()

# Max data points to display
MAX_POINTS = 500

# Temporary data storage
toothbrush_data = {
    'timestamps': deque(maxlen=MAX_POINTS),
    'accel_x': deque(maxlen=MAX_POINTS),
    'accel_y': deque(maxlen=MAX_POINTS),
    'accel_z': deque(maxlen=MAX_POINTS),
    'last_update': None
}


# Initialize Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'health-trac-dashboard'
socketio = SocketIO(app, cors_allowed_origins='*')

# Create threading lock
data_lock = threading.Lock()


def read_csv_data(csv_path):
        """Read data from CSV file"""
        try:
            df = pd.read_csv(csv_path)

            with data_lock:
                # Clear existing data
                toothbrush_data['timestamps'].clear()
                toothbrush_data['accel_x'].clear()
                toothbrush_data['accel_y'].clear()
                toothbrush_data['accel_z'].clear()

                # Load new data (last MAX_POINTS rows)
                for _, row in df.tail(MAX_POINTS).iterrows():
                    toothbrush_data['timestamps'].append(row['timestamp_hub'])
                    toothbrush_data['accel_x'].append(row['accel_x'])
                    toothbrush_data['accel_y'].append(row['accel_y'])
                    toothbrush_data['accel_z'].append(row['accel_z'])

                toothbrush_data['last_update'] = datetime.now()

            print(f"[CSV] Loaded {len(toothbrush_data['timestamps'])} data points")
            return True
        except Exception as e:
            print(f"[CSV] Error reading file: {e}")
            return False
        
def generate_toothbrush_plot():
    """Generate toothbrush accelerometer plot"""
    print(f"[PLOT] Generating plot with {len(toothbrush_data['timestamps'])} data points")

    if len(toothbrush_data['timestamps']) == 0:
        # Return empty plot
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', fontsize=14)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    else:
        timestamps = list(toothbrush_data['timestamps'])
        accel_x = list(toothbrush_data['accel_x'])
        accel_y = list(toothbrush_data['accel_y'])
        accel_z = list(toothbrush_data['accel_z'])

        # Convert timestamps to relative time (seconds from start)
        t0 = timestamps[0]
        times = [(t - t0) for t in timestamps]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(times, accel_x, label='X', alpha=0.7)
        ax.plot(times, accel_y, label='Y', alpha=0.7)
        ax.plot(times, accel_z, label='Z', alpha=0.7)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Acceleration (g)')
        ax.set_title('Toothbrush IMU Data')
        ax.legend()
        ax.grid(True, alpha=0.3)

    # Convert to base64 image
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=80, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return img_base64

def update_dashboard():
    """Generate and return all plots"""
    plots = {
        'toothbrush': generate_toothbrush_plot(),
        'fsr': '',  # Empty for now
        'audio': '',  # Empty for now
        'status': {
            'toothbrush': {
                'status': 'Reading from CSV',
                'battery': 'N/A',
                'last_seen': toothbrush_data['last_update'].strftime('%H:%M:%S') if toothbrush_data[
                    'last_update'] else 'Never'
            },
            'fsr_bridge': {'status': 'N/A', 'last_seen': 'N/A'},
            'audio': {'status': 'N/A', 'last_seen': 'N/A'},
            'hub': {'status': 'Online', 'uptime': 'N/A'}
        }
    }
    return plots

def update_dashboard_loop(csv_path):
    """Periodically update dashboard plots from CSV"""
    while True:
        time.sleep(5)  # Update every 5 seconds

        print("[DASHBOARD] Reading CSV and updating plots")
        read_csv_data(csv_path)

        plots = update_dashboard()
        socketio.emit('update_plots', plots)
        print("[DASHBOARD] Dashboard plots updated")

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Combined Sensor Dashboard')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the dashboard on')
    parser.add_argument('--csv-file', type=str, default='data/toothbrush.csv',
                        help='Path to CSV file (default: data/toothbrush.csv)')
    parser.add_argument('--web-port', type=int, default=8080,
                        help='Web dashboard port (default: 8080)')
    args = parser.parse_args()


    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        return
    
    # Initial load
    read_csv_data(csv_path)

    # Start dashboard update thread
    update_thread = threading.Thread(target=update_dashboard_loop, args=(csv_path,))
    update_thread.daemon = True
    update_thread.start()

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
