#!/usr/bin/env python3
"""
Brute force test to find working commands for firmware 1.7.3
"""

import asyncio
from bleak import BleakClient
import struct
import time

ADDRESS = "EC762719-9838-7A35-23BD-22EB21D3A994"
COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"

packets_received = []


def handle_notification(sender, data):
    """Capture any notification data"""
    packets_received.append(data)
    print(f"\n✅ PACKET RECEIVED: {data.hex()}")

    # Try to parse as accelerometer
    if len(data) >= 7 and data[0] == 0x02:
        try:
            x = struct.unpack('<h', data[2:4])[0] / 16384.0
            y = struct.unpack('<h', data[4:6])[0] / 16384.0
            z = struct.unpack('<h', data[6:8])[0] / 16384.0
            print(f"   Accelerometer: X={x:.3f}, Y={y:.3f}, Z={z:.3f}")
        except:
            pass


async def try_sequence(client, name, commands, wait_time=2.0):
    """Try a command sequence and wait for data"""
    print(f"\n{'=' * 50}")
    print(f"Testing: {name}")
    packets_received.clear()

    for cmd in commands:
        print(f"  Sending: {' '.join(f'{b:02x}' for b in cmd)}")
        try:
            await client.write_gatt_char(COMMAND_UUID, cmd)
            await asyncio.sleep(0.2)
        except Exception as e:
            print(f"  Error: {e}")

    print(f"  Waiting {wait_time}s for data...")
    await asyncio.sleep(wait_time)

    if packets_received:
        print(f"  ✅ SUCCESS! Got {len(packets_received)} packets")
        return True
    else:
        print(f"  ❌ No data received")
        return False


async def main():
    print("MetaMotion 1.7.3 Command Discovery")
    print("=" * 60)

    async with BleakClient(ADDRESS) as client:
        print("Connected!")

        # Subscribe to notifications
        await client.start_notify(NOTIFY_UUID, handle_notification)
        print("Notifications enabled\n")

        # Test sequences
        sequences = [
            # Basic sequences
            ("Direct start", [
                bytes([0x02, 0x01, 0x01])
            ]),

            ("Stop then start", [
                bytes([0x02, 0x01, 0x00]),
                bytes([0x02, 0x01, 0x01])
            ]),

            # With configuration
            ("Configure 25Hz + Start", [
                bytes([0x02, 0x03, 0x27, 0x00]),
                bytes([0x02, 0x01, 0x01])
            ]),

            ("Configure 50Hz + Start", [
                bytes([0x02, 0x03, 0x28, 0x00]),
                bytes([0x02, 0x01, 0x01])
            ]),

            # With enable
            ("Enable + Start", [
                bytes([0x02, 0x02, 0x01, 0x00]),
                bytes([0x02, 0x01, 0x01])
            ]),

            ("Enable + Configure + Start", [
                bytes([0x02, 0x02, 0x01, 0x00]),
                bytes([0x02, 0x03, 0x27, 0x00]),
                bytes([0x02, 0x01, 0x01])
            ]),

            # Different register values
            ("Alternative enable", [
                bytes([0x02, 0x02, 0x01, 0x01]),
                bytes([0x02, 0x01, 0x01])
            ]),

            # Multiple enables
            ("Double enable", [
                bytes([0x02, 0x02, 0x01, 0x00]),
                bytes([0x02, 0x02, 0x01, 0x01]),
                bytes([0x02, 0x01, 0x01])
            ]),

            # Different order
            ("Start then configure", [
                bytes([0x02, 0x01, 0x01]),
                bytes([0x02, 0x03, 0x27, 0x00])
            ]),

            # Power cycle
            ("Power off/on + start", [
                bytes([0x02, 0x02, 0x00, 0x00]),  # Power off
                bytes([0x02, 0x02, 0x01, 0x00]),  # Power on
                bytes([0x02, 0x01, 0x01])  # Start
            ]),

            # Different module registers
            ("Module 0x11 start", [
                bytes([0x11, 0x02, 0x00, 0x00]),  # Settings module
                bytes([0x02, 0x01, 0x01])
            ]),

            # Global commands
            ("Global enable", [
                bytes([0x01, 0x01]),
                bytes([0x02, 0x01, 0x01])
            ]),

            # Sensor fusion approach
            ("Sensor fusion enable", [
                bytes([0x19, 0x02, 0x00, 0x20]),  # Enable accel in fusion
                bytes([0x19, 0x01, 0x01])  # Start fusion
            ])
        ]

        # Try each sequence
        for name, commands in sequences:
            success = await try_sequence(client, name, commands)
            if success:
                print(f"\n🎉 Found working sequence: {name}")
                print("Letting it run for 5 more seconds...")
                await asyncio.sleep(5)
                break

        # If nothing worked, try reading state
        if not packets_received:
            print("\n" + "=" * 60)
            print("No streaming data received. Trying to read device state...")

            # Try reading various registers
            read_commands = [
                (bytes([0x02, 0x80]), "Accelerometer info"),
                (bytes([0x02, 0x81]), "Accelerometer config"),
                (bytes([0x11, 0x80]), "Settings info"),
                (bytes([0x19, 0x80]), "Sensor fusion info")
            ]

            for cmd, desc in read_commands:
                print(f"\nReading {desc}...")
                packets_received.clear()
                await client.write_gatt_char(COMMAND_UUID, cmd)
                await asyncio.sleep(0.5)
                if packets_received:
                    print(f"  Response: {packets_received[0].hex()}")

        # Summary
        print("\n" + "=" * 60)
        print("Test complete!")

        if not any(len(p) >= 7 for p in packets_received):
            print("\n⚠️  No accelerometer data received")
            print("\nPossible solutions:")
            print("1. The device might need initialization via the MetaWear app first")
            print("2. Try this sequence:")
            print("   - Open MetaWear app")
            print("   - Connect to device")
            print("   - Go to Accelerometer section")
            print("   - Start streaming (verify you see data)")
            print("   - KEEP THE APP OPEN and streaming")
            print("   - Run this script again quickly")
            print("\n3. The device might be in a locked state and need a factory reset")


if __name__ == "__main__":
    asyncio.run(main())