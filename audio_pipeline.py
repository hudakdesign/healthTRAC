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

curr_recording_file = f"{save_path}{file_name}{time.time_ns()}.wav"

# Buffer to hold recorded data
recorded_frames = []
recording = True

def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    recorded_frames.append(indata.copy())

def check_recording_status():
    with open("recording", 'r') as infile:
        line = infile.readline()
        line = line.strip()
        print(line)
        if line == "True":
            return True
        else:
            return False

def toggle_recording():
    rec = check_recording_status()

    with open("recording", 'w') as outfile:
        if rec:
            outfile.write("False")
        else:
            outfile.write("True")

def update_recording_file():
    global curr_recording_file
    curr_recording_file = f"{save_path}{file_name}{time.time_ns()}.wav"

def start_recording():
    # Start recording stream
    with sd.InputStream(samplerate=sample_rate, 
                        channels=channels, 
                        dtype=dtype, 
                        callback=callback):
        while check_recording_status():
            sd.sleep(100)

    # Combine and save to file
    audio_data = np.concatenate(recorded_frames)

    with wave.open(curr_recording_file, 'wb') as wf:
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
    # Restarts recording if flag is set again
    while True:
        if recording:
            update_recording_file()
            start_recording()
        else:
            time.sleep(1/10)

if __name__ == "__main__":
    main()