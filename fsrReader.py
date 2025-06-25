#!/usr/bin/env python3
"""
Simple FSR sensor reader via ESP32 serial connection
"""

import serial
import serial.tools.list_ports
import time
import threading
import queue
from datetime import datetime


class FSRReader:
    def __init__(self, port=None, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.dataQueue = queue.Queue()
        self.running = False
        self.thread = None

    def findESP32(self):
        """Auto-detect ESP32 port"""
        ports = serial.tools.list_ports.comports()

        print("Available serial ports:")
        for port in ports:
            print(f"  {port.device} - {port.description}")

            # Check for common ESP32/USB-serial identifiers
            desc_lower = (port.description or "").lower()

            # SparkFun boards often use FTDI or CP2102
            if any(x in desc_lower for x in ['usbserial', 'cp210', 'ch340', 'ftdi', 'esp32', 'sparkfun']):
                print(f"Found potential ESP32 on {port.device}")
                return port.device

            # Also check the device name
            if 'usbserial' in port.device.lower():
                print(f"Found USB-serial device on {port.device}")
                return port.device

        return None

    def connect(self):
        """Connect to ESP32"""
        if not self.port:
            self.port = self.findESP32()
            if not self.port:
                print("No ESP32 found! Available ports:")
                for port in serial.tools.list_ports.comports():
                    print(f"  {port.device}")
                return False

        try:
            print(f"Attempting to connect to {self.port}...")
            self.serial = serial.Serial(self.port, self.baudrate, timeout=0.1)
            time.sleep(2)  # Wait for ESP32 to reset

            # Clear any startup messages
            self.serial.reset_input_buffer()

            print(f"Connected to FSR on {self.port}")
            return True
        except Exception as e:
            print(f"Failed to connect to {self.port}: {e}")
            return False

    def start(self):
        """Start reading data"""
        if not self.serial:
            return

        self.running = True
        self.serial.write(b"START\n")
        self.thread = threading.Thread(target=self._readLoop)
        self.thread.start()
        print("FSR streaming started")

    def stop(self):
        """Stop reading data"""
        self.running = False
        if self.serial:
            try:
                self.serial.write(b"STOP\n")
            except:
                pass
        if self.thread:
            self.thread.join()

    def _readLoop(self):
        """Background thread to read serial data"""
        buffer = ""
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    data = self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data

                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line and not line.startswith('#'):
                            self._processLine(line)

                time.sleep(0.001)  # Small delay to prevent CPU spinning

            except Exception as e:
                print(f"Read error: {e}")
                break

    def _processLine(self, line):
        """Process a line of data"""
        try:
            parts = line.strip().split(',')
            if len(parts) >= 2:
                # Use system timestamp for consistency
                timestamp = time.time()
                value = float(parts[1])

                # Simple force conversion (customize based on your FSR)
                force = self._adcToForce(value)

                self.dataQueue.put({
                    'timestamp': timestamp,
                    'force': force,
                    'raw': value
                })
        except:
            pass

    def _adcToForce(self, adc):
        """Convert ADC to force in Newtons (simplified)"""
        # This is a placeholder - calibrate for your specific FSR
        if adc < 100:
            return 0.0
        return (adc - 100) * 0.01  # Simple linear conversion

    def getData(self):
        """Get all available data"""
        data = []
        while not self.dataQueue.empty():
            try:
                data.append(self.dataQueue.get_nowait())
            except:
                break
        return data

    def close(self):
        """Clean up"""
        self.stop()
        if self.serial:
            self.serial.close()