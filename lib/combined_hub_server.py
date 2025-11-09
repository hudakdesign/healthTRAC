#!/usr/bin/env python3
import socket
import threading
import json
import time
import argparse
import http.server
import socketserver
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS


class TimeServer(http.server.SimpleHTTPRequestHandler):
    """Time synchronization API endpoint"""

    def do_GET(self):
        if self.path == "/api/time":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

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

    def log_message(self, format, *args):
        pass


class CombinedHubServer:
    """Combined hub for toothbrush and audio data"""

    def __init__(self, tcp_port=5555, data_dir='recorded_data'):
        self.tcp_port = tcp_port
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # TCP server state
        self.running = False
        self.clients = {}
        self.lock = threading.Lock()

        # Recording state
        self.recording_state = {"is_recording": False}
        self.current_session_file = None
        self.session_data = []

        # Latest data from devices
        self.toothbrush_data = {}
        self.audio_features = {}

        # Statistics
        self.packets_received = 0
        self.data_samples_received = 0

    def start_tcp_server(self):
        """Start TCP server for toothbrush bridge"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.tcp_port))
        self.server_socket.listen(5)
        self.running = True

        self.accept_thread = threading.Thread(target=self._accept_connections)
        self.accept_thread.daemon = True
        self.accept_thread.start()

        print(f"[TCP] Server started on port {self.tcp_port}")

    def _accept_connections(self):
        while self.running:
            try:
                client, address = self.server_socket.accept()
                print(f"[TCP] Connection from {address[0]}:{address[1]}")

                client_thread = threading.Thread(
                    target=self._handle_client, args=(client, address))
                client_thread.daemon = True
                client_thread.start()

                with self.lock:
                    self.clients[address] = client
            except:
                if self.running:
                    print("[TCP] Error accepting connection")
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
                buffer = lines.pop()

                for line in lines:
                    if line.strip():
                        self._process_toothbrush_data(line)
        except:
            print(f"[TCP] Error handling client {address}")
        finally:
            with self.lock:
                if address in self.clients:
                    del self.clients[address]
            client.close()

    def _process_toothbrush_data(self, message):
        """Process incoming toothbrush data"""
        try:
            data = json.loads(message)

            with self.lock:
                self.packets_received += 1

                if data.get("type") == "heartbeat":
                    pass  # Ignore heartbeats
                elif "accel_x" in data:
                    self.data_samples_received += 1
                    device_id = data.get("device_id", "toothbrush_01")

                    # Store latest data
                    self.toothbrush_data[device_id] = {
                        "timestamp": data.get("timestamp_hub"),
                        "data": {
                            "accel_x": data.get("accel_x"),
                            "accel_y": data.get("accel_y"),
                            "accel_z": data.get("accel_z")
                        }
                    }

                    # Save to session if recording
                    if self.recording_state["is_recording"]:
                        self.session_data.append({
                            "type": "toothbrush",
                            "device_id": device_id,
                            "timestamp": data.get("timestamp_hub"),
                            "data": self.toothbrush_data[device_id]["data"]
                        })
        except json.JSONDecodeError:
            print(f"[TCP] Invalid JSON received")

    def save_session_data(self):
        """Save current session to file"""
        if self.current_session_file and self.session_data:
            with open(self.current_session_file, 'w') as f:
                json.dump(self.session_data, f, indent=2)
            print(f"[HUB] Session saved: {len(self.session_data)} records")

    def stop(self):
        self.running = False
        if self.recording_state["is_recording"]:
            self.save_session_data()
        for client in list(self.clients.values()):
            client.close()
        self.server_socket.close()


# Flask app for audio endpoints and recording control
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
hub_server = None


@app.route('/api/recording_state', methods=['GET'])
def get_recording_state():
    with hub_server.lock:
        return jsonify(hub_server.recording_state)


@app.route('/api/start_recording', methods=['POST'])
def start_recording():
    with hub_server.lock:
        hub_server.recording_state["is_recording"] = True

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hub_server.current_session_file = hub_server.data_dir / f"session_{timestamp}.json"
    hub_server.session_data = []

    print(f"[HUB] Recording started: {hub_server.current_session_file}")
    return jsonify({"success": True})


@app.route('/api/stop_recording', methods=['POST'])
def stop_recording():
    with hub_server.lock:
        hub_server.recording_state["is_recording"] = False

    hub_server.save_session_data()
    print(f"[HUB] Recording stopped")
    return jsonify({"success": True})


@app.route('/api/audio_features', methods=['POST'])
def receive_audio_features():
    data = request.json
    device_id = data.get("device_id")

    with hub_server.lock:
        hub_server.audio_features[device_id] = {
            "timestamp": data.get("timestamp"),
            "features": data.get("features")
        }

        if hub_server.recording_state["is_recording"]:
            hub_server.session_data.append({
                "type": "audio",
                "device_id": device_id,
                "timestamp": data.get("timestamp"),
                "features": data.get("features")
            })

    return jsonify({"success": True})


@app.route('/api/toothbrush_devices', methods=['GET'])
def get_toothbrush_devices():
    with hub_server.lock:
        return jsonify(hub_server.toothbrush_data)


@app.route('/api/audio_devices', methods=['GET'])
def get_audio_devices():
    with hub_server.lock:
        return jsonify(hub_server.audio_features)


def start_time_server(port=5000):
    """Start time sync server"""
    while True:
        try:
            httpd = socketserver.TCPServer(("", port), TimeServer)
            break
        except OSError as e:
            if e.errno == 48:
                port += 1
            else:
                raise

    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()
    return httpd, port


def main():
    global hub_server

    parser = argparse.ArgumentParser(description='Combined Hub Server')
    parser.add_argument('--tcp-port', type=int, default=5555)
    parser.add_argument('--http-port', type=int, default=5000)
    parser.add_argument('--flask-port', type=int, default=8080)
    args = parser.parse_args()

    print("\n========== COMBINED HUB SERVER ==========")
    print(f"TCP (toothbrush): port {args.tcp_port}")
    print(f"HTTP (time sync): port {args.http_port}")
    print(f"Flask (audio + control): port {args.flask_port}")
    print("=========================================\n")

    # Start time sync server
    time_httpd, actual_http_port = start_time_server(args.http_port)
    print(f"[TIME] Server started on port {actual_http_port}")

    # Start combined hub
    hub_server = CombinedHubServer(tcp_port=args.tcp_port)
    hub_server.start_tcp_server()

    # Start Flask app
    print(f"[FLASK] Starting on port {args.flask_port}")
    try:
        app.run(host='0.0.0.0', port=args.flask_port, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        hub_server.stop()
        time_httpd.shutdown()


if __name__ == "__main__":
    main()
