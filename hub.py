# Just checks if the recording flag is set to true or false
# Returns the current timestamp if true, otherwise returns 0

import time
import subprocess

flag_directory = "data/"
flag_file = "recording_flag"
flag_path = f"{flag_directory}{flag_file}"

if __name__ == "__main__":
    # cat the recording flag
    flag = subprocess.run(['cat', flag_path], capture_output=True, text=True).stdout.strip()

    # Checks if the flag is 1
    if flag == "1":
        print(time.time_ns())
    # otherwise, print 0
    else:
        print(0)