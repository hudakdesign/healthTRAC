#!/usr/bin/env python3
"""
Web-Based Dashboard for HealthTRAC
Displays live accelerometer data with NTP timestamps
No PyQt5 required - runs in any web browser!
"""

from flask import Flask, render_template_string, jsonify
import threading
import socket
import json
import time
from collections import deque
from datetime import datetime
import os

app = Flask(__name__)

# Configuration
HUB_HOST = 'localhost'
HUB_PORT = 5555
MAX_SAMPLES = 200  # Keep last 200 samples for display

# Global data storage
data_lock = threading.Lock()
accelerometer_data = deque(maxlen=MAX_SAMPLES)
connection_status = {"connected": False, "last_update": 0}
stats = {
    "samples_received": 0,
    "session_start": time.time(),
    "current_magnitude": 0,
    "motion_detected": False
}

# HTML template with embedded JavaScript for live updates
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>HealthTRAC Live Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f0f0f0;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .status-card {
            background-color: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .status-card h3 {
            margin-top: 0;
            color: #2c3e50;
        }
        .value {
            font-size: 24px;
            font-weight: bold;
            color: #3498db;
        }
        .chart-container {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .connected {
            color: #27ae60;
        }
        .disconnected {
            color: #e74c3c;
        }
        .motion {
            color: #e67e22;
        }
        .still {
            color: #95a5a6;
        }
        #timestamp {
            font-family: monospace;
            color: #7f8c8d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>HealthTRAC Live Dashboard</h1>
            <p>MetaMotion RL Accelerometer Data</p>
        </div>

        <div class="status-grid">
            <div class="status-card">
                <h3>Connection Status</h3>
                <div class="value" id="connection">Connecting...</div>
            </div>
            <div class="status-card">
                <h3>Samples Received</h3>
                <div class="value" id="samples">0</div>
            </div>
            <div class="status-card">
                <h3>Current Magnitude</h3>
                <div class="value" id="magnitude">0.000 g</div>
            </div>
            <div class="status-card">
                <h3>Motion Status</h3>
                <div class="value" id="motion">Unknown</div>
            </div>
        </div>

        <div class="chart-container">
            <h3>Accelerometer Data (Last 200 Samples)</h3>
            <canvas id="accelChart"></canvas>
        </div>

        <div class="chart-container">
            <h3>Magnitude Over Time</h3>
            <canvas id="magnitudeChart"></canvas>
        </div>

        <div style="text-align: center; color: #7f8c8d;">
            <p>Last Update: <span id="timestamp">Never</span></p>
            <p>NTP Synchronized Time</p>
        </div>
    </div>

    <script>
        // Chart setup
        const accelCtx = document.getElementById('accelChart').getContext('2d');
        const magCtx = document.getElementById('magnitudeChart').getContext('2d');

        const accelChart = new Chart(accelCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'X-axis',
                        data: [],
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        tension: 0.1
                    },
                    {
                        label: 'Y-axis',
                        data: [],
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.1)',
                        tension: 0.1
                    },
                    {
                        label: 'Z-axis',
                        data: [],
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: false,
                        min: -2,
                        max: 2,
                        title: {
                            display: true,
                            text: 'Acceleration (g)'
                        }
                    }
                }
            }
        });

        const magnitudeChart = new Chart(magCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Magnitude',
                    data: [],
                    borderColor: 'rgb(153, 102, 255)',
                    backgroundColor: 'rgba(153, 102, 255, 0.1)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        min: 0,
                        max: 2.5,
                        title: {
                            display: true,
                            text: 'Magnitude (g)'
                        }
                    }
                }
            }
        });

        // Update function
        function updateDashboard() {
            fetch('/data')
                .then(response => response.json())
                .then(data => {
                    // Update status
                    document.getElementById('connection').innerHTML = 
                        data.connected ? '<span class="connected">Connected</span>' : 
                                       '<span class="disconnected">Disconnected</span>';
                    document.getElementById('samples').textContent = data.samples;
                    document.getElementById('magnitude').textContent = data.magnitude.toFixed(3) + ' g';
                    document.getElementById('motion').innerHTML = 
                        data.motion ? '<span class="motion">Motion Detected</span>' : 
                                    '<span class="still">Still</span>';

                    // Update timestamp
                    if (data.last_timestamp) {
                        const date = new Date(data.last_timestamp * 1000);
                        document.getElementById('timestamp').textContent = 
                            date.toLocaleString() + '.' + date.getMilliseconds();
                    }

                    // Update charts
                    if (data.recent_data && data.recent_data.length > 0) {
                        const labels = data.recent_data.map((_, i) => i);
                        const xData = data.recent_data.map(d => d.x);
                        const yData = data.recent_data.map(d => d.y);
                        const zData = data.recent_data.map(d => d.z);
                        const magData = data.recent_data.map(d => 
                            Math.sqrt(d.x*d.x + d.y*d.y + d.z*d.z));

                        accelChart.data.labels = labels;
                        accelChart.data.datasets[0].data = xData;
                        accelChart.data.datasets[1].data = yData;
                        accelChart.data.datasets[2].data = zData;
                        accelChart.update('none');

                        magnitudeChart.data.labels = labels;
                        magnitudeChart.data.datasets[0].data = magData;
                        magnitudeChart.update('none');
                    }
                });
        }

        // Update every 500ms
        setInterval(updateDashboard, 500);
        updateDashboard();
    </script>
</body>
</html>
'''


class DashboardClient(threading.Thread):
    """Background thread that connects to hub and collects data"""

    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.socket = None

    def connect_to_hub(self):
        """Connect to the hub server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((HUB_HOST, HUB_PORT))

            # Identify as viewer (special type)
            self.socket.send(b"SENSOR:DASHBOARD_VIEWER\n")

            # Read acknowledgment
            ack_data = self.socket.recv(1024).decode('utf-8').strip()

            with data_lock:
                connection_status["connected"] = True
                connection_status["last_update"] = time.time()

            print(f"Connected to hub: {ack_data}")
            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def run(self):
        """Main data collection loop"""
        buffer = ""

        while self.running:
            if not self.socket:
                if not self.connect_to_hub():
                    time.sleep(5)
                    continue

            try:
                # Read data from hub
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    raise ConnectionError("Hub disconnected")

                buffer += data

                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self.process_data(line.strip())

            except Exception as e:
                print(f"Data collection error: {e}")
                self.socket = None
                with data_lock:
                    connection_status["connected"] = False
                time.sleep(5)

    def process_data(self, line):
        """Process incoming data line"""
        try:
            data = json.loads(line)

            # Check if it's accelerometer data
            if 'x' in data and 'y' in data and 'z' in data:
                timestamp = data.get('timestamp', time.time())

                with data_lock:
                    accelerometer_data.append({
                        'timestamp': timestamp,
                        'x': data['x'],
                        'y': data['y'],
                        'z': data['z']
                    })

                    # Update stats
                    stats["samples_received"] += 1
                    magnitude = (data['x'] ** 2 + data['y'] ** 2 + data['z'] ** 2) ** 0.5
                    stats["current_magnitude"] = magnitude
                    stats["motion_detected"] = magnitude > 1.1

                    connection_status["last_update"] = time.time()

        except json.JSONDecodeError:
            pass  # Ignore non-JSON lines


@app.route('/')
def index():
    """Serve the main dashboard page"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/data')
def get_data():
    """API endpoint for current data"""
    with data_lock:
        # Get recent data
        recent_data = list(accelerometer_data)

        # Prepare response
        response = {
            'connected': connection_status["connected"],
            'samples': stats["samples_received"],
            'magnitude': stats["current_magnitude"],
            'motion': stats["motion_detected"],
            'recent_data': recent_data[-MAX_SAMPLES:],
            'last_timestamp': recent_data[-1]['timestamp'] if recent_data else None
        }

    return jsonify(response)


def main():
    """Main entry point"""
    print("=" * 60)
    print("HealthTRAC Web Dashboard")
    print("=" * 60)
    print(f"Hub connection: {HUB_HOST}:{HUB_PORT}")
    print("Starting dashboard server...")
    print("")

    # Start data collection thread
    collector = DashboardClient()
    collector.start()

    # Get local IP
    import subprocess
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
        if result.returncode == 0:
            ips = result.stdout.strip().split()
            if ips:
                print(f"Access dashboard at:")
                print(f"  Local: http://localhost:5000")
                for ip in ips:
                    print(f"  Network: http://{ip}:5000")
    except:
        print("Dashboard running at: http://localhost:5000")

    print("")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)


if __name__ == '__main__':
    main()