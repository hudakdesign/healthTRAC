"""
Global timestamp helper.

• get_gst() -> float   (Global System Time, seconds since epoch)
• fallback_timestamp() -> float  (sensor‐local fallback)
"""
import time

# In v0 we let GST == system clock; later you can NTP-discipline this.
def get_gst() -> float:
    """Return UTC time in seconds (float)."""
    return time.time()

def fallback_timestamp() -> float:
    """
    Return a sensor-local timestamp (monotonic) in seconds.
    Suitable if GST unavailable; later aligns with GST by offset.
    """
    return time.monotonic()
