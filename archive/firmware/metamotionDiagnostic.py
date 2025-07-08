#!/usr/bin/env python3
"""
MetaMotion BLE Diagnostic Script
Helps debug why data isn't flowing from MetaMotion RL
"""

import asyncio
import logging
import struct
from bleak import BleakClient

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class MetaMotionDiagnostic:
    """Diagnostic tool for MetaMotion RL"""

    # MetaMotion RL UUIDs
    COMMAND_UUID = "326a9001-85cb-9195-d9dd-464cfbbae75a"
    NOTIFY_UUID = "326a9006-85cb-9195-d9dd-464cfbbae75a"

    # Commands
    CMD_ACC_ENABLE = bytes([0x02, 0x02, 0x01, 0x00])
    CMD_ACC_CONFIG = bytes([0x02, 0x03, 0x28, 0x0C])  # 100Hz, ±4g
    CMD_ACC_START = bytes([0x02, 0x01, 0x01])
    CMD_ACC_STOP = bytes([0x02, 0x01, 0x00])

    def __init__(self, address):
        self.address = address
        self.client = None
        self.notification_count = 0

    def notification_handler(self, sender, data):
        """Handle notifications from MetaMotion"""
        self.notification_count += 1

        print(f"\n📦 Notification #{self.notification_count}")
        print(f"   Sender: {sender}")
        print(f"   Data length: {len(data)} bytes")
        print(f"   Raw bytes: {data.hex()}")

        # Try to parse as accelerometer data
        if len(data) >= 7 and data[0] == 0x02:
            try:
                x = struct.unpack('<h', data[2:4])[0] / 16384.0
                y = struct.unpack('<h', data[4:6])[0] / 16384.0
                z = struct.unpack('<h', data[6:8])[0] / 16384.0
                print(f"   Parsed accel: X={x:.3f}g Y={y:.3f}g Z={z:.3f}g")
            except Exception as e:
                print(f"   Parse error: {e}")
        else:
            print(f"   Not accelerometer data (first byte: 0x{data[0]:02x})")

    async def run_diagnostic(self):
        """Run full diagnostic"""
        print("🔍 MetaMotion RL Diagnostic Starting...")
        print(f"Target device: {self.address}")

        try:
            # Connect
            print("\n1️⃣ Connecting...")
            self.client = BleakClient(self.address)
            await self.client.connect()

            if not self.client.is_connected:
                print("❌ Failed to connect")
                return

            print("✅ Connected!")

            # Get services
            print("\n2️⃣ Discovering services...")
            services = await self.client.get_services()
            print(f"Found {len(services)} services:")

            for service in services:
                print(f"  📋 {service.uuid}")
                for char in service.characteristics:
                    props = ", ".join(char.properties)
                    print(f"     └─ {char.uuid} ({props})")

            # Check battery
            print("\n3️⃣ Reading battery level...")
            try:
                battery_uuid = "00002a19-0000-1000-8000-00805f9b34fb"
                battery_data = await self.client.read_gatt_char(battery_uuid)
                battery_level = int.from_bytes(battery_data, byteorder='little')
                print(f"🔋 Battery: {battery_level}%")
            except Exception as e:
                print(f"⚠️ Could not read battery: {e}")

            # Start notifications
            print("\n4️⃣ Setting up notifications...")
            await self.client.start_notify(self.NOTIFY_UUID, self.notification_handler)
            print(f"✅ Subscribed to {self.NOTIFY_UUID}")

            # Configure accelerometer step by step
            print("\n5️⃣ Configuring accelerometer...")

            print("   Enabling accelerometer...")
            await self.client.write_gatt_char(self.COMMAND_UUID, self.CMD_ACC_ENABLE)
            await asyncio.sleep(0.5)

            print("   Setting configuration...")
            await self.client.write_gatt_char(self.COMMAND_UUID, self.CMD_ACC_CONFIG)
            await asyncio.sleep(0.5)

            print("   Starting data stream...")
            await self.client.write_gatt_char(self.COMMAND_UUID, self.CMD_ACC_START)
            print("✅ Accelerometer configured")

            # Wait for data
            print("\n6️⃣ Waiting for data (30 seconds)...")
            print("   Move the MetaMotion to generate data...")

            for i in range(30):
                await asyncio.sleep(1)
                if i % 5 == 4:  # Every 5 seconds
                    print(f"   {30 - i - 1}s remaining... Notifications received: {self.notification_count}")

            # Stop streaming
            print("\n7️⃣ Stopping stream...")
            await self.client.write_gatt_char(self.COMMAND_UUID, self.CMD_ACC_STOP)
            await self.client.stop_notify(self.NOTIFY_UUID)

            print(f"\n📊 Final Results:")
            print(f"   Total notifications: {self.notification_count}")
            if self.notification_count > 0:
                print(f"   Average rate: {self.notification_count / 30:.1f} Hz")
                print("   ✅ Data flow working!")
            else:
                print("   ❌ No data received")
                print("\n🔧 Troubleshooting suggestions:")
                print("   1. Try resetting MetaMotion (hold button 6+ seconds)")
                print("   2. Check if another app is connected")
                print("   3. Move device closer to computer")
                print("   4. Try different configuration commands")

        except Exception as e:
            print(f"❌ Diagnostic failed: {e}")
        finally:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                print("🔌 Disconnected")


async def main():
    """Main entry point"""
    # Use the MAC address from your config
    device_address = "C8:0B:FB:24:C1:65"  # Update if different

    diagnostic = MetaMotionDiagnostic(device_address)
    await diagnostic.run_diagnostic()


if __name__ == "__main__":
    asyncio.run(main())