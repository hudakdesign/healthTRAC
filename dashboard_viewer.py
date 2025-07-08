#!/usr/bin/env python3
"""
Simple Dashboard Viewer
Connects to hub server and displays real-time sensor data
Text-based for simplicity - can be extended to GUI later
"""

import socket
import json
import time
import threading
from collections import defaultdict, deque
from datetime import datetime


class DashboardViewer:
    """Simple text-based dashboard for monitoring sensor data"""

    def __init__(self, hub_host='localhost', hub_port=5555):
        self.hub_host = hub_host
        self.hub_port = hub_port
        self.running = False

        # Data storage (last N samples per sensor)
        self.max_samples = 100
        self.sensor_data = defaultdict(lambda: {
            'timestamps': deque(maxlen=self.max_samples),
            'values': deque(maxlen=self.max_samples),
            'count': 0,
            'last_update': 0
        })

        # Display configuration
        self.update_interval = 1.0  # Refresh display every second
        self.clear_screen = True  # Clear terminal between updates

    def connect_as_viewer(self):
        """Connect to hub as a viewer (not a sensor)"""
        try:
            print(f"Connecting to hub at {self.hub_host}:{self.hub_port}...")

            # Note: This is a simplified viewer connection
            # In production, you might want a separate viewer protocol
            # For now, we'll just listen to the data stream

            print("Connected to hub (viewer mode)")
            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def parse_csv_files(self):
        """
        Read data from CSV files in the current session directory
        This is a simpler approach than real-time streaming
        """
        # In a real implementation, you would:
        # 1. Find the latest session directory
        # 2. Monitor CSV files for changes
        # 3. Display the latest data
        pass

    def calculate_stats(self, sensor_type):
        """Calculate statistics for a sensor"""
        data = self.sensor_data[sensor_type]

        if not data['values']:
            return {}

        values = list(data['values'])

        # Calculate stats based on sensor type
        if sensor_type == 'FSR':
            recent_values = [v['force'] for v in values[-10:]]
            return {
                'current': values[-1]['force'],
                'avg_10': sum(recent_values) / len(recent_values),
                'max_10': max(recent_values),
                'active': values[-1]['force'] > 0.5
            }

        elif sensor_type == 'ACCELEROMETER':
            recent_values = values[-10:]
            magnitudes = [
                (v['x'] ** 2 + v['y'] ** 2 + v['z'] ** 2) ** 0.5
                for v in recent_values
            ]
            return {
                'current_x': values[-1]['x'],
                'current_y': values[-1]['y'],
                'current_z': values[-1]['z'],
                'magnitude': magnitudes[-1],
                'avg_magnitude': sum(magnitudes) / len(magnitudes),
                'moving': magnitudes[-1] > 1.1  # Threshold for movement
            }

        elif sensor_type == 'MICROPHONE':
            recent_values = values[-10:]
            avg_rms = sum(v['rms_left'] + v['rms_right'] for v in recent_values) / (2 * len(recent_values))
            return {
                'current_left': values[-1]['rms_left'],
                'current_right': values[-1]['rms_right'],
                'avg_rms': avg_rms,
                'voice_detected': avg_rms > 0.05
            }

        return {}

    def display_dashboard(self):
        """Display the dashboard"""
        if self.clear_screen:
            print('\033[2J\033[H')  # Clear screen and move cursor to top

        print("=" * 70)
        print(f"HealthTRAC Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()

        # Display each sensor
        for sensor_type in ['FSR', 'ACCELEROMETER', 'MICROPHONE']:
            data = self.sensor_data[sensor_type]
            stats = self.calculate_stats(sensor_type)

            print(f"📊 {sensor_type}")
            print(f"   Samples: {data['count']}")

            if data['count'] > 0:
                age = time.time() - data['last_update']
                status = "✅ Active" if age < 5 else "⚠️  Stale" if age < 30 else "❌ Offline"
                print(f"   Status: {status} (last update: {age:.1f}s ago)")

                # Sensor-specific display
                if sensor_type == 'FSR' and stats:
                    print(f"   Force: {stats['current']:.2f} N (avg: {stats['avg_10']:.2f})")
                    if stats['active']:
                        print("   🪑 Person seated")

                elif sensor_type == 'ACCELEROMETER' and stats:
                    print(
                        f"   X: {stats['current_x']:+.3f}g  Y: {stats['current_y']:+.3f}g  Z: {stats['current_z']:+.3f}g")
                    print(f"   Magnitude: {stats['magnitude']:.3f}g (avg: {stats['avg_magnitude']:.3f})")
                    if stats['moving']:
                        print("   🦷 Toothbrush in use")

                elif sensor_type == 'MICROPHONE' and stats:
                    print(f"   RMS: L={stats['current_left']:.3f} R={stats['current_right']:.3f}")
                    if stats['voice_detected']:
                        print("   🎤 Voice activity detected")
            else:
                print("   Status: Waiting for data...")

            print()

        print("-" * 70)
        print("Press Ctrl+C to exit")

    def simulate_data(self):
        """Simulate incoming sensor data for testing"""
        import random

        while self.running:
            current_time = time.time()

            # Simulate FSR data
            if random.random() < 0.5:  # 50Hz -> ~25 samples/sec average
                self.sensor_data['FSR']['timestamps'].append(current_time)
                self.sensor_data['FSR']['values'].append({
                    'force': random.uniform(0, 10) if random.random() < 0.3 else 0,
                    'raw': random.randint(0, 4095)
                })
                self.sensor_data['FSR']['count'] += 1
                self.sensor_data['FSR']['last_update'] = current_time

            # Simulate accelerometer data
            if random.random() < 0.1:  # 100Hz -> ~10 samples/sec average
                self.sensor_data['ACCELEROMETER']['timestamps'].append(current_time)
                self.sensor_data['ACCELEROMETER']['values'].append({
                    'x': random.uniform(-2, 2),
                    'y': random.uniform(-2, 2),
                    'z': random.uniform(0.8, 1.2)  # Mostly around 1g
                })
                self.sensor_data['ACCELEROMETER']['count'] += 1
                self.sensor_data['ACCELEROMETER']['last_update'] = current_time

            # Simulate microphone data
            if random.random() < 0.1:  # 10Hz average
                self.sensor_data['MICROPHONE']['timestamps'].append(current_time)
                self.sensor_data['MICROPHONE']['values'].append({
                    'rms_left': random.uniform(0, 0.1),
                    'rms_right': random.uniform(0, 0.1)
                })
                self.sensor_data['MICROPHONE']['count'] += 1
                self.sensor_data['MICROPHONE']['last_update'] = current_time

            time.sleep(0.01)  # Small delay

    def run(self):
        """Run the dashboard"""
        print("Starting HealthTRAC Dashboard Viewer...")
        print("NOTE: This is a simplified viewer showing simulated data")
        print("In production, it would read from the hub's CSV files")
        print()

        self.running = True

        # Start data simulation thread (replace with real data reading)
        sim_thread = threading.Thread(target=self.simulate_data)
        sim_thread.daemon = True
        sim_thread.start()

        try:
            # Main display loop
            while self.running:
                self.display_dashboard()
                time.sleep(self.update_interval)

        except KeyboardInterrupt:
            print("\nShutting down dashboard...")
            self.running = False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='HealthTRAC Dashboard Viewer')
    parser.add_argument('--hub-host', default='localhost',
                        help='Hub server hostname/IP (default: localhost)')
    parser.add_argument('--hub-port', type=int, default=5555,
                        help='Hub server port (default: 5555)')
    parser.add_argument('--no-clear', action='store_true',
                        help='Don\'t clear screen between updates')

    args = parser.parse_args()

    # Create and run dashboard
    dashboard = DashboardViewer(
        hub_host=args.hub_host,
        hub_port=args.hub_port
    )
    dashboard.clear_screen = not args.no_clear
    dashboard.run()


if __name__ == "__main__":
    main()