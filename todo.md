# Architectural Notes

## Priority
- Get live toothbrush data displaying
- Get live audio data displaying
- 2 minute plots (and 24 hour ones)

## Audio
- fixed scale graphs
- store last `n` datapoints for the last 24 hours in memory
- also store datapoints at 60hz for last 2 minutes
- save data in `time` length chunks
- implement getting audio wave amplitude data into api running on satellite

## All sensors
- store last `n` datapoints for the last 24 hours in memory
- also store datapoints at 60hz for last 2 minutes
- save data in `time` length chunks
    - all sensors should have the same chunk length defined in `constants.py`

## Backburner
- Hands off setup
    - Satellite pis are just imaged and call api on hub to get identifier