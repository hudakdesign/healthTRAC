"""Script for simultaneously collecting data from FSR and force gauge"""

import csv
import glob
import struct

import serial


class ForceGauge:
    """Class for encapsulating the force gauge"""

    def __init__(self, device_port):
        device = serial.Serial(device_port)

    def _get_reading_from_rx_bytes(rx_bytes: bytes) -> float:
        """Takes the force reading out of the received bytes"""

        READING_BYTES_START = 3  # idx 3 in response
        NUM_READING_BYTES = 4  # 4 byte reading (32-bit)
        READING_BYTES_END = READING_BYTES_START + NUM_READING_BYTES

        # take the slice of the bytes with the reading
        reading_bytes = rx_bytes[READING_BYTES_START:READING_BYTES_END]

        # decode the bytes into a float
        return struct.unpack(">f", reading_bytes)

    def _get_unit_from_rx_bytes(rx_bytes: bytes) -> str:
        """Takes the force unit out of the received bytes"""

        # bytes associated with each unit
        NEWTON_BYTES = b"\x43\xfa\x00\x00"
        KILOGRAM_FORCE_BYTES = b"\x42\x4c\x14\xe6"
        POUND_FORCE_BYTES = b"\x42\xe0\xcf\x5e"

        UNIT_BYTES_START = 7  # idx 3 in response
        NUM_UNIT_BYTES = 4
        UNIT_BYTES_END = UNIT_BYTES_START + NUM_UNIT_BYTES

        # take the slice of the bytes with the unit
        unit_bytes = rx_bytes[UNIT_BYTES_START:UNIT_BYTES_END]

        if unit_bytes == NEWTON_BYTES:
            return "N"
        elif unit_bytes == KILOGRAM_FORCE_BYTES:
            return "kgf"
        elif unit_bytes == POUND_FORCE_BYTES:
            return "lbf"
        else:
            raise ValueError

    def get_reading(self) -> tuple[float, str]:
        """Gets the force reading from the gauge alongside its unit"""

        # message to get a reading from the gauge
        POLL_MESSAGE = b"\x01\x03\x00\x00\x00\x0d\x84\x0f"

        # throw out the current bytes to avoid corruption
        self.device.read_all()

        # ask the device for a reading
        self.device.write(POLL_MESSAGE)

        # read the reading that it sent back
        rx_bytes = self.device.read_all()

        # decode the received bytes into the reading and units
        reading = self._get_reading_from_rx_bytes(rx_bytes)
        unit = self._get_unit_from_rx_bytes(rx_bytes)

        return reading, unit


if __name__ == "__main__":
    available_devices = glob.glob("/dev/ttyACM*")

    # ask which port the force gauge is using
    print("Available Devices:")
    for i, available_device in enumerate(available_devices):
        print(f"[{i}]: {available_device}")

    print("Selecting device [0]")

    gauge = ForceGauge(available_devices[0])
