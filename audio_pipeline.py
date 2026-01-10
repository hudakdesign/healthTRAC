import sounddevice as sd
import numpy as np
import wave
import threading
import sys
import os

# Parameters
sample_rate = 44100  # 44.1 kHz
channels = 1  # 1 = Mono, 2 = Stereo
file_name = "recording.wav"
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
        recording_check = os.popen("cat recording").read()
        if recording_check == "True":
            recording = True
        else:
            recording = False
            break

# Start is_recording thread
stop_thread = threading.Thread(target=is_recording)
stop_thread.start()

# Start recording stream
with sd.InputStream(samplerate=sample_rate, 
                    channels=channels, 
                    dtype=dtype, 
                    callback=callback):
    while recording:
        sd.sleep(100)

# Combine and save to file
audio_data = np.concatenate(recorded_frames)

with wave.open(file_name, 'wb') as wf:
    wf.setnchannels(channels)
    wf.setsampwidth(np.dtype(dtype).itemsize)
    wf.setframerate(sample_rate)
    wf.writeframes(audio_data.tobytes())