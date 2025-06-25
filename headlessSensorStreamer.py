#!/usr/bin/env python3
"""
Headless sensor streamer for Ubuntu
Runs both FSR and MetaMotion sensors without GUI
Streams data via TCP to Mac dashboard
"""

import asyncio
import socket
import threading
import time
import yaml
from pathlib import Path

# Import our existing sensor readers
from fsrReader import FSRReader
from metaMotionReader import MetaMotionReader


class HeadlessSensorStreamer:
    """Runs sensors on Ubuntu and streams to Mac"""

    def __init__(self, tcp_port=5556):
        self.tcp_port = tcp_port
        self.tcp_clients = []
        self.running = False

        # Load config
        self.config = self.loadConfig()

        # Initialize sensors
        self.fsr = FSRReader(port="/dev/ttyUSB0")  # Adjust port as needed
        self.mm = MetaMotionReader(macAddress="C8:0B:FB:24:C1:65")

        # Stats
        self.start_time = time.time()
        self.fsr_count = 0
        self.mm_count = 0

    def loadConfig(self):
        """Load configuration"""
        config_file = Path("config.yaml")
        if config_file.exists():
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Default config
            return {
                'sensors': {
                    'fsr': {'enabled': True, 'port': None},
                    'metamotion': {'enabled': True, 'macAddress': "C8:0B:FB:24:C1:65"}
                },
                'streaming': {
                    'tcp_port': 5556
                }
            }

    async def start_tcp_server(self):
        """TCP server for streaming data to Mac"""

        async def handle_client(reader, writer):
            addr = writer.get_extra_info('peername')
            print(f"Dashboard connected from {addr}")
            self.tcp_clients.append(writer)

            # Send initial status
            status = f"STATUS,FSR:{self.fsr.serial is not None},MM:{self.mm.connected}\n"
            writer.write(status.encode())
            await writer.drain()

            try:
                await reader.read()
            except:
                pass
            finally:
                self.tcp_clients.remove(writer)
                writer.close()
                print(f"Dashboard {addr} disconnected")

        server = await asyncio.start_server(handle_client, '0.0.0.0', self.tcp_port)
        addr = server.sockets[0].getsockname()
        print(f"\nTCP server listening on {addr[0]}:{addr[1]}")

        # Show connection info
        import subprocess
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            ips = result.stdout.strip().split()
            if ips:
                print(f"Connect from Mac using: {ips[0]}:{self.tcp_port}")
        except:
            pass

        async with server:
            await server.serve_forever()

    def broadcast_data(self, sensor_type, data):
        """Send data to all connected clients"""
        # Format: SENSOR_TYPE,timestamp,value1,value2,...
        if sensor_type == "FSR":
            line = f"FSR,{data['timestamp']:.6f},{data['force']:.4f},{data['raw']}\n"
            self.fsr_count += 1
        elif sensor_type == "MM":
            line = f"MM,{data['timestamp']:.6f},{data['x']:.4f},{data['y']:.4f},{data['z']:.4f}\n"
            self.mm_count += 1
        else:
            return

        # Send to all clients
        for writer in self.tcp_clients[:]:
            try:
                writer.write(line.encode())
                asyncio.create_task(writer.drain())
            except:
                self.tcp_clients.remove(writer)

    def fsr_data_handler(self):
        """Handle FSR data in background"""
        while self.running:
            data_batch = self.fsr.getData()
            for data in data_batch:
                self.broadcast_data("FSR", data)
            time.sleep(0.01)

    async def mm_data_handler(self):
        """Handle MetaMotion data"""
        while self.running:
            data_batch = self.mm.getData()
            for data in data_batch:
                self.broadcast_data("MM", data)
            await asyncio.sleep(0.01)

    async def connect_sensors(self):
        """Connect to all sensors"""
        print("\n🔌 Connecting to sensors...")

        # Connect FSR
        if self.config['sensors']['fsr']['enabled']:
            print("Connecting to FSR...")
            if self.fsr.connect():
                print("✅ FSR connected")
            else:
                print("❌ FSR connection failed")

        # Connect MetaMotion
        if self.config['sensors']['metamotion']['enabled']:
            print("Connecting to MetaMotion...")
            if await self.mm.connect():
                print("✅ MetaMotion connected")
            else:
                print("❌ MetaMotion connection failed")

    async def start_streaming(self):
        """Start all sensor streams"""
        print("\n📊 Starting sensor streams...")

        self.running = True
        self.start_time = time.time()

        # Start FSR
        if self.fsr.serial:
            self.fsr.start()
            # Start FSR handler thread
            fsr_thread = threading.Thread(target=self.fsr_data_handler)
            fsr_thread.daemon = True
            fsr_thread.start()

        # Start MetaMotion
        if self.mm.connected:
            await self.mm.startStreaming()
            # Start MM handler task
            asyncio.create_task(self.mm_data_handler())

        print("✅ Streaming started")

    async def print_stats(self):
        """Print statistics periodically"""
        while self.running:
            await asyncio.sleep(10)

            elapsed = time.time() - self.start_time
            print(f"\n📈 Stats after {elapsed:.0f}s:")
            print(f"  FSR: {self.fsr_count} samples ({self.fsr_count / elapsed:.1f} Hz)")
            print(f"  MetaMotion: {self.mm_count} samples ({self.mm_count / elapsed:.1f} Hz)")
            print(f"  Connected dashboards: {len(self.tcp_clients)}")

    async def run(self):
        """Main run method"""
        print("=" * 60)
        print("HealthTRAC Headless Sensor Streamer")
        print("=" * 60)

        # Start TCP server
        tcp_task = asyncio.create_task(self.start_tcp_server())

        # Wait a bit
        await asyncio.sleep(1)

        # Connect sensors
        await self.connect_sensors()

        # Start streaming
        await self.start_streaming()

        # Start stats printer
        asyncio.create_task(self.print_stats())

        print("\n✅ System running! Waiting for dashboard connections...")
        print("Press Ctrl+C to stop\n")

        # Keep running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")
            self.running = False

            # Stop sensors
            self.fsr.stop()
            await self.mm.stopStreaming()

            # Disconnect
            self.fsr.close()
            await self.mm.disconnect()


async def main():
    streamer = HeadlessSensorStreamer()
    await streamer.run()


if __name__ == "__main__":
    asyncio.run(main())