#!/usr/bin/env python3
"""
Alternative approach using PyMetaWear or manual BLE commands
Since the official metawear package won't build
"""

import asyncio
from bleak import BleakClient
import struct
import time

# Try using pymetawear instead (community maintained)
# Install with: pip install pymetawear

try:
    from pymetawear.client import MetaWearClient

    PYMETAWEAR_AVAILABLE = True
except ImportError:
    PYMETAWEAR_AVAILABLE = False
    print("PyMetaWear not available, using manual approach")

ADDRESS = "C8:0B:FB:24:C1:65"


# Option 1: Try PyMetaWear (community package)
def test_pymetawear():
    """Test using pymetawear package"""
    if not PYMETAWEAR_AVAILABLE:
        print("Install pymetawear first: pip install pymetawear")
        return

    print("Testing with PyMetaWear...")
    client = MetaWearClient(ADDRESS)

    # This package handles firmware 1.7.3 better
    client.connect()

    print("Battery:", client.battery.read())

    # Subscribe to accelerometer
    def acc_callback(data):
        print(f"Accel: {data}")

    client.accelerometer.notifications(acc_callback)

    time.sleep(10)

    client.disconnect()


# Option 2: Use mbientlab's recommended initialization for 1.7.3
async def test_mbientlab_init():
    """Use initialization sequence from mbientlab forums for 1.7.3"""
    print("Testing MbientLab recommended init for 1.7.3...")

    COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
    NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"

    data_count = 0

    def handle_notification(sender, data):
        nonlocal data_count
        data_count += 1

        print(f"Packet {data_count}: {data.hex()}")

        # Check different packet types
        if len(data) >= 7:
            module = data[0]
            if module == 0x02:  # Standard accelerometer
                x = struct.unpack('<h', data[2:4])[0] / 16384.0
                y = struct.unpack('<h', data[4:6])[0] / 16384.0
                z = struct.unpack('<h', data[6:8])[0] / 16384.0
                print(f"  Accel: X={x:.3f}, Y={y:.3f}, Z={z:.3f}")
            elif module == 0x03:  # Alternative accelerometer ID
                # Some 1.7.3 firmware uses module 0x03
                x = struct.unpack('<h', data[2:4])[0] / 16384.0
                y = struct.unpack('<h', data[4:6])[0] / 16384.0
                z = struct.unpack('<h', data[6:8])[0] / 16384.0
                print(f"  Accel (0x03): X={x:.3f}, Y={y:.3f}, Z={z:.3f}")

    async with BleakClient(ADDRESS) as client:
        print("Connected!")

        # Subscribe first
        await client.start_notify(NOTIFY_UUID, handle_notification)

        print("Trying firmware 1.7.3 specific initialization...")

        # Sequence from MbientLab forums for 1.7.3
        commands = [
            # 1. Stop everything
            bytes([0x02, 0x01, 0x00]),
            bytes([0x03, 0x01, 0x00]),

            # 2. Set data route (required for 1.7.3)
            bytes([0x09, 0x02, 0x02, 0x01, 0x00, 0xFF, 0xFF, 0x00]),

            # 3. Configure accelerometer
            bytes([0x03, 0x02, 0x01, 0x00]),  # Set range
            bytes([0x03, 0x03, 0x27, 0x00]),  # Set ODR

            # 4. Enable output
            bytes([0x03, 0x04, 0x01]),

            # 5. Start
            bytes([0x03, 0x01, 0x01]),

            # Also try module 0x02
            bytes([0x02, 0x04, 0x01]),
            bytes([0x02, 0x01, 0x01]),
        ]

        for cmd in commands:
            print(f"Sending: {cmd.hex()}")
            try:
                await client.write_gatt_char(COMMAND_UUID, cmd)
                await asyncio.sleep(0.2)
            except Exception as e:
                print(f"  Error: {e}")

        print("\nWaiting for data (10 seconds)...")
        await asyncio.sleep(10)

        print(f"\nTotal packets: {data_count}")


# Option 3: Use raw BLE and capture app packets
async def capture_app_init():
    """
    Monitor what the MetaWear app sends
    Run this while the app is connecting
    """
    print("Monitoring BLE traffic...")
    print("1. Start this script")
    print("2. Open MetaWear app and connect")
    print("3. Start accelerometer in app")
    print("4. Watch what commands are sent")

    COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
    NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"

    # We'll just listen for notifications
    def handle_all(sender, data):
        print(f"From {sender}: {data.hex()}")

    try:
        async with BleakClient(ADDRESS) as client:
            print("Connected! Monitoring...")

            # Subscribe to notifications
            await client.start_notify(NOTIFY_UUID, handle_all)

            # Monitor for 60 seconds
            await asyncio.sleep(60)

    except Exception as e:
        print(f"Error: {e}")


async def main():
    print("MetaMotion 1.7.3 Alternative Approaches")
    print("=" * 50)

    # Try different approaches
    print("\n1. Testing MbientLab init sequence...")
    await test_mbientlab_init()

    print("\n" + "=" * 50)
    print("\nIf no data received, options:")
    print("1. Install pymetawear: pip install pymetawear")
    print("2. Use MetaWear app + capture mode")
    print("3. Consider using a different sensor")

    # Uncomment to try other options:
    # await capture_app_init()
    # test_pymetawear()


if __name__ == "__main__":
    asyncio.run(main())