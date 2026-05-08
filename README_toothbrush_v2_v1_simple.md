# Toothbrush Bridge v2 + Hub v1 Simple

This path mirrors the FSR simple architecture for toothbrush IMU data.

## New versioned files

- Bridge firmware: `firmware/toothbrush_bridge_firmware_v2_simple/toothbrush_bridge_firmware_v2_simple.ino`
- Hub server: `toothbrush_hub_server_v1_simple.py`
- Dashboard: `templates/toothbrush_dashboard_v1_simple.html`
- Start script: `scripts/start_toothbrush_demo_v1_simple.sh`
- Tests: `testing/test_toothbrush_hub_server_v1_simple.py`

## Existing firmware note

- `firmware/toothbrush_firmware_timer_isr/toothbrush_firmware_timer_isr.ino` remains unchanged.
- This keeps your current known-good XIAO firmware intact.

## Bridge endpoints

- `GET /id`
- `GET /data`
- `GET /status`

`GET /data` payload:

```json
{
  "timestamps": [12345, 12365, 12385],
  "sensors": [
    [100, 101, 102],
    [200, 201, 202],
    [300, 301, 302]
  ]
}
```

where sensors are `[accel_x, accel_y, accel_z]`.

## Run hub + dashboard

```bash
cd /Users/airbook/Downloads/healthTRAC
python3 toothbrush_hub_server_v1_simple.py --bridge-ip 10.0.1.20 --poll 0.05 --flask-port 8090
```

or

```bash
cd /Users/airbook/Downloads/healthTRAC
./scripts/start_toothbrush_demo_v1_simple.sh 10.0.1.20 8090 0.05
```

Open:

- `http://localhost:8090/`
- `http://localhost:8090/status`

## Upload bridge firmware

```bash
arduino-cli compile --fqbn arduino:esp32:nano_nora /Users/airbook/Downloads/healthTRAC/firmware/toothbrush_bridge_firmware_v2_simple
arduino-cli upload --fqbn arduino:esp32:nano_nora --port /dev/cu.usbmodemXXXX /Users/airbook/Downloads/healthTRAC/firmware/toothbrush_bridge_firmware_v2_simple
```

