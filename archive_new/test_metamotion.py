#!/usr/bin/env python3
"""
Test script for MetaMotion RL with firmware 1.7.3
Based on diagnostic info from iOS
"""

import asyncio
import struct
from bleak import BleakClient
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger('FW173Test')

# Use the correct MAC address
MAC_ADDRESS = "C8:0B:FB:24:C1:65"
COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"


class MetaMotion173Test:
    def __init__(self):
        self.client = None
        self.data_count = 0
        self.notifications = []

    def handle_notification(self, sender, data):
        """Handle all notifications"""
        logger.info(f"📦 Notification: {data.hex()}")
        self.notifications.append(data)

        # Parse accelerometer data
        if len(data) >= 7 and data[0] == 0x03 and data[1] == 0x04:  # Accel module=0x03 for BMI160
            try:
                x = struct.unpack('<h', data[2:4])[0] / 16384.0
                y = struct.unpack('<h', data[4:6])[0] / 16384.0
                z = struct.unpack('<h', data[6:8])[0] / 16384.0
                self.data_count += 1
                logger.info(f"🎉 Accel #{self.data_count}: X={x:+.3f}, Y={y:+.3f}, Z={z:+.3f}")
            except:
                pass

    async def connect(self):
        """Connect to device"""
        logger.info(f"Connecting to {MAC_ADDRESS}...")
        self.client = BleakClient(MAC_ADDRESS)

        # Connect with longer timeout
        await self.client.connect(timeout=30.0)

        if not self.client.is_connected:
            raise Exception("Failed to connect")

        logger.info("✅ Connected!")

        # Wait for service discovery
        logger.info("Waiting for service discovery...")
        await asyncio.sleep(5.0)

        # Subscribe to notifications
        await self.client.start_notify(NOTIFY_UUID, self.handle_notification)
        await asyncio.sleep(1.0)

        logger.info("Ready for testing")

    async def test_bmi160_commands(self):
        """Test BMI160-specific commands for firmware 1.7.3"""
        logger.info("\n🔧 Testing BMI160 Accelerometer Commands...")

        # BMI160 uses module ID 0x03 (not 0x02)
        sequences = [
            {
                "name": "BMI160 Standard Enable",
                "commands": [
                    ([0x03, 0x01, 0x00], "Stop data"),
                    ([0x03, 0x02, 0x01, 0x00], "Power on"),
                    ([0x03, 0x03, 0x28, 0x0C], "Configure 100Hz, ±4g"),
                    ([0x03, 0x01, 0x01], "Start data"),
                ]
            },
            {
                "name": "BMI160 with Output Enable",
                "commands": [
                    ([0x03, 0x02, 0x01, 0x00], "Power on"),
                    ([0x03, 0x03, 0x28, 0x0C], "Configure"),
                    ([0x03, 0x04, 0x01, 0x01], "Enable output"),
                    ([0x03, 0x01, 0x01], "Start"),
                ]
            },
            {
                "name": "Legacy Mode (0x02 module)",
                "commands": [
                    ([0x02, 0x01, 0x00], "Stop"),
                    ([0x02, 0x02, 0x01, 0x00], "Enable"),
                    ([0x02, 0x03, 0x28, 0x0C], "Configure"),
                    ([0x02, 0x01, 0x01], "Start"),
                ]
            },
            {
                "name": "Direct Subscribe",
                "commands": [
                    ([0x03, 0x02, 0x01, 0x00], "Power on"),
                    ([0x03, 0x11, 0x01], "Subscribe to data"),
                ]
            }
        ]

        for seq in sequences:
            logger.info(f"\n📍 Testing: {seq['name']}")
            self.notifications.clear()
            self.data_count = 0

            for cmd, desc in seq['commands']:
                logger.info(f"  → {desc}")
                try:
                    await self.client.write_gatt_char(COMMAND_UUID, bytes(cmd))
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.warning(f"    Error: {e}")

            # Wait for data
            logger.info("  Waiting for data (move device!)...")
            await asyncio.sleep(3.0)

            if self.data_count > 0:
                logger.info(f"  ✅ SUCCESS! Got {self.data_count} samples")
                return True
            else:
                logger.info(f"  ❌ No data received")

        return False

    async def check_module_info(self):
        """Check module information"""
        logger.info("\n📋 Checking Module Info...")

        # Try both module IDs
        for module_id in [0x02, 0x03]:
            logger.info(f"\nChecking module 0x{module_id:02x}...")

            # Read module info
            await self.client.write_gatt_char(COMMAND_UUID, bytes([module_id, 0x80]))
            await asyncio.sleep(0.5)

            # Read status
            await self.client.write_gatt_char(COMMAND_UUID, bytes([module_id, 0x82]))
            await asyncio.sleep(0.5)

    async def try_mbientlab_protocol(self):
        """Try MbientLab's newer protocol"""
        logger.info("\n🔬 Testing MbientLab Protocol...")

        # Try packed output mode
        logger.info("Enabling packed output...")
        try:
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x12, 0x01, 0x00]))
            await asyncio.sleep(1.0)
        except:
            pass

        # Try high frequency mode
        logger.info("Enabling high frequency...")
        try:
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x03, 0x0A, 0x01, 0x00]))
            await asyncio.sleep(1.0)
        except:
            pass

    async def run_test(self):
        """Run complete test"""
        try:
            await self.connect()

            # Check module info first
            await self.check_module_info()

            # Test BMI160 commands
            success = await self.test_bmi160_commands()

            if not success:
                # Try MbientLab protocol
                await self.try_mbientlab_protocol()

            # Summary
            logger.info("\n" + "=" * 60)
            logger.info("TEST SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Device: MetaMotion RL")
            logger.info(f"Firmware: 1.7.3")
            logger.info(f"Accelerometer: BMI160")
            logger.info(f"Total notifications: {len(self.notifications)}")
            logger.info(f"Accel samples: {self.data_count}")

            if self.data_count > 0:
                logger.info("\n✅ Found working configuration!")
            else:
                logger.info("\n❌ No accelerometer data received")
                logger.info("\nNext steps:")
                logger.info("1. Try factory reset in iOS app")
                logger.info("2. Use iOS app to configure, then test")
                logger.info("3. Check if device needs DFU mode reset")

        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.client and self.client.is_connected:
                try:
                    await self.client.disconnect()
                except:
                    pass


async def main():
    logger.info("=" * 60)
    logger.info("MetaMotion RL Firmware 1.7.3 Test")
    logger.info("=" * 60)
    logger.info(f"Target: {MAC_ADDRESS}")
    logger.info("Based on iOS diagnostic info")
    logger.info("=" * 60)

    tester = MetaMotion173Test()
    await tester.run_test()


if __name__ == "__main__":
    asyncio.run(main())