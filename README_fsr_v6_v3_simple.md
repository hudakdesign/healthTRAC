# FSR v6 + Hub v3 Simple Pipeline

This is a stripped-down FSR path focused on stable live behavior:

- Firmware: `firmware/FSR_v6_simple/FSR_v6_simple.ino`
- Hub: `fsr_hub_server_v3_simple.py`
- Dashboard: `templates/fsr_dashboard_v3_simple.html`
- Start script: `scripts/start_fsr_demo_v3_simple.sh`

## Design goals

- Keep transport simple.
- Sample fast (100 Hz) on Nano.
- Return only payload needed by hub:
  - `{ "timestamps": [...], "sensors": [[], [], ...] }`
- Use destructive pull semantics:
  - Hub calls `GET /data`
  - Nano returns current batch and clears exactly what it returned

## Nano endpoints

- `GET /id`
- `GET /data`
- `GET /status`

## Hub endpoints

- `GET /` dashboard
- `GET /fsr` latest rolling buffer (30s)
- `GET /status` hub + bridge health
- `GET /api/time` Nano time-sync source

## Run

```bash
cd /Users/airbook/Downloads/healthTRAC
python3 fsr_hub_server_v3_simple.py --bridge-ip 10.0.1.10 --poll 0.1 --flask-port 8080
```

Or:

```bash
cd /Users/airbook/Downloads/healthTRAC
./scripts/start_fsr_demo_v3_simple.sh 10.0.1.10 8080 0.1
```

Open:

- `http://localhost:8080/`
- `http://localhost:8080/status`

## Firmware upload

```bash
arduino-cli compile --fqbn arduino:esp32:nano_nora /Users/airbook/Downloads/healthTRAC/firmware/FSR_v6_simple
arduino-cli upload --fqbn arduino:esp32:nano_nora --port /dev/cu.usbmodemXXXX /Users/airbook/Downloads/healthTRAC/firmware/FSR_v6_simple
```

## Notes

- `timestamps` are Nano local `millis()` values.
- FFat spillover is enabled in firmware and used only if RAM queue fills.
- If upload fails with device configured/busy errors, stop hub polling first, then upload.

