#!/usr/bin/env python3
"""
debugReceiver.py - Simple debug receiver to see what Ubuntu VM is sending
"""

import socket
import sys

def debugReceiver(vmIp, port=5556):
    """Connect and print raw data from Ubuntu VM"""
    print(f"Connecting to {vmIp}:{port}")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((vmIp, port))
        print("✅ Connected! Showing raw data from Ubuntu VM:")
        print("-" * 50)

        buffer = ""
        lineCount = 0
        fsrSamples = 0
        mmSamples = 0

        while lineCount < 100:  # Show first 100 lines
            data = sock.recv(1024)
            if not data:
                break

            buffer += data.decode('utf-8')

            # Process complete lines
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if line.strip():
                    lineCount += 1
                    print(f"Line {lineCount:2d}: {line}")

                    # Count data types
                    if line.startswith('FSR,'):
                        fsrSamples += 1
                    elif line.startswith('MM,'):
                        mmSamples += 1

                    # Parse and show structure for first few lines
                    if lineCount <= 10:
                        parts = line.split(',')
                        print(f"        Parts: {parts}")
                        print()

                    # Show summary every 20 lines
                    if lineCount % 20 == 0:
                        print(f"📊 Summary: {fsrSamples} FSR samples, {mmSamples} MM samples")
                        print()

        sock.close()
        print(f"\n📊 Final count: {fsrSamples} FSR samples, {mmSamples} MM samples")

        if fsrSamples == 0:
            print("⚠️  No FSR data - check if FSR sensor is working")
            print("⚠️  No MetaMotion data - check BLE connection")
        if mmSamples == 0:
            print("⚠️  No MetaMotion data - check BLE connection")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        vmIp = sys.argv[1]
    else:
        vmIp = input("Enter Ubuntu VM IP: ")
        if not vmIp:
            vmIp = "192.168.0.24"  # Default IP for Ubuntu VM
    debugReceiver(vmIp)