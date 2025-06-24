#!/usr/bin/env python3
# dashboard/serialDebug.py
# --------------
# Simple script to open a serial port, read incoming lines,
# and print them with a timestamp for debugging.

#!/usr/bin/env python3
import serial      # pyserial for UART
import time        # for human-readable timestamps

import serial

# Configuration: adjust to your port and baud rate
PORT    = "/dev/cu.usbserial-10"  # e.g. "/dev/cu.usbserial-XXXX"
BAUD    = 115200                # must match sender
TIMEOUT = 1                     # read timeout in seconds

def main():
    """
    Open the serial port and continuously read lines.
    Each received line is printed with a HH:MM:SS prefix.
    """
    # open serial connection
    ser = serial.Serial(PORT, BAUD, timeout=TIMEOUT)
    print(f"Opened serial port {PORT} @ {BAUD} baud. Ctrl-C to exit.")

    try:
        while True:
            # read one line (up to newline)
            raw = ser.readline().decode('utf-8', errors='ignore').strip()
            if raw:
                # print with current clock time
                stamp = time.strftime("%H:%M:%S")
                print(f"[{stamp}] {raw}")
    except KeyboardInterrupt:
        # allow user to stop with Ctrl-C
        print("\nExiting serial debug.")
    finally:
        ser.close()

if __name__ == "__main__":
    main()

