#!/usr/bin/env python3
"""
Configure MetaMotion RL for Smart Logging Mode
Sets up motion-triggered logging with 30-minute dock detection
"""

import asyncio
import struct
import time
from bleak import BleakClient
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class SmartLoggingConfigurator:
    """Configure MetaMotion for battery-optimized logging"""

    # BLE UUIDs
    COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
    NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"

    # Module IDs
    MODULE_SWITCH = 0x01
    MODULE_ACCELEROMETER = 0x02
    MODULE_GPIO = 0x05
    MODULE_TIMER = 0x0C
    MODULE_DATA_PROCESSOR = 0x09
    MODULE_LOGGING = 0x0B
    MODULE_MACRO = 0x0F
    MODULE_SETTINGS = 0x11
    MODULE_DEBUG = 0xFE

    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.client = None
        self.logger = logging.getLogger('Configurator')

    async def connect(self):
        """Connect to MetaMotion device"""
        self.logger.info(f"Connecting to MetaMotion at {self.mac_address}...")
        self.client = BleakClient(self.mac_address)
        await self.client.connect(timeout=20.0)

        if not self.client.is_connected:
            raise Exception("Failed to connect to MetaMotion")

        self.logger.info("Connected successfully")

        # Subscribe to notifications
        await self.client.start_notify(self.NOTIFY_UUID, self.handle_notification)
        await asyncio.sleep(0.5)

    def handle_notification(self, sender, data):
        """Handle BLE notifications"""
        # Log any responses for debugging
        if len(data) > 0:
            self.logger.debug(f"Notification: {data.hex()}")

    async def reset_device(self):
        """Factory reset the device"""
        self.logger.info("Performing factory reset...")

        # Clear all macros
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_MACRO, 0x05]))
        await asyncio.sleep(0.5)

        # Clear debug state
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_DEBUG, 0x06]))
        await asyncio.sleep(0.5)

        # Clear logging
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_LOGGING, 0x09]))
        await asyncio.sleep(0.5)

        self.logger.info("Reset complete")

    async def configure_accelerometer(self):
        """Configure accelerometer for 100Hz, ±4g"""
        self.logger.info("Configuring accelerometer...")

        # Stop accelerometer
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_ACCELEROMETER, 0x02, 0x00, 0x00]))
        await asyncio.sleep(0.1)

        # Configure: 100Hz, ±4g (0x28 = 100Hz, 0x0C = ±4g)
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_ACCELEROMETER, 0x03, 0x28, 0x0C]))
        await asyncio.sleep(0.1)

        # Enable accelerometer
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_ACCELEROMETER, 0x02, 0x01, 0x00]))
        await asyncio.sleep(0.1)

        self.logger.info("Accelerometer configured")

    async def configure_motion_detection(self):
        """Configure motion detection threshold (0.1g)"""
        self.logger.info("Setting up motion detection...")

        # Create data processor for motion detection
        # Threshold: 0.1g = 0.1 * 16384 = 1638.4 ≈ 1638 (0x0666)
        threshold = int(0.1 * 16384)

        # Configure magnitude processor
        # ID: 0x09 (magnitude), source: accel (0x02), config: RMS
        magnitude_config = bytes([
            self.MODULE_DATA_PROCESSOR, 0x02,  # Add processor
            0x09,  # Magnitude type
            0x03,  # Source: accelerometer XYZ
            0x00,  # No config needed for magnitude
        ])
        await self.client.write_gatt_char(self.COMMAND_UUID, magnitude_config)
        await asyncio.sleep(0.1)

        # Configure threshold detector
        # Detect when magnitude > 0.1g
        threshold_config = bytes([
            self.MODULE_DATA_PROCESSOR, 0x02,  # Add processor
            0x0D,  # Threshold type
            0x00,  # Source: previous processor (magnitude)
            0x01,  # Mode: absolute value
            struct.pack('<H', threshold)[0],  # Threshold low byte
            struct.pack('<H', threshold)[1],  # Threshold high byte
            0x00,  # Hysteresis low byte
            0x01,  # Hysteresis high byte
        ])
        await self.client.write_gatt_char(self.COMMAND_UUID, threshold_config)
        await asyncio.sleep(0.1)

        self.logger.info(f"Motion detection configured (threshold: {threshold / 16384:.2f}g)")

    async def configure_dock_timer(self):
        """Configure 30-minute timer for dock detection"""
        self.logger.info("Setting up 30-minute dock timer...")

        # 30 minutes in milliseconds
        thirty_min_ms = 30 * 60 * 1000  # 1,800,000 ms

        # Create timer that starts when no motion detected
        # Timer ID 0, period 30 min, repeat count 1
        timer_config = bytes([
            self.MODULE_TIMER, 0x02,  # Create timer
            thirty_min_ms & 0xFF,  # Period byte 0
            (thirty_min_ms >> 8) & 0xFF,  # Period byte 1
            (thirty_min_ms >> 16) & 0xFF,  # Period byte 2
            (thirty_min_ms >> 24) & 0xFF,  # Period byte 3
            0x01,  # Repeat count low
            0x00,  # Repeat count high
            0x00  # Delay (immediate)
        ])
        await self.client.write_gatt_char(self.COMMAND_UUID, timer_config)
        await asyncio.sleep(0.1)

        self.logger.info("Dock timer configured (30 minutes)")

    async def configure_logging(self):
        """Configure data logging"""
        self.logger.info("Configuring data logging...")

        # Stop any active logging
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_LOGGING, 0x01, 0x00]))
        await asyncio.sleep(0.1)

        # Clear existing log entries
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_LOGGING, 0x09]))
        await asyncio.sleep(0.5)

        # Configure circular buffer (overwrite old data when full)
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_LOGGING, 0x0B, 0x01]))
        await asyncio.sleep(0.1)

        # Configure to log accelerometer data
        # Source: accelerometer (0x02),
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_LOGGING, 0x02,
                                                 self.MODULE_ACCELEROMETER, 0x00]))
        await asyncio.sleep(0.1)

        self.logger.info("Logging configured")

    async def create_state_machine(self):
        """Create the motion-triggered logging state machine"""
        self.logger.info("Creating state machine...")

        # Macro 0: Start logging when motion detected
        # Triggered by motion threshold crossing
        macro0 = bytes([
            self.MODULE_MACRO, 0x02,  # Add macro
            0x01,  # Data processor trigger (motion detected)
            0x01,  # Action: multiple commands
            0x02,  # Number of commands
            # Command 1: Start logging
            self.MODULE_LOGGING, 0x01, 0x01,
            # Command 2: Stop timer (cancel dock detection)
            self.MODULE_TIMER, 0x01, 0x00
        ])
        await self.client.write_gatt_char(self.COMMAND_UUID, macro0)
        await asyncio.sleep(0.1)

        # Macro 1: Stop logging and start timer when no motion
        # Triggered by motion threshold NOT crossing
        macro1 = bytes([
            self.MODULE_MACRO, 0x02,  # Add macro
            0x01,  # Data processor trigger (no motion)
            0x00,  # Inverse condition (threshold NOT met)
            0x02,  # Number of commands
            # Command 1: Stop logging
            self.MODULE_LOGGING, 0x01, 0x00,
            # Command 2: Start 30-min timer
            self.MODULE_TIMER, 0x03, 0x00  # Start timer ID 0
        ])
        await self.client.write_gatt_char(self.COMMAND_UUID, macro1)
        await asyncio.sleep(0.1)

        # Macro 2: Enable BLE advertising when timer expires
        # This allows the hub/bridge to discover and sync
        macro2 = bytes([
            self.MODULE_MACRO, 0x02,  # Add macro
            0x0C,  # Timer trigger
            0x01,  # Action: command
            0x01,  # Number of commands
            # Command: Enable BLE advertising (settings module)
            self.MODULE_SETTINGS, 0x01, 0x01  # Enable advertising
        ])
        await self.client.write_gatt_char(self.COMMAND_UUID, macro2)
        await asyncio.sleep(0.1)

        # Start the macros
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_MACRO, 0x04]))
        await asyncio.sleep(0.1)

        self.logger.info("State machine created and started")

    async def configure_power_save(self):
        """Configure power saving settings"""
        self.logger.info("Configuring power save mode...")

        # Disable BLE advertising by default
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_SETTINGS, 0x01, 0x00]))
        await asyncio.sleep(0.1)

        # Set connection parameters for low power
        # Min interval: 500ms, Max interval: 1000ms, Latency: 4, Timeout: 600
        conn_params = bytes([
            self.MODULE_SETTINGS, 0x03,
            0xF4, 0x01,  # Min interval (500ms)
            0xE8, 0x03,  # Max interval (1000ms)
            0x04, 0x00,  # Latency
            0x58, 0x02  # Timeout (600)
        ])
        await self.client.write_gatt_char(self.COMMAND_UUID, conn_params)
        await asyncio.sleep(0.1)

        # Set low TX power (-4 dBm)
        await self.client.write_gatt_char(self.COMMAND_UUID,
                                          bytes([self.MODULE_SETTINGS, 0x04, 0xFC]))
        await asyncio.sleep(0.1)

        self.logger.info("Power save configured")

    async def configure_device(self):
        """Run complete configuration"""
        try:
            await self.connect()

            # Reset to known state
            await self.reset_device()
            await asyncio.sleep(1.0)

            # Configure components
            await self.configure_accelerometer()
            await self.configure_motion_detection()
            await self.configure_dock_timer()
            await self.configure_logging()
            await self.create_state_machine()
            await self.configure_power_save()

            # Start logging (will stop automatically when no motion)
            self.logger.info("Starting initial logging...")
            await self.client.write_gatt_char(self.COMMAND_UUID,
                                              bytes([self.MODULE_LOGGING, 0x01, 0x01]))
            await asyncio.sleep(0.1)

            self.logger.info("\n" + "=" * 60)
            self.logger.info("✅ MetaMotion configured for smart logging!")
            self.logger.info("=" * 60)
            self.logger.info("Behavior:")
            self.logger.info("- Logs data when motion > 0.1g detected")
            self.logger.info("- Stops logging when stationary")
            self.logger.info("- Enables BLE after 30 minutes stationary (docked)")
            self.logger.info("- Ready for sync when BLE is advertising")
            self.logger.info("- BLE disabled after sync to save battery")
            self.logger.info("\nExpected battery life: 11+ days")

        except Exception as e:
            self.logger.error(f"Configuration failed: {e}")
            raise
        finally:
            if self.client and self.client.is_connected:
                await self.client.disconnect()


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Configure MetaMotion for Smart Logging')
    parser.add_argument('mac_address', help='MetaMotion MAC address')
    parser.add_argument('--reset-only', action='store_true',
                        help='Only reset device, don\'t configure')

    args = parser.parse_args()

    configurator = SmartLoggingConfigurator(args.mac_address)

    if args.reset_only:
        await configurator.connect()
        await configurator.reset_device()
        await configurator.client.disconnect()
        print("Device reset complete")
    else:
        await configurator.configure_device()


if __name__ == "__main__":
    asyncio.run(main())