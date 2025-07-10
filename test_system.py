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
        import os
        import grp
        import pwd

        # First check for /dev/ttyUSB* and /dev/ttyACM* devices directly
        usb_devices = []
        for pattern in ['/dev/ttyUSB*', '/dev/ttyACM*']:
            import glob
            usb_devices.extend(glob.glob(pattern))

        # Also use serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())

        # Separate USB serial from built-in ports
        usb_ports = []
        system_ports = []

        for port in ports:
            # Check if it's a USB device
            if port.vid is not None or 'USB' in port.device.upper() or 'ACM' in port.device.upper():
                usb_ports.append(port)
            else:
                system_ports.append(port)

        # Check if we found USB devices directly
        if usb_devices:
            test_result("USB Serial devices found", True, f"Found {len(usb_devices)} USB serial device(s)")

            for device in usb_devices:
                print(f"\n  {GREEN}✓ USB Serial Device: {device}{RESET}")

                # Check device details
                try:
                    # Get device info
                    stat_info = os.stat(device)
                    mode = stat_info.st_mode
                    uid = stat_info.st_uid
                    gid = stat_info.st_gid

                    # Get owner and group names
                    owner = pwd.getpwuid(uid).pw_name
                    group = grp.getgrgid(gid).gr_name

                    # Check permissions
                    readable = os.access(device, os.R_OK)
                    writable = os.access(device, os.W_OK)

                    print(f"    Owner: {owner}, Group: {group}")
                    print(
                        f"    Permissions: {'Read' if readable else 'No read'}, {'Write' if writable else 'No write'}")

                    if not (readable and writable):
                        print(f"    {YELLOW}Permission issue! Try:{RESET}")
                        print(f"      sudo chmod 666 {device}")
                        print(f"      or: sudo usermod -a -G dialout $USER (then logout/login)")

                    # Try to identify the chip
                    if os.path.exists(device):
                        # Check dmesg for chip info
                        try:
                            import subprocess
                            dmesg_out = subprocess.run(['sudo', 'dmesg'], capture_output=True, text=True)
                            if 'ch34' in dmesg_out.stdout.lower():
                                print(f"    Chip: CH340/CH341 USB-Serial")
                            elif 'cp210' in dmesg_out.stdout.lower():
                                print(f"    Chip: CP2102/CP2104 USB-Serial")
                            elif 'ftdi' in dmesg_out.stdout.lower():
                                print(f"    Chip: FTDI USB-Serial")
                        except:
                            pass

                except Exception as e:
                    print(f"    Could not check device details: {e}")

            # Check if user is in dialout group
            current_user = os.getlogin()
            user_groups = [g.gr_name for g in grp.getgrall() if current_user in g.gr_mem]
            if 'dialout' not in user_groups:
                print(f"\n  {YELLOW}Note: User '{current_user}' is not in 'dialout' group{RESET}")
                print(f"  Run: sudo usermod -a -G dialout {current_user}")
                print(f"  Then logout and login again")

            return True

        elif usb_ports:
            # Found ports through serial.tools but not as /dev/ttyUSB*
            test_result("Serial ports found", True, f"Found {len(ports)} port(s)")
            print(f"\n  {YELLOW}Found serial ports but no /dev/ttyUSB* devices{RESET}")
            for port in usb_ports:
                print(f"  - {port.device}: {port.description}")
            return True

        else:
            # No USB serial devices found
            test_result("USB Serial devices found", False, "No USB serial devices detected")

            if system_ports:
                print(f"\n  System serial ports: {len(system_ports)} (ttyS0-ttyS{len(system_ports) - 1})")

            print(f"\n  {RED}Troubleshooting:{RESET}")
            print("  1. Check USB passthrough in VirtualBox:")
            print("     Devices → USB → Select your ESP32")
            print("  2. Check dmesg for USB events:")
            print("     sudo dmesg | grep -i usb | tail")
            print("  3. Verify ESP32 is connected to host")

            return False

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


def test_network_info():
    """Display network information for hub connectivity"""
    print_header("Network Information")

    try:
        import socket
        import subprocess

        # Get hostname
        hostname = socket.gethostname()
        print(f"Hostname: {hostname}")

        # Method 1: Using hostname -I (most reliable on Linux)
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            if result.returncode == 0:
                ips = result.stdout.strip().split()
                if ips:
                    print(f"\n{GREEN}IP Address(es):{RESET}")
                    for ip in ips:
                        print(f"  • {ip}")
                        # Check if it's a private IP
                        parts = ip.split('.')
                        if len(parts) == 4:
                            first_octet = int(parts[0])
                            if first_octet == 10 or (first_octet == 172 and 16 <= int(parts[1]) <= 31) or (
                                    first_octet == 192 and int(parts[1]) == 168):
                                print(f"    → Private/Local network")
                            else:
                                print(f"    → Public/University network")
        except:
            pass

        # Method 2: Parse ip addr output for more details
        try:
            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"\n{YELLOW}Network Interfaces:{RESET}")
                lines = result.stdout.split('\n')
                current_iface = None
                for line in lines:
                    # Interface name
                    if ': ' in line and not line.startswith(' '):
                        parts = line.split(': ')
                        if len(parts) >= 2:
                            current_iface = parts[1].split('@')[0]
                            if current_iface not in ['lo', 'docker0']:
                                print(f"\n  Interface: {current_iface}")
                    # IPv4 address
                    elif 'inet ' in line and current_iface and current_iface != 'lo':
                        parts = line.strip().split()
                        ip_cidr = parts[1]
                        ip = ip_cidr.split('/')[0]
                        print(f"    IPv4: {ip}")
        except:
            pass

        # Show connection test commands
        print(f"\n{GREEN}For other machines to connect:{RESET}")
        print("1. Use one of the IP addresses above (usually the 192.168.x.x or 10.x.x.x)")
        print("2. Make sure firewall allows port 5555:")
        print("   sudo ufw allow 5555/tcp")
        print("3. Test from another machine:")
        print("   ping <IP_ADDRESS>")
        print("   telnet <IP_ADDRESS> 5555")

        print(f"\n{YELLOW}University Network Note:{RESET}")
        print("• Your VM might be behind NAT - use the private IP shown above")
        print("• Ensure all machines are on the same network/subnet")
        print("• Some university networks block certain ports")

        return True

    except Exception as e:
        test_result("Network info", False, f"Error: {e}")
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
        ("Network info", test_network_info()),
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
        print("- Check USB passthrough in VM settings")
        print("- Start hub_server.py if testing network connectivity")


if __name__ == "__main__":
    main()