import sounddevice as sd
import numpy as np
import wave
import threading
import sys
import os
import time

# Parameters
sample_rate = 44100  # 44.1 kHz
channels = 1  # 1 = Mono, 2 = Stereo
save_path = "recordings/"
file_name = "audio_recording"
dtype = 'int16'

# Buffer to hold recorded data
recorded_frames = []
recording = True

def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    recorded_frames.append(indata.copy())

def is_recording():
    global recording
    # Check if the recording flag is set
    while True:
        if check_recording_status():
            print("Is true")
            recording = True
        else:
            print("Is false")
            recording = False
            break
        time.sleep(1)

def check_recording_status():
    with open("recording", 'r') as infile:
        line = infile.readline()
        line = line.strip()
        print(line)
        if line == "True":
            print("Is True")
            return True
        else:
            print("Is False")
            return False

def toggle_recording():
    rec = check_recording_status()

    with open("recording", 'w') as outfile:
        if rec:
            outfile.write("False")
        else:
            outfile.write("True")

def start_recording():
    # Start recording stream
    with sd.InputStream(samplerate=sample_rate, 
                        channels=channels, 
                        dtype=dtype, 
                        callback=callback):
        while recording:
            sd.sleep(100)

    # Combine and save to file
    audio_data = np.concatenate(recorded_frames)

    with wave.open(f'{save_path}{file_name}_{time.time_ns()}', 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(np.dtype(dtype).itemsize)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())

def main():
    def tui_toggle_recording():
        while True:
            if check_recording_status():
                os.system("clear")
                print("RECORDING RUNNING")
                print("Press [ENTER] to pause")
            else:
                os.system("clear")
                print("RECORDING PAUSED")
                print("Press [ENTER] to resume")
            input()
            toggle_recording()

    # Start thread for toggling recording status
    toggle_recording_thread = threading.Thread(target=tui_toggle_recording)
    toggle_recording_thread.start()
    # Start thread to check for recording flag
    is_recording_thread = threading.Thread(target=is_recording)
    is_recording_thread.start()
    # Restarts recording if flag is set again
    while True:
        if recording:
            start_recording()
        else:
            time.sleep(1/10)

if __name__ == "__main__":
    main()