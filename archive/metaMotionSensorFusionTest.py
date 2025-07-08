#!/usr/bin/env python3
"""
Try using sensor fusion module instead of direct accelerometer
"""

import asyncio
from bleak import BleakClient
import struct

ADDRESS = "EC762719-9838-7A35-23BD-22EB21D3A994"
COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"

count = 0


def handle_data(sender, data):
    global count
    count += 1
    print(f"\nPacket {count}: {data.hex()}")

    # Try different parsing approaches
    if len(data) >= 7:
        if data[0] == 0x02:  # Accelerometer
            x = struct.unpack('<h', data[2:4])[0] / 16384.0
            y = struct.unpack('<h', data[4:6])[0] / 16384.0
            z = struct.unpack('<h', data[6:8])[0] / 16384.0
            print(f"  Accel: X={x:.3f}, Y={y:.3f}, Z={z:.3f}")
        elif data[0] == 0x19:  # Sensor fusion
            print(f"  Sensor fusion data (module 0x19)")
            if len(data) >= 15:  # Quaternion data
                print(f"  Possible quaternion or euler angles")


async def main():
    print("MetaMotion Sensor Fusion Test")
    print("=" * 50)

    async with BleakClient(ADDRESS) as client:
        print("Connected!")

        await client.start_notify(NOTIFY_UUID, handle_data)

        # Try sensor fusion approach
        print("\n1. Trying sensor fusion commands...")

        # Stop any existing streams
        await client.write_gatt_char(COMMAND_UUID, bytes([0x19, 0x01, 0x00]))
        await asyncio.sleep(0.5)

        # Configure sensor fusion
        print("   Configuring sensor fusion...")
        # Mode: 0x00 = sleep, 0x01 = ACC, 0x02 = ACC+GYRO, 0x03 = ACC+MAG, 0x04 = ACC+GYRO+MAG
        await client.write_gatt_char(COMMAND_UUID, bytes([0x19, 0x02, 0x01, 0x00]))  # ACC only mode
        await asyncio.sleep(0.5)

        # Start sensor fusion
        print("   Starting sensor fusion...")
        await client.write_gatt_char(COMMAND_UUID, bytes([0x19, 0x01, 0x01]))
        await asyncio.sleep(2)

        if count == 0:
            print("\n2. Trying different fusion modes...")

            # Try ACC+GYRO mode
            await client.write_gatt_char(COMMAND_UUID, bytes([0x19, 0x02, 0x02, 0x00]))
            await asyncio.sleep(0.5)
            await client.write_gatt_char(COMMAND_UUID, bytes([0x19, 0x01, 0x01]))
            await asyncio.sleep(2)

        if count == 0:
            print("\n3. Trying to enable accelerometer through fusion...")

            # Enable individual sensors through fusion
            await client.write_gatt_char(COMMAND_UUID, bytes([0x19, 0x03, 0x00, 0x20]))  # Enable accel
            await asyncio.sleep(0.5)
            await client.write_gatt_char(COMMAND_UUID, bytes([0x19, 0x01, 0x01]))
            await asyncio.sleep(2)

        if count == 0:
            print("\n4. Last attempt - trying raw accelerometer with different parameters...")

            # Different configuration bytes
            configs = [
                bytes([0x02, 0x03, 0x26, 0x00]),  # 12.5Hz
                bytes([0x02, 0x03, 0x27, 0x03]),  # 25Hz, different range
                bytes([0x02, 0x03, 0x28, 0x0C]),  # Original config
            ]

            for config in configs:
                print(f"   Config: {config.hex()}")
                await client.write_gatt_char(COMMAND_UUID, config)
                await asyncio.sleep(0.2)
                await client.write_gatt_char(COMMAND_UUID, bytes([0x02, 0x01, 0x01]))
                await asyncio.sleep(1)
                if count > 0:
                    break

        print(f"\nTotal packets received: {count}")

        if count == 0:
            print("\n" + "=" * 50)
            print("IMPORTANT: Firmware 1.7.3 requires app initialization")
            print("\nPlease follow these steps EXACTLY:")
            print("1. Install MetaWear app on your phone")
            print("2. Open the app and connect to your MetaMotion")
            print("3. Go to 'Accelerometer' section")
            print("4. Tap 'Start' to begin streaming")
            print("5. Verify you see live data graphs")
            print("6. Leave the app running and streaming")
            print("7. On your computer, run: python piggybackTest.py")
            print("\nThe device MUST be streaming in the app first!")


if __name__ == "__main__":
    asyncio.run(main())