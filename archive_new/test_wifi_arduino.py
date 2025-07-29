#!/usr/bin/env python3
"""
Test WiFi Arduino Connection
Simulates hub server to test Arduino WiFi connectivity
"""

import socket
import json
import time
import threading
import sys

# Colors
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'


class TestHub:
    """Simple test hub server"""

    def __init__(self, port=5555):
        self.port = port
        self.running = True
        self.connections = []

    def handle_client(self, client_socket, address):
        """Handle Arduino connection"""
        print(f"\n{GREEN}✓ Arduino connected from {address[0]}:{address[1]}{RESET}")
        self.connections.append(address)

        try:
            # Wait for identification
            client_socket.settimeout(5.0)
            data = client_socket.recv(1024).decode('utf-8').strip()

            if data.startswith('SENSOR:'):
                sensor_type = data.split(':')[1]
                print(f"  Sensor type: {sensor_type}")

                # Send acknowledgment
                ack = json.dumps({
                    'status': 'connected',
                    'ntp_time': time.time(),
                    'server_time': time.time()
                }) + '\n'
                client_socket.send(ack.encode())
                print(f"  {GREEN}✓ Sent acknowledgment{RESET}")

                # Listen for data
                print(f"\n  Listening for data from Arduino...")
                print(f"  {YELLOW}(Place toothbrush near Arduino to test){RESET}")

                timeout_count = 0
                while self.running:
                    try:
                        data = client_socket.recv(4096)
                        if not data:
                            break

                        # Process data
                        for line in data.decode('utf-8').split('\n'):
                            if line.strip():
                                try:
                                    msg = json.loads(line)
                                    self.display_message(msg)
                                except json.JSONDecodeError:
                                    print(f"  Raw: {line}")

                    except socket.timeout:
                        timeout_count += 1
                        if timeout_count % 10 == 0:
                            print(f"  {YELLOW}Waiting for data... (Arduino should be scanning){RESET}")

            else:
                print(f"  {YELLOW}Unexpected data: {data}{RESET}")

        except socket.timeout:
            print(f"  {RED}✗ No identification received{RESET}")
        except Exception as e:
            print(f"  {RED}✗ Error: {e}{RESET}")
        finally:
            client_socket.close()
            print(f"\n{YELLOW}Arduino disconnected{RESET}")

    def display_message(self, msg):
        """Display formatted message from Arduino"""
        timestamp = msg.get('timestamp', time.time())

        # Format based on message content
        if 'force' in msg:
            print(f"  FSR: {msg['force']:.2f}N (raw: {msg.get('raw', 0)})")
        elif 'x' in msg and 'y' in msg and 'z' in msg:
            mag = (msg['x'] ** 2 + msg['y'] ** 2 + msg['z'] ** 2) ** 0.5
            print(f"  Accel: X={msg['x']:+.3f} Y={msg['y']:+.3f} Z={msg['z']:+.3f} |a|={mag:.3f}g")
        else:
            print(f"  Data: {msg}")

    def run(self):
        """Run test server"""
        # Create server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server_socket.bind(('0.0.0.0', self.port))
            server_socket.listen(5)
            server_socket.settimeout(1.0)

            print(f"{GREEN}Test hub listening on port {self.port}{RESET}")
            print(f"Waiting for Arduino connection...")
            print(f"\n{YELLOW}Arduino should connect automatically if:{RESET}")
            print(f"  1. WiFi credentials are correct")
            print(f"  2. This machine's IP is set in HUB_HOST")
            print(f"  3. Arduino is powered and in range")

            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    # Handle in thread
                    thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address)
                    )
                    thread.daemon = True
                    thread.start()
                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    break

        except Exception as e:
            print(f"{RED}✗ Server error: {e}{RESET}")
        finally:
            server_socket.close()
            self.running = False


def main():
    print("=" * 60)
    print(" WiFi Arduino Connection Test")
    print("=" * 60)
    print()
    print("This tool simulates the hub server to test Arduino connectivity")
    print()

    # Show network info
    import subprocess
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
        if result.returncode == 0:
            ips = result.stdout.strip().split()
            print(f"This machine's IP addresses:")
            for ip in ips:
                print(f"  {GREEN}{ip}{RESET}")
            print()
            print(f"Make sure Arduino code has one of these in HUB_HOST")
    except:
        pass

    print()
    print("Starting test hub server...")
    print()

    # Run test server
    port = 5555
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    test_hub = TestHub(port)

    try:
        test_hub.run()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Test stopped{RESET}")

    # Summary
    if test_hub.connections:
        print(f"\n{GREEN}✓ Successfully received connections from:{RESET}")
        for addr in test_hub.connections:
            print(f"  {addr[0]}:{addr[1]}")
    else:
        print(f"\n{RED}✗ No Arduino connections received{RESET}")
        print("\nTroubleshooting:")
        print("1. Check Arduino Serial Monitor for errors")
        print("2. Verify WiFi credentials are correct")
        print("3. Ensure HUB_HOST matches this machine's IP")
        print("4. Try pinging this machine from another device")
        print("5. Check firewall: sudo ufw allow 5555/tcp")


if __name__ == "__main__":
    main()