#!/usr/bin/env python3
# dashboard/chairRealtimePlot_pg.py
# ----------------------
# Real-time plotting of FSR sensor data from a chair, read over serial.
# Uses PyQtGraph for fast updates and a custom time axis down to milliseconds.

import serial               # pyserial for UART communication
import sys                  # access to sys.argv and exit
import time                 # epoch timestamps and delays
import pyqtgraph as pg      # high-performance plotting library
from collections import deque  # efficient queue for sliding window
from PyQt5 import QtWidgets # Qt widgets for GUI
from datetime import datetime  # formatting timestamps

# --- Configuration ----------------------------------------------------------
PORT  = "/dev/cu.usbserial-10"      # replace with your serial port (e.g. "/dev/cu.usbserial-10")
BAUD  = 115200                      # serial baud rate (must match the Arduino)
WIN_S = 10                          # seconds of history to keep on the plot
INTV  = 0.02                        # update interval in seconds (20 ms)

def parse(line):
    """
    Parse a single line of incoming serial data.
    Expected format: "<timestamp_ms>,<fsr_value>"
    Returns the integer sensor reading or None on failure.
    """
    try:
        # split at comma and convert the second field to int
        return int(line.strip().split(",")[1])
    except Exception:
        # malformed line or missing data
        return None

class TimeAxis(pg.AxisItem):
    """
    A custom AxisItem that formats epoch timestamps
    into human-readable strings: "HH:MM:SS.mmm"
    """
    def tickStrings(self, values, scale, spacing):
        # values: list of epoch times in seconds (floats)
        return [
            datetime.fromtimestamp(val).strftime("%H:%M:%S.%f")[:-3]
            for val in values
        ]

def main():
    # --- Open serial port -----------------------------------------------------
    ser = serial.Serial(PORT, BAUD, timeout=None)

    # --- Data buffer ----------------------------------------------------------
    # store tuples of (epoch_time, fsr_reading)
    data = deque()

    # --- Set up Qt / PyQtGraph window ----------------------------------------
    app  = QtWidgets.QApplication(sys.argv)
    win  = pg.GraphicsLayoutWidget(title="Live Chair FSR")
    # replace default bottom axis with our TimeAxis
    plot = win.addPlot(axisItems={'bottom': TimeAxis(orientation='bottom')})
    curve = plot.plot(pen='y')  # yellow line

    # axis labels and ranges
    plot.setLabel('left', "FSR Raw")
    plot.setLabel('bottom', "Time")
    plot.setYRange(0, 4095)  # 12-bit ADC range
    win.show()

    def update():
        """
        Called regularly by a Qt timer.
        Reads all available serial lines, updates the buffer,
        and refreshes the plot.
        """
        # Read any waiting lines from the serial port
        while ser.in_waiting:
            raw_line = ser.readline().decode('utf-8', errors='ignore')
            fsr_val = parse(raw_line)
            if fsr_val is None:
                continue
            now = time.time()  # current epoch time in seconds
            data.append((now, fsr_val))

            # drop old data beyond WIN_S window
            while data and (now - data[0][0]) > WIN_S:
                data.popleft()

        # if we have data, re-draw the curve
        if data:
            xs, ys = zip(*data)
            curve.setData(xs, ys)
            # keep x-axis to last WIN_S seconds
            plot.setXRange(xs[-1] - WIN_S, xs[-1], padding=0)

    # --- Start update timer --------------------------------------------------
    timer = pg.QtCore.QTimer()
    timer.timeout.connect(update)
    timer.start(int(INTV * 1000))  # convert to milliseconds

    # --- Enter Qt event loop -------------------------------------------------
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
