import csv, os, yaml
from datetime import datetime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
with open(os.path.join(ROOT, "config", "config.yaml")) as f:
    cfg = yaml.safe_load(f)
LOG_DIR = cfg.get("logging", {}).get("log_dir", "data/logs")
os.makedirs(LOG_DIR, exist_ok=True)

_handles = {}
_counts  = {}

def log_data(sensor: str, values, flush_every=100):
    if sensor not in _handles:
        path = os.path.join(LOG_DIR, f"{sensor}.csv")
        fh   = open(path, "a", newline="")
        _handles[sensor] = (csv.writer(fh), fh)
        _counts[sensor]  = 0
    writer, fh = _handles[sensor]
    writer.writerow([datetime.utcnow().isoformat(), sensor, *values])
    _counts[sensor] += 1
    if _counts[sensor] % flush_every == 0:
        fh.flush()
