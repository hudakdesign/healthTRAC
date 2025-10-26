#!/usr/bin/env python3
"""
Record accelerometer data from XIAO IMU via serial connection.
Saves 2 minutes of data to a CSV file.
"""
import serial
import time
import csv
import argparse
from datetime import datetime
from pathlib import Path


def find_serial_port():
    """Try to find the XIAO device automatically"""
    import serial.tools.list_ports

    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        # XIAO typically shows up as USB Serial or with specific VID/PID
        if 'USB' in port.description or 'Serial' in port.description:
            print(f"Found potential device: {port.device} - {port.description}")
            return port.device

    return None


def record_imu_data(port, duration_seconds=120, output_file='test_data/toothbrush.csv'):
    """Record IMU data from serial port for specified duration"""
    import serial.tools.list_ports

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Opening serial port: {port}")
    try:
        ser = serial.Serial(port, 115200, timeout=1, dsrdtr=False)
        print("Waiting for connection to stabilize...")
        time.sleep(2)
        print("Waiting for first data packet from device...")
        while True:
            line = ser.readline().decode('utf-8').strip()
            if line.startswith('Accel:'):
                print("Data stream started. Beginning recording...")
                break
            else:
                # Print any unexpected lines during startup
                if line:
                    print(f"[SETUP] Received: '{line}'")

        print("Starting to read data...")

        start_time = time.time()
        sample_count = 0
        debug_count = 0

        with open(output_file, 'w', newline='') as csvfile:
            fieldnames = ['timestamp_hub', 'accel_x', 'accel_y', 'accel_z']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            while (time.time() - start_time) < duration_seconds:
                if ser.in_waiting > 0:
                    try:
                        line = ser.readline().decode('utf-8').strip()

                        # Debug: print first 10 lines to see format
                        if debug_count < 50:
                            print(f"[DEBUG] Received: '{line}'")
                            debug_count += 1

                        if not line:
                            continue

                        # Parse the line: "Accel: 0.852, 0.325, 0.272"
                        if line.startswith('Accel:'):
                            try:
                                # Remove "Accel: " prefix and split by comma
                                values = line[7:].split(', ')
                                if len(values) != 3:
                                    print(f"[ERROR] Expected 3 values, got {len(values)}: {values}")
                                    continue
                                x = float(values[0].strip())
                                y = float(values[1].strip())
                                z = float(values[2].strip())

                                timestamp = time.time()

                                writer.writerow({
                                    'timestamp_hub': timestamp,
                                    'accel_x': x,
                                    'accel_y': y,
                                    'accel_z': z
                                })

                                sample_count += 1

                                if sample_count % 50 == 0:
                                    elapsed = time.time() - start_time
                                    remaining = duration_seconds - elapsed
                                    print(f"[{elapsed:.1f}s] Samples: {sample_count}, "
                                          f"Rate: {sample_count / elapsed:.1f} Hz, "
                                          f"Remaining: {remaining:.1f}s")

                            except ValueError as e:
                                print(f"Parse error: {e} - Line: '{line}'")
                                continue

                    except UnicodeDecodeError as e:
                        print(f"Decode error: {e}")
                        continue
                else:
                    time.sleep(0.01)

        ser.close()

        total_time = time.time() - start_time
        avg_rate = sample_count / total_time if sample_count > 0 else 0

        print(f"\nRecording complete!")
        print(f"Total samples: {sample_count}")
        print(f"Duration: {total_time:.2f} seconds")
        print(f"Average sample rate: {avg_rate:.2f} Hz")
        print(f"Data saved to: {output_file}")

        if sample_count == 0:
            print("\nWARNING: No data was received!")

    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        print("\nAvailable ports:")
        for port_info in serial.tools.list_ports.comports():
            print(f"  {port_info.device} - {port_info.description}")
    except KeyboardInterrupt:
        print("\nRecording interrupted by user")
        if 'ser' in locals():
            ser.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description='Record XIAO IMU data to CSV')
    parser.add_argument('--port', type=str, help='Serial port (e.g., /dev/cu.usbmodem101)')
    parser.add_argument('--duration', type=int, default=120,
                        help='Recording duration in seconds (default: 120)')
    parser.add_argument('--output', type=str, default='test_data/toothbrush.csv',
                        help='Output CSV file (default: test_data/toothbrush.csv)')
    args = parser.parse_args()

    # Auto-detect port if not specified
    port = args.port
    if not port:
        port = find_serial_port()
        if not port:
            print("Error: Could not auto-detect serial port")
            print("Please specify port manually with --port")
            return

    record_imu_data(port, args.duration, args.output)


if __name__ == '__main__':
    main()