# Network Architecture

## Local:
Devices are listed in the hierarchy for which they are connected.
- Raspberry Pi 5:
    - Wired:
        - Microphone
    - Wireless (Wifi):
        - Toothbrush Bridge:
            - Toothbrush IMU (Bluetooth)
        - FSR Array
        - Raspberry Pi Zero (Only transmits confirmation that recording is happening):
            - Microphone (wired)


## External:
- Tailscale connection to Pi Hub

## Notes:
Pi Hub (Raspberry Pi 5) is the only device that connects to the outside world via tailscale. Any data viewed from the outside is aggregated and displayed on a web-server