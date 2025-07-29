#!/usr/bin/env python3
"""
HealthTRAC - Hub Server v2
Improved TCP server that receives data from the Arduino bridge,
assigns NTP-based timestamps, validates JSON data, and stores in CSV format.
"""

import socket
import time
import csv
import json
import threading
import os
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("hub_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Hub")

# Configuration
HOST = "10.0.1.3"  # Listen on all interfaces
PORT = 5555        # Port for incoming data
CSV_DIR = "data"  # Directory for CSV files
MAX_CONNECTIONS = 5

def get_ntp_timestamp():
    """Get the current timestamp using system time (NTP-synced)."""
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

def get_csv_filename():
    """Generate a CSV filename based on the current date."""
    date_str = datetime.utcnow().strftime('%Y%m%d')
    return os.path.join(CSV_DIR, f"healthtrac_{date_str}.csv")

def ensure_csv_exists(filename):
    """Ensure the CSV file exists with headers."""
    # Create directory if needed
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Check if file exists and has headers
    file_exists = os.path.exists(filename)
    if not file_exists:
        with open(filename, mode='w', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([
                "timestamp", "sensor_type", "index",
                "x", "y", "z", "raw_data"
            ])
            logger.info(f"Created new CSV file: {filename}")

    return filename

def handle_client(conn, addr):
    """Handle a client connection."""
    logger.info(f"Connection established with {addr}")
    sensor_type = "unknown"
    buffer = ""

    try:
        # Get client identification
        data = conn.recv(1024).decode('utf-8').strip()
        if data.startswith("SENSOR:"):
            sensor_type = data[7:]
            logger.info(f"Client identified as: {sensor_type}")
            conn.sendall(f"ACK:{sensor_type}\n".encode('utf-8'))

        # Open CSV file for writing
        csv_filename = ensure_csv_exists(get_csv_filename())

        with open(csv_filename, mode='a', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)

            # Process incoming data
            while True:
                data = conn.recv(1024).decode('utf-8')
                if not data:
                    break

                buffer += data

                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue

                    # Assign timestamp
                    timestamp = get_ntp_timestamp()

                    try:
                        # Try to parse as JSON
                        json_data = json.loads(line)

                        # Extract values
                        sensor = json_data.get("sensor", sensor_type)
                        index = json_data.get("index", 0)
                        x = json_data.get("x", 0)
                        y = json_data.get("y", 0)
                        z = json_data.get("z", 0)

                        # Write to CSV
                        csv_writer.writerow([
                            timestamp, sensor, index, x, y, z, line
                        ])

                        # Log data receipt
                        if index % 10 == 0:  # Only log every 10th sample
                            logger.info(f"Data from {sensor}: x={x:.2f}, y={y:.2f}, z={z:.2f}")

                    except json.JSONDecodeError:
                        # Not valid JSON, store as raw data
                        logger.warning(f"Non-JSON data received: {line}")
                        csv_writer.writerow([
                            timestamp, sensor_type, 0, 0, 0, 0, line
                        ])

                    # Flush to ensure data is written
                    csv_file.flush()

    except Exception as e:
        logger.error(f"Error processing client data: {e}")

    finally:
        conn.close()
        logger.info(f"Connection closed with {addr}")

def start_server():
    """Start the TCP server to receive data."""
    # Create server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Set socket options to allow address reuse
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(MAX_CONNECTIONS)
        logger.info(f"Hub Server started. Listening on {HOST}:{PORT}...")

        while True:
            # Accept connection
            conn, addr = server_socket.accept()

            # Handle client in a new thread
            client_thread = threading.Thread(
                target=handle_client,
                args=(conn, addr)
            )
            client_thread.daemon = True
            client_thread.start()

    except KeyboardInterrupt:
        logger.info("Server shutting down...")

    except Exception as e:
        logger.error(f"Server error: {e}")

    finally:
        server_socket.close()
        logger.info("Server stopped.")

if __name__ == "__main__":
    # Print banner
    print("\n" + "=" * 60)
    print("HealthTRAC Hub Server v2")
    print("=" * 60)

    # Start the server
    start_server()