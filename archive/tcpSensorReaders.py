#!/usr/bin/env python3
"""
TCP-based sensor readers for Mac
These replace the direct sensor connections and get data from Ubuntu
"""

import socket
import threading
import queue
import time
import numpy as np


class TCPFSRReader:
    """FSR reader that gets data via TCP from Ubuntu"""

    def __init__(self, ubuntu_host='localhost', ubuntu_port=5556):
        self.ubuntu_host = ubuntu_host
        self.ubuntu_port = ubuntu_port
        self.socket = None
        self.dataQueue = queue.Queue()
        self.connected = False
        self.thread = None
        self.running = False

    async def connect(self):
        """Connect to Ubuntu streamer"""
        try:
            print(f"Connecting to Ubuntu at {self.ubuntu_host}:{self.ubuntu_port}...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.ubuntu_host, self.ubuntu_port))
            self.connected = True

            # Start receiver thread
            self.running = True
            self.thread = threading.Thread(target=self._receive_loop)
            self.thread.daemon = True
            self.thread.start()

            print("Connected to Ubuntu sensor streamer (FSR)")
            return True

        except Exception as e:
            print(f"Failed to connect to Ubuntu: {e}")
            return False

    async def disconnect(self):
        """Disconnect"""
        self.stop()
        if self.socket:
            self.socket.close()
        self.connected = False

    async def startStreaming(self):
        """Compatibility method - streaming starts automatically"""
        print("FSR streaming from Ubuntu")

    async def stopStreaming(self):
        """Compatibility method"""
        pass

    def start(self):
        """Compatibility method"""
        pass

    def stop(self):
        """Stop receiving"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def _receive_loop(self):
        """Receive data from Ubuntu"""
        buffer = ""
        while self.running and self.socket:
            try:
                data = self.socket.recv(1024)
                if not data:
                    break

                buffer += data.decode('utf-8')

                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.startswith('FSR,'):
                        self._process_fsr_line(line)

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Receive error: {e}")
                break

    def _process_fsr_line(self, line):
        """Process FSR data line"""
        try:
            parts = line.split(',')
            if len(parts) >= 4:
                timestamp = float(parts[1])
                force = float(parts[2])
                raw = float(parts[3])

                self.dataQueue.put({
                    'timestamp': timestamp,
                    'force': force,
                    'raw': raw
                })
        except:
            pass

    def getData(self):
        """Get available data"""
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
        if self.socket:
            self.socket.close()


class TCPMetaMotionReader:
    """MetaMotion reader that gets data via TCP from Ubuntu"""

    def __init__(self, ubuntu_host='localhost', ubuntu_port=5556):
        self.ubuntu_host = ubuntu_host
        self.ubuntu_port = ubuntu_port
        self.socket = None
        self.dataQueue = queue.Queue()
        self.connected = False
        self.streaming = False
        self.dataCount = 0
        self.thread = None
        self.running = False

        # Share socket with FSR if same host/port
        self.shared_socket = None

    async def findDevice(self):
        """Compatibility method"""
        return True

    async def connect(self):
        """Connect to Ubuntu streamer"""
        try:
            # Check if we can share socket with FSR
            if not self.socket:
                print(f"Connecting to Ubuntu at {self.ubuntu_host}:{self.ubuntu_port}...")
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(5.0)
                self.socket.connect((self.ubuntu_host, self.ubuntu_port))

            self.connected = True

            # Start receiver thread
            self.running = True
            self.thread = threading.Thread(target=self._receive_loop)
            self.thread.daemon = True
            self.thread.start()

            print("Connected to Ubuntu sensor streamer (MetaMotion)")
            return True

        except Exception as e:
            print(f"Failed to connect to Ubuntu: {e}")
            return False

    async def disconnect(self):
        """Disconnect"""
        await self.stopStreaming()
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.socket:
            self.socket.close()
        self.connected = False

    async def startStreaming(self):
        """Compatibility method"""
        self.streaming = True
        self.dataCount = 0
        print("MetaMotion streaming from Ubuntu")

    async def stopStreaming(self):
        """Compatibility method"""
        self.streaming = False
        print(f"MetaMotion streaming stopped. Samples: {self.dataCount}")

    def _receive_loop(self):
        """Receive data from Ubuntu"""
        buffer = ""
        while self.running and self.socket:
            try:
                data = self.socket.recv(1024)
                if not data:
                    break

                buffer += data.decode('utf-8')

                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.startswith('MM,'):
                        self._process_mm_line(line)

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Receive error: {e}")
                break

    def _process_mm_line(self, line):
        """Process MetaMotion data line"""
        try:
            parts = line.split(',')
            if len(parts) >= 5:
                timestamp = float(parts[1])
                x = float(parts[2])
                y = float(parts[3])
                z = float(parts[4])

                self.dataCount += 1

                self.dataQueue.put({
                    'timestamp': timestamp,
                    'x': x,
                    'y': y,
                    'z': z,
                    'magnitude': np.sqrt(x ** 2 + y ** 2 + z ** 2)
                })

                if self.dataCount == 1:
                    print(f"First MM data: X={x:.3f}, Y={y:.3f}, Z={z:.3f}")
                elif self.dataCount % 100 == 0:
                    print(f"MM samples: {self.dataCount}")

        except:
            pass

    def getData(self):
        """Get available data"""
        data = []
        while not self.dataQueue.empty():
            try:
                data.append(self.dataQueue.get_nowait())
            except:
                break
        return data


# For drop-in replacement in dashboard.py
def get_tcp_readers(ubuntu_host, ubuntu_port=5556):
    """Get TCP-based readers that work with existing dashboard"""
    return TCPFSRReader(ubuntu_host, ubuntu_port), TCPMetaMotionReader(ubuntu_host, ubuntu_port)