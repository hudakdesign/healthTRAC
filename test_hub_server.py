#!/usr/bin/env python3
"""
Health TRAC Hub Server Test Script
----------------------------------
Simulates multiple sensors sending data to the hub server.
Used for testing server functionality without real hardware.

Features:
- Simulates FSR, IMU, and microphone sensors
- Configurable data rate and patterns
- Validates connection and data flow
"""

import socket
import time
import json
import threading
import random
import argparse
import sys
from typing import Dict, List, Any

# Default configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5555
DEFAULT_DURATION = 60  # seconds
DEFAULT_SENSORS = ["fsr", "imu", "mic"]
DEFAULT_RATE = 20  # samples per second


class SensorSimulator:
    """Base class for sensor simulators"""

    def __init__(self, host: str, port: int, sensor_type: str, rate: int):
        """Initialize the sensor simulator"""
        self.host = host
        self.port = port
        self.sensor_type = sensor_type
        self.rate = rate
        self.interval = 1.0 / rate
        self.sequence = 0
        self.running = False
        self.socket = None
        self.thread = None

    def connect(self) -> bool:
        """Connect to the hub server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))

            # Send handshake
            handshake = f"SENSOR:{self.sensor_type}\n"
            self.socket.send(handshake.encode('utf-8'))

            # Wait for ready response
            response = self.socket.recv(1024).decode('utf-8').strip()
            if response != "READY":
                print(f"[{self.sensor_type}] Unexpected response: {response}")
                self.socket.close()
                return False

            print(f"[{self.sensor_type}] Connected to hub server")
            return True

        except Exception as e:
            print(f"[{self.sensor_type}] Connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from the hub server"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

        self.running = False
        print(f"[{self.sensor_type}] Disconnected")

    def generate_data(self) -> Dict[str, Any]:
        """Generate simulated sensor data"""
        # To be implemented by subclasses
        return {
            'sensor': self.sensor_type,
            'sequence': self.sequence
        }

    def send_data(self, data: Dict[str, Any]) -> bool:
        """Send data to the hub server"""
        try:
            json_data = json.dumps(data) + "\n"
            self.socket.send(json_data.encode('utf-8'))
            self.sequence += 1
            return True
        except Exception as e:
            print(f"[{self.sensor_type}] Error sending data: {e}")
            return False

    def start(self, duration: int = None):
        """Start the simulator"""
        if self.running:
            return

        if not self.connect():
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, args=(duration,))
        self.thread.daemon = True
        self.thread.start()

    def _run_loop(self, duration: int = None):
        """Run loop for sending data"""
        start_time = time.time()

        while self.running:
            # Check if duration has elapsed
            if duration and time.time() - start_time >= duration:
                break

            # Generate and send data
            data = self.generate_data()
            if not self.send_data(data):
                break

            # Display periodic stats
            if self.sequence % (self.rate * 5) == 0:  # Every 5 seconds
                elapsed = time.time() - start_time
                print(
                    f"[{self.sensor_type}] Sent {self.sequence} samples in {elapsed:.1f}s ({self.sequence / elapsed:.1f} samples/sec)")

            # Sleep until next sample time
            time.sleep(self.interval)

        self.disconnect()

    def stop(self):
        """Stop the simulator"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
        self.disconnect()


class FSRSimulator(SensorSimulator):
    """Simulates an FSR sensor"""

    def __init__(self, host: str, port: int, rate: int):
        super().__init__(host, port, "fsr", rate)
        self.baseline = 0.5  # Base force when not "pressed"

    def generate_data(self) -> Dict[str, Any]:
        """Generate simulated FSR data"""
        # Simulate occasional "presses" on the FSR
        if random.random() < 0.05:  # 5% chance of starting a press
            force = random.uniform(2.0, 8.0)  # Strong press
        else:
            # Normal slight variation around baseline
            force = self.baseline + random.uniform(-0.2, 0.2)
            force = max(0, force)  # Ensure non-negative

        # Calculate raw value (simulating 12-bit ADC)
        raw = int(force * 500)  # Simple conversion formula

        return {
            'sensor': self.sensor_type,
            'sequence': self.sequence,
            'force': round(force, 2),
            'raw': raw
        }


class IMUSimulator(SensorSimulator):
    """Simulates an IMU sensor"""

    def __init__(self, host: str, port: int, rate: int):
        super().__init__(host, port, "imu", rate)
        self.activity = "idle"
        self.activity_start = 0
        self.activity_duration = 0

    def generate_data(self) -> Dict[str, Any]:
        """Generate simulated IMU data"""
        current_time = time.time()

        # Check if we should change activity
        if current_time - self.activity_start > self.activity_duration:
            # Choose a new activity
            activities = ["idle", "walking", "brushing"]
            self.activity = random.choice(activities)
            self.activity_start = current_time
            self.activity_duration = random.uniform(3.0, 10.0)  # Activity lasts 3-10 seconds
            print(f"[{self.sensor_type}] Activity changed to: {self.activity}")

        # Generate accelerometer values based on activity
        if self.activity == "idle":
            # Almost no movement
            x = random.uniform(-0.1, 0.1)
            y = random.uniform(-0.1, 0.1)
            z = random.uniform(0.9, 1.1)  # Gravity
        elif self.activity == "walking":
            # Periodic motion
            t = current_time * 2
            x = 0.5 * math.sin(t) + random.uniform(-0.1, 0.1)
            y = 0.5 * math.cos(t) + random.uniform(-0.1, 0.1)
            z = 0.8 + 0.3 * abs(math.sin(t * 2)) + random.uniform(-0.1, 0.1)
        else:  # brushing
            # Rapid oscillations
            t = current_time * 10
            x = 2.0 * math.sin(t) + random.uniform(-0.5, 0.5)
            y = 1.5 * math.cos(t) + random.uniform(-0.5, 0.5)
            z = 0.5 + random.uniform(-0.3, 0.3)

        return {
            'sensor': self.sensor_type,
            'sequence': self.sequence,
            'x': round(x, 3),
            'y': round(y, 3),
            'z': round(z, 3),
            'activity': self.activity
        }


class MicSimulator(SensorSimulator):
    """Simulates a microphone sensor"""

    def __init__(self, host: str, port: int, rate: int):
        super().__init__(host, port, "mic", rate)
        self.is_active = False
        self.activity_start = 0
        self.activity_duration = 0

    def generate_data(self) -> Dict[str, Any]:
        """Generate simulated microphone data"""
        current_time = time.time()

        # Check if we should change voice activity
        if current_time - self.activity_start > self.activity_duration:
            # Toggle voice activity
            self.is_active = not self.is_active
            self.activity_start = current_time
            self.activity_duration = random.uniform(2.0, 8.0)
            print(f"[{self.sensor_type}] Voice activity: {self.is_active}")

        # Generate audio features based on activity
        if self.is_active:
            # Active voice: higher RMS, moderate ZCR, mid-range centroid
            rms = random.uniform(0.4, 0.8)
            zcr = random.uniform(0.2, 0.4)
            centroid = random.uniform(1000, 3000)
        else:
            # Silence/background: low RMS, variable ZCR, wide centroid range
            rms = random.uniform(0.01, 0.1)
            zcr = random.uniform(0.1, 0.6)  # Can be high for noise
            centroid = random.uniform(500, 5000)

        return {
            'sensor': self.sensor_type,
            'sequence': self.sequence,
            'rms': round(rms, 3),
            'zcr': round(zcr, 3),
            'centroid': round(centroid, 0)
        }


def main():
    """Main function for the test script"""
    # Import math for IMUSimulator
    global math
    import math

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test the Health TRAC hub server')
    parser.add_argument('--host', type=str, default=DEFAULT_HOST, help='Hub server hostname')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Hub server port')
    parser.add_argument('--duration', type=int, default=DEFAULT_DURATION, help='Test duration in seconds')
    parser.add_argument('--sensors', type=str, default=','.join(DEFAULT_SENSORS),
                        help='Comma-separated list of sensors to simulate (fsr,imu,mic)')
    parser.add_argument('--rate', type=int, default=DEFAULT_RATE, help='Sample rate in Hz')

    args = parser.parse_args()

    # Parse sensors list
    sensors = args.sensors.split(',')

    # Create sensor simulators
    simulators = []

    for sensor_type in sensors:
        if sensor_type == 'fsr':
            simulators.append(FSRSimulator(args.host, args.port, args.rate))
        elif sensor_type == 'imu':
            simulators.append(IMUSimulator(args.host, args.port, args.rate))
        elif sensor_type == 'mic':
            simulators.append(MicSimulator(args.host, args.port, args.rate))
        else:
            print(f"Unknown sensor type: {sensor_type}")

    # Start simulators
    print(f"Starting {len(simulators)} sensor simulators for {args.duration} seconds")

    for simulator in simulators:
        simulator.start(args.duration)

    try:
        # Wait for the specified duration
        time.sleep(args.duration + 2)  # Add a little buffer
    except KeyboardInterrupt:
        print("Test interrupted by user")
    finally:
        # Stop simulators
        for simulator in simulators:
            simulator.stop()

    print("Test completed")


if __name__ == "__main__":
    main()