#!/usr/bin/env python3
"""
FSR Sensor Client
Reads data from ESP32 via serial and sends to hub via TCP
"""

import serial
import serial.tools.list_ports
import time
import threading
from sensor_client import SensorClient


class FSRClient(SensorClient):
    """FSR sensor client that reads from ESP32 serial"""

    def __init__(self, hub_host='localhost', hub_port=5555,
                 serial_port=None, baudrate=115200):
        super().__init__('FSR', hub_host, hub_port)

        # Serial configuration
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.serial_conn = None

        # Reader thread
        self.reader_thread = None
        self.reading = False

        # Calibration parameters (adjust based on your FSR)
        self.force_threshold = 100  # Minimum ADC value to register force
        self.force_scale = 0.01  # ADC to Newtons conversion factor

    def find_esp32_port(self):
        """Auto-detect ESP32 serial port"""
        self.logger.info("Searching for ESP32...")

        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.logger.debug(f"Found port: {port.device} - {port.description}")

            # Check for common ESP32 identifiers
            if any(x in (port.description or "").lower()
                   for x in ['esp32', 'cp210', 'ch340', 'ftdi', 'usbserial']):
                self.logger.info(f"Found potential ESP32 on {port.device}")
                return port.device

            # Also check device name
            if 'usbserial' in port.device.lower() or 'ttyusb' in port.device.lower():
                self.logger.info(f"Found USB serial device on {port.device}")
                return port.device

        self.logger.warning("No ESP32 found. Available ports:")
        for port in ports:
            self.logger.warning(f"  {port.device}: {port.description}")
        return None

    def connect_serial(self):
        """Connect to ESP32 via serial"""
        # Auto-detect port if not specified
        if not self.serial_port:
            self.serial_port = self.find_esp32_port()
            if not self.serial_port:
                return False

        try:
            self.logger.info(f"Connecting to ESP32 on {self.serial_port}...")
            self.serial_conn = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                timeout=1.0
            )

            # Wait for ESP32 to initialize
            time.sleep(2)

            # Clear any startup messages
            self.serial_conn.reset_input_buffer()

            # Send start command
            self.serial_conn.write(b"START\n")
            time.sleep(0.1)

            # Read response
            response = self.serial_conn.readline().decode('utf-8').strip()
            if response:
                self.logger.info(f"ESP32 response: {response}")

            self.logger.info("Connected to ESP32")
            return True

        except Exception as e:
            self.logger.error(f"Serial connection failed: {e}")
            return False

    def adc_to_force(self, adc_value):
        """Convert ADC reading to force in Newtons"""
        if adc_value < self.force_threshold:
            return 0.0
        return (adc_value - self.force_threshold) * self.force_scale

    def _read_serial_loop(self):
        """Background thread that reads serial data"""
        buffer = ""

        while self.reading and self.serial_conn:
            try:
                # Read available data
                if self.serial_conn.in_waiting:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    buffer += data.decode('utf-8', errors='ignore')

                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()

                        # Skip comments and empty lines
                        if line and not line.startswith('#'):
                            self._process_serial_line(line)

                time.sleep(0.001)  # Small delay to prevent CPU hogging

            except Exception as e:
                self.logger.error(f"Serial read error: {e}")
                break

    def _process_serial_line(self, line):
        """Process a line of serial data from ESP32"""
        try:
            # Expected format: "timestamp,adc_value"
            parts = line.split(',')
            if len(parts) >= 2:
                # esp32_timestamp = float(parts[0])  # Not used, we use NTP time
                adc_value = float(parts[1])

                # Convert ADC to force
                force = self.adc_to_force(adc_value)

                # Send to hub
                self.send_data({
                    'force': round(force, 3),
                    'raw': int(adc_value)
                })

        except ValueError as e:
            self.logger.warning(f"Invalid data line: {line} - {e}")

    def start_sensor(self):
        """Start FSR data collection"""
        # Connect to ESP32
        if not self.connect_serial():
            raise Exception("Failed to connect to ESP32")

        # Start reader thread
        self.reading = True
        self.reader_thread = threading.Thread(target=self._read_serial_loop)
        self.reader_thread.daemon = True
        self.reader_thread.start()

        self.logger.info("FSR data collection started")

    def stop_sensor(self):
        """Stop FSR data collection"""
        self.reading = False

        # Send stop command to ESP32
        if self.serial_conn:
            try:
                self.serial_conn.write(b"STOP\n")
                time.sleep(0.1)
            except:
                pass

        # Wait for reader thread
        if self.reader_thread:
            self.reader_thread.join(timeout=2.0)

        # Close serial connection
        if self.serial_conn:
            self.serial_conn.close()

        self.logger.info("FSR data collection stopped")


def main():
    """Main entry point for standalone FSR client"""
    import argparse

    parser = argparse.ArgumentParser(description='FSR Sensor Client')
    parser.add_argument('--hub-host', default='localhost',
                        help='Hub server hostname/IP (default: localhost)')
    parser.add_argument('--hub-port', type=int, default=5555,
                        help='Hub server port (default: 5555)')
    parser.add_argument('--serial-port', default=None,
                        help='Serial port for ESP32 (default: auto-detect)')
    parser.add_argument('--baudrate', type=int, default=115200,
                        help='Serial baudrate (default: 115200)')

    args = parser.parse_args()

    # Create and run FSR client
    client = FSRClient(
        hub_host=args.hub_host,
        hub_port=args.hub_port,
        serial_port=args.serial_port,
        baudrate=args.baudrate
    )

    client.run_forever()


if __name__ == "__main__":
    main()