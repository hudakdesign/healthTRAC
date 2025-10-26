┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              HEALTH TRAC SYSTEM ARCHITECTURE                            │
│                           Target Completion: 2025-11-15                                 │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    SENSOR LAYER                                         │
├─────────────────────────┬─────────────────────────┬─────────────────────────────────────┤
│   XIAO nRF52 SENSE        │   FSR Array (×6)        │   USB Mic Array (×3)              │
│   [Toothbrush IMU]      │   [Chair Armrests]      │   [Room Audio]                      │
│                         │                         │                                     │
│ ┌─────────────────────┐ │ ┌─────────────────────┐ │ ┌─────────────────────────────────┐ │
│ │ • CPU: ARM Cortex-M0│ │ │ Flexiforce A201-100 │ │ │ • 1 USB audio interface         │ │
│ │   SAMD21G18 @48MHz  │ │ │ • 0-100 lbs (445N)  │ │ │ • 3 MEMS mic inputs             │ │
│ │ • Flash: 256KB      │ │ │ • 3 per armrest     │ │ │ • 16kHz sampling                │ │
│ │ • SRAM: 32KB        │ │ │ • Sit-to-stand push │ │ │ • Direct USB to Pi 5            │ │
│ │ • LSM6DS3TR-C IMU   │ │ │ • Analog 0-3.3V     │ │ │ • PyAudio capture               │ │
│ │ • BLE advertising   │ │ │                     │ │ │                                 │ │
│ │ • 110mAh LiPo       │ │ │ USB-C powered       │ │ │ Privacy: Local processing only  │ │
│ │ • Target: ≥7 days   │ │ │ via bridge          │ │ │ Raw audio stored on Pi SSD      │ │
│ │                     │ │ │                     │ │ │ Features only for monitoring    │ │
│ └─────────────────────┘ │ └─────────────────────┘ │ └─────────────────────────────────┘ │
│                         │                         │                                     │
│ MAC: C8:0B:FB:24:C1:65  │  6 sensors total        │  Model: TBD                         │
│ Module ID: 0x6A (LSM6DS3TR-C)│  (2 armrests × 3)       │                                │
│                         │                         │                                     │
│ ✅ STREAMING            │  🔄 PLANNED             │  🔄 PLANNED                         │
└────────────┬────────────┴────────────┬────────────┴─────────────┬───────────────────────┘
             │ BLE 5.0                 │ Analog                   │ USB 3.0
             │ As-needed connection    │ Continuous 20Hz          │ Continuous 16kHz
             │ Motion-triggered        │                          │
             ▼                         ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              INTEGRATION LAYER                                           │
├─────────────────────────┬─────────────────────────┬─────────────────────────────────────┤
│  Nano ESP32-S3          │  Nano ESP32-S3          │  Raspberry Pi 5 Hub Server          │
│  [Toothbrush Bridge]    │  [FSR Bridge]           │  [Central Controller]               │
│                         │                         │                                     │
│ ┌─────────────────────┐ │ ┌─────────────────────┐ │ ┌─────────────────────────────────┐ │
│ │ ESP32-S3 dual-core  │ │ │ ESP32-S3 dual-core  │ │ │ BCM2712 Cortex-A76 @ 2.4GHz     │ │
│ │ 240MHz, 512KB SRAM  │ │ │ 240MHz, 512KB SRAM  │ │ │ 16GB LPDDR4X-4267 RAM           │ │
│ │ 16MB Flash (SPIFFS) │ │ │ 16MB Flash (SPIFFS) │ │ │ 64GB microSD (boot)             │ │
│ │                     │ │ │                     │ │ │ 2TB USB-C SSD (data, encrypted) │ │
│ │ Role: BLE Scanner   │ │ │ Role: 6-ch ADC      │ │ │                                 │ │
│ │ • Connect to XIAO   │ │ │ • 12-bit, 20Hz/ch   │ │ │ Services:                       │ │
│ │ • Download buffered │ │ │ • Voltage→Force     │ │ │ • TCP Server (port 5555)        │ │
│ │   data from flash   │ │ │ • Per-sensor cal    │ │ │ • NTP Time Authority            │ │
│ │ • Translate time    │ │ │ • No event detection│ │ │ • Flask Dashboard (port 5000)   │ │
│ │ • WiFi relay        │ │ │ • WiFi relay        │ │ │ • PyAudio + VAD processing      │ │
│ │                     │ │ │                     │ │ │ • CSV storage + session mgmt    │ │
│ │ TCP: Persistent     │ │ │ TCP: Persistent     │ │ │                                 │ │
│ │ Heartbeat: 3s       │ │ │ Heartbeat: 3s       │ │ │ IP: 10.0.1.3 (static, local)    │ │
│ │ Buffering: 16MB     │ │ │ Buffering: 16MB     │ │ │ NTP: Syncs to pool.ntp.org      │ │
│ └─────────────────────┘ │ └─────────────────────┘ │ └─────────────────────────────────┘ │
│                         │                         │                                     │
│ USB-C powered           │ USB-C powered           │ USB-C PD 5V/5A (UPS recommended)    │
│                         │                         │                                     │
│ ⏳ IN PROGRESS          │  🔄 PLANNED             │  🔴 VM → Pi 5 MIGRATION DUE 10/16   │
└────────────┬────────────┴────────────┬────────────┴─────────────┬───────────────────────┘
             │ WiFi TCP/JSON           │ WiFi TCP/JSON            │ HTTP/WebSocket
             │ Local network           │ Local network            │ Local + Internet (IT approval)
             ▼                         ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            PRESENTATION LAYER                                            │
│                         (Remote Monitoring - Status Only)                                │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │                    Web Dashboard (Flask + Chart.js)                              │   │
│  │                    Accessible via: http://10.0.1.3:5000 (local)                  │   │
│  │                                   https://[external-IP] (remote, VPN/IT approved) │   │
│  │                                                                                   │   │
│  │  ┌──────────────────────┐  ┌─────────────────────────────────────────────────┐  │   │
│  │  │ System Status Panel  │  │ Sensor Activity Panel (Live Plots - 10min lag OK)│  │   │
│  │  │ ┌──────────────────┐ │  │ ┌────────────────────────────────────────────┐ │  │   │
│  │  │ │ Sensor: ✅ XIAO  │ │  │ │ Toothbrush: 3-axis accel (X, Y, Z)        │ │  │   │
│  │  │ │ Bridge: ✅ Nano  │ │  │ │ FSR: 6-channel force plot                 │ │  │   │
│  │  │ │ Hub:    ✅ Pi 5  │ │  │ │ Audio: VAD activity + RMS                 │ │  │   │
│  │  │ │ Battery: 87%     │ │  │ │                                           │ │  │   │
│  │  │ │ Time Sync: ±8ms  │ │  │ │ Rolling window: Last 60 seconds           │ │  │   │
│  │  │ │ Uptime: 4d 12h   │ │  │ │ Update rate: Every 10-30 seconds (relaxed)│ │  │   │
│  │  │ └──────────────────┘ │  │ └────────────────────────────────────────────┘ │  │   │
│  │  └──────────────────────┘  └─────────────────────────────────────────────────┘  │   │
│  │                                                                                   │   │
│  │  ┌──────────────────────┐  ┌─────────────────────────────────────────────────┐  │   │
│  │  │ Session Controls     │  │ System Log (Events, Errors, Warnings)          │  │   │
│  │  │ ┌──────────────────┐ │  │ ┌────────────────────────────────────────────┐ │  │   │
│  │  │ │ [Start Session]  │ │  │ │ 15:04:23 INFO: XIAO connected              │ │  │   │
│  │  │ │ [Stop Session]   │ │  │ │ 15:03:12 WARN: Time drift corrected        │ │  │   │
│  │  │ │ Session: 20251009│ │  │ │ 15:02:45 INFO: FSR calibration complete    │ │  │   │
│  │  │ │ Duration: 2h 34m │ │  │ │ 15:01:30 ERROR: Network blip, reconnected  │ │  │   │
│  │  │ │ [Export CSV]     │ │  │ │                                           │ │  │   │
│  │  │ └──────────────────┘ │  │ └────────────────────────────────────────────┘ │  │   │
│  │  └──────────────────────┘  └─────────────────────────────────────────────────┘  │   │
│  │                                                                                   │   │
│  │  Note: Remote access (internet) is STATUS MONITORING ONLY.                       │   │
│  │        No raw data transmission over internet - only system health metrics.      │   │
│  │        Requires IT department VPN/firewall approval.                             │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
│  🔄 DESIGNED - Implementation In Progress                                               │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA STORAGE & PRIVACY                                      │
│                                                                                          │
│  Local Storage (Pi 5 - 2TB USB-C SSD, LUKS Encrypted):                                  │
│  • Raw sensor data: CSV files organized by session and sensor type                      │
│  • Raw audio files: WAV format, 16kHz, 3-channel, encrypted at rest                     │
│  • System logs: Connection events, errors, calibration records                          │
│  • Metadata: Session info, participant ID (anonymized), timestamps                      │
│                                                                                          │
│  Remote Transmission (Internet - IT Approved Only):                                     │
│  • System health metrics: CPU, RAM, disk usage, connection status                       │
│  • Sensor status: Connected/disconnected, battery level, last-seen timestamp            │
│  • Dashboard visualizations: Limited feature data for status checking                   │
│  • NO RAW AUDIO transmitted over internet                                               │
│  • NO personally identifiable information transmitted                                   │
│                                                                                          │
│  Privacy Compliance:                                                                    │
│  • Participants informed of local audio storage in consent form                         │
│  • Data anonymized before export for research analysis                                  │
│  • Access controls: Dashboard password-protected (optional for pilot, required for prod)│
│  • Audit trail: All system access logged with timestamps                                │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           KEY SPECIFICATIONS SUMMARY                                     │
├──────────────────────┬──────────────────────────────────────────────────────────────────┤
│ Time Sync Target     │ ±10ms (goal) / ±0.5s (hard requirement)                          │
│ Toothbrush Battery   │ ≥7 days with motion-triggered logging                            │
│ FSR Sampling Rate    │ 20Hz continuous, all 6 channels                                  │
│ Audio Sampling       │ 16kHz, 3-channel, VAD + features extracted                       │
│ Dashboard Latency    │ 10-minute lag acceptable for status monitoring                   │
│ System Uptime Target │ >99% over 7-day deployment                                       │
│ Data Capture Target  │ >99% (packet loss <0.1%)                                         │
│ Network              │ Local WiFi (2.4/5GHz) + Ethernet for Pi 5                        │
│ Remote Access        │ VPN/IT-approved only, status monitoring (no raw data)            │
└──────────────────────┴──────────────────────────────────────────────────────────────────┘