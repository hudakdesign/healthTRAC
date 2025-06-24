"""
ChairFSRSensor
• Opens real serial port and yields (gst, value) tuples
"""
import serial, yaml, os, itertools
from core.timestamp import get_gst, fallback_timestamp

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
with open(os.path.join(ROOT, "config", "config.yaml")) as f:
    cfg = yaml.safe_load(f)
PORT = cfg["chair"]["port"]
BAUD = cfg["chair"]["baud"]

class ChairFSRSensor:
    def __init__(self):
        self.ser = serial.Serial(PORT, BAUD, timeout=1)

    def stream(self):
        """Infinite generator of (GST, value)."""
        for _ in itertools.count():
            line = self.ser.readline().decode("utf-8", errors="ignore").strip()
            try:
                _, raw = line.split(",")
                val = int(raw)
                yield get_gst(), val
            except ValueError:
                pass
