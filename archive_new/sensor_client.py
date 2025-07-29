#!/usr/bin/env python3
"""
Base Sensor Client Class
Provides TCP connection and NTP time sync for all sensor types
"""

import socket
import json
import time
import threading
import logging
import ntplib
from abc import ABC, abstractmethod
from queue import Queue, Empty

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class SensorClient(ABC):
    """
    Base class for all sensor clients
    Handles TCP connection, NTP sync, and data transmission
    """

    def __init__(self, sensor_type, hub_host='localhost', hub_port=5555,
                 ntp_server='pool.ntp.org'):
        # Basic info
        self.sensor_type = sensor_type
        self.hub_host = hub_host
        self.hub_port = hub_port
        self.ntp_server = ntp_server

        # Connection state
        self.socket = None
        self.connected = False
        self.running = False

        # NTP synchronization
        self.ntp_client = ntplib.NTPClient()
        self.time_offset = 0.0
        self.last_ntp_sync = 0

        # Data queue for reliable transmission
        self.data_queue = Queue(maxsize=1000)
        self.send_thread = None

        # Statistics
        self.samples_sent = 0
        self.samples_dropped = 0
        self.connection_attempts = 0

        # Logger
        self.logger = logging.getLogger(f'{sensor_type}Client')

    def connect(self):
        """Connect to the hub server"""
        try:
            self.connection_attempts += 1
            self.logger.info(f"Connecting to hub at {self.hub_host}:{self.hub_port}...")

            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)
            self.socket.connect((self.hub_host, self.hub_port))

            # Send identification
            id_msg = f"SENSOR:{self.sensor_type}\n"
            self.socket.send(id_msg.encode())

            # Wait for acknowledgment
            ack_data = self.socket.recv(1024).decode('utf-8').strip()
            ack = json.loads(ack_data)

            if ack.get('status') == 'connected':
                self.connected = True

                # Sync time with server's NTP time
                if 'ntp_time' in ack and 'server_time' in ack:
                    server_ntp_time = ack['ntp_time']
                    server_system_time = ack['server_time']
                    local_time = time.time()

                    # Calculate offset to match server's NTP time
                    self.time_offset = server_ntp_time - local_time
                    self.logger.info(f"Time synchronized with hub. Offset: {self.time_offset:.3f}s")

                self.logger.info("Successfully connected to hub")
                return True
            else:
                self.logger.error(f"Connection rejected: {ack}")
                return False

        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            if self.socket:
                self.socket.close()
                self.socket = None
            return False

    def sync_ntp_time(self):
        """Synchronize with NTP server"""
        try:
            # Only sync every hour
            if time.time() - self.last_ntp_sync < 3600:
                return

            self.logger.info("Synchronizing with NTP server...")
            response = self.ntp_client.request(self.ntp_server, version=3)
            self.time_offset = response.offset
            self.last_ntp_sync = time.time()
            self.logger.info(f"NTP sync complete. Offset: {self.time_offset:.3f}s")

        except Exception as e:
            self.logger.warning(f"NTP sync failed: {e}")

    def get_timestamp(self):
        """Get NTP-adjusted timestamp"""
        return time.time() + self.time_offset

    def send_data(self, data_dict):
        """
        Queue data for transmission to hub
        data_dict should contain sensor-specific fields
        """
        # Add timestamp if not present
        if 'timestamp' not in data_dict:
            data_dict['timestamp'] = self.get_timestamp()

        # Try to add to queue
        try:
            self.data_queue.put_nowait(data_dict)
        except:
            # Queue full, drop oldest data
            try:
                self.data_queue.get_nowait()
                self.data_queue.put_nowait(data_dict)
                self.samples_dropped += 1
            except:
                pass

    def _send_loop(self):
        """Background thread that sends queued data to hub"""
        while self.running:
            try:
                # Get data from queue (with timeout)
                data = self.data_queue.get(timeout=1.0)

                if self.connected and self.socket:
                    # Convert to JSON and send
                    json_data = json.dumps(data) + '\n'
                    self.socket.send(json_data.encode())
                    self.samples_sent += 1

            except Empty:
                # No data to send
                continue
            except Exception as e:
                self.logger.error(f"Send error: {e}")
                self.connected = False

                # Try to reconnect
                time.sleep(5)
                if self.connect():
                    self.logger.info("Reconnected to hub")

    def start(self):
        """Start the sensor client"""
        self.logger.info(f"Starting {self.sensor_type} sensor client...")

        # Connect to hub
        if not self.connect():
            self.logger.error("Failed to connect to hub")
            return False

        # Start send thread
        self.running = True
        self.send_thread = threading.Thread(target=self._send_loop)
        self.send_thread.daemon = True
        self.send_thread.start()

        # Start sensor-specific data collection
        self.start_sensor()

        self.logger.info(f"{self.sensor_type} sensor client started")
        return True

    def stop(self):
        """Stop the sensor client"""
        self.logger.info(f"Stopping {self.sensor_type} sensor client...")

        # Stop sensor-specific collection
        self.stop_sensor()

        # Stop send thread
        self.running = False
        if self.send_thread:
            self.send_thread.join(timeout=5.0)

        # Close connection
        if self.socket:
            self.socket.close()

        self.logger.info(f"{self.sensor_type} sensor client stopped")
        self.logger.info(f"Statistics: {self.samples_sent} sent, {self.samples_dropped} dropped")

    @abstractmethod
    def start_sensor(self):
        """Start sensor-specific data collection (implement in subclass)"""
        pass

    @abstractmethod
    def stop_sensor(self):
        """Stop sensor-specific data collection (implement in subclass)"""
        pass

    def run_forever(self):
        """Convenience method to run until interrupted"""
        try:
            if self.start():
                self.logger.info("Press Ctrl+C to stop...")
                while True:
                    time.sleep(1)

                    # Print periodic status
                    if time.time() % 60 < 1:  # Every minute
                        self.logger.info(f"Status: {self.samples_sent} samples sent, "
                                         f"queue size: {self.data_queue.qsize()}")
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        finally:
            self.stop()