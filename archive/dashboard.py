#!/usr/bin/env python3
"""
Simple real-time dashboard for sensor data
"""

import sys
import asyncio
import numpy as np
from collections import deque
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore
import qasync
import time
from datetime import datetime

from fsrReader import FSRReader
from metaMotionReader import MetaMotionReader


class SensorDashboard(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # Data buffers (keep last 10 seconds)
        self.maxPoints = 1000
        self.fsrTime = deque(maxlen=self.maxPoints)
        self.fsrForce = deque(maxlen=self.maxPoints)

        self.mmTime = deque(maxlen=self.maxPoints)
        self.mmX = deque(maxlen=self.maxPoints)
        self.mmY = deque(maxlen=self.maxPoints)
        self.mmZ = deque(maxlen=self.maxPoints)

        # Sensors - specify your port here if needed
        # For auto-detection, use: FSRReader()
        # For specific port, use: FSRReader(port="/dev/tty.usbserial-10")
        self.fsr = FSRReader(port="/dev/tty.usbserial-10")  # Specify your port
        self.mm = MetaMotionReader()

        # Setup UI
        self.setupUI()

        # Update timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.updatePlots)
        self.timer.start(50)  # 20 Hz refresh

        # Start time for relative timestamps
        self.startTime = time.time()

    def setupUI(self):
        """Create the UI"""
        self.setWindowTitle("HealthTRAC Sensor Monitor")
        self.resize(1000, 700)

        # Central widget
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # Title and status
        header = QtWidgets.QHBoxLayout()
        layout.addLayout(header)

        title = QtWidgets.QLabel("HealthTRAC Real-Time Monitor")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        self.statusLabel = QtWidgets.QLabel("Initializing...")
        header.addWidget(self.statusLabel)

        # FSR Plot
        self.fsrPlot = pg.PlotWidget(title="Force Sensor")
        self.fsrPlot.setLabel('left', 'Force', units='N')
        self.fsrPlot.setLabel('bottom', 'Time', units='s')
        self.fsrPlot.showGrid(x=True, y=True)
        self.fsrCurve = self.fsrPlot.plot(pen='y')
        layout.addWidget(self.fsrPlot)

        # Accelerometer Plot
        self.accelPlot = pg.PlotWidget(title="Toothbrush Motion")
        self.accelPlot.setLabel('left', 'Acceleration', units='g')
        self.accelPlot.setLabel('bottom', 'Time', units='s')
        self.accelPlot.showGrid(x=True, y=True)
        self.accelPlot.addLegend()

        self.xCurve = self.accelPlot.plot(pen='r', name='X')
        self.yCurve = self.accelPlot.plot(pen='g', name='Y')
        self.zCurve = self.accelPlot.plot(pen='b', name='Z')

        layout.addWidget(self.accelPlot)

        # Stats panel
        statsLayout = QtWidgets.QHBoxLayout()
        layout.addLayout(statsLayout)

        self.fsrStats = QtWidgets.QLabel("FSR: No data")
        statsLayout.addWidget(self.fsrStats)

        statsLayout.addStretch()

        self.mmStats = QtWidgets.QLabel("Motion: No data")
        statsLayout.addWidget(self.mmStats)

        # Control buttons
        buttonLayout = QtWidgets.QHBoxLayout()
        layout.addLayout(buttonLayout)

        self.connectButton = QtWidgets.QPushButton("Connect Sensors")
        self.connectButton.clicked.connect(self.connectSensors)
        buttonLayout.addWidget(self.connectButton)

        self.startButton = QtWidgets.QPushButton("Start Streaming")
        self.startButton.clicked.connect(self.startStreaming)
        self.startButton.setEnabled(False)
        buttonLayout.addWidget(self.startButton)

        buttonLayout.addStretch()

        self.timeLabel = QtWidgets.QLabel("")
        buttonLayout.addWidget(self.timeLabel)

    def connectSensors(self):
        """Connect to sensors"""
        self.statusLabel.setText("Connecting...")

        # Connect FSR
        if self.fsr.connect():
            self.statusLabel.setText("FSR connected, connecting MetaMotion...")
        else:
            self.statusLabel.setText("FSR connection failed")
            return

        # Connect MetaMotion (async)
        asyncio.create_task(self.connectMetaMotion())

    async def connectMetaMotion(self):
        """Connect to MetaMotion (async)"""
        if await self.mm.connect():
            self.statusLabel.setText("Both sensors connected")
            self.startButton.setEnabled(True)
        else:
            self.statusLabel.setText("MetaMotion connection failed")

    def startStreaming(self):
        """Start data streaming"""
        # Start FSR
        self.fsr.start()

        # Start MetaMotion
        asyncio.create_task(self.mm.startStreaming())

        self.statusLabel.setText("Streaming...")
        self.startButton.setText("Stop Streaming")
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.stopStreaming)

        # Reset start time
        self.startTime = time.time()

    def stopStreaming(self):
        """Stop streaming"""
        self.fsr.stop()
        asyncio.create_task(self.mm.stopStreaming())

        self.statusLabel.setText("Stopped")
        self.startButton.setText("Start Streaming")
        self.startButton.clicked.disconnect()
        self.startButton.clicked.connect(self.startStreaming)

    def updatePlots(self):
        """Update plots with new data"""
        currentTime = time.time()
        relativeTime = currentTime - self.startTime

        # Update time display
        self.timeLabel.setText(datetime.now().strftime("%H:%M:%S.%f")[:-3])

        # Get FSR data
        fsrData = self.fsr.getData()
        for sample in fsrData:
            t = sample['timestamp'] - self.startTime
            self.fsrTime.append(t)
            self.fsrForce.append(sample['force'])

        # Get MetaMotion data
        mmData = self.mm.getData()
        for sample in mmData:
            t = sample['timestamp'] - self.startTime
            self.mmTime.append(t)
            self.mmX.append(sample['x'])
            self.mmY.append(sample['y'])
            self.mmZ.append(sample['z'])

        # Update plots
        if self.fsrTime:
            self.fsrCurve.setData(list(self.fsrTime), list(self.fsrForce))
            self.fsrStats.setText(f"FSR: {len(self.fsrTime)} samples, "
                                  f"Latest: {self.fsrForce[-1]:.2f} N")

        if self.mmTime:
            self.xCurve.setData(list(self.mmTime), list(self.mmX))
            self.yCurve.setData(list(self.mmTime), list(self.mmY))
            self.zCurve.setData(list(self.mmTime), list(self.mmZ))

            mag = np.sqrt(self.mmX[-1] ** 2 + self.mmY[-1] ** 2 + self.mmZ[-1] ** 2)
            self.mmStats.setText(f"Motion: {len(self.mmTime)} samples, "
                                 f"Magnitude: {mag:.2f} g")

        # Auto-scale plots to show last 10 seconds
        if relativeTime > 10:
            self.fsrPlot.setXRange(relativeTime - 10, relativeTime)
            self.accelPlot.setXRange(relativeTime - 10, relativeTime)

    def closeEvent(self, event):
        """Clean shutdown"""
        self.fsr.close()
        if self.mm.connected:
            asyncio.create_task(self.mm.disconnect())
        event.accept()


async def main():
    """Main entry point"""
    app = QtWidgets.QApplication(sys.argv)

    # Create event loop
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Create and show dashboard
    dashboard = SensorDashboard()
    dashboard.show()

    # Run event loop
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    asyncio.run(main())