import time
import threading
import os

RECORDING_FILE = "recording_timestamp"
is_recording = True

# Writes the passed in value to RECORDING_FILE 
def write_to_recording_file(value):
    with open(RECORDING_FILE, 'w') as outfile:
        outfile.write(str(value))

# Sets the recording file to the current timestamp in ns
def set_recording_timestamp():
    write_to_recording_file(time.time_ns())

# Sets the recording file to 0, this tells the satellites to stop recording
# BC they check if their current time is less than
# the value in the recording file plus an offset
def pause_recording():
    write_to_recording_file(0)

# Gets user input to toggle if the satellites should be recording or not
def user_input_loop():
    while True:
        os.system("clear")
        input(f"is_recording: {is_recording}\nTo toggle [PRESS ENTER]")
        if is_recording:
            is_recording = False
        else:
            is_recording = True

# Repeatedly checks if it should be recording and either sets the timestamp
# to the time or to zero
def recording_update_loop():
    while True:
        if is_recording:
            set_recording_timestamp()
        else:
            pause_recording()

def main():
    input_loop_thread = threading.Thread(target=user_input_loop)
    update_loop_thread = threading.Thread(target=recording_update_loop)
    input_loop_thread.start()
    update_loop_thread.start()

if __name__ == "__main__":
    main()