#!/usr/bin/env python3
"""
Find ESP32 Serial Port on Mac
Uses same detection method as your original code
"""

import serial.tools.list_ports
import subprocess
import os

print("=" * 60)
print("ESP32 Serial Port Finder for Mac")
print("=" * 60)

# 1. Use Python serial tools (like your original code)
print("\n1. Checking with Python serial tools:")
print("-" * 40)

ports = serial.tools.list_ports.comports()

if not ports:
    print("No serial ports found!")
else:
    print(f"Found {len(ports)} serial port(s):\n")

    esp32_candidates = []

    for i, port in enumerate(ports):
        print(f"Port {i}: {port.device}")
        print(f"  Description: {port.description}")
        print(f"  Hardware ID: {port.hwid}")

        # Additional details if available
        if port.manufacturer:
            print(f"  Manufacturer: {port.manufacturer}")
        if port.product:
            print(f"  Product: {port.product}")
        if port.serial_number:
            print(f"  Serial Number: {port.serial_number}")

        # Check if it's likely an ESP32 (matching your original code logic)
        desc_lower = (port.description or "").lower()
        device_lower = port.device.lower()

        if any(x in desc_lower for x in ['usbserial', 'cp210', 'ch340', 'ftdi', 'esp32', 'sparkfun', 'serial']):
            esp32_candidates.append(port)
            print(f"  → LIKELY ESP32!")
        elif 'usbserial' in device_lower:
            esp32_candidates.append(port)
            print(f"  → Possible ESP32 (device name match)")

        print()

    if esp32_candidates:
        print("\n✅ Likely ESP32 device(s):")
        for port in esp32_candidates:
            print(f"  {port.device} - {port.description}")

# 2. Check all /dev entries
print("\n2. Checking /dev entries:")
print("-" * 40)

# Get all tty devices
all_ttys = []
for name in os.listdir('/dev'):
    if name.startswith('tty.') or name.startswith('cu.'):
        full_path = f"/dev/{name}"
        # Skip known non-USB devices
        if not any(skip in name for skip in ['Bluetooth', 'debug', 'stdin']):
            all_ttys.append(full_path)

if all_ttys:
    print("Found these serial devices:")
    for dev in sorted(all_ttys):
        print(f"  {dev}")
        # Check if it's the USB serial device
        if 'usb' in dev.lower() or 'serial' in dev.lower():
            print(f"    → Possible ESP32!")

# 3. Check system profiler for USB Serial
print("\n3. Checking System Profiler for USB devices:")
print("-" * 40)

try:
    result = subprocess.run(['system_profiler', 'SPUSBDataType'],
                            capture_output=True, text=True)

    lines = result.stdout.split('\n')
    in_serial_section = False
    serial_info = []

    for line in lines:
        if 'USB Serial' in line or 'Serial' in line:
            in_serial_section = True
            serial_info = [line]
        elif in_serial_section:
            if line.strip() and not line.startswith(' ' * 10):
                serial_info.append(line)
            elif not line.strip():
                in_serial_section = False
                if serial_info:
                    print("Found USB Serial Device:")
                    for info_line in serial_info:
                        print(f"  {info_line}")
                    serial_info = []

except Exception as e:
    print(f"Could not run system_profiler: {e}")

# 4. Try to detect by testing ports
print("\n4. Testing likely ports:")
print("-" * 40)

test_ports = []
if esp32_candidates:
    test_ports = [p.device for p in esp32_candidates]
else:
    # Try common patterns
    for pattern in ['tty.usbserial', 'cu.usbserial', 'tty.usbmodem', 'cu.usbmodem',
                    'tty.SLAB_USBtoUART', 'cu.SLAB_USBtoUART']:
        import glob

        found = glob.glob(f"/dev/{pattern}*")
        test_ports.extend(found)

if test_ports:
    print("Testing these ports:")
    for port in test_ports:
        print(f"\nTesting {port}...")
        try:
            ser = serial.Serial(port, 115200, timeout=0.5)
            print(f"  ✅ Opened successfully!")
            ser.close()
        except Exception as e:
            print(f"  ❌ Failed: {e}")

# 5. Final recommendations
print("\n" + "=" * 60)
print("RECOMMENDATIONS:")
print("=" * 60)

if esp32_candidates:
    print(f"\n✅ Found ESP32 on: {esp32_candidates[0].device}")
    print("\nTo use in VirtualBox:")
    print("1. Make sure no Mac applications are using this port")
    print("2. In VirtualBox: Devices → USB → 'USB Serial'")
    print("3. The device should appear in Ubuntu as /dev/ttyUSB0")
else:
    print("\n❌ No obvious ESP32 device found!")
    print("\nTroubleshooting:")
    print("1. Unplug and replug the ESP32")
    print("2. Install the driver for your chip:")
    print("   - CP210x: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers")
    print("   - CH340: https://github.com/adrianmihalko/ch340g-ch34g-ch34x-mac-os-x-driver")
    print("   - FTDI: Built into macOS")
    print("3. Check if Arduino IDE can see it")
    print("4. Try a different USB cable (data cable, not charge-only)")