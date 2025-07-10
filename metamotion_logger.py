#!/usr/bin/env python3
"""
MetaMotion Smart Logger
Syncs logged data from MetaMotion RL when it's docked
Integrates with existing TCP/NTP hub architecture
"""

import asyncio
import struct
import time
import json
from datetime import datetime
from bleak import BleakClient, BleakScanner
from sensor_client import SensorClient
import logging


class MetaMotionLogger(SensorClient):
    """MetaMotion RL logger that syncs stored data when docked"""

    # MetaMotion RL BLE UUIDs
    COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
    NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"

    # MbientLab commands for data logger
    CMD_LOGGING_START = bytes([0x0b, 0x01, 0x01])
    CMD_LOGGING_STOP = bytes([0x0b, 0x01, 0x00])
    CMD_LOGGING_FLUSH = bytes([0x0b, 0x07])
    CMD_LOGGING_DOWNLOAD = bytes([0x0b, 0x06, 0x01])
    CMD_LOGGING_DROP = bytes([0x0b, 0x09])
    CMD_LOGGING_LENGTH = bytes([0x0b, 0x08])

    # Accelerometer commands
    CMD_ACC_ENABLE = bytes([0x02, 0x02, 0x01, 0x00])
    CMD_ACC_DISABLE = bytes([0x02, 0x02, 0x00, 0x00])
    CMD_ACC_CONFIG = bytes([0x02, 0x03, 0x28, 0x0C])  # 100Hz, ±4g

    # Reset command
    CMD_RESET = bytes([0xfe, 0x05])

    def __init__(self, hub_host='localhost', hub_port=5555,
                 mac_address=None, sync_interval_hours=8):
        super().__init__('ACCELEROMETER_LOGGER', hub_host, hub_port)

        self.mac_address = mac_address
        self.sync_interval = sync_interval_hours * 3600  # Convert to seconds
        self.last_sync_time = 0

        # BLE state
        self.ble_client = None
        self.download_progress = 0
        self.total_entries = 0
        self.entries_received = 0

        # Data buffer for downloaded samples
        self.download_buffer = []
        self.sync_start_time = None

    async def find_metamotion_ready_for_sync(self):
        """Scan for MetaMotion devices advertising (ready for sync)"""
        self.logger.info("Scanning for MetaMotion devices ready to sync...")

        try:
            devices = await BleakScanner.discover(timeout=10.0)

            for device in devices:
                if device.name and ("MetaWear" in device.name or "MetaMotion" in device.name):
                    # Check if it's our target device
                    if self.mac_address and device.address.upper() != self.mac_address.upper():
                        continue

                    self.logger.info(f"Found MetaMotion ready for sync: {device.name} at {device.address}")
                    return device.address

            return None

        except Exception as e:
            self.logger.error(f"Scan error: {e}")
            return None

    def handle_notification(self, sender, data):
        """Handle BLE notifications during log download"""
        try:
            if len(data) < 2:
                return

            # Check if this is logging data
            if data[0] == 0x0b:
                if data[1] == 0x08:  # Log length response
                    if len(data) >= 6:
                        self.total_entries = struct.unpack('<I', data[2:6])[0]
                        self.logger.info(f"Log contains {self.total_entries} entries")

                elif data[1] == 0x07:  # Log readout data
                    if len(data) >= 11:
                        # Parse log entry
                        entry_id = struct.unpack('<I', data[2:6])[0]
                        epoch_ticks = struct.unpack('<I', data[6:10])[0]

                        # The actual sensor data starts at byte 10
                        sensor_data = data[10:]

                        # Check if this is accelerometer data (module 0x02)
                        if len(sensor_data) >= 7 and sensor_data[0] == 0x02:
                            # Parse accelerometer values
                            x = struct.unpack('<h', sensor_data[2:4])[0] / 16384.0
                            y = struct.unpack('<h', sensor_data[4:6])[0] / 16384.0
                            z = struct.unpack('<h', sensor_data[6:8])[0] / 16384.0

                            # Convert epoch ticks to timestamp
                            # MetaMotion epoch is milliseconds since boot
                            timestamp = self.sync_start_time - (self.total_entries - entry_id) * 0.01

                            # Add to buffer
                            self.download_buffer.append({
                                'timestamp': timestamp,
                                'x': round(x, 4),
                                'y': round(y, 4),
                                'z': round(z, 4),
                                'entry_id': entry_id
                            })

                            self.entries_received += 1

                            # Show progress
                            if self.entries_received % 100 == 0:
                                progress = (self.entries_received / self.total_entries) * 100
                                self.logger.info(f"Download progress: {progress:.1f}% "
                                                 f"({self.entries_received}/{self.total_entries})")

                elif data[1] == 0x0a:  # Download complete
                    self.logger.info("Log download complete")

        except Exception as e:
            self.logger.error(f"Notification error: {e}")

    async def sync_logged_data(self, device_address):
        """Download and sync logged data from MetaMotion"""
        try:
            self.logger.info(f"Connecting to {device_address} for data sync...")

            # Connect to device
            self.ble_client = BleakClient(device_address)
            await self.ble_client.connect(timeout=20.0)

            if not self.ble_client.is_connected:
                self.logger.error("Failed to connect")
                return False

            self.logger.info("Connected. Starting data sync...")

            # Subscribe to notifications
            await self.ble_client.start_notify(self.NOTIFY_UUID, self.handle_notification)
            await asyncio.sleep(0.5)

            # Stop any active logging
            await self.ble_client.write_gatt_char(self.COMMAND_UUID, self.CMD_LOGGING_STOP)
            await asyncio.sleep(0.5)

            # Get log length
            await self.ble_client.write_gatt_char(self.COMMAND_UUID, self.CMD_LOGGING_LENGTH)
            await asyncio.sleep(1.0)

            if self.total_entries == 0:
                self.logger.info("No logged data to sync")
                return True

            # Start download
            self.sync_start_time = self.get_timestamp()
            self.entries_received = 0
            self.download_buffer = []

            await self.ble_client.write_gatt_char(self.COMMAND_UUID, self.CMD_LOGGING_DOWNLOAD)

            # Wait for download to complete (with timeout)
            timeout = 60 + (self.total_entries / 100)  # Scale timeout with data size
            start_time = time.time()

            while self.entries_received < self.total_entries and time.time() - start_time < timeout:
                await asyncio.sleep(0.1)

            if self.entries_received >= self.total_entries:
                self.logger.info(f"Successfully downloaded {self.entries_received} entries")

                # Send all data to hub
                for entry in sorted(self.download_buffer, key=lambda x: x['timestamp']):
                    self.send_data({
                        'timestamp': entry['timestamp'],
                        'x': entry['x'],
                        'y': entry['y'],
                        'z': entry['z'],
                        'logged': True  # Mark as logged data
                    })

                # Clear the log on device
                await self.ble_client.write_gatt_char(self.COMMAND_UUID, self.CMD_LOGGING_DROP)
                await asyncio.sleep(0.5)

                # Restart logging
                await self.ble_client.write_gatt_char(self.COMMAND_UUID, self.CMD_LOGGING_START)

                self.last_sync_time = time.time()
                return True
            else:
                self.logger.error(f"Download timeout. Got {self.entries_received}/{self.total_entries}")
                return False

        except Exception as e:
            self.logger.error(f"Sync error: {e}")
            return False
        finally:
            if self.ble_client and self.ble_client.is_connected:
                await self.ble_client.disconnect()
                self.logger.info("Disconnected from MetaMotion")

    async def continuous_sync_loop(self):
        """Main loop that periodically checks for devices ready to sync"""
        while self.running:
            try:
                # Check if it's time to look for sync
                time_since_last_sync = time.time() - self.last_sync_time

                if time_since_last_sync >= self.sync_interval:
                    self.logger.info(f"Checking for MetaMotion ready to sync "
                                     f"(last sync: {time_since_last_sync / 3600:.1f} hours ago)")

                    # Look for device advertising
                    device_address = await self.find_metamotion_ready_for_sync()

                    if device_address:
                        # Sync data
                        success = await self.sync_logged_data(device_address)

                        if success:
                            self.logger.info("Data sync completed successfully")
                        else:
                            self.logger.error("Data sync failed")
                    else:
                        self.logger.info("No MetaMotion devices ready for sync")

                # Wait before next check (5 minutes)
                await asyncio.sleep(300)

            except Exception as e:
                self.logger.error(f"Sync loop error: {e}")
                await asyncio.sleep(60)

    def start_sensor(self):
        """Start the logger sync service"""
        self.running = True

        # Run async loop in thread
        import threading

        def run_async_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.continuous_sync_loop())

        self.sync_thread = threading.Thread(target=run_async_loop)
        self.sync_thread.daemon = True
        self.sync_thread.start()

        self.logger.info(f"MetaMotion logger started. Sync interval: {self.sync_interval / 3600:.1f} hours")

    def stop_sensor(self):
        """Stop the logger sync service"""
        self.running = False

        if hasattr(self, 'sync_thread'):
            self.sync_thread.join(timeout=5.0)

        self.logger.info("MetaMotion logger stopped")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='MetaMotion Smart Logger')
    parser.add_argument('--hub-host', default='localhost',
                        help='Hub server hostname/IP (default: localhost)')
    parser.add_argument('--hub-port', type=int, default=5555,
                        help='Hub server port (default: 5555)')
    parser.add_argument('--mac-address', required=True,
                        help='MetaMotion MAC address')
    parser.add_argument('--sync-hours', type=int, default=8,
                        help='Hours between sync attempts (default: 8)')

    args = parser.parse_args()

    # Create and run logger
    logger = MetaMotionLogger(
        hub_host=args.hub_host,
        hub_port=args.hub_port,
        mac_address=args.mac_address,
        sync_interval_hours=args.sync_hours
    )

    logger.run_forever()


if __name__ == "__main__":
    main()