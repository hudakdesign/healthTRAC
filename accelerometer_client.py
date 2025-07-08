#!/usr/bin/env python3
"""
MetaMotion Accelerometer Client
Reads data from MetaMotion RL via BLE and sends to hub via TCP
"""

import asyncio
import struct
import threading
import time
from bleak import BleakClient, BleakScanner
from sensor_client import SensorClient


class AccelerometerClient(SensorClient):
    """MetaMotion RL accelerometer client using BLE"""

    # MetaMotion RL BLE UUIDs
    COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
    NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"

    # MetaMotion commands (from working code)
    CMD_ACC_ENABLE = bytes([0x02, 0x02, 0x01, 0x00])
    CMD_ACC_CONFIG = bytes([0x02, 0x03, 0x28, 0x0C])  # 100Hz, ±4g
    CMD_ACC_START = bytes([0x02, 0x01, 0x01])
    CMD_ACC_STOP = bytes([0x02, 0x01, 0x00])

    def __init__(self, hub_host='localhost', hub_port=5555,
                 mac_address=None):
        super().__init__('ACCELEROMETER', hub_host, hub_port)

        # BLE configuration
        self.mac_address = mac_address
        self.ble_client = None
        self.ble_connected = False

        # Asyncio event loop for BLE
        self.loop = None
        self.ble_thread = None

        # Data statistics
        self.notification_count = 0

    def find_metamotion(self):
        """Auto-discover MetaMotion device"""

        async def scan():
            self.logger.info("Scanning for MetaMotion devices...")
            devices = await BleakScanner.discover(timeout=10.0)

            for device in devices:
                if device.name and ("MetaWear" in device.name or "MetaMotion" in device.name):
                    self.logger.info(f"Found MetaMotion: {device.name} at {device.address}")
                    return device.address

            self.logger.warning("No MetaMotion devices found")
            return None

        # Run scan in event loop
        if not self.loop:
            self.loop = asyncio.new_event_loop()

        return self.loop.run_until_complete(scan())

    def handle_notification(self, sender, data):
        """Handle BLE notification with accelerometer data"""
        try:
            # Check if this is accelerometer data
            if len(data) >= 7 and data[0] == 0x02:
                # Parse accelerometer values
                x = struct.unpack('<h', data[2:4])[0] / 16384.0  # Convert to g
                y = struct.unpack('<h', data[4:6])[0] / 16384.0
                z = struct.unpack('<h', data[6:8])[0] / 16384.0

                self.notification_count += 1

                # Send to hub
                self.send_data({
                    'x': round(x, 4),
                    'y': round(y, 4),
                    'z': round(z, 4)
                })

                # Log first sample and periodic updates
                if self.notification_count == 1:
                    self.logger.info(f"First accelerometer data: X={x:.3f}g, Y={y:.3f}g, Z={z:.3f}g")
                elif self.notification_count % 1000 == 0:
                    self.logger.info(f"Accelerometer samples: {self.notification_count}")

        except Exception as e:
            self.logger.error(f"Notification handler error: {e}")

    async def connect_ble(self):
        """Connect to MetaMotion via BLE"""
        try:
            self.logger.info(f"Connecting to MetaMotion at {self.mac_address}...")
            self.ble_client = BleakClient(self.mac_address)
            await self.ble_client.connect(timeout=20.0)

            if not self.ble_client.is_connected:
                self.logger.error("Failed to connect to MetaMotion")
                return False

            self.ble_connected = True
            self.logger.info("Connected to MetaMotion")

            # Read battery level
            try:
                battery_uuid = "00002a19-0000-1000-8000-00805f9b34fb"
                battery_data = await self.ble_client.read_gatt_char(battery_uuid)
                battery_level = int(battery_data[0])
                self.logger.info(f"MetaMotion battery: {battery_level}%")
            except:
                pass

            return True

        except Exception as e:
            self.logger.error(f"BLE connection failed: {e}")
            return False

    async def start_streaming(self):
        """Start accelerometer streaming"""
        try:
            # Subscribe to notifications
            self.logger.info("Subscribing to accelerometer notifications...")
            await self.ble_client.start_notify(self.NOTIFY_UUID, self.handle_notification)
            await asyncio.sleep(0.5)

            # Configure accelerometer (following working sequence)
            self.logger.info("Configuring accelerometer...")

            # Enable accelerometer
            await self.ble_client.write_gatt_char(self.COMMAND_UUID, self.CMD_ACC_ENABLE)
            await asyncio.sleep(0.1)

            # Configure settings
            await self.ble_client.write_gatt_char(self.COMMAND_UUID, self.CMD_ACC_CONFIG)
            await asyncio.sleep(0.1)

            # Start streaming
            await self.ble_client.write_gatt_char(self.COMMAND_UUID, self.CMD_ACC_START)

            self.logger.info("Accelerometer streaming started")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start streaming: {e}")
            return False

    async def stop_streaming(self):
        """Stop accelerometer streaming"""
        try:
            # Stop accelerometer
            await self.ble_client.write_gatt_char(self.COMMAND_UUID, self.CMD_ACC_STOP)
            await asyncio.sleep(0.1)

            # Stop notifications
            await self.ble_client.stop_notify(self.NOTIFY_UUID)

            self.logger.info("Accelerometer streaming stopped")

        except Exception as e:
            self.logger.error(f"Error stopping stream: {e}")

    async def ble_main_loop(self):
        """Main BLE async loop"""
        # Auto-detect if needed
        if not self.mac_address:
            self.mac_address = self.find_metamotion()
            if not self.mac_address:
                self.logger.error("No MetaMotion device found")
                return

        # Connect to MetaMotion
        if not await self.connect_ble():
            return

        # Start streaming
        if not await self.start_streaming():
            return

        # Keep running until stopped
        try:
            while self.ble_connected:
                await asyncio.sleep(1)
        except:
            pass
        finally:
            # Clean up
            if self.ble_client and self.ble_client.is_connected:
                await self.stop_streaming()
                await self.ble_client.disconnect()

    def _ble_thread_func(self):
        """BLE thread function"""
        # Create new event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Run BLE main loop
        self.loop.run_until_complete(self.ble_main_loop())

    def start_sensor(self):
        """Start accelerometer data collection"""
        # Start BLE thread
        self.ble_connected = True
        self.ble_thread = threading.Thread(target=self._ble_thread_func)
        self.ble_thread.daemon = True
        self.ble_thread.start()

        self.logger.info("Accelerometer client started")

    def stop_sensor(self):
        """Stop accelerometer data collection"""
        self.ble_connected = False

        # Wait for BLE thread to finish
        if self.ble_thread:
            self.ble_thread.join(timeout=5.0)

        self.logger.info(f"Accelerometer client stopped. Total notifications: {self.notification_count}")


def main():
    """Main entry point for standalone accelerometer client"""
    import argparse

    parser = argparse.ArgumentParser(description='MetaMotion Accelerometer Client')
    parser.add_argument('--hub-host', default='localhost',
                        help='Hub server hostname/IP (default: localhost)')
    parser.add_argument('--hub-port', type=int, default=5555,
                        help='Hub server port (default: 5555)')
    parser.add_argument('--mac-address', default=None,
                        help='MetaMotion MAC address (default: auto-detect)')

    args = parser.parse_args()

    # Create and run accelerometer client
    client = AccelerometerClient(
        hub_host=args.hub_host,
        hub_port=args.hub_port,
        mac_address=args.mac_address
    )

    client.run_forever()


if __name__ == "__main__":
    main()