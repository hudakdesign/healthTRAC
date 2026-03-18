from concurrent.futures import ThreadPoolExecutor
import time
import sounddevice as sd
from scipy.io.wavfile import write
# import wavio as wv

SAVE_PATH = "data/"
FREQ = 44100 # Sample frequency
DURATION = 5 # Duration in seconds

recordings = {}

def create_recording(duration):
    recording = sd.rec(int(duration * FREQ),
                   samplerate=FREQ,
                   channels=2)
    sd.wait()

    return recording

def save_recording(recording):
    write(f"{SAVE_PATH}{time.time()}.wav", FREQ, recording)

if __name__ == "__main__":
    # recording_index = 0
    # while True:
    #     curr_recording = create_recording(DURATION)
    #     write(f"{SAVE_PATH}{time.time()}.wav", FREQ, curr_recording)
    #     recording_index += 1

    # record_thread = threading.Thread(target=)

    # save_thread


    while True:
        try:
            recordings[time.time()] = create_recording(DURATION)
        except KeyboardInterrupt:
            print(recordings.keys())
            raise SystemExit

    # while True:
    #     try:
    #         executor.submit()