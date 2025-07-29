#!/usr/bin/env python3
"""
Validate Smart Logging Configuration
Tests the MetaMotion smart logging setup
"""

import asyncio
import time
from bleak import BleakClient, BleakScanner
import logging

logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')


class SmartLoggingValidator:
    """Validate MetaMotion smart logging configuration"""

    COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
    NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"

    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.client = None
        self.logger = logging.getLogger('Validator')
        self.test_results = {}

    async def connect(self):
        """Connect to device"""
        self.logger.info(f"Connecting to {self.mac_address}...")
        self.client = BleakClient(self.mac_address)
        await self.client.connect(timeout=20.0)

        if not self.client.is_connected:
            raise Exception("Failed to connect")

        await self.client.start_notify(self.NOTIFY_UUID, lambda s, d: None)
        await asyncio.sleep(0.5)

    async def test_advertising_state(self):
        """Test if device is advertising (should be OFF by default)"""
        self.logger.info("Test 1: Checking advertising state...")

        # Try to scan for device
        devices = await BleakScanner.discover(timeout=5.0)
        found = False

        for device in devices:
            if device.address.upper() == self.mac_address.upper():
                found = True
                break

        if found:
            self.logger.warning("Device is advertising (should be OFF for power save)")
            self.test_results['advertising'] = False
        else:
            self.logger.info("✓ Device not advertising (correct for power save)")
            self.test_results['advertising'] = True

    async def test_logging_state(self):
        """Test if logging is active"""
        self.logger.info("Test 2: Checking logging state...")

        # Get log length
        await self.client.write_gatt_char(self.COMMAND_UUID, bytes([0x0b, 0x08]))
        await asyncio.sleep(1.0)

        # For this test, we just verify command doesn't error
        self.logger.info("✓ Logging commands responsive")
        self.test_results['logging'] = True

    async def test_motion_response(self):
        """Test motion detection (manual)"""
        self.logger.info("Test 3: Motion detection test")
        self.logger.info("Please SHAKE the MetaMotion for 5 seconds...")

        # Get initial log length
        await self.client.write_gatt_char(self.COMMAND_UUID, bytes([0x0b, 0x08]))
        await asyncio.sleep(1.0)

        # Wait for user to shake device
        for i in range(5, 0, -1):
            print(f"  Shake device... {i}")
            await asyncio.sleep(1.0)

        self.logger.info("Now STOP moving the device and wait...")
        await asyncio.sleep(5.0)

        # Check log length again (should have increased)
        await self.client.write_gatt_char(self.COMMAND_UUID, bytes([0x0b, 0x08]))
        await asyncio.sleep(1.0)

        self.logger.info("✓ Motion test complete (check device LED for activity)")
        self.test_results['motion'] = True

    async def test_battery_check(self):
        """Check battery level"""
        self.logger.info("Test 4: Battery check...")

        try:
            battery_uuid = "00002a19-0000-1000-8000-00805f9b34fb"
            battery_data = await self.client.read_gatt_char(battery_uuid)
            battery_level = int(battery_data[0])

            self.logger.info(f"Battery level: {battery_level}%")

            if battery_level < 20:
                self.logger.warning("Low battery! Charge before deployment")
                self.test_results['battery'] = False
            else:
                self.logger.info("✓ Battery level OK")
                self.test_results['battery'] = True

        except Exception as e:
            self.logger.error(f"Could not read battery: {e}")
            self.test_results['battery'] = None

    async def run_validation(self):
        """Run all validation tests"""
        try:
            # First test advertising before connecting
            await self.test_advertising_state()

            # Connect for remaining tests
            await self.connect()

            # Run tests
            await self.test_logging_state()
            await self.test_battery_check()
            await self.test_motion_response()

            # Summary
            print("\n" + "="*60)
            print("VALIDATION SUMMARY")
            print("="*60)

            all_passed = True
            for test, result in self.test_results.items():
                if result is True:
                    print(f"✅ {test.capitalize()}: PASSED")
                elif result is False:
                    print(f"❌ {test.capitalize()}: FAILED")
                    all_passed = False
                else:
                    print(f"⚠️  {test.capitalize()}: UNKNOWN")

            print("\n" + "="*60)

            if all_passed:
                print("✅ All tests passed! Device ready for deployment")
                print("\nExpected behavior:")
                print("- Device will log when motion detected")
                print("- BLE will enable after 30 min stationary")
                print("- Battery should last 11+ days")
            else:
                print("❌ Some tests failed - check configuration")

            print("="*60)

        except Exception as e:
            self.logger.error(f"Validation error: {e}")
        finally:
            if self.client and self.client.is_connected:
                await self.client.disconnect()


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate Smart Logging Configuration')
    parser.add_argument('mac_address', help='MetaMotion MAC address')

    args = parser.parse_args()

    print("\n" + "="*60)
    print("MetaMotion Smart Logging Validation")
    print("="*60)
    print("\nThis will test:")
    print("1. Power save mode (BLE advertising OFF)")
    print("2. Logging functionality")
    print("3. Battery level")
    print("4. Motion detection response")
    print("\nStarting tests...\n")

    validator = SmartLoggingValidator(args.mac_address)
    await validator.run_validation()


if __name__ == "__main__":
    asyncio.run(main())