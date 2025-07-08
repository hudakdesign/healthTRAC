#!/usr/bin/env python3
"""
HealthTRAC Hub Server
Central data collection point with NTP time synchronization
Runs on Ubuntu VM (development) or Raspberry Pi (production)
"""

import socket
import threading
import time
import json
import csv
import os
from datetime import datetime
from collections import defaultdict
import logging
import ntplib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('HubServer')


class NTPManager:
    """Manages NTP time synchronization for accurate timestamps"""

    def __init__(self, ntp_server='pool.ntp.org'):
        self.ntp_server = ntp_server
        self.ntp_client = ntplib.NTPClient()
        self.time_offset = 0.0  # Offset between system time and NTP time
        self.last_sync = 0
        self.sync_interval = 3600  # Re-sync every hour

        # Do initial sync
        self.sync_time()

    def sync_time(self):
        """Synchronize with NTP server and calculate offset"""
        try:
            logger.info(f"Syncing with NTP server {self.ntp_server}...")
            response = self.ntp_client.request(self.ntp_server, version=3)

            # Calculate offset between local time and NTP time
            self.time_offset = response.offset
            self.last_sync = time.time()

            logger.info(f"NTP sync successful. Offset: {self.time_offset:.3f} seconds")
            return True

        except Exception as e:
            logger.error(f"NTP sync failed: {e}")
            return False

    def get_ntp_time(self):
        """Get current NTP-adjusted timestamp"""
        # Re-sync if needed
        if time.time() - self.last_sync > self.sync_interval:
            self.sync_time()

        # Return system time adjusted by NTP offset
        return time.time() + self.time_offset

    def format_timestamp(self, timestamp=None):
        """Format timestamp for logging"""
        if timestamp is None:
            timestamp = self.get_ntp_time()
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # Millisecond precision


class SensorConnection:
    """Represents a connected sensor client"""

    def __init__(self, client_socket, address, sensor_type):
        self.socket = client_socket
        self.address = address
        self.sensor_type = sensor_type
        self.connected_at = time.time()
        self.last_data = time.time()
        self.sample_count = 0
        self.error_count = 0

    def __str__(self):
        return f"{self.sensor_type}@{self.address[0]}:{self.address[1]}"


class DataWriter:
    """Handles writing sensor data to CSV files"""

    def __init__(self, data_dir='./data'):
        self.data_dir = data_dir
        self.session_dir = None
        self.files = {}
        self.writers = {}

        # Create data directory
        os.makedirs(data_dir, exist_ok=True)

        # Start new session
        self.start_session()

    def start_session(self):
        """Start a new data collection session"""
        # Create session directory with timestamp
        session_name = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session_dir = os.path.join(self.data_dir, session_name)
        os.makedirs(self.session_dir, exist_ok=True)

        logger.info(f"Started new session: {session_name}")

        # Create metadata file
        metadata_path = os.path.join(self.session_dir, 'session_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump({
                'start_time': time.time(),
                'start_time_formatted': datetime.now().isoformat(),
                'sensors': []
            }, f, indent=2)

    def get_writer(self, sensor_type):
        """Get CSV writer for a sensor type"""
        if sensor_type not in self.writers:
            # Create new CSV file for this sensor
            filename = f"{sensor_type.lower()}_data.csv"
            filepath = os.path.join(self.session_dir, filename)

            self.files[sensor_type] = open(filepath, 'w', newline='')
            self.writers[sensor_type] = csv.writer(self.files[sensor_type])

            # Write header based on sensor type
            if sensor_type == 'FSR':
                self.writers[sensor_type].writerow(['timestamp', 'force', 'raw_value'])
            elif sensor_type == 'ACCELEROMETER':
                self.writers[sensor_type].writerow(['timestamp', 'x', 'y', 'z', 'magnitude'])
            elif sensor_type == 'MICROPHONE':
                self.writers[sensor_type].writerow(['timestamp', 'rms_left', 'rms_right'])
            else:
                self.writers[sensor_type].writerow(['timestamp', 'value'])

            logger.info(f"Created CSV file for {sensor_type}")

        return self.writers[sensor_type]

    def write_data(self, sensor_type, timestamp, values):
        """Write sensor data to CSV"""
        writer = self.get_writer(sensor_type)
        row = [timestamp] + values
        writer.writerow(row)

        # Flush periodically for safety
        if time.time() % 10 < 0.1:  # Every ~10 seconds
            self.files[sensor_type].flush()

    def close(self):
        """Close all files"""
        for f in self.files.values():
            f.close()


class HubServer:
    """Main TCP server that collects data from all sensors"""

    def __init__(self, port=5555):
        self.port = port
        self.running = False
        self.server_socket = None

        # Connected clients
        self.clients = {}  # {client_id: SensorConnection}
        self.clients_lock = threading.Lock()

        # Components
        self.ntp_manager = NTPManager()
        self.data_writer = DataWriter()

        # Statistics
        self.stats = defaultdict(lambda: {
            'total_samples': 0,
            'error_count': 0,
            'last_sample_time': 0
        })

    def start(self):
        """Start the hub server"""
        self.running = True

        # Create server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(5)

        logger.info(f"Hub server listening on port {self.port}")

        # Start accept thread
        accept_thread = threading.Thread(target=self._accept_clients)
        accept_thread.daemon = True
        accept_thread.start()

        # Start status thread
        status_thread = threading.Thread(target=self._status_loop)
        status_thread.daemon = True
        status_thread.start()

        logger.info("Hub server started successfully")

    def _accept_clients(self):
        """Accept new client connections"""
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                client_socket, address = self.server_socket.accept()

                # Start handler thread for this client
                handler_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address)
                )
                handler_thread.daemon = True
                handler_thread.start()

            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Accept error: {e}")

    def _handle_client(self, client_socket, address):
        """Handle a connected sensor client"""
        client_id = f"{address[0]}:{address[1]}"
        sensor_conn = None

        try:
            # Set socket timeout
            client_socket.settimeout(30.0)

            # Wait for identification message
            data = client_socket.recv(1024).decode('utf-8').strip()
            if not data.startswith('SENSOR:'):
                logger.warning(f"Invalid identification from {client_id}: {data}")
                client_socket.close()
                return

            # Parse sensor type
            sensor_type = data.split(':')[1]
            sensor_conn = SensorConnection(client_socket, address, sensor_type)

            # Register client
            with self.clients_lock:
                self.clients[client_id] = sensor_conn

            logger.info(f"New sensor connected: {sensor_conn}")

            # Send acknowledgment with NTP time
            ack_msg = json.dumps({
                'status': 'connected',
                'ntp_time': self.ntp_manager.get_ntp_time(),
                'server_time': time.time()
            }) + '\n'
            client_socket.send(ack_msg.encode())

            # Handle data from this client
            buffer = ""
            while self.running:
                data = client_socket.recv(4096).decode('utf-8')
                if not data:
                    break

                buffer += data

                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self._process_data(sensor_conn, line.strip())

        except socket.timeout:
            logger.warning(f"Client {sensor_conn or client_id} timed out")
        except Exception as e:
            logger.error(f"Client {sensor_conn or client_id} error: {e}")
        finally:
            # Clean up
            with self.clients_lock:
                if client_id in self.clients:
                    del self.clients[client_id]
            client_socket.close()
            logger.info(f"Client {sensor_conn or client_id} disconnected")

    def _process_data(self, sensor_conn, data_line):
        """Process a line of sensor data"""
        try:
            # Parse JSON data
            data = json.loads(data_line)

            # Get NTP timestamp (or use provided timestamp)
            if 'timestamp' in data:
                timestamp = float(data['timestamp'])
            else:
                timestamp = self.ntp_manager.get_ntp_time()

            # Extract values based on sensor type
            values = []
            if sensor_conn.sensor_type == 'FSR':
                values = [data.get('force', 0), data.get('raw', 0)]
            elif sensor_conn.sensor_type == 'ACCELEROMETER':
                x, y, z = data.get('x', 0), data.get('y', 0), data.get('z', 0)
                magnitude = (x ** 2 + y ** 2 + z ** 2) ** 0.5
                values = [x, y, z, magnitude]
            elif sensor_conn.sensor_type == 'MICROPHONE':
                values = [data.get('rms_left', 0), data.get('rms_right', 0)]

            # Write to CSV
            self.data_writer.write_data(sensor_conn.sensor_type, timestamp, values)

            # Update statistics
            sensor_conn.sample_count += 1
            sensor_conn.last_data = time.time()
            self.stats[sensor_conn.sensor_type]['total_samples'] += 1
            self.stats[sensor_conn.sensor_type]['last_sample_time'] = timestamp

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from {sensor_conn}: {data_line}")
            sensor_conn.error_count += 1
            self.stats[sensor_conn.sensor_type]['error_count'] += 1
        except Exception as e:
            logger.error(f"Data processing error from {sensor_conn}: {e}")
            sensor_conn.error_count += 1

    def _status_loop(self):
        """Print status updates periodically"""
        while self.running:
            time.sleep(30)  # Every 30 seconds

            logger.info("=== Hub Status ===")
            logger.info(f"NTP time: {self.ntp_manager.format_timestamp()}")

            with self.clients_lock:
                logger.info(f"Connected clients: {len(self.clients)}")
                for client_id, conn in self.clients.items():
                    age = time.time() - conn.last_data
                    logger.info(f"  {conn}: {conn.sample_count} samples, "
                                f"last data {age:.1f}s ago")

            logger.info("Sensor statistics:")
            for sensor_type, stats in self.stats.items():
                logger.info(f"  {sensor_type}: {stats['total_samples']} total samples, "
                            f"{stats['error_count']} errors")

    def stop(self):
        """Stop the hub server"""
        logger.info("Stopping hub server...")
        self.running = False

        # Close all client connections
        with self.clients_lock:
            for conn in self.clients.values():
                conn.socket.close()

        # Close server socket
        if self.server_socket:
            self.server_socket.close()

        # Close data files
        self.data_writer.close()

        logger.info("Hub server stopped")


def main():
    """Main entry point"""
    # Create and start hub server
    hub = HubServer(port=5555)

    try:
        hub.start()

        # Keep running until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        hub.stop()


if __name__ == "__main__":
    main()