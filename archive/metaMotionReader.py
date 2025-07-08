#!/usr/bin/env python3
"""
Simple MetaMotion RL reader via BLE
"""

import asyncio
from bleak import BleakClient, BleakScanner
import struct
import time
import queue
import numpy as np


class MetaMotionReader:
    # BLE UUIDs
    COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
    NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"

    def __init__(self, macAddress=None):
        self.macAddress = macAddress
        self.client = None
        self.dataQueue = queue.Queue()
        self.connected = False
        self.streaming = False
        self.dataCount = 0

    async def findDevice(self):
        """Auto-discover MetaMotion device"""
        print("Scanning for MetaMotion devices...")
        devices = await BleakScanner.discover(timeout=10.0)

        for device in devices:
            print(f"  Found BLE device: {device.name} - {device.address}")
            if device.name and ("MetaWear" in device.name or "MetaMotion" in device.name):
                print(f"Found MetaMotion: {device.name} at {device.address}")
                return device.address
        return None

    async def connect(self):
        """Connect to MetaMotion"""
        if not self.macAddress:
            self.macAddress = await self.findDevice()
            if not self.macAddress:
                print("No MetaMotion found!")
                return False

        try:
            print(f"Connecting to MetaMotion at {self.macAddress}...")
            self.client = BleakClient(self.macAddress)
            await self.client.connect(timeout=20.0)

            if not self.client.is_connected:
                print("Failed to connect!")
                return False

            self.connected = True
            print(f"Connected to MetaMotion {self.macAddress}")

            # Read battery level as a connection test
            try:
                battery = await self.client.read_gatt_char("00002a19-0000-1000-8000-00805f9b34fb")
                print(f"Battery level: {int(battery[0])}%")
            except:
                print("Could not read battery level")

            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    # Replace the startStreaming method in your metaMotionReader.py with this:

    async def startStreaming(self):
        """Start accelerometer streaming - FIXED VERSION"""
        if not self.connected:
            print("Not connected!")
            return

        try:
            print("Starting MetaMotion streaming...")

            # Subscribe to notifications
            print("Subscribing to notifications...")
            await self.client.start_notify(self.NOTIFY_UUID, self._handleData)
            await asyncio.sleep(0.5)

            # Use EXACT sequence from working testMetaMotionUbuntu.py
            print("Configuring accelerometer (100Hz, ±4g)...")

            # Step 1: Enable accelerometer (this was missing!)
            await self.client.write_gatt_char(self.COMMAND_UUID, bytes([0x02, 0x02, 0x01, 0x00]))
            await asyncio.sleep(0.1)

            # Step 2: Configure settings (FIXED: 0x0C instead of 0x03)
            await self.client.write_gatt_char(self.COMMAND_UUID, bytes([0x02, 0x03, 0x28, 0x0C]))
            await asyncio.sleep(0.1)

            # Step 3: Start streaming
            print("Starting data stream...")
            await self.client.write_gatt_char(self.COMMAND_UUID, bytes([0x02, 0x01, 0x01]))

            self.streaming = True
            self.dataCount = 0
            print("MetaMotion streaming started!")

        except Exception as e:
            print(f"Failed to start streaming: {e}")
            import traceback
            traceback.print_exc()

    async def stopStreaming(self):
        """Stop streaming"""
        if self.connected and self.client:
            try:
                # Stop accelerometer
                await self.client.write_gatt_char(self.COMMAND_UUID, bytes([0x02, 0x01, 0x00]))
                await asyncio.sleep(0.1)

                # Stop notifications
                await self.client.stop_notify(self.NOTIFY_UUID)
                self.streaming = False
                print(f"Streaming stopped. Total samples received: {self.dataCount}")
            except Exception as e:
                print(f"Error stopping stream: {e}")

    def _handleData(self, sender, data):
        """Handle incoming BLE notification data"""
        try:
            if len(data) >= 7 and data[0] == 0x02:  # Accelerometer module
                # Parse accelerometer data
                x = struct.unpack('<h', data[2:4])[0] / 16384.0  # ±2g scale
                y = struct.unpack('<h', data[4:6])[0] / 16384.0
                z = struct.unpack('<h', data[6:8])[0] / 16384.0

                self.dataCount += 1

                # Add to queue
                self.dataQueue.put({
                    'timestamp': time.time(),
                    'x': x,
                    'y': y,
                    'z': z,
                    'magnitude': np.sqrt(x ** 2 + y ** 2 + z ** 2)
                })

                # Show first sample and periodic updates
                if self.dataCount == 1:
                    print(f"First accelerometer data: X={x:.3f}g, Y={y:.3f}g, Z={z:.3f}g")
                elif self.dataCount % 100 == 0:
                    print(f"Samples received: {self.dataCount}")

        except Exception as e:
            print(f"Error in data handler: {e}")

    def getData(self):
        """Get all available data"""
        data = []
        while not self.dataQueue.empty():
            try:
                data.append(self.dataQueue.get_nowait())
            except:
                break
        return data

    async def disconnect(self):
        """Disconnect from device"""
        await self.stopStreaming()
        if self.client:
            await self.client.disconnect()
        self.connected = False
        print("Disconnected from MetaMotion")