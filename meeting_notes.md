# Meeting Notes
## New hub-satellite architecture
- Satellite ssh's into hub, checks timestamp in recording file
    - `if (curr_time < (record_time + timeout)): keep recording; otherwise stop`
    - If the hub wants recordings to stop, it changes its timestamp to zero (which is always outside the timeout)
    - If the satellite loses connection, it no longer can update what it knows the timestamp to be and the timeout occurs after `timeout` time elapses
## Audio recording changes
- Satellite records continuously. Pausing the recording tells it to write zeros to the wav file as opposed to writing frequency values.