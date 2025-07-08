#!/usr/bin/env python3
"""
Microphone Client
Captures audio features (RMS, ZCR) and sends to hub via TCP
Currently simulates data - replace with actual audio capture
"""

import time
import threading
import random
import math
from sensor_client import SensorClient


# Uncomment these when implementing real audio
# import pyaudio
# import numpy as np


class MicrophoneClient(SensorClient):
    """Microphone sensor client for voice analysis"""

    def __init__(self, hub_host='localhost', hub_port=5555,
                 sample_rate=48000, chunk_size=4800):
        super().__init__('MICROPHONE', hub_host, hub_port)

        # Audio configuration
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size  # 100ms chunks at 48kHz
        self.channels = 2  # Stereo (left and right)

        # Processing thread
        self.audio_thread = None
        self.processing = False

        # For real implementation
        # self.audio = None
        # self.stream = None

    def calculate_rms(self, audio_data):
        """Calculate RMS (Root Mean Square) of audio signal"""
        # For real implementation:
        # return np.sqrt(np.mean(audio_data**2))

        # Simulated data
        base_level = 0.01
        if random.random() < 0.1:  # 10% chance of "voice activity"
            return base_level + random.uniform(0.1, 0.3)
        return base_level + random.uniform(0, 0.02)

    def calculate_zcr(self, audio_data):
        """Calculate Zero Crossing Rate of audio signal"""
        # For real implementation:
        # signs = np.sign(audio_data)
        # diff = np.diff(signs)
        # zcr = len(np.where(diff)[0]) / len(audio_data)
        # return zcr

        # Simulated data
        return random.uniform(0.1, 0.3)

    def _audio_processing_loop(self):
        """Main audio processing loop"""
        self.logger.info("Starting audio processing (simulated)...")

        # For real implementation:
        # self.audio = pyaudio.PyAudio()
        # self.stream = self.audio.open(
        #     format=pyaudio.paFloat32,
        #     channels=self.channels,
        #     rate=self.sample_rate,
        #     input=True,
        #     frames_per_buffer=self.chunk_size
        # )

        while self.processing:
            try:
                # For real implementation:
                # # Read audio chunk
                # audio_chunk = self.stream.read(self.chunk_size, exception_on_overflow=False)
                # audio_data = np.frombuffer(audio_chunk, dtype=np.float32)
                #
                # # Separate channels
                # left_channel = audio_data[0::2]
                # right_channel = audio_data[1::2]
                #
                # # Calculate features
                # rms_left = self.calculate_rms(left_channel)
                # rms_right = self.calculate_rms(right_channel)

                # Simulated processing
                time.sleep(0.1)  # Simulate 100ms chunks

                # Calculate simulated features
                rms_left = self.calculate_rms(None)
                rms_right = self.calculate_rms(None)

                # Send to hub
                self.send_data({
                    'rms_left': round(rms_left, 4),
                    'rms_right': round(rms_right, 4)
                })

            except Exception as e:
                self.logger.error(f"Audio processing error: {e}")
                time.sleep(1)

    def start_sensor(self):
        """Start microphone data collection"""
        self.processing = True
        self.audio_thread = threading.Thread(target=self._audio_processing_loop)
        self.audio_thread.daemon = True
        self.audio_thread.start()

        self.logger.info("Microphone client started (simulated mode)")

    def stop_sensor(self):
        """Stop microphone data collection"""
        self.processing = False

        if self.audio_thread:
            self.audio_thread.join(timeout=2.0)

        # For real implementation:
        # if self.stream:
        #     self.stream.stop_stream()
        #     self.stream.close()
        # if self.audio:
        #     self.audio.terminate()

        self.logger.info("Microphone client stopped")


def main():
    """Main entry point for standalone microphone client"""
    import argparse

    parser = argparse.ArgumentParser(description='Microphone Client')
    parser.add_argument('--hub-host', default='localhost',
                        help='Hub server hostname/IP (default: localhost)')
    parser.add_argument('--hub-port', type=int, default=5555,
                        help='Hub server port (default: 5555)')
    parser.add_argument('--sample-rate', type=int, default=48000,
                        help='Audio sample rate (default: 48000)')
    parser.add_argument('--chunk-size', type=int, default=4800,
                        help='Audio chunk size (default: 4800)')

    args = parser.parse_args()

    print("=" * 60)
    print("Microphone Client (Simulation Mode)")
    print("=" * 60)
    print("NOTE: This is currently simulating microphone data.")
    print("To implement real audio capture:")
    print("1. Install pyaudio: pip install pyaudio numpy")
    print("2. Uncomment the audio code in microphone_client.py")
    print("3. Connect USB microphones")
    print("=" * 60)

    # Create and run microphone client
    client = MicrophoneClient(
        hub_host=args.hub_host,
        hub_port=args.hub_port,
        sample_rate=args.sample_rate,
        chunk_size=args.chunk_size
    )

    client.run_forever()


if __name__ == "__main__":
    main()