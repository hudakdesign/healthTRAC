import numpy as np
import sounddevice as sd
import subprocess
import sys
import threading
import wave

# Defaults
channels = 2
duration = 5
dtype = 'int16'
sample_rate = 44100
file_name = "recording.wav"
file_directory = "recordings/"
file_path = f"{file_directory}{file_name}"


audio_frames = []
recording = True


def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    audio_frames.append(indata.copy())

def start_recording():
    # Start recording stream
    with sd.InputStream(samplerate=sample_rate,
                        channels=channels,
                        dtype=dtype,
                        callback=callback):
        global recording
        while recording:
            sd.sleep(100)
        
    audio_data = np.concatenate(audio_frames)

    with wave.open(file_path, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(np.dtype(dtype).itemsize)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

if __name__ == "__main__":
    def tui_toggle_recording():
        global recording

        while True:
            subprocess.run('clear')
            input(f"Recording running {recording}\nToggle with [Enter]")
            recording = not recording
    
    toggle_recording_thread = threading.Thread(target=tui_toggle_recording)
    toggle_recording_thread.start()

    start_recording()