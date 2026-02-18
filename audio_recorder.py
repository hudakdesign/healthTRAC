import sounddevice as sd
from scipy.io.wavfile import write
import wavio as wv
import sys

# Defaults
channels = 2
duration = 5
dtype = 'int16'
sample_rate = 44100
file_name = "recording.wav"
file_directory = "data/"
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

if __name__ == "__main__":
    # sample recording
    recording = sd.rec(int(duration * freq),
                       samplerate=freq, channels=2)

    sd.wait()

    wv.write(file_path, recording, freq, sampwidth=2)

