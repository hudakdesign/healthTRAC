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

    while True:
        # TODO: Implement paramiko ssh connection
        # for now call hub.py locally
        hub_timestamp = subprocess.run(['python3', 'hub.py'], capture_output=True, text=True)

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

    while True:
        # If recording is toggled on, retoggle it
        if recording:
            start_recording()
        # Otherwise, sleep for a sec
        else:
            time.sleep(sleep_time)