import time
import threading
import os
import paramiko

DEBUG = True
RECORDING_FILE = "recording_timestamp"
THRESHOLD = 10e9 # In nanoseconds
UPDATE_FREQUENCY = 1/60
check_recording_command = f"cat ~/Projects/Hub-Audio-Test/{RECORDING_FILE}"
recording_timestamp = 0

running = True 

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

ssh.load_system_host_keys()
ssh.connect(hostname="health-trac-pi", username="healthtrac")
# Check the recording flag value on the hub
# Set global recording timestamp value
# TODO: currently checks own file system
# def set_recording_timestamp():
#     global recording_timestamp

#     # recording_timestamp = int(os.popen(check_recording_command).read())
        
# Check if stored recording flag value is within the threshold
def check_if_in_threshold():
    curr_time = time.time_ns()
    if (curr_time < (recording_timestamp + THRESHOLD )):
        return True
    return False

# # Repeatedly updates recording timestamp
# def set_recording_timestamp_loop():
#     while running:
#         set_recording_timestamp()
#         time.sleep(UPDATE_FREQUENCY)

def ssh_set_recording_timestamp_loop():
    global recording_timestamp

    while running:
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(check_recording_command)
        recording_timestamp = int(ssh_stdout.read().decode())
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
        server_threads.append(threading.Thread(target=ssh_set_recording_timestamp_loop))
        
        for thread in server_threads:
            thread.start()

    except KeyboardInterrupt:
        global running
        running = False
        # for thread in server_threads:
        #     thread.stop()
if __name__ == "__main__":
    main()