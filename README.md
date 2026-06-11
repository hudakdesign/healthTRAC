# Health-TRAC v0.1.0 Prototype

Proof-of-concept for the **chair FSR, toothbrush IMU, and satellite microphone** home-monitoring system.

---

## Repository Layout

```txt
audio-subsystem/           <- Code for facilitating audio recording via
                              satellite microphones

dashboard-subsystem/       <- Code for facilitating data collection from
                              connected sensors, and telemetry for all
                              connected devices

firmware/                  <- Firmware for microcontrollers collecting both
                              FSR and IMU data

simulated-sensors/         <- Scripts for simulating FSR and IMU api's for
                              ease of development
```

---

## Quick Start

### 1. Prerequisites

#### System Packages

- `python3.14.5`
- `portaudio19-dev`

#### Python Packages

- `flask`
- `gpiozero`
- `numpy`
- `requests`
- `sounddevice`

### 2. Setup

```bash
# Clone repository and enter directory
git clone https://github.com/hudakdesign/healthTRAC
cd healthTRAC

# Set up virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start the dashboard
python dashboard-subsystem/dashboard.py
```

---

## Scripts

### `audio-subsystem/hub/hub.py`

Script to run on pi hub to control whether or not the satellite microphone is recording and to determine whether or not the microphone is recording properly

### `audio-subsystem/satellite/satellite.py`

Script to run on microphone satellite to record audio, send telemetry data to the hub, and to check with the hub to determine whether or not to record

### `dashboard-subsystem/dashboard.py`

Flask app to serve a dashboard for live debugging, and for logging data from connected sensors

---

## Development Notes

- This codebase is subject to heavy change and refactoring as we continue development and testing of the prototype
- The main branch is meant for (more) stable code, and development should not be done directly on main. Instead, it should be done on a different branch, and then merged into main after review.

---

## License

© 2026 Center for Biomedical Innovation - University of Vermont • MIT License
