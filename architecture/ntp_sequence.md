┌───────────────────┐     ┌───────────────────┐     ┌───────────────────────────────────┐
│  Internet NTP     │     │ Raspberry Pi 5    │     │ Nano ESP32-S3 Bridges (×2)        │
│  Pool             │     │ Hub Server        │     │ • Toothbrush Bridge               │
│  (pool.ntp.org)   │     │                   │     │ • FSR Bridge                      │
└─────────┬─────────┘     └─────────┬─────────┘     └─────────┬─────────────────────────┘
          │                         │                         │
          │                         │                         │
[PHASE 1: HUB SERVER NTP SYNCHRONIZATION]                     │
          │                         │                         │
          │                         │──Boot sequence          │
          │                         │──Start ntpd service     │
          │                         │                         │
          │<────NTP Query (UDP/123)─│                         │
          │     Client Request      │                         │
          │                         │                         │
          │─────NTP Response───────>│                         │
          │  • Server time: T_ntp   │                         │
          │  • Stratum: 2           │                         │
          │  • Root delay: 15ms     │                         │
          │                         │                         │
          │                         │──Adjust system clock    │
          │                         │  (ntpd disciplined)     │
          │                         │                         │
          │                         │──Hub is now TIME        │
          │                         │  AUTHORITY for local    │
          │                         │  network                │
          │                         │                         │
          │                         │──Start Flask API:       │
          │                         │  GET /api/time          │
          │                         │  (for bridge sync)      │
          │                         │                         │
[Periodic NTP updates every 1 hour]│                         │
          │<────NTP Query───────────│                         │
          │─────NTP Response───────>│                         │
          │                         │──Drift correction       │
          │                         │                         │
          │                         │                         │
[PHASE 2: BRIDGE INITIAL SYNCHRONIZATION]                     │
          │                         │                         │
          │                         │                         │──Boot sequence
          │                         │                         │──Connect to WiFi
          │                         │                         │
          │                         │<────HTTP GET /api/time──│
          │                         │  (Bridge requests time) │
          │                         │                         │
          │                         │  Measure RTT:           │
          │                         │  t_request = micros()   │
          │                         │                         │
          │                         │─────HTTP Response──────>│
          │                         │  {"timestamp_ns":       │
          │                         │     1728485394123456000,│
          │                         │   "timestamp_s":        │
          │                         │     1728485394.123456,  │
          │                         │   "stratum":2,          │
          │                         │   "source":"ntp"}       │
          │                         │                         │
          │                         │                         │  t_response = micros()
          │                         │                         │
          │                         │                         │──Calculate offset:
          │                         │                         │  RTT = t_response -
          │                         │                         │        t_request
          │                         │                         │  T_offset = T_hub +
          │                         │                         │    (RTT / 2)
          │                         │                         │  t_offset = millis()
          │                         │                         │
          │                         │                         │──Store sync params:
          │                         │                         │  • T_offset
          │                         │                         │  • t_offset
          │                         │                         │  • last_sync_time
          │                         │                         │
          │                         │                         │──Log sync event
          │                         │                         │
          │                         │                         │
[PHASE 3: PERIODIC RE-SYNCHRONIZATION (Every 5 Minutes)]      │
          │                         │                         │
          │                         │                         │──5 minutes elapsed
          │                         │                         │
          │                         │<────HTTP GET /api/time──│
          │                         │                         │
          │                         │─────HTTP Response──────>│
          │                         │  new_T_hub              │
          │                         │                         │
          │                         │                         │──Calculate drift:
          │                         │                         │  expected_T = 
          │                         │                         │    T_offset +
          │                         │                         │    (millis() -
          │                         │                         │     t_offset)
          │                         │                         │  drift_ms =
          │                         │                         │    new