import time
import threading
import os

DEBUG = True
RECORDING_FILE = "recording_timestamp"
THRESHOLD = 10e9 # In nanoseconds
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
    curr_time = time.time_ns
    if (curr_time < (recording_timestamp + THRESHOLD )):
        return True
    return False

def set_recording_timestamp_loop():
    while running:
        set_recording_timestamp()

def test():
    while running:
        print(f"Current timestamp: {time.time_ns()}\nHub timestamp: {recording_timestamp}\nIn threshold: {check_if_in_threshold()}")

def main():
    server_threads = []
    if DEBUG:
        server_threads.append(threading.Thread(target=test))
    server_threads.append(threading.Thread(target=set_recording_timestamp_loop))
    
    for thread in server_threads:
        thread.start()

if __name__ == "__main__":
    main()