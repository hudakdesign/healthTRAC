#!/usr/bin/env python3
"""
Exact copy of working metaMotionReader.py streaming sequence
Testing with exact same commands and timing
"""

import asyncio
import struct
from bleak import BleakClient, BleakScanner
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger('ExactTest')

MAC_ADDRESS = "C8:0B:FB:24:C1:65"
COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"


class ExactMetaMotionTest:
    def __init__(self):
        self.client = None
        self.data_count = 0
        self.connected = False
        self.streaming = False

    def _handleData(self, sender, data):
        """Handle incoming BLE notification data - EXACT copy from metaMotionReader"""
        try:
            if len(data) >= 7 and data[0] == 0x02:  # Accelerometer module
                # Parse accelerometer data
                x = struct.unpack('<h', data[2:4])[0] / 16384.0  # ±2g scale
                y = struct.unpack('<h', data[4:6])[0] / 16384.0
                z = struct.unpack('<h', data[6:8])[0] / 16384.0

                self.data_count += 1

                # Show first sample and periodic updates
                if self.data_count == 1:
                    logger.info(f"First accelerometer data: X={x:.3f}g, Y={y:.3f}g, Z={z:.3f}g")
                elif self.data_count % 100 == 0:
                    logger.info(f"Samples received: {self.data_count}")
                elif self.data_count % 10 == 0:  # More frequent for testing
                    logger.info(f"Sample {self.data_count}: X={x:.3f}, Y={y:.3f}, Z={z:.3f}")

        except Exception as e:
            logger.error(f"Error in data handler: {e}")

    async def connect(self):
        """Connect to MetaMotion - following exact pattern"""
        try:
            logger.info(f"Connecting to MetaMotion at {MAC_ADDRESS}...")
            self.client = BleakClient(MAC_ADDRESS)
            await self.client.connect(timeout=20.0)

            if not self.client.is_connected:
                logger.error("Failed to connect!")
                return False

            self.connected = True
            logger.info(f"Connected to MetaMotion {MAC_ADDRESS}")

            # Read battery level as a connection test
            try:
                battery = await self.client.read_gatt_char("00002a19-0000-1000-8000-00805f9b34fb")
                logger.info(f"Battery level: {int(battery[0])}%")
            except:
                logger.info("Could not read battery level")

            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def startStreaming(self):
        """Start accelerometer streaming - EXACT copy from metaMotionReader"""
        if not self.connected:
            logger.error("Not connected!")
            return

        try:
            logger.info("Starting MetaMotion streaming...")

            # Subscribe to notifications
            logger.info("Subscribing to notifications...")
            await self.client.start_notify(NOTIFY_UUID, self._handleData)
            await asyncio.sleep(0.5)

            # Use EXACT sequence from working testMetaMotionUbuntu.py
            logger.info("Configuring accelerometer (100Hz, ±4g)...")

            # Step 1: Enable accelerometer
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x02, 0x02, 0x01, 0x00]))
            await asyncio.sleep(0.1)

            # Step 2: Configure settings
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x02, 0x03, 0x28, 0x0C]))
            await asyncio.sleep(0.1)

            # Step 3: Start streaming
            logger.info("Starting data stream...")
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x02, 0x01, 0x01]))

            self.streaming = True
            self.data_count = 0
            logger.info("MetaMotion streaming started!")

        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            import traceback
            traceback.print_exc()

    async def test_different_configs(self):
        """Try different accelerometer configurations to see what works"""
        logger.info("\n🔧 Trying different configurations...")

        configs = [
            ("25Hz, ±2g", [0x02, 0x03, 0x19, 0x03]),
            ("50Hz, ±4g", [0x02, 0x03, 0x14, 0x0C]),
            ("100Hz, ±2g", [0x02, 0x03, 0x28, 0x03]),
            ("100Hz, ±4g", [0x02, 0x03, 0x28, 0x0C]),
            ("100Hz, ±8g", [0x02, 0x03, 0x28, 0x10]),
        ]

        for name, config_cmd in configs:
            logger.info(f"\nTrying {name}...")
            self.data_count = 0

            # Stop streaming
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x02, 0x01, 0x00]))
            await asyncio.sleep(0.5)

            # Apply config
            await self.client.write_gatt_char(COMMAND_UUID, bytes(config_cmd))
            await asyncio.sleep(0.5)

            # Start streaming
            await self.client.write_gatt_char(COMMAND_UUID, bytes([0x02, 0x01, 0x01]))
            await asyncio.sleep(2.0)

            if self.data_count > 0:
                logger.info(f"✅ {name} works! Got {self.data_count} samples")
                return True
            else:
                logger.info(f"❌ {name} - no data")

        return False

    async def test_raw_commands(self):
        """Test with raw register reads to debug"""
        logger.info("\n🔍 Testing raw register reads...")

        # Try reading accelerometer data register directly
        logger.info("Reading accelerometer output register...")
        await self.client.write_gatt_char(COMMAND_UUID, bytes([0x02, 0x81]))  # Read data register
        await asyncio.sleep(1.0)

        # Try reading accelerometer status
        logger.info("Reading accelerometer status...")
        await self.client.write_gatt_char(COMMAND_UUID, bytes([0x02, 0x82]))  # Read status
        await asyncio.sleep(1.0)

    async def run_test(self):
        """Run complete test"""
        try:
            # Connect
            if not await self.connect():
                return

            # Try exact sequence first
            await self.startStreaming()

            # Wait for data
            logger.info("\n📊 Waiting for data (MOVE THE DEVICE!)...")
            for i in range(10):
                await asyncio.sleep(1)
                if self.data_count > 0:
                    logger.info(f"✅ Data flowing! Count: {self.data_count}")
                else:
                    logger.info(f"Waiting... {i + 1}/10 (shake the device!)")

            # If no data, try different configs
            if self.data_count == 0:
                logger.info("\n⚠️ No data with default config, trying alternatives...")
                success = await self.test_different_configs()

                if not success:
                    # Try raw reads
                    await self.test_raw_commands()

            # Summary
            logger.info("\n" + "=" * 60)
            logger.info("TEST RESULTS")
            logger.info("=" * 60)
            logger.info(f"Total samples received: {self.data_count}")

            if self.data_count > 0:
                logger.info("\n✅ SUCCESS! Device is streaming")
                logger.info("The accelerometer is working!")
            else:
                logger.info("\n❌ No accelerometer data received")
                logger.info("\nPossible issues:")
                logger.info("1. Device might need firmware update")
                logger.info("2. Device might be in different mode")
                logger.info("3. Try using iOS app to start streaming first")

        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.connected and self.client:
                try:
                    # Stop streaming
                    await self.client.write_gatt_char(COMMAND_UUID, bytes([0x02, 0x01, 0x00]))
                    await asyncio.sleep(0.5)
                    await self.client.stop_notify(NOTIFY_UUID)
                except:
                    pass

                try:
                    await self.client.disconnect()
                    logger.info("Disconnected")
                except:
                    pass


async def main():
    logger.info("=" * 60)
    logger.info("Exact MetaMotion Test")
    logger.info("Following exact pattern from metaMotionReader.py")
    logger.info("=" * 60)

    tester = ExactMetaMotionTest()
    await tester.run_test()


if __name__ == "__main__":
    asyncio.run(main())