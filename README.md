# Health-TRAC v0 Prototype

Wired proof-of-concept for the **chair FSR + toothbrush IMU** home-monitoring system.

---

## Repository Layout

```
health-trac/
├─ arduino/
│  └─ chair_fsr.ino           ← ESP32 sketch: streams raw FSR values
│
├─ dashboard/
│  ├─ chairRealtimePlot.py    ← Live 10-s PyQtGraph plot of FSR
│  └─ serialDebug.py          ← Console reader prints each serial line
│
└─ data/
    └─ chair/                 ← CSV logs will be written here
```

---

## Quick Start

### 1. Prerequisites

| Tool                     | Notes |
|--------------------------|-------|
| Python 3.10+             | Create a project virtualenv |
| pip 23+                  | `python -m pip install --upgrade pip` |
| pyserial, pyqtgraph      | Serial comms and real-time plotting |
| Arduino IDE or CLI 2.x   | To flash ESP32 sketch |
| ESP32 board support      | Install via Arduino Boards Manager in Arduino IDE |

### 2. Setup

```bash
# Clone repo and enter directory
git clone https://github.com/<your-org>/health-trac.git
cd health-trac

# Create & activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install pyserial pyqtgraph

# Compile and upload sketch (adjust port name if needed)
arduino-cli compile -b esp32:esp32:esp32 arduino
arduino-cli upload  -b esp32:esp32:esp32 -p /dev/cu.usbserial-10 arduino
```

---

## Scripts

### `dashboard/serialDebug.py`
Verifies that the board is streaming correctly.  
**Run:**  
```bash
python dashboard/serialDebug.py
```

### `dashboard/chairRealtimePlot.py`
Shows a 10-second scrolling plot of force data using PyQtGraph.  
**Run:**  
```bash
python dashboard/chairRealtimePlot.py
```
Edit the hardcoded `PORT`, `BAUD`, etc. at the top of the script.

### `arduino/chair_fsr.ino`
ESP32 firmware for the chair-mounted FSR sensor.  
- Idles at 2 Hz, switches to 50 Hz when threshold is crossed  
- Outputs lines in the format:  
  ```
  <millis>,<raw_adc_value>
  ```

Upload via Arduino IDE or `arduino-cli` as shown above.

---

## Next Steps

1. **Add CSV logging** to `chairRealtimePlot.py` in `data/chair/`.
2. **Create `toothbrushStream.py`** to read MetaMotion RL accelerometer via BLE (or USB simulation for now).
3. **Implement a heartbeat** (e.g. cron job or script) to report sensor status via email or push to GitHub.

---

© 2025 Center for Biomedical Innovation - University of Vermont • MIT License
