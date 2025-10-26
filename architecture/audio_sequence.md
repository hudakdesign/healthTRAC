┌───────────────────┐                    ┌───────────────────┐     ┌──────────┐
│ USB Mic Array (×3)│                    │ Raspberry Pi 5    │     │Dashboard │
│                   │                    │ Hub Server        │     │ (Web)    │
│ • 1 USB audio     │                    │                   │     │          │
│   interface       │                    │ • PyAudio capture │     │          │
│ • 3 mic inputs    │                    │ • librosa         │     │          │
│ • 16kHz sampling  │                    │ • webrtcvad       │     │          │
│ • Model: TBD      │                    │ • 2TB SSD storage │     │          │
└─────────┬─────────┘                    └─────────┬─────────┘     └────┬─────┘
          │                                        │                    │
          │                                        │                    │
[PHASE 1: SYSTEM INITIALIZATION]                   │                    │
          │                                        │                    │
          │                                        │──Power on          │
          │                                        │──Load PyAudio      │
          │                                        │──Detect USB device │
          │                                        │  (ALSA/PulseAudio) │
          │                                        │                    │
USB audio interface enumerated                     │                    │
          │────Device Info (3-ch, 16kHz)──────────>│                    │
          │                                        │                    │
          │                                        │──Configure capture:│
          │                                        │  • Channels: 3     │
          │                                        │  • Rate: 16000 Hz  │
          │                                        │  • Format: INT16   │
          │                                        │  • Chunk: 512 samp │
          │                                        │                    │
          │                                        │──Initialize VAD:   │
          │                                        │  webrtcvad.Vad(3)  │
          │                                        │  (aggressiveness)  │
          │                                        │                    │
          │                                        │──Create session dir│
          │                                        │  /data/sessions/   │
          │                                        │   session_20251009/│
          │                                        │   audio_raw/       │
          │                                        │   audio_features/  │
          │                                        │                    │
          │                                        │──Start capture     │
          │                                        │                    │
          │                                        │                    │
[PHASE 2: CONTINUOUS AUDIO CAPTURE & PROCESSING]   │                    │
          │                                        │                    │
[Every 32ms - Frame of 512 samples @ 16kHz]        │                    │
          │                                        │                    │
3-channel audio data (16-bit PCM)                  │                    │
          │────[Frame 512 samples × 3 ch]─────────>│                    │
          │                                        │                    │
          │                                        │──PyAudio callback  │
          │                                        │  receives data     │
          │                                        │                    │
          │                                        │──Write raw audio   │
          │                                        │  to WAV file:      │
          │                                        │  audio_raw/        │
          │                                        │   20251009_150423. │
          │                                        │   wav              │
          │                                        │  (3-ch, 16kHz,     │
          │                                        │   16-bit PCM)      │
          │                                        │                    │
          │                                        │  NOTE: Encrypted   │
          │                                        │  at rest (LUKS SSD)│
          │                                        │                    │
          │                                        │                    │
[Every 50ms - Feature Extraction Window]           │                    │
          │                                        │                    │
          │                                        │──Accumulate 800    │
          │                                        │  samples (50ms @   │
          │                                        │  16kHz, overlapping│
          │                                        │  windows)          │
          │                                        │                    │
          │                                        │──For each channel: │
          │                                        │                    │
          │                                        │  [Channel 1]       │
          │                                        │  • RMS = sqrt(mean │
          │                                        │    (x²)) = 0.42    │
          │                                        │  • ZCR = zero-     │
          │                                        │    crossing rate   │
          │                                        │    = 0.27          │
          │                                        │  • Centroid =      │
          │                                        │    spectral centroid│
          │                                        │    = 2380 Hz       │
          │                                        │                    │
          │                                        │  [Channel 2]       │
          │                                        │  • RMS = 0.38      │
          │                                        │  • ZCR = 0.24      │
          │                                        │  • Centroid = 2210 │
          │                                        │                    │
          │                                        │  [Channel 3]       │
          │                                        │  • RMS = 0.45      │
          │                                        │  • ZCR = 0.31      │
          │                                        │  • Centroid = 2550 │
          │                                        │                    │
          │                                        │──Voice Activity    │
          │                                        │  Detection (VAD):  │
          │                                        │  webrtcvad.is_speech│
          │                                        │   (audio, 16000)   │
          │                                        │  Result: True      │
          │                                        │  (speech detected) │
          │                                        │                    │
          │                                        │──Select best channel│
          │                                        │  (highest RMS):    │
          │                                        │  Channel 3 = 0.45  │
          │                                        │                    │
          │                                        │──Write features CSV│
          │                                        │  audio_features/   │
          │                                        │   features.csv     │
          │                                        │                    │
          │                                        │  Format:           │
          │                                        │  timestamp_hub,    │
          │                                        │  vad, rms_ch1,     │
          │                                        │  zcr_ch1,          │
          │                                        │  centroid_ch1,     │
          │                                        │  rms_ch2, ...,     │
          │                                        │  best_channel      │
          │                                        │                    │
          │                                        │──WebSocket push───>│
          │                                        │  (Every ~2 seconds │
          │                                        │   = 40 feature rows│
          │                                        │   aggregated)      │
          │                                        │                    │
          │                                        │  {"sensor":"audio",│
          │                                        │   "timestamp":..., │
          │                                        │   "vad":1,         │
          │                                        │   "rms":0.45,      │
          │                                        │   "zcr":0.31,      │
          │                                        │   "centroid":2550, │
          │                                        │   "channel":3}     │
          │                                        │                    │
          │                                        │                    │──Update chart
          │                                        │                    │  • VAD timeline
          │                                        │                    │  • RMS plot
          │                                        │                    │  • Rolling 60s
          │                                        │                    │
          │                                        │                    │
[PHASE 3: PRIVACY PROTECTION - NO RAW AUDIO TRANSMISSION]     │                    │
          │                                        │                    │
          │                                        │──Dashboard connects│
          │                                        │  from laptop (local│
          │                                        │  network or VPN)   │
          │                                        │                    │
          │                                        │──WebSocket sends───>│
          │                                        │  ONLY FEATURES:    │
          │                                        │  • RMS, ZCR,       │
          │                                        │    Centroid        │
          │                                        │  • VAD (0/1)       │
          │                                        │  • Channel number  │
          │                                        │                    │
          │                                        │  NO RAW AUDIO!     │
          │                                        │                    │
          │                                        │                    │──Display charts
          │                                        │                    │  (features only)
          │                                        │                    │
          │                                        │                    │
[PHASE 4: REMOTE MONITORING (INTERNET ACCESS - IT APPROVED)]  │                    │
          │                                        │                    │
          │                                        │                    │
          │                    ┌──────────────────────────────────┐    │
          │                    │ Remote User (Researcher Laptop)  │    │
          │                    │ • Location: Off-site             │    │
          │                    │ • Connection: VPN or firewall    │    │
          │                    │   (IT approved)                  │    │
          │                    └──────────────┬───────────────────┘    │
          │                                   │                        │
          │                                   │──HTTPS GET (VPN)───────>│
          │                                   │  https://[external-IP]: │
          │                                   │   5000/dashboard        │
          │                                   │                        │
          │                                   │<──Dashboard HTML───────│
          │                                   │  (Status page only)    │
          │                                   │                        │
          │                                   │──WebSocket Connect─────>│
          │                                   │  (via VPN tunnel)      │
          │                                   │                        │
          │                                   │<──System Status────────│
          │                                   │  {"audio":"connected", │
          │                                   │   "vad_active":true,   │
          │                                   │   "last_update":"5s",  │
          │                                   │   "features":{...}}    │
          │                                   │                        │
          │                                   │  TRANSMITTED:          │
          │                                   │  • System health       │
          │                                   │  • Feature summary     │
          │                                   │  • VAD activity        │
          │                                   │                        │
          │                                   │  NOT TRANSMITTED:      │
          │                                   │  • Raw audio data      │
          │                                   │  • Participant identity│
          │                                   │  • Detailed waveforms  │
          │                                   │                        │
          │                                   │                        │
          │                                        │                    │
[PHASE 5: WAV FILE MANAGEMENT & ROTATION]          │                    │
          │                                        │                    │
          │                                        │──Every 10 minutes: │
          │                                        │  Close current WAV │
          │                                        │  Start new WAV file│
          │                                        │  (for manageability│
          │                                        │                    │
          │                                        │──File naming:      │
          │                                        │  audio_raw/        │
          │                                        │   20251009_150423. │
          │                                        │   wav              │
          │                                        │   20251009_151023. │
          │                                        │   wav              │
          │                                        │  (timestamp-based) │
          │                                        │                    │
          │                                        │──Check disk usage: │
          │                                        │  If >80% full:     │
          │                                        │  • Alert dashboard │
          │                                        │  • Compress old WAV│
          │                                        │  • Delete >30 days │
          │                                        │                    │
          │                                        │                    │
[PHASE 6: POST-DEPLOYMENT DATA EXPORT]             │                    │
          │                                        │                    │
          │                                        │──Researcher login  │
          │                                        │  via dashboard     │
          │                                        │                    │
          │                                        │──Click "Export CSV"│
          │                                        │  button            │
          │                                        │                    │
          │                                        │──Server creates ZIP│
          │                                        │  • audio_features/ │
          │                                        │    features.csv    │
          │                                        │  • Metadata file   │
          │                                        │                    │
          │                                        │  NOTE: Raw audio   │
          │                                        │  NOT included in   │
          │                                        │  automatic export  │
          │                                        │  (requires manual  │
          │                                        │  transfer via USB) │
          │                                        │                    │
          │                                        │<──Download ZIP─────│
          │                                        │  (features only)   │
          │                                        │                    │
          ▼                                        ▼                    ▼

Key Design Notes:
─────────────────
1. Privacy Architecture:
   • Raw audio stored ONLY on Pi 5 SSD (encrypted LUKS)
   • Network transmission (local or internet): Features ONLY
   • No speech content recoverable from RMS, ZCR, Centroid
   • VAD (voice activity) binary flag, not speech content

2. Remote Monitoring (Internet):
   • Requires IT department VPN/firewall approval
   • Status monitoring only: System health, sensor connectivity
   • Limited feature data for verification (not full waveforms)
   • No personally identifiable information transmitted
   • Dashboard shows: "Audio system: UP, VAD active, Last update: 5s"

3. Feature Extraction Rate:
   • 20Hz (every 50ms) for responsiveness
   • Each feature window: 800 samples (50ms @ 16kHz)
   • Overlapping windows (256 sample hop) for smoothness

4. Voice Activity Detection (VAD):
   • webrtcvad library (Google, BSD license)
   • Aggressiveness level 3 (most aggressive filtering)
   • Binary output: 0 (no speech) or 1 (speech detected)
   • Used for voice usage metrics (e.g., % time speaking)

5. Audio File Management:
   • 10-minute WAV files for manageability
   • Automatic rotation to prevent huge files
   • Compression/archival after 7 days (optional)
   • Deletion after 30 days (configurable)

6. Multi-Channel Processing:
   • 3 microphones → 3 channels simultaneously captured
   • Features extracted per-channel
   • Best channel auto-selected (highest RMS)
   • Allows post-hoc channel selection by researchers

7. Dashboard Latency:
   • WebSocket updates every ~2 seconds (aggregated features)
   • 10-minute lag acceptable for status monitoring
   • Not real-time tracking, just verification system is working

8. Participants Informed:
   • Consent form clearly states local audio storage
   • Encrypted at rest, not transmitted over internet
   • Used for research purposes, de-identified before analysis