import os, sys, numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets
import pyqtgraph as pg
from sensors.chair import ChairFSRSensor
from sensors.toothbrush_sim import ToothbrushSensorSim
from core.logger import log_data
from core.timestamp import get_gst

# --- PyQtGraph window -------------------------------------------------
app = QtWidgets.QApplication([])
win = pg.GraphicsLayoutWidget(show=True, title="healthTRAC Dashboard")
win.resize(1200, 600)

# Chair plot
chair_axis = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation='bottom')
chair_plot = win.addPlot(axisItems={'bottom': chair_axis}, title="Chair FSR")
chair_curve = chair_plot.plot(pen='y')
chair_ts, chair_vals = [], []

# Toothbrush plot
win.nextRow()
brush_plot = win.addPlot(title="Toothbrush |a| (g)")
brush_curve = brush_plot.plot(pen='c')
brush_ts, brush_mag = [], []

WIN_S = 10
def trim(ts, vals):
    tmin = get_gst() - WIN_S
    while ts and ts[0] < tmin:
        ts.pop(0); vals.pop(0)

# --- Sensor generators ------------------------------------------------
chair_gen = ChairFSRSensor().stream()
brush_gen = ToothbrushSensorSim().stream()

# --- Update loop ------------------------------------------------------
def update():
    # Chair sample
    gst, fsr = next(chair_gen)
    chair_ts.append(gst); chair_vals.append(fsr)
    trim(chair_ts, chair_vals)
    chair_curve.setData(chair_ts, chair_vals)
    log_data("chair", [fsr])

    # Toothbrush sample
    gst_b, ax, ay, az = next(brush_gen)
    mag = np.sqrt(ax**2 + ay**2 + az**2)
    brush_ts.append(gst_b); brush_mag.append(mag)
    trim(brush_ts, brush_mag)
    brush_curve.setData(brush_ts, brush_mag)
    log_data("toothbrush_sim", [ax, ay, az])

timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(20)            # 50 Hz GUI

if __name__ == "__main__":
    QtWidgets.QApplication.instance().exec_()
