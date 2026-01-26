import time
import threading
import os

DEBUG = True
RECORDING_FILE = "recording_timestamp"
# THRESHOLD = In nanoseconds
check_recording_command = f"cat {RECORDING_FILE}"
recording_timestamp = 0

# Check the recording flag value on the hub
def get_recording_timestamp():
    # TESTING CODE
    if DEBUG:
        recording_timestamp = int(os.popen(check_recording_command).read())
        


# Check if stored recording flag value is within the threshold
def check_if_in_threshold():
    curr_time = time.time_ns
    if (curr_time < (recording_timestamp + THR )

def main():
    get_recording_timestamp()

if __name__ == "__main__":
    main()