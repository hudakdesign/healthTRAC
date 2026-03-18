# HealthTRAC Audio Pipeline

## Architecture:

### Overview:
Code operates on two different types of devices:
- Hub
- Satellite

The Hub tells the satellites when they should be recording, and collects data on if the satellites are recording

The Satellite records audio data from its attached microphone and stores it locally, this data is *not* transmitted

### Details:
- The satellite runs `satellite.py`. The hub runs `hub.py`
- The hub and satellite communicate using `paramiko`

## Code:
### Hub:
- To record:
    - When polled by satellite, return current timestamp
- To pause recording:
    - When polled by satellite, return 0 (triggers timeout)
### Satellite:
- Repeatedly poll the hub
- Compare returned timestamp to current timestamp
    - If `satellite_timestamp < hub_timestamp + timeout`
    - Keep recording
    - Otherwise write zeros in place of audio data. Keep track of time but leave out the data.
- Continuously record to file in recordings directory

## Libraries:
- flask
- gpiozero
- numpy
- requests
- sounddevice

## Packages:
- portaudio19-dev