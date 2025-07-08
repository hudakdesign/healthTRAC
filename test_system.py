#!/usr/bin/env python3
"""
System Test Script for HealthTRAC TCP/NTP Architecture
Tests each component and verifies connectivity
"""

import time
import socket
import subprocess
import sys
import os
from datetime import datetime

# ANSI color codes for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'


def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


def test_result(test_name, success, message=""):
    """Print test result with color"""
    if success:
        print(f"{GREEN}✓{RESET} {test_name}")
    else:
        print(f"{RED}✗{RESET} {test_name}")
    if message:
        print(f"  {message}")


def test_imports():
    """Test if all required modules can be imported"""
    print_header("Testing Python Imports")

    modules = [
        ("ntplib", True),
        ("serial", True),
        ("bleak", True),
        ("pyaudio", False),  # Optional
        ("numpy", False),  # Optional
    ]

    all_required_ok = True

    for module_name, required in modules:
        try:
            __import__(module_name)
            test_result(f"Import {module_name}", True)
        except ImportError:
            test_result(f"Import {module_name}", False,
                        f"Run: pip install {module_name}" if required else "Optional module")
            if required:
                all_required_ok = False

    return all_required_ok


def test_ntp():
    """Test NTP connectivity"""
    print_header("Testing NTP Time Sync")

    try:
        import ntplib
        client = ntplib.NTPClient()
        response = client.request('pool.ntp.org', version=3, timeout=5)

        offset = response.offset
        test_result("NTP server reachable", True, f"Time offset: {offset:.3f} seconds")

        # Show current time
        ntp_time = time.time() + offset
        print(f"  System time: {datetime.fromtimestamp(time.time())}")
        print(f"  NTP time:    {datetime.fromtimestamp(ntp_time)}")

        return True

    except Exception as e:
        test_result("NTP server reachable", False, f"Error: {e}")
        return False


def test_hub_server_port(port=5555):
    """Test if hub server port is available"""
    print_header(f"Testing Hub Server Port {port}")

    try:
        # Try to bind to the port
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.bind(('0.0.0.0', port))
        test_socket.close()

        test_result(f"Port {port} available", True)
        return True

    except OSError:
        test_result(f"Port {port} available", False,
                    "Port in use - is hub_server.py already running?")
        return False


def test_serial_ports():
    """Test for available serial ports"""
    print_header("Testing Serial Ports (for FSR)")

    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())

        if not ports:
            test_result("Serial ports found", False, "No serial ports detected")
            return False

        test_result("Serial ports found", True, f"Found {len(ports)} port(s)")

        for port in ports:
            print(f"  - {port.device}: {port.description}")

        # Look for likely ESP32 ports
        esp32_found = False
        for port in ports:
            if any(x in (port.description or "").lower()
                   for x in ['esp32', 'cp210', 'ch340', 'ftdi', 'usbserial']):
                print(f"  {GREEN}Likely ESP32 port: {port.device}{RESET}")
                esp32_found = True

        return esp32_found

    except Exception as e:
        test_result("Serial ports found", False, f"Error: {e}")
        return False


def test_bluetooth():
    """Test Bluetooth availability"""
    print_header("Testing Bluetooth (for MetaMotion)")

    try:
        import asyncio
        from bleak import BleakScanner

        async def scan():
            try:
                devices = await BleakScanner.discover(timeout=5.0)
                return devices
            except Exception as e:
                return str(e)

        print("  Scanning for BLE devices (5 seconds)...")
        result = asyncio.run(scan())

        if isinstance(result, str):
            test_result("Bluetooth available", False, f"Error: {result}")
            return False

        test_result("Bluetooth available", True, f"Found {len(result)} BLE devices")

        # Look for MetaMotion devices
        metamotion_found = False
        for device in result:
            if device.name:
                print(f"  - {device.name} ({device.address})")
                if "MetaWear" in device.name or "MetaMotion" in device.name:
                    print(f"  {GREEN}Found MetaMotion device!{RESET}")
                    metamotion_found = True

        return True

    except Exception as e:
        test_result("Bluetooth available", False, f"Error: {e}")
        return False


def test_data_directory():
    """Test data directory creation"""
    print_header("Testing Data Storage")

    data_dir = "./data"
    test_file = os.path.join(data_dir, "test.txt")

    try:
        # Create directory
        os.makedirs(data_dir, exist_ok=True)
        test_result("Create data directory", True)

        # Test write permissions
        with open(test_file, 'w') as f:
            f.write("test")
        test_result("Write permissions", True)

        # Clean up
        os.remove(test_file)

        return True

    except Exception as e:
        test_result("Data directory accessible", False, f"Error: {e}")
        return False


def test_network_connectivity(host='localhost', port=5555):
    """Test network connectivity to hub"""
    print_header(f"Testing Network to {host}:{port}")

    if host == 'localhost':
        test_result("Network test", True, "Localhost - no network test needed")
        return True

    try:
        # Try to connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            test_result(f"Connect to {host}:{port}", True, "Hub server is running")
        else:
            test_result(f"Connect to {host}:{port}", False,
                        "Cannot connect - is hub_server.py running?")

        return result == 0

    except Exception as e:
        test_result(f"Connect to {host}:{port}", False, f"Error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print(" HealthTRAC System Test")
    print("=" * 60)

    # Parse arguments
    hub_host = 'localhost'
    if len(sys.argv) > 1:
        hub_host = sys.argv[1]
        print(f"\nTesting with hub host: {hub_host}")

    # Run tests
    tests = [
        ("Python imports", test_imports()),
        ("NTP connectivity", test_ntp()),
        ("Hub server port", test_hub_server_port()),
        ("Serial ports", test_serial_ports()),
        ("Bluetooth", test_bluetooth()),
        ("Data directory", test_data_directory()),
    ]

    # Network test only if not localhost
    if hub_host != 'localhost':
        tests.append(("Network connectivity", test_network_connectivity(hub_host)))

    # Summary
    print_header("Test Summary")

    passed = sum(1 for _, result in tests if result)
    total = len(tests)

    print(f"\nPassed: {passed}/{total} tests")

    if passed == total:
        print(f"\n{GREEN}✓ All tests passed! System ready.{RESET}")
        print("\nNext steps:")
        print("1. Start hub server: python hub_server.py")
        print("2. Start sensor clients with --hub-host option")
    else:
        print(f"\n{YELLOW}⚠ Some tests failed. Check the errors above.{RESET}")
        print("\nCommon fixes:")
        print("- Install missing modules: pip install -r requirements.txt")
        print("- Connect ESP32 via USB")
        print("- Enable Bluetooth")
        print("- Start hub_server.py if testing network connectivity")


if __name__ == "__main__":
    main()