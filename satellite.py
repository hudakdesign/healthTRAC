import numpy as np
import sounddevice as sd
import subprocess
import sys
import threading
import time
import wave

# Defaults
sleep_time = 1/10
channels = 2
dtype = 'int16'
sample_rate = 44100
file_name = "recording"
file_directory = "recordings/"
file_path = f"{file_directory}{file_name}"


audio_frames = []
recording = True
hub_timestamp = 0
timeout = 5e9 # 5 seconds in nanoseconds


def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    audio_frames.append(indata.copy())

def start_recording():
    # Log start time
    start_time = time.time_ns()

    # Start recording stream
    with sd.InputStream(samplerate=sample_rate,
                        channels=channels,
                        dtype=dtype,
                        callback=callback):
        global recording
        while recording:
            sd.sleep(100)
        
    audio_data = np.concatenate(audio_frames)

    # Writes data to file timestamped with the start time
    with wave.open(f"{file_path}_{start_time}.wav", 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(np.dtype(dtype).itemsize)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

# Thread for polling the hub using paramiko
def check_recording_status():
    global recording
    global hub_timestamp

    while True:
        # TODO: Implement paramiko ssh connection
        # for now call hub.py locally
        # this is very similar, just isn't networked yet
        str_hub_timestamp = subprocess.run(['python3', 'hub.py'], capture_output=True, text=True).stdout.strip()
        hub_timestamp = int(str_hub_timestamp)
        print(f"hub_timestamp: {hub_timestamp}")

        # Sleep for a bit
        time.sleep(sleep_time)

# Thread for toggling recording on and off based on timestamp from the hub
def toggle_recording():
    global recording

    while True:
        # Current timestamp on the satellite
        satellite_timestamp = time.time_ns()

        # If the satellite timestamp is within the timeout, then the hub wants it to be recording
        if satellite_timestamp < hub_timestamp + timeout:
            recording = True
        # Otherwise, the hub is down, or doesnt want it to be recording
        else:
            recording = False

        # Sleep for a bit
        time.sleep(sleep_time)



if __name__ == "__main__":
    def tui_toggle_recording():
        global recording

        while True:
            subprocess.run('clear')
            input(f"Recording running {recording}\nToggle with [Enter]")
            recording = not recording
    
    toggle_recording_thread = threading.Thread(target=tui_toggle_recording)
    toggle_recording_thread.start()

    check_recording_status_thread = threading.Thread(target=check_recording_status)
    check_recording_status_thread.start()

    while True:
        # If recording is toggled on, retoggle it
        if recording:
            start_recording()
        # Otherwise, sleep for a sec
        time.sleep(sleep_time)