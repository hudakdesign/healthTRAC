┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐     ┌──────────┐
│  XIAO nRF52   │     │ Nano ESP32-S3     │     │ Raspberry Pi 5    │     │Dashboard │
│  (Toothbrush)     │     │ (Toothbrush       │     │ Hub Server        │     │ (Web)    │
│                   │     │  Bridge)          │     │                   │     │          │
│ • 256KB Flash     │     │ • 16MB SPIFFS     │     │ • 2TB SSD         │     │          │
│ • 32KB SRAM       │     │ • BLE + WiFi      │     │ • NTP Authority   │     │          │
│ • BMI160 IMU      │     │ • TCP Client      │     │ • TCP Server 5555 │     │          │
└─────────┬─────────┘     └─────────┬─────────┘     └─────────┬─────────┘     └────┬─────┘
          │                         │                         │                    │
          │                         │                         │                    │
[PHASE 1: IDLE MONITORING]          │                         │                    │
          │                         │                         │                    │
IMU samples @1Hz (low power)        │                         │                    │
          │──Check motion threshold │                         │                    │
          │   (e.g., 1.1g)          │                         │                    │
          │                         │                         │                    │
BLE advertising @1s interval        │                         │                    │
          │─────"XIAO-TB"─────────> │                         │                    │
          │                         │                         │                    │
          │                         │                         │                    │
[PHASE 2: MOTION DETECTED - START LOGGING]                    │                    │
          │                         │                         │                    │
Motion > 1.1g detected!             │                         │                    │
          │──Switch to ACTIVE mode  │                         │                    │
          │──IMU sampling @25Hz (TBD)                         │                    │
          │                         │                         │                    │
          │──Log to Flash (256KB):  │                         │                    │
          │   • timestamp_local (ms)│                         │                    │
          │   • accel_x, y, z       │                         │                    │ 
          │                         │                         │                    │
[Brushing continues for ~2 minutes] │                         │                    │
          │                         │                         │                    │
          │                         │                         │                    │
[PHASE 3: MOTION STOPS - TRIGGER DATA DOWNLOAD]               │                    │
          │                         │                         │                    │
Motion < 1.1g for 5 seconds         │                         │                    │
          │──Stop logging           │                         │                    │
          │──Update advertisement:  │                         │                    │
          │   "Data Available"      │                         │                    │
          │                         │                         │                    │
          │─────"XIAO-TB (DATA)"───>│                         │                    │
          │                         │                         │                    │
          │                         │ Bridge detects signal   │                    │
          │                         │──Initiate BLE scan      │                    │
          │                         │                         │                    │
          │<─────BLE Connect────────│                         │                    │
          │                         │                         │                    │
          │───Send t_sync (local)───>│                         │                    │
          │                         │──Record T_hub + t_sync  │                    │
          │                         │  (for timestamp         │                    │
          │                         │   translation)          │                    │
          │                         │                         │                    │
          │───Download logged data──>│                         │                    │
          │   (CSV-like format:     │                         │                    │
          │    seq, t_local, x,y,z) │                         │                    │
          │                         │                         │                    │
          │<──ACK (data received)───│                         │                    │
          │                         │                         │                    │
          │──Clear flash buffer     │                         │                    │
          │                         │                         │                    │
          │───BLE Disconnect────────>│                         │                    │
          │                         │                         │                    │
          │──Return to IDLE mode    │                         │                    │
          │  (1Hz monitoring)       │                         │                    │
          │                         │                         │                    │
          │                         │                         │                    │
[PHASE 4: BRIDGE PROCESSES & RELAYS DATA]                     │                    │
          │                         │                         │                    │
          │                         │──Translate timestamps:  │                    │
          │                         │  For each sample:       │                    │
          │                         │  T_global = T_hub +     │                    │
          │                         │   (t_local - t_sync)    │                    │
          │                         │                         │                    │
          │                         │──Format JSON packets:   │                    │
          │                         │  {"sensor":"toothbrush",│                    │
          │                         │   "device_id":"C8:...", │                    │
          │                         │   "timestamp_hub":...,  │                    │
          │                         │   "timestamp_local":...,│                    │
          │                         │   "accel_x":0.45,       │                    │
          │                         │   "accel_y":-0.12,      │                    │
          │                         │   "accel_z":0.98}       │                    │
          │                         │                         │                    │
          │                         │──TCP Send (batch)──────>│                    │
          │                         │  (Multiple JSON packets,│                    │
          │                         │   one per line)         │                    │
          │                         │                         │                    │
          │                         │                         │──Parse & validate  │
          │                         │                         │──Write to CSV:     │
          │                         │                         │  /data/sessions/   │
          │                         │                         │   session_20251009/│
          │                         │                         │   toothbrush.csv   │
          │                         │                         │                    │
          │                         │                         │──WebSocket push───>│
          │                         │                         │  (Throttled to     │
          │                         │                         │   10-30s updates)  │
          │                         │                         │                    │
          │                         │                         │                    │──Update chart
          │                         │                         │                    │  (within 10min)
          │                         │                         │                    │
          │                         │                         │                    │
[PHASE 5: HEARTBEAT MAINTENANCE (No Data Period)]             │                    │
          │                         │                         │                    │
          │─────BLE Advert @1s─────>│                         │                    │
          │  (No data available)    │                         │                    │
          │                         │                         │                    │
          │                         │──No BLE connection      │                    │
          │                         │  (saves XIAO battery)   │                    │
          │                         │                         │                    │
          │                         │──TCP Heartbeat @3s─────>│                    │
          │                         │  {"type":"heartbeat",   │                    │
          │                         │   "device_id":"...",    │                    │
          │                         │   "timestamp":...}      │                    │
          │                         │                         │                    │
          │                         │                         │──Update status────>│
          │                         │                         │  "XIAO: Connected" │
          │                         │                         │  "Last seen: 2s ago"│
          │                         │                         │                    │
          │                         │                         │                    │
[ERROR RECOVERY: Connection Lost]   │                         │                    │
          │                         │                         │                    │
          │                         │──TCP connection drops   │                    │
          │                         │                         │                    │
          │                         │──Buffer data to SPIFFS  │                    │
          │                         │  (16MB capacity)        │                    │
          │                         │                         │                    │
          │                         │──Attempt reconnect      │                    │
          │                         │  (exponential backoff:  │                    │
          │                         │   1s, 2s, 4s...max 30s) │                    │
          │                         │                         │                    │
          │                         │────TCP Reconnect───────>│                    │
          │                         │                         │                    │
          │                         │──Send buffered data────>│                    │
          │                         │  (with original         │                    │
          │                         │   timestamps preserved) │                    │
          │                         │                         │                    │
          │                         │                         │──Recover all data  │
          │                         │                         │  (no data loss)    │
          │                         │                         │                    │
          │                         │<───ACK─────────────────│                    │
          │                         │                         │                    │
          │                         │──Clear SPIFFS buffer    │                    │
          │                         │                         │                    │
          │                         │──Resume normal ops      │                    │
          │                         │                         │                    │
          ▼                         ▼                         ▼                    ▼

Key Design Notes:
─────────────────
1. XIAO Flash Capacity: 256KB total
   • Reserve ~200KB for data logging
   • At 25Hz, 12 bytes/sample → ~16,600 samples
   • Covers ~11 minutes of brushing (plenty for 2-min events)

2. BLE Connection Trigger: "As-needed"
   • XIAO advertises "data available" flag when buffer non-empty
   • Bridge scans periodically (TBD: every 30s or on-demand?)
   • Minimizes BLE connection time to save XIAO battery

3. Timestamp Translation:
   • XIAO only has local millisecond counter (millis())
   • Bridge requests hub time T_hub during connection
   • Bridge correlates XIAO t_sync with T_hub
   • All subsequent samples: T_global = T_hub + (t_local - t_sync)

4. Battery Optimization:
   • IDLE: 1Hz IMU + BLE advert = ~1mA
   • ACTIVE: 25Hz IMU + flash writes = ~10mA (2min/day)
   • BLE downloads: ~15mA (1min/day)
   • Target: 7+ days on 110mAh battery

5. Dashboard Latency:
   • Real-time not required - 10min delay acceptable
   • WebSocket updates throttled to reduce Pi 5 load
   • Focus: Verify sensor is working, not live tracking