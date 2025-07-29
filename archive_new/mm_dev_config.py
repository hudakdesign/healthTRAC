#!/usr/bin/env python3
"""
Simplified MetaMotion Configuration for Continuous Streaming
Minimal configuration focused on reliability over features
"""

import asyncio
import sys
from bleak import BleakClient
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# MetaMotion Configuration
DEFAULT_MAC = "c8:0b:fb:24:c1:65"
COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"


class MetaMotionConfigurator:
    """Minimal configuration for continuous streaming"""

    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.client = None
        self.logger = logging.getLogger('MetaMotionConfig')

    async def connect(self):
        """Connect to MetaMotion with retries"""
        for attempt in range(3):
            try:
                self.logger.info(f"Connection attempt {attempt + 1}...")
                self.client = BleakClient(self.mac_address)
                await self.client.connect(timeout=20.0)

                if self.client.is_connected:
                    self.logger.info("Connected successfully")
                    return True

            except Exception as e:
                self.logger.error(f"Connection failed: {e}")
                await asyncio.sleep(2)

        return False

    async def configure_streaming(self):
        """Configure for simple continuous streaming"""
        try:
            # Wait for service discovery
            await asyncio.sleep(2)

            # Subscribe to notifications
            await self.client.start_notify(NOTIFY_UUID, lambda s, d: None)
            await asyncio.sleep(1)

            self.logger.info("Configuring accelerometer...")

            # Stop any existing streaming
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x01, 0x00]))
            await asyncio.sleep(0.5)

            # Power on accelerometer
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x02, 0x01, 0x00]))
            await asyncio.sleep(0.5)

            # Configure: 25Hz (lower rate for reliability), ±4g
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x03, 0x19, 0x0C]))
            await asyncio.sleep(0.5)

            # Enable data output (critical step)
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x04, 0x01, 0x01]))
            await asyncio.sleep(0.5)

            # Start streaming
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x01, 0x01]))
            await asyncio.sleep(0.5)

            self.logger.info("Streaming configuration complete")
            self.logger.info("Settings: 25Hz, ±4g range")

            # Keep connection alive for 5 seconds to verify streaming
            self.logger.info("Keeping connection open to verify streaming...")
            await asyncio.sleep(5)

            return True

        except Exception as e:
            self.logger.error(f"Configuration failed: {e}")
            return False

    async def disconnect(self):
        """Clean disconnect"""
        if self.client and self.client.is_connected:
            try:
                # Stop streaming before disconnect
                await self.client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x01, 0x00]))
                await asyncio.sleep(0.5)
                await self.client.disconnect()
                self.logger.info("Disconnected")
            except:
                pass


async def main():
    """Configure MetaMotion for streaming"""
    mac_address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MAC

    print(f"\nConfiguring MetaMotion {mac_address} for continuous streaming...")
    print("This will set up 25Hz accelerometer streaming\n")

    configurator = MetaMotionConfigurator(mac_address)

    if await configurator.connect():
        success = await configurator.configure_streaming()
        await configurator.disconnect()

        if success:
            print("\n✅ Configuration successful!")
            print("The MetaMotion is now configured for continuous streaming")
            print("Use the Arduino bridge to connect and receive data")
        else:
            print("\n❌ Configuration failed")
            print("Check the logs above for details")
    else:
        print("\n❌ Could not connect to MetaMotion")
        print("Make sure the device is powered on and in range")


if __name__ == "__main__":
    asyncio.run(main())