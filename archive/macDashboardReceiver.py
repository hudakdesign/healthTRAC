#!/usr/bin/env python3
"""
macDashboardReceiver.py - Receives data from Ubuntu VM
Real-time plotting of FSR and MetaMotion data with UTC timestamps
"""

import sys
import socket
import threading
import time
import numpy as np
from collections import deque
from datetime import datetime
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui


class DateAxisItem(pg.AxisItem):
    """Custom axis that shows UTC timestamps with milliseconds"""

    def tickStrings(self, values, scale, spacing):
        """Convert timestamp values to strings"""
        strings = []
        for v in values:
            try:
                # Convert Unix timestamp to datetime
                dt = datetime.utcfromtimestamp(v)
                # Format with milliseconds
                strings.append(dt.strftime('%H:%M:%S.%f')[:-3])  # [:-3] to show only milliseconds
            except:
                strings.append('')
        return strings


class DataReceiver(QtCore.QThread):
    """Background thread for receiving TCP data from Ubuntu VM"""

    # Signals for different data types
    fsrData = QtCore.pyqtSignal(float, float, int)  # timestamp, force, raw
    mmData = QtCore.pyqtSignal(float, float, float, float)  # timestamp, x, y, z
    statusUpdate = QtCore.pyqtSignal(str)

    def __init__(self, vmIp, vmPort=5556):
        super().__init__()
        self.vmIp = vmIp
        self.vmPort = vmPort
        self.socket = None
        self.running = True
        self.connected = False
        self.reconnectAttempts = 0

    def connectToVm(self):
        """Connect to Ubuntu VM"""
        try:
            self.statusUpdate.emit(f"🔄 Connecting to {self.vmIp}:{self.vmPort} (attempt {self.reconnectAttempts + 1})")

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)  # Longer timeout for initial connection
            self.socket.connect((self.vmIp, self.vmPort))

            self.connected = True
            self.reconnectAttempts = 0
            self.statusUpdate.emit(f"✅ Connected to Ubuntu VM at {self.vmIp}:{self.vmPort}")
            return True

        except socket.timeout:
            self.reconnectAttempts += 1
            self.statusUpdate.emit(f"⏰ Connection timeout to {self.vmIp}:{self.vmPort}")
            return False
        except ConnectionRefused:
            self.reconnectAttempts += 1
            self.statusUpdate.emit(f"❌ Connection refused - is Ubuntu VM running the streamer?")
            return False
        except Exception as e:
            self.reconnectAttempts += 1
            self.statusUpdate.emit(f"❌ Connection failed: {e}")
            return False

    def run(self):
        """Main receiver loop"""
        while self.running:
            if not self.connected:
                if self.connectToVm():
                    # Set socket to non-blocking for data reception
                    self.socket.settimeout(1.0)
                else:
                    time.sleep(5)  # Wait before retry
                    continue

            try:
                # Receive data
                data = self.socket.recv(4096)  # Larger buffer
                if not data:
                    self.statusUpdate.emit("❌ Connection lost - no data received")
                    self.connected = False
                    continue

                # Parse incoming lines
                lines = data.decode('utf-8').strip().split('\n')
                for line in lines:
                    if line.strip():
                        self.parseLine(line.strip())

            except socket.timeout:
                # Normal timeout, continue
                continue
            except ConnectionResetError:
                self.statusUpdate.emit("❌ Connection reset by Ubuntu VM")
                self.connected = False
            except Exception as e:
                self.statusUpdate.emit(f"❌ Receive error: {e}")
                self.connected = False

            if not self.connected and self.socket:
                self.socket.close()
                self.socket = None
                time.sleep(2)

    def parseLine(self, line):
        """Parse CSV line from Ubuntu"""
        try:
            parts = line.split(',')
            if len(parts) < 2:
                print(f"Debug: Short line: {line}")
                return

            sensorType = parts[0]

            # Handle STATUS messages (different format)
            if sensorType == "STATUS" or ":" in parts[1]:
                status = ",".join(parts[1:]) if len(parts) > 1 else parts[0]
                # self.statusUpdate.emit(f"📊 Ubuntu status: {status}")
                # show the Ubuntu status in green text if both the FSR and MM sensors show 'true'
                if "true" in status and "true" in status.split(":")[1]:
                    self.statusUpdate.emit(f"✅ Ubuntu status: {status}")
                print(f"Debug: Status message: {line}")
                return

            # Handle data messages (timestamp, values...)
            try:
                timestamp = float(parts[1])
            except ValueError:
                print(f"Debug: Invalid timestamp in: {line}")
                return

            if sensorType == "FSR" and len(parts) >= 4:
                try:
                    force = float(parts[2])
                    raw = int(float(parts[3]))  # Convert to float first, then int
                    self.fsrData.emit(timestamp, force, raw)
                except ValueError as e:
                    print(f"Debug: FSR parse error: {line} -> {e}")

            elif sensorType == "MM" and len(parts) >= 5:
                try:
                    x = float(parts[2])
                    y = float(parts[3])
                    z = float(parts[4])
                    self.mmData.emit(timestamp, x, y, z)
                except ValueError as e:
                    print(f"Debug: MM parse error: {line} -> {e}")
            else:
                print(f"Debug: Unknown message format: {line}")

        except Exception as e:
            print(f"Debug: General parse error: {line} -> {e}")

    def stop(self):
        """Stop the receiver"""
        self.running = False
        if self.socket:
            self.socket.close()


class SensorPlotWidget(pg.PlotWidget):
    """Custom plot widget for sensor data with UTC timestamps"""

    def __init__(self, title, yLabel, maxPoints=2000):
        # Create custom axis item for timestamps
        date_axis = DateAxisItem(orientation='bottom')

        super().__init__(title=title, axisItems={'bottom': date_axis})
        self.setLabel('left', yLabel)
        self.setLabel('bottom', 'Time (UTC)')
        self.showGrid(x=True, y=True)

        # Data storage - now storing absolute timestamps
        self.maxPoints = maxPoints
        self.timestamps = deque(maxlen=maxPoints)
        self.dataLines = []

        # Stats
        self.sampleCount = 0

        # Set up x-axis range to show time window
        self.timeWindow = 60  # Show last 60 seconds of data
        self.enableAutoRange(axis='y')

    def addDataLine(self, name, color):
        """Add a data line to the plot"""
        line = self.plot(pen=color, name=name)
        data = deque(maxlen=self.maxPoints)
        self.dataLines.append({'line': line, 'data': data, 'name': name})
        return len(self.dataLines) - 1

    def updateData(self, timestamp, values):
        """Update plot with new data"""
        # Store absolute timestamp
        self.timestamps.append(timestamp)

        # Update each data line
        for i, value in enumerate(values):
            if i < len(self.dataLines):
                self.dataLines[i]['data'].append(value)

                # Update plot (only if we have data)
                if len(self.timestamps) > 1:
                    times = list(self.timestamps)
                    data = list(self.dataLines[i]['data'])
                    self.dataLines[i]['line'].setData(times, data)

        # Update x-axis range to show recent data
        if len(self.timestamps) > 0:
            current_time = self.timestamps[-1]
            self.setXRange(current_time - self.timeWindow, current_time, padding=0.02)

        self.sampleCount += 1


class MacDashboard(QtWidgets.QMainWindow):
    """Main dashboard window"""

    def __init__(self, vmIp):
        super().__init__()
        self.vmIp = vmIp

        # Setup UI
        self.setupUi()

        # Start data receiver
        self.dataReceiver = DataReceiver(vmIp)
        self.dataReceiver.fsrData.connect(self.handleFsrData)
        self.dataReceiver.mmData.connect(self.handleMmData)
        self.dataReceiver.statusUpdate.connect(self.updateStatus)
        self.dataReceiver.start()

        # Stats
        self.fsrCount = 0
        self.mmCount = 0
        self.startTime = time.time()
        self.lastFsrValue = 0
        self.lastMmValues = (0, 0, 0)
        self.lastFsrTimestamp = None
        self.lastMmTimestamp = None

        # Update timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.updateStats)
        self.timer.start(1000)  # 1 Hz

    def setupUi(self):
        """Create the user interface"""
        self.setWindowTitle(f"HealthTRAC Dashboard - {self.vmIp}")
        self.setGeometry(100, 100, 1400, 900)

        # Central widget
        centralWidget = QtWidgets.QWidget()
        self.setCentralWidget(centralWidget)
        layout = QtWidgets.QVBoxLayout()
        centralWidget.setLayout(layout)

        # Status bar
        self.statusLabel = QtWidgets.QLabel("🔄 Connecting to Ubuntu VM...")
        self.statusLabel.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(self.statusLabel)

        # Create plots
        self.setupPlots(layout)

        # Stats panel
        self.setupStatsPanel(layout)

    def setupPlots(self, layout):
        """Setup plot widgets"""
        # FSR Plot
        self.fsrPlot = SensorPlotWidget("Force Sensitive Resistor (FSR)", "Force (N)")
        self.fsrPlot.addDataLine("Force", 'y')
        layout.addWidget(self.fsrPlot)

        # MetaMotion Plot
        self.mmPlot = SensorPlotWidget("MetaMotion Accelerometer", "Acceleration (g)")
        self.mmPlot.addLegend()
        self.mmXIdx = self.mmPlot.addDataLine("X", 'r')
        self.mmYIdx = self.mmPlot.addDataLine("Y", 'g')
        self.mmZIdx = self.mmPlot.addDataLine("Z", 'b')
        layout.addWidget(self.mmPlot)

    def setupStatsPanel(self, layout):
        """Setup statistics panel"""
        statsLayout = QtWidgets.QHBoxLayout()
        layout.addLayout(statsLayout)

        # FSR stats
        fsrGroup = QtWidgets.QGroupBox("FSR Statistics")
        fsrLayout = QtWidgets.QVBoxLayout()
        fsrGroup.setLayout(fsrLayout)

        self.fsrCountLabel = QtWidgets.QLabel("Samples: 0")
        self.fsrRateLabel = QtWidgets.QLabel("Rate: 0.0 Hz")
        self.fsrLastLabel = QtWidgets.QLabel("Last Value: --")
        self.fsrTimestampLabel = QtWidgets.QLabel("Last Time: --")

        fsrLayout.addWidget(self.fsrCountLabel)
        fsrLayout.addWidget(self.fsrRateLabel)
        fsrLayout.addWidget(self.fsrLastLabel)
        fsrLayout.addWidget(self.fsrTimestampLabel)
        statsLayout.addWidget(fsrGroup)

        # MetaMotion stats
        mmGroup = QtWidgets.QGroupBox("MetaMotion Statistics")
        mmLayout = QtWidgets.QVBoxLayout()
        mmGroup.setLayout(mmLayout)

        self.mmCountLabel = QtWidgets.QLabel("Samples: 0")
        self.mmRateLabel = QtWidgets.QLabel("Rate: 0.0 Hz")
        self.mmLastLabel = QtWidgets.QLabel("Last Value: --")
        self.mmTimestampLabel = QtWidgets.QLabel("Last Time: --")

        mmLayout.addWidget(self.mmCountLabel)
        mmLayout.addWidget(self.mmRateLabel)
        mmLayout.addWidget(self.mmLastLabel)
        mmLayout.addWidget(self.mmTimestampLabel)
        statsLayout.addWidget(mmGroup)

        # Connection stats
        connGroup = QtWidgets.QGroupBox("Connection")
        connLayout = QtWidgets.QVBoxLayout()
        connGroup.setLayout(connLayout)

        self.connStatusLabel = QtWidgets.QLabel("Status: Connecting...")
        self.uptimeLabel = QtWidgets.QLabel("Uptime: 0s")
        self.vmIpLabel = QtWidgets.QLabel(f"VM IP: {self.vmIp}")
        self.currentTimeLabel = QtWidgets.QLabel("Current Time: --")

        connLayout.addWidget(self.connStatusLabel)
        connLayout.addWidget(self.uptimeLabel)
        connLayout.addWidget(self.vmIpLabel)
        connLayout.addWidget(self.currentTimeLabel)
        statsLayout.addWidget(connGroup)

    def handleFsrData(self, timestamp, force, raw):
        """Handle incoming FSR data"""
        self.fsrPlot.updateData(timestamp, [force])
        self.fsrCount += 1
        self.lastFsrValue = force
        self.lastFsrTimestamp = timestamp

        # Update labels
        self.fsrLastLabel.setText(f"Last Value: {force:.2f}N (raw: {raw})")

        # Convert timestamp to UTC datetime with milliseconds
        dt = datetime.utcfromtimestamp(timestamp)
        time_str = dt.strftime('%H:%M:%S.%f')[:-3]  # [:-3] for milliseconds
        self.fsrTimestampLabel.setText(f"Last Time: {time_str} UTC")

        # Update connection status since we're receiving data
        if self.connStatusLabel.text() != "Status: Connected":
            self.connStatusLabel.setText("Status: Connected")

    def handleMmData(self, timestamp, x, y, z):
        """Handle incoming MetaMotion data"""
        self.mmPlot.updateData(timestamp, [x, y, z])
        self.mmCount += 1
        self.lastMmValues = (x, y, z)
        self.lastMmTimestamp = timestamp

        # Update labels
        magnitude = np.sqrt(x ** 2 + y ** 2 + z ** 2)
        self.mmLastLabel.setText(f"Last Value: |a|={magnitude:.2f}g")

        # Convert timestamp to UTC datetime with milliseconds
        dt = datetime.utcfromtimestamp(timestamp)
        time_str = dt.strftime('%H:%M:%S.%f')[:-3]  # [:-3] for milliseconds
        self.mmTimestampLabel.setText(f"Last Time: {time_str} UTC")

    def updateStatus(self, message):
        """Update status label"""
        self.statusLabel.setText(message)
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

        if "✅" in message:
            self.statusLabel.setStyleSheet("color: green; font-weight: bold; padding: 5px;")
            self.connStatusLabel.setText("Status: Connected")
        elif "🔄" in message:
            self.statusLabel.setStyleSheet("color: orange; font-weight: bold; padding: 5px;")
            self.connStatusLabel.setText("Status: Connecting...")
        else:
            self.statusLabel.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
            self.connStatusLabel.setText("Status: Disconnected")

    def updateStats(self):
        """Update statistics display"""
        elapsed = time.time() - self.startTime

        # Update sample counts and rates
        fsrRate = self.fsrCount / elapsed if elapsed > 0 else 0
        mmRate = self.mmCount / elapsed if elapsed > 0 else 0

        self.fsrCountLabel.setText(f"Samples: {self.fsrCount}")
        self.fsrRateLabel.setText(f"Rate: {fsrRate:.1f} Hz")

        self.mmCountLabel.setText(f"Samples: {self.mmCount}")
        self.mmRateLabel.setText(f"Rate: {mmRate:.1f} Hz")

        # Uptime
        self.uptimeLabel.setText(f"Uptime: {int(elapsed)}s")

        # Current UTC time
        current_utc = datetime.utcnow()
        time_str = current_utc.strftime('%H:%M:%S.%f')[:-3]
        self.currentTimeLabel.setText(f"Current UTC: {time_str}")

    def closeEvent(self, event):
        """Clean shutdown"""
        print("Shutting down dashboard...")
        self.dataReceiver.stop()
        self.dataReceiver.wait()
        event.accept()


def main():
    """Main entry point"""
    app = QtWidgets.QApplication(sys.argv)

    # Get VM IP from user
    if len(sys.argv) > 1:
        vmIp = sys.argv[1]
    else:
        vmIp, ok = QtWidgets.QInputDialog.getText(
            None, 'Ubuntu VM IP Address',
            'Enter Ubuntu VM IP address:\n(After switching to Bridged Adapter)',
            text='192.168.0.24'
        )
        if not ok:
            sys.exit()

    print(f"Connecting to Ubuntu VM at {vmIp}:5556")

    # Create and show dashboard
    dashboard = MacDashboard(vmIp)
    dashboard.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()