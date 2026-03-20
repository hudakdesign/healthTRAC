import numpy as np
import sounddevice as sd
import subprocess
import sys
import threading
import time
import wave
import requests
import constants as c

# Defaults
file_path = f"{c.file_directory}{c.file_name}"

# Sets sample rate to default of default device
sample_rate = sd.query_devices(0)["default_samplerate"]

audio_frames = []
recording = False
hub_timestamp = 0

running = True


def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    audio_frames.append(indata.copy())


def create_recording():
    # Log start time
    start_time = time.time_ns()

    # Start recording stream
    with sd.InputStream(
        samplerate=sample_rate, channels=c.channels, dtype=c.dtype, callback=callback
    ):
        global recording
        while recording:
            sd.sleep(100)

    audio_data = np.concatenate(audio_frames)

    # Writes data to file timestamped with the start time
    with wave.open(f"{file_path}_{start_time}.wav", "wb") as wav_file:
        wav_file.setnchannels(c.channels)
        wav_file.setsampwidth(np.dtype(c.dtype).itemsize)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())


# Recording control thread
def recording_control():
    global recording

    # Function for checking with hub if it should be recording
    # takes in hub address
    def query_recording_status(address):
        url = f"http://{address}:5000/"
        response = requests.get(url)

        if response.status_code == 200:
            return response.json()
        else:
            return None

    # stores most recent hub status just in case connection is lost
    most_recent_recording_status = {"time_ns": 0, "recording": False}

    while running:
        # current timestamp on the satellite
        satellite_timestamp = time.time_ns()
        # status message for debugging
        status_message = "Recording Control Dashboard\n"

        # Attempt to call the API,
        # Otherwise: we have the most recent timestamp

        try:
            # if recording is true and
            # the satellite timestamp is withing the hub timestamp + timeout
            # then: recording is true
            most_recent_recording_status = query_recording_status(c.HUB_ADDRESS)

            status_message += "API: connected\n"
        except:
            status_message += "API: DISCONNECTED\n"

        if most_recent_recording_status["recording"] == False:
            recording = False
        elif satellite_timestamp > most_recent_recording_status["time_ns"] + c.timeout:
            recording = False
        else:
            recording = True

        if recording:
            status_message += "Recording: recording\n"
        else:
            status_message += "Recording: NOT RECORDING\n"

        status_message += "[Enter] to terminate\n"
        status_message += "\n---DEBUG INFO---\n"

        status_message += f"Satellite Timestamp: {satellite_timestamp}\n"
        status_message += (
            f"Hub Timestamp      : {most_recent_recording_status['time_ns']}\n"
        )
        status_message += f"Timeout            : {(satellite_timestamp - most_recent_recording_status['time_ns'])/1e9:.2f}/{c.timeout/1e9:.2f}s"

        subprocess.run(["clear"])
        print(status_message)
        # waits sleep_time seconds to avoid busy waiting
        time.sleep(c.sleep_time)


# Thread for terminating the program
# tells recording to stop when enter is pressed
# then sets running to false to end all loops
def terminate_threads():
    global recording
    global running

    input()
    recording = False
    running = False


if __name__ == "__main__":
    # create recordings directory if it doesnt exist
    subprocess.run(["mkdir", "-p", c.file_directory])

    recording_control_thread = threading.Thread(target=recording_control)
    recording_control_thread.start()

    termination_thread = threading.Thread(target=terminate_threads)
    termination_thread.start()

    while running:
        # If recording is toggled on, retoggle it
        if recording:
            create_recording()
        # Otherwise, sleep for a sleep_time
        time.sleep(c.sleep_time)
