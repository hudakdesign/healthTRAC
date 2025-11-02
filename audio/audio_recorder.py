import pyaudio
import wave
import numpy as np
import requests
import time
import threading
import webrtcvad  # Import VAD library
from pathlib import Path
from datetime import datetime


class AudioRecorder:
    def __init__(self, device_id, hub_url, storage_path="./audio_data"):
        self.CHUNK = 512  # 32ms at 16kHz, valid for VAD
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000  # 16kHz, valid for VAD
        self.device_id = device_id
        self.hub_url = hub_url
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.recording_thread = None
        self.wav_file = None

        # Initialize VAD with aggressiveness level 3 (most aggressive)
        self.vad = webrtcvad.Vad(3)

    def check_recording_state(self):
        try:
            response = requests.get(f"{self.hub_url}/api/recording_state", timeout=1)
            if response.status_code == 200:
                return response.json().get("is_recording", False)
        except requests.RequestException:
            # If hub is down, default to not recording
            return False
        return False

    def calculate_audio_features(self, audio_data):
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_np.astype(float) ** 2))

        # Calculate VAD - returns True if speech is detected
        try:
            is_speech = self.vad.is_speech(audio_data, self.RATE)
        except:
            # is_speech can fail if frame is not the right size
            is_speech = False

        return {
            "rms": rms,
            "vad": 1 if is_speech else 0  # Send as 1 or 0
        }

    def send_features(self, features):
        payload = {
            "device_id": self.device_id,
            "timestamp": datetime.now().isoformat(),
            "features": features
        }
        try:
            requests.post(f"{self.hub_url}/api/audio_features", json=payload, timeout=0.5)
        except requests.RequestException:
            pass  # Ignore if hub is not available

    def record_audio(self):
        self.stream = self.audio.open(format=self.FORMAT,
                                      channels=self.CHANNELS,
                                      rate=self.RATE,
                                      input=True,
                                      frames_per_buffer=self.CHUNK)
        print(f"[{self.device_id}] Recording stream opened.")

        while self.is_recording:
            try:
                data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                self.frames.append(data)

                features = self.calculate_audio_features(data)
                self.send_features(features)

            except IOError as e:
                print(f"[{self.device_id}] IO Error: {e}")
                break

        self.stream.stop_stream()
        self.stream.close()
        self.stream = None
        print(f"[{self.device_id}] Recording stream closed.")

    def start_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.recording_thread = threading.Thread(target=self.record_audio)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            print(f"[{self.device_id}] Recording started.")

    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            if self.recording_thread:
                self.recording_thread.join(timeout=2)

            if self.frames:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = self.storage_path / f"{self.device_id}_{timestamp}.wav"

                wf = wave.open(str(filename), 'wb')
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
                wf.setframerate(self.RATE)
                wf.writeframes(b''.join(self.frames))
                wf.close()
                print(f"[{self.device_id}] Saved audio to {filename}")
                self.frames = []

            print(f"[{self.device_id}] Recording stopped.")

    def run(self):
        """Main loop - monitor recording state from hub"""
        print(f"[{self.device_id}] Audio recorder started")
        print(f"Hub URL: {self.hub_url}")
        print(f"Storage path: {self.storage_path}")

        try:
            while True:
                should_record = self.check_recording_state()

                if should_record and not self.is_recording:
                    self.start_recording()
                elif not should_record and self.is_recording:
                    self.stop_recording()

                time.sleep(1)  # Check state every second

        except KeyboardInterrupt:
            print(f"\n[{self.device_id}] Shutting down...")
            self.stop_recording()
            self.audio.terminate()


if __name__ == "__main__":
    DEVICE_ID = "mac_mic_01"
    HUB_URL = "http://localhost:8080"
    STORAGE_PATH = "./audio_data"

    recorder = AudioRecorder(DEVICE_ID, HUB_URL, STORAGE_PATH)
    recorder.run()
