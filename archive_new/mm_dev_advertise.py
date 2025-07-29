#!/usr/bin/env python3
"""
Simple BLE Scanner to check if MetaMotion is advertising
"""
import asyncio
from bleak import BleakScanner
import time

TARGET_MAC = "C8:0B:FB:24:C1:65"  # Your MetaMotion MAC


async def scan_for_device():
    print(f"Scanning for MetaMotion ({TARGET_MAC})...")

    # Scan for 5 seconds
    devices = await BleakScanner.discover(timeout=5.0)

    found = False
    for d in devices:
        if d.address.lower() == TARGET_MAC.lower():
            print(f"✅ FOUND: {d.name} ({d.address})")
            print(f"Signal strength: {d.rssi} dBm")
            print(f"Advertisement data: {d.metadata}")
            found = True
            break

    if not found:
        print(f"❌ NOT FOUND: No device with address {TARGET_MAC}")
        print("Available devices:")
        for d in devices:
            print(f"  - {d.name or 'Unknown'}: {d.address}, RSSI: {d.rssi}")


if __name__ == "__main__":
    asyncio.run(scan_for_device())