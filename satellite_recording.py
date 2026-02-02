import time
import threading
import os

DEBUG = True
RECORDING_FILE = "recording_timestamp"
THRESHOLD = 10e9 # In nanoseconds
UPDATE_FREQUENCY = 1/60
check_recording_command = f"cat {RECORDING_FILE}"
recording_timestamp = 0

running = True

# Check the recording flag value on the hub
# Set global recording timestamp value
def set_recording_timestamp():
    global recording_timestamp
    recording_timestamp = int(os.popen(check_recording_command).read())
        
# Check if stored recording flag value is within the threshold
def check_if_in_threshold():
    curr_time = time.time_ns()
    if (curr_time < (recording_timestamp + THRESHOLD )):
        return True
    return False

# Repeatedly updates recording timestamp
def set_recording_timestamp_loop():
    while running:
        set_recording_timestamp()
        time.sleep(UPDATE_FREQUENCY)

# Displays debug info
def test():
    while running:
        os.system("clear")
        print(f"Current timestamp: {time.time_ns()}\nHub timestamp: {recording_timestamp}\nIn threshold: {check_if_in_threshold()}")
        time.sleep(UPDATE_FREQUENCY)

def main():
    try:
        server_threads = []
        if DEBUG:
            server_threads.append(threading.Thread(target=test))
        server_threads.append(threading.Thread(target=set_recording_timestamp_loop))
        
        for thread in server_threads:
            thread.start()

    except KeyboardInterrupt:
        for thread in server_threads:
            thread.stop()
if __name__ == "__main__":
    main()