# TODO: Integrate with the rest of the system

# Imports
import json
import threading
import time
import queue
import sys
import subprocess


from flask import Flask
import sounddevice as sd
import soundfile as sf
import numpy
import requests

assert numpy


# Constants
DEVICE_ID = 1
NUM_CHANNELS = sd.query_devices(DEVICE_ID)["max_input_channels"]
MICROPHONE_FREQUENCY = sd.query_devices(DEVICE_ID)["default_samplerate"]

FILENAME = "test_recording.wav"
HUB_API_URL = "http://127.0.0.1:8050/"
DIAGNOSTIC_API_PORT = 8051
SLEEP_TIME = 1
TIMEOUT_TIME_SECONDS = (
    4  # including sleep time, this means theres at most a 5 second delay before pausing
)
RECORDING_DIRECTORY = "recordings/"
CHUNK_TIME_MINUTES = 1
CHUNK_TIME_NS = (
    CHUNK_TIME_MINUTES * 60 * 1e9
)  # minutes * 60 (sec in minute) * 1e9 (ns in sec)
# frequency is 16000hz, 1500 frames per chunk. taking a sample every 250 frames will yield a 64hz polling rate
DIAGNOSTIC_SAMPLE_RATE = 250  # takes a sample every 250 frames
FRAME_TIME_NS = int((1.0 / MICROPHONE_FREQUENCY) * 1e9)


# Globals
app = Flask(__name__)

audio_block_queue = (
    queue.Queue()
)  # used to queue up audio chunks from callback for writing
diagnostic_frame_queue = (
    queue.Queue()
)  # used to queue up audio diagnostics data to share with the hub

last_poll_time = 0  # used for poll timing
last_poll_time_lock = threading.Lock()
running = True  # controls if the whole system is running
running_lock = threading.Lock()
recording = True  # controls if the data recorder is recording
recording_lock = threading.Lock()


# Tasks:
# record audio data
def audio_data_recorder():
    # callback function used to process every block of audio data
    # this is from a separate thread
    # DONE: queue heavily downsampled data from each block
    def callback(indata, frames, t_, status):
        if status:
            print(status, file=sys.stderr)
        audio_block_queue.put(indata.copy())

        curr_time = time.time_ns()

        # if a block is 1500 frames, and the sample rate is 16000hz,
        # then when we get a block the start time is roughly (1500 / 16000) seconds before the current time
        # this isnt perfectly accurate, but it should be good enough for diagnostics
        # a frame represents audio from ((1 / MICROPHONE_FREQUENCY) * 1e9) nanoseconds
        # the block should start at curr_time - frame_time_ns * frames (the number of frames)

        block_start_time = time.time_ns() - FRAME_TIME_NS * frames
        # print("-" * 80)
        # print(f"Callback called again after {(curr_time - get_last_poll_time()) / 1e6} milliseconds")
        # print(f"Number of frames {frames}")

        # DONE: collect diagnostic data at 64hz
        # loop through indata with a step of `DIAGNOSTIC_SAMPLE_RATE`
        # print("Frames in block")
        for i in range(0, len(indata), DIAGNOSTIC_SAMPLE_RATE):
            new_diagnostic_frame = {}
            new_diagnostic_frame["timestamp"] = block_start_time + (
                i * FRAME_TIME_NS
            )  # calculates time at frame recording
            new_diagnostic_frame["sensors"] = indata[i].copy()
            diagnostic_frame_queue.put(new_diagnostic_frame)  # queue up the frame

        #     print(f"Index {i}: {new_diagnostic_frame}")
        # print("-" * 80)

    # DONE: query device for sample rate and channel count
    device_info = sd.query_devices(DEVICE_ID)
    sample_rate = int(device_info["default_samplerate"])
    channels = device_info["max_input_channels"]

    # DONE: record data to wav file
    # DONE: update to change filename for each chunk
    while get_running():
        if get_recording():
            # each time recording is restarted update the filename
            file_path = f"{RECORDING_DIRECTORY}recording_{time.time_ns()}.wav"
            next_chunk_time = time.time_ns() + CHUNK_TIME_NS

            with sf.SoundFile(
                file_path, mode="x", samplerate=sample_rate, channels=channels
            ) as file:
                with sd.InputStream(
                    samplerate=sample_rate,
                    device=DEVICE_ID,
                    channels=channels,
                    callback=callback,
                ):
                    print("New recording started")

                    while (
                        get_recording()
                        and get_running()
                        and (time.time_ns() < next_chunk_time)
                    ):
                        # DONE: restart the recording after a set amount of time passes to help avoid corruption
                        file.write(audio_block_queue.get())
        else:
            time.sleep(SLEEP_TIME)

    # DONE: stop and resume recording based on global recording flag
    print("audio_data_recorder(): Shutting down")


# check recording flag
def recording_flag_checker():
    global recording
    # DONE: poll hub to check if recording should be happening
    # DONE: use a request timeout to pause recording if hub is down
    # DONE (implemented mutex to be safe): determine if lock is necessary for running and recording
    while get_running():
        try:  # try to request the hub api
            response = requests.get(HUB_API_URL, timeout=TIMEOUT_TIME_SECONDS)

            if response.json() == "True":
                set_recording(True)
            else:
                set_recording(False)
        except:
            set_recording(False)
            print("recording_flag_checker(): Exception when requesting hub")

        time.sleep(SLEEP_TIME)
    print("recording_flag_checker(): Shutting down")


# diagnostics api (main)
def diagnostics_api_server():
    # DONE: host flask app making diagnostics data accessible at route
    # consume items from the queue
    @app.route("/")
    def diagnostics_api():
        # DONE: fill dictionary with diagnostics data from queue until queue is empty
        # DONE: once the dictionary is ready, call json.dumps() and return it
        response_dict = {
            "timestamps": [],
            "sensors": [[] for _ in range(NUM_CHANNELS)],
        }  # temporarily stores response while it is being built

        # while the queue isnt empty,
        # get frames from it and add them to the response json
        while not diagnostic_frame_queue.empty():
            diagnostic_frame = diagnostic_frame_queue.get()
            response_dict["timestamps"].append(diagnostic_frame["timestamp"])

            # populate the sensors part of things
            for channel_index in range(NUM_CHANNELS):
                response_dict["sensors"][channel_index].append(
                    float(diagnostic_frame["sensors"][channel_index])
                )

        # once the queue is emptied,
        # turn it into json string and send it off
        return json.dumps(response_dict)

    app.run(host="0.0.0.0", port=DIAGNOSTIC_API_PORT, debug=False)

    print("diagnostics_api_server(): Shutting down")


def queue_tester():
    while running:
        diagnostic_frame = diagnostic_frame_queue.get(timeout=1)
        print(f"queue_tester(): {diagnostic_frame}")

    print("queue_tester(): Shutting down")


# Utility functions:
# gets recording in a thread-safe manner
def get_recording():
    with recording_lock:
        return recording


# sets recording in a thread-safe manner
def set_recording(recording_state: bool):
    global recording

    with recording_lock:
        recording = recording_state


# gets running in a thread-safe manner
def get_running():
    with running_lock:
        return running


# sets running in a thread-safe manner
def set_running(running_state: bool):
    global running

    with running_lock:
        running = running_state


if __name__ == "__main__":
    # DONE: make sure that the recording directory is set up
    subprocess.call(["mkdir", "-p", RECORDING_DIRECTORY])

    recording_flag_checker_thread = threading.Thread(target=recording_flag_checker)
    audio_data_recorder_thread = threading.Thread(target=audio_data_recorder)
    # queue_tester_thread = threading.Thread(target=queue_tester)

    recording_flag_checker_thread.start()
    time.sleep(1)
    audio_data_recorder_thread.start()
    # queue_tester_thread.start()

    diagnostics_api_server()

    # when the api server is closed
    # shut down all the threads
    print("main(): Shutting everything down")
    set_running(False)
