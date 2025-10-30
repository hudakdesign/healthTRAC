#!/usr/bin/env python3
import socket
import threading
import json
import time
import argparse
import http.server
import socketserver
from datetime import datetime
import csv
import os
from pathlib import Path


class MockTimeServer(http.server.SimpleHTTPRequestHandler):
    """Simulates the Hub's time synchronization API endpoint"""

    def do_GET(self):
        if self.path == "/api/time":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # Create time response in the format expected by the bridge
            timestamp_s = time.time()
            timestamp_ns = int(timestamp_s * 1e9)

            response = {
                "timestamp_s": timestamp_s,
                "timestamp_ns": timestamp_ns,
                "stratum": 2,
                "source": "ntp"
            }

            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_error(404)

    # Suppress log messages
    def log_message(self, format, *args):
        pass


class MockHubServer:
    """Simulates the Raspberry Pi Hub TCP server"""

    def __init__(self, tcp_port=5555, data_dir='test_data'):
        self.tcp_port = tcp_port
        self.tcp_port = tcp_port
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.csv_file = self.data_dir / 'toothbrush.csv'
        self.running = False
        self.clients = {}
        self.lock = threading.Lock()
        self.packets_received = 0
        self.heartbeats_received = 0
        self.data_samples_received = 0
        self.last_data_time = None

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.tcp_port))
        self.server_socket.listen(5)
        self.running = True

        self.accept_thread = threading.Thread(target=self._accept_connections)
        self.accept_thread.daemon = True
        self.accept_thread.start()

        print(f"[+] TCP server started on port {self.tcp_port}")

    def stop(self):
        self.running = False
        for client in list(self.clients.values()):
            client.close()
        self.server_socket.close()

    def _accept_connections(self):
        while self.running:
            try:
                client, address = self.server_socket.accept()
                print(f"[+] New connection from {address[0]}:{address[1]}")
                client_thread = threading.Thread(
                    target=self._handle_client, args=(client, address))
                client_thread.daemon = True
                client_thread.start()

                with self.lock:
                    self.clients[address] = client
            except:
                if self.running:
                    print("[!] Error accepting connection")
                break

    def _handle_client(self, client, address):
        try:
            buffer = ""
            while self.running:
                data = client.recv(4096)
                if not data:
                    break

                buffer += data.decode('utf-8')
                lines = buffer.split('\n')
                buffer = lines.pop()  # Keep the last incomplete line

                for line in lines:
                    if line.strip():
                        self._process_message(line, address)
        except:
            print(f"[!] Error handling client {address[0]}:{address[1]}")
        finally:
            with self.lock:
                if address in self.clients:
                    del self.clients[address]
            client.close()
            print(f"[-] Connection closed: {address[0]}:{address[1]}")

    def _process_message(self, message, address):
        try:
            data = json.loads(message)

            with self.lock:
                self.packets_received += 1
                if data.get("type") == "heartbeat":
                    self.heartbeats_received += 1
                elif "accel_x" in data:
                    self.data_samples_received += 1
                    self.last_data_time = datetime.now().strftime("%H:%M:%S")

                    # Get data
                    timestamp_hub = data.get('timestamp_hub')
                    accel_x = data.get('accel_x')
                    accel_y = data.get('accel_y')
                    accel_z = data.get('accel_z')

                    # Write to CSV
                    file_exists = self.csv_file.exists()
                    with open(self.csv_file, 'a', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=['timestamp_hub', 'accel_x', 'accel_y', 'accel_z'])
                        if not file_exists:
                            writer.writeheader()
                        writer.writerow({
                            'timestamp_hub': data.get('timestamp_hub'),
                            'accel_x': data.get('accel_x'),
                            'accel_y': data.get('accel_y'),
                            'accel_z': data.get('accel_z')
                        })
                    # Add debug statement to show when data would be sent to dashbaord
                    print(f"[→] Sending data to dashboard: sensor={data.get('sensor')} time={data.get('timestamp_hub')}")

            # Print message based on type
            if data.get("type") == "handshake":
                print(f"[*] Handshake from {data.get('device_id', 'unknown')}")
            elif data.get("type") == "heartbeat":
                pass  # Don't log heartbeats, they're too frequent
            else:
                print(f"[*] Data: {message[:60]}...")
        except json.JSONDecodeError:
            print(f"[!] Invalid JSON: {message[:60]}...")


def print_statistics(server):
    """Print server statistics periodically"""
    while True:
        time.sleep(10)  # Update every 10 seconds
        with server.lock:
            bridges = len(server.clients)
            packets = server.packets_received
            heartbeats = server.heartbeats_received
            samples = server.data_samples_received
            last_data = server.last_data_time or "Never"

        print("\n--- STATISTICS ---")
        print(f"Connected bridges: {bridges}")
        print(f"Packets received: {packets}")
        print(f"Heartbeats: {heartbeats}")
        print(f"Data samples: {samples}")
        print(f"Last data: {last_data}")
        print("-----------------\n")


def get_local_ip():
    """Get the local IP address that would be used for internet connections"""
    try:
        # Create a socket to a public address to determine which interface would be used
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return socket.gethostbyname(socket.gethostname())

def start_time_server(port=5000):
    """Start the time server in a separate thread"""
    handler = MockTimeServer

    # Try the specified port, if busy try others
    while True:
        try:
            httpd = socketserver.TCPServer(("", port), handler)
            break
        except OSError as e:
            if e.errno == 48:  # Address already in use
                print(f"Port {port} already in use, trying {port+1}")
                port += 1
            else:
                raise

    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()

    return httpd, port


def main():
    parser = argparse.ArgumentParser(description='Mock Hub Server for toothbrush subsystem testing')
    parser.add_argument('--tcp-port', type=int, default=5555, help='TCP server port (default: 5555)')
    parser.add_argument('--http-port', type=int, default=5000, help='HTTP server port (default: 5000)')
    args = parser.parse_args()

    local_ip = get_local_ip()

    # Print configuration instructions
    print("\n========== TOOTHBRUSH SUBSYSTEM TEST SERVER ==========")
    print(f"Local IP: {local_ip}")
    print(f"TCP Server: {local_ip}:{args.tcp_port}")
    print(f"Time API: http://{local_ip}:{args.http_port}/api/time")
    print("=====================================================\n")

    # Start the time server with auto-port selection if needed
    time_httpd, actual_http_port = start_time_server(port=args.http_port)
    print(f"[+] Time sync server started on port {actual_http_port}")

    if actual_http_port != args.http_port:
        print(f"[!] Note: Using port {actual_http_port} instead of {args.http_port}")
        print(f"[!] Update ESP32 firmware to use: http://{local_ip}:{actual_http_port}/api/time")

    # Create and start the TCP server
    server = MockHubServer(tcp_port=args.tcp_port)
    server.start()

    # Start statistics reporting thread
    stats_thread = threading.Thread(target=print_statistics, args=(server,))
    stats_thread.daemon = True
    stats_thread.start()

    try:
        print("\nServer is running. Press Ctrl+C to stop...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.stop()
        time_httpd.shutdown()
        print("Server stopped.")


if __name__ == "__main__":
    main()