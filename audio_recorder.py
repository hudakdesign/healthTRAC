import sounddevice as sd
from scipy.io.wavfile import write
import wavio as wv

# Defaults
channels = 2
duration = 5
dtype = 'int16'
freq = 44100
file_name = "recording.wav"
file_directory = "data/"
file_path = f"{file_directory}{file_name}"


audio_frames = []
recording = True





if __name__ == "__main__":
    # sample recording
    recording = sd.rec(int(duration * freq),
                       samplerate=freq, channels=2)

    sd.wait()

    wv.write(file_path, recording, freq, sampwidth=2)

