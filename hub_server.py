#!/usr/bin/env python3
"""
Health TRAC Hub Server (Version 3.0)
-----------------------------------
TCP server that receives sensor data, timestamps it with NTP-synchronized time,
stores it to CSV files, and broadcasts it via WebSocket for real-time visualization.

Features:
- TCP listener on port 5555
- NTP time synchronization
- CSV data storage by session
- WebSocket server for real-time data
- Modular sensor support
"""

import socket
import threading
import json
import time
import os
import datetime
import logging
import signal
import sys
import ntplib
from flask import Flask, render_template
from flask_socketio import SocketIO
import csv
import queue
from typing import Dict, List, Any, Optional

# Configuration
TCP_PORT = 5555
WEBSOCKET_PORT = 5000
DATA_DIR = "./data/sessions"
LOG_DIR = "./logs"
NTP_SERVER = "pool.ntp.org"
NTP_UPDATE_INTERVAL = 3600  # seconds
SENSOR_TIMEOUT = 10  # seconds to consider a sensor disconnected
MAX_CONNECTIONS = 20
BUFFER_SIZE = 1024

# Global variables
active_sensors = {}  # Track connected sensors
sensor_last_seen = {}  # Last time we heard from each sensor
ntp_offset = 0.0  # Time difference between local and NTP
session_id = ""  # Current session identifier
data_files = {}  # Open file handles for each sensor
data_queues = {}  # Queues for each sensor type
stop_event = threading.Event()  # For clean shutdown
lock = threading.Lock()  # Thread synchronization

# Setup Flask and SocketIO for web interface
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("hub_server")


def setup_directories():
    """Create necessary directories if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    # Add file handler for logging
    file_handler = logging.FileHandler(
        os.path.join(LOG_DIR, f"hub_server_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"))
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)


def create_new_session():
    """Create a new data collection session with unique ID."""
    global session_id
    session_id = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    session_dir = os.path.join(DATA_DIR, f"session_{session_id}")
    os.makedirs(session_dir, exist_ok=True)
    logger.info(f"Created new session: {session_id}")
    return session_dir


def get_ntp_time():
    """Synchronize with NTP server and calculate offset."""
    global ntp_offset
    try:
        ntp_client = ntplib.NTPClient()
        response = ntp_client.request(NTP_SERVER, timeout=5)
        # Calculate the offset between system time and NTP time
        ntp_offset = response.offset
        logger.info(f"NTP sync successful. Offset: {ntp_offset:.6f} seconds")
        return True
    except Exception as e:
        logger.error(f"NTP sync failed: {e}")
        return False


def get_current_time():
    """Get current time adjusted by NTP offset."""
    return time.time() + ntp_offset


def update_ntp_periodically():
    """Update NTP offset periodically in the background."""
    while not stop_event.is_set():
        get_ntp_time()
        # Sleep until next update, but check stop_event every second
        for _ in range(NTP_UPDATE_INTERVAL):
            if stop_event.is_set():
                break
            time.sleep(1)


def monitor_connections():
    """Monitor sensor connections and detect timeouts."""
    while not stop_event.is_set():
        current_time = get_current_time()
        with lock:
            for sensor_id, last_seen in list(sensor_last_seen.items()):
                if current_time - last_seen > SENSOR_TIMEOUT:
                    logger.info(f"Sensor {sensor_id} timed out (no data for {SENSOR_TIMEOUT}s)")
                    # Don't remove from active_sensors yet, just mark as disconnected
                    socketio.emit('sensor_status', {'sensor': sensor_id, 'status': 'disconnected'})
        time.sleep(1)


def open_data_file(sensor_type, session_dir):
    """Open a CSV file for the specified sensor type."""
    filename = os.path.join(session_dir, f"{sensor_type}_data.csv")

    # Define headers based on sensor type
    headers = {
        'fsr': ['timestamp', 'force', 'raw'],
        'imu': ['timestamp', 'x', 'y', 'z', 'activity'],
        'mic': ['timestamp', 'rms', 'zcr', 'centroid'],
    }

    # Use default headers if sensor type is unknown
    file_headers = headers.get(sensor_type, ['timestamp', 'data'])

    # Create file and write header
    file = open(filename, 'w', newline='')
    writer = csv.writer(file)
    writer.writerow(file_headers)

    return file, writer


def data_writer_thread(sensor_type, q):
    """Thread that writes data from queue to CSV file."""
    while not stop_event.is_set():
        try:
            data = q.get(timeout=1.0)
            if data is None:  # None is our signal to exit
                break

            # Check if we have an open file for this sensor
            if sensor_type not in data_files or data_files[sensor_type] is None:
                with lock:
                    session_dir = os.path.join(DATA_DIR, f"session_{session_id}")
                    file, writer = open_data_file(sensor_type, session_dir)
                    data_files[sensor_type] = (file, writer)

            # Write data to CSV
            file, writer = data_files[sensor_type]

            # Extract fields based on sensor type
            if sensor_type == 'fsr':
                row = [data.get('timestamp', 0), data.get('force', 0), data.get('raw', 0)]
            elif sensor_type == 'imu':
                row = [data.get('timestamp', 0), data.get('x', 0), data.get('y', 0),
                       data.get('z', 0), data.get('activity', '')]
            elif sensor_type == 'mic':
                row = [data.get('timestamp', 0), data.get('rms', 0),
                       data.get('zcr', 0), data.get('centroid', 0)]
            else:
                # Generic fallback
                row = [data.get('timestamp', 0), str(data)]

            writer.writerow(row)
            file.flush()  # Ensure data is written to disk

            q.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Error in data writer thread for {sensor_type}: {e}")


def handle_client(client_socket, client_address):
    """Handle an individual client connection."""
    logger.info(f"New connection from {client_address}")

    try:
        # Wait for handshake
        data = client_socket.recv(BUFFER_SIZE).decode('utf-8').strip()
        if not data.startswith("SENSOR:"):
            logger.warning(f"Invalid handshake from {client_address}: {data}")
            client_socket.close()
            return

        # Extract sensor type
        sensor_type = data[7:].lower()  # Remove "SENSOR:" prefix
        sensor_id = f"{sensor_type}_{client_address[0]}_{client_address[1]}"

        logger.info(f"Sensor {sensor_id} ({sensor_type}) connected")

        # Send ready signal
        client_socket.send(b"READY\n")

        # Create data queue if it doesn't exist
        if sensor_type not in data_queues:
            data_queues[sensor_type] = queue.Queue()
            # Start a writer thread for this sensor type
            threading.Thread(
                target=data_writer_thread,
                args=(sensor_type, data_queues[sensor_type]),
                daemon=True
            ).start()

        # Add to active sensors
        with lock:
            active_sensors[sensor_id] = {
                'type': sensor_type,
                'address': client_address,
                'connected_at': get_current_time(),
                'samples_received': 0
            }
            sensor_last_seen[sensor_id] = get_current_time()

        # Notify web clients
        socketio.emit('sensor_status', {
            'sensor': sensor_id,
            'type': sensor_type,
            'status': 'connected'
        })

        # Process incoming data
        buffer = ""
        while not stop_event.is_set():
            try:
                chunk = client_socket.recv(BUFFER_SIZE).decode('utf-8')
                if not chunk:
                    break  # Connection closed

                buffer += chunk

                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)

                    try:
                        # Parse JSON data
                        data = json.loads(line)

                        # Add accurate timestamp if not present
                        if 'timestamp' not in data or data['timestamp'] == 0:
                            data['timestamp'] = round(get_current_time(), 3)  # ms precision

                        # Add sequence number if not present
                        if 'sequence' not in data:
                            with lock:
                                data['sequence'] = active_sensors[sensor_id]['samples_received']

                        # Update last seen time and count
                        with lock:
                            sensor_last_seen[sensor_id] = get_current_time()
                            active_sensors[sensor_id]['samples_received'] += 1

                        # Add to processing queue
                        data_queues[sensor_type].put(data)

                        # Forward to websocket clients
                        socketio.emit('sensor_data', data)

                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from {sensor_id}: {line}")

            except socket.timeout:
                # Socket timeout, check if we should exit
                if stop_event.is_set():
                    break
            except Exception as e:
                logger.error(f"Error handling {sensor_id}: {e}")
                break

        # Cleanup on disconnect
        logger.info(f"Sensor {sensor_id} disconnected")
        socketio.emit('sensor_status', {'sensor': sensor_id, 'status': 'disconnected'})

    except Exception as e:
        logger.error(f"Error handling connection from {client_address}: {e}")
    finally:
        client_socket.close()


def tcp_server():
    """Main TCP server thread."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind(('0.0.0.0', TCP_PORT))
        server.listen(MAX_CONNECTIONS)
        server.settimeout(1.0)  # Allow checking stop_event periodically

        logger.info(f"Hub server listening on port {TCP_PORT}")

        while not stop_event.is_set():
            try:
                client_socket, client_address = server.accept()
                client_thread = threading.Thread(
                    target=handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
            except socket.timeout:
                continue  # This allows us to check stop_event periodically
            except Exception as e:
                logger.error(f"Error accepting connection: {e}")
                if stop_event.is_set():
                    break
                time.sleep(1)  # Avoid tight loop on repeated errors

    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        server.close()
        logger.info("TCP server stopped")


def close_data_files():
    """Close all open data files."""
    for sensor_type, (file, _) in list(data_files.items()):
        try:
            file.flush()
            file.close()
            logger.info(f"Closed data file for {sensor_type}")
        except Exception as e:
            logger.error(f"Error closing data file for {sensor_type}: {e}")
        data_files[sensor_type] = None


def shutdown_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutdown signal received")
    stop_event.set()

    # Close data files
    close_data_files()

    # Signal data writer threads to exit
    for q in data_queues.values():
        q.put(None)

    logger.info("Shutdown complete")
    sys.exit(0)


@app.route('/')
def index():
    """Serve the status page."""
    return render_template('status.html')


@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connections."""
    logger.info("Web client connected")
    # Send current sensor status
    with lock:
        for sensor_id, info in active_sensors.items():
            status = 'connected'
            if get_current_time() - sensor_last_seen.get(sensor_id, 0) > SENSOR_TIMEOUT:
                status = 'disconnected'

            socketio.emit('sensor_status', {
                'sensor': sensor_id,
                'type': info['type'],
                'status': status,
                'samples': info['samples_received']
            })


@socketio.on('start_session')
def start_new_session():
    """Start a new data collection session."""
    with lock:
        # Close existing files
        close_data_files()
        # Create new session
        session_dir = create_new_session()
        logger.info(f"Starting new session: {session_id}")
        socketio.emit('session_update', {'session': session_id, 'status': 'started'})
        return {'status': 'success', 'session': session_id}


@socketio.on('stop_session')
def stop_current_session():
    """Stop the current data collection session."""
    with lock:
        # Close existing files
        close_data_files()
        logger.info(f"Stopping session: {session_id}")
        socketio.emit('session_update', {'session': session_id, 'status': 'stopped'})
        return {'status': 'success', 'session': session_id}


def start_server():
    """Start the hub server."""
    # Set up directories
    setup_directories()

    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Create initial session
    create_new_session()

    # Start NTP synchronization
    get_ntp_time()  # Initial sync
    ntp_thread = threading.Thread(target=update_ntp_periodically, daemon=True)
    ntp_thread.start()

    # Start connection monitor
    monitor_thread = threading.Thread(target=monitor_connections, daemon=True)
    monitor_thread.start()

    # Start TCP server in a thread
    tcp_thread = threading.Thread(target=tcp_server, daemon=True)
    tcp_thread.start()

    # Start Flask-SocketIO server
    logger.info(f"Web dashboard available at http://localhost:{WEBSOCKET_PORT}")
    socketio.run(app, host='0.0.0.0', port=WEBSOCKET_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    start_server()