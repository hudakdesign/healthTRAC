"""Script for simultaneously collecting data from FSR and force gauge"""

import csv
import glob
import json
import os
import struct
import subprocess
import time


import serial

# Constants
NUM_SEPARATOR_DASHES = 40
NUM_FSR_CHANNELS = 8
CALIBRATION_TIME = 30


class ForceGauge:
    """Class for encapsulating the force gauge"""

    def __init__(self, device_port):
        self.device = serial.Serial(device_port, baudrate=9600)

    def _get_reading_from_rx_bytes(self, rx_bytes: bytes) -> float:
        """Takes the force reading out of the received bytes"""

        READING_BYTES_START = 3  # idx 3 in response
        NUM_READING_BYTES = 4  # 4 byte reading (32-bit)
        READING_BYTES_END = READING_BYTES_START + NUM_READING_BYTES

        # take the slice of the bytes with the reading
        reading_bytes = rx_bytes[READING_BYTES_START:READING_BYTES_END]

        # decode the bytes into a float
        # * -1 because pushing down is read as negative
        return struct.unpack(">f", reading_bytes)[0] * -1

    def _get_unit_from_rx_bytes(self, rx_bytes: bytes) -> str:
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

    def get_reading(self) -> tuple[float, str, float]:
        """Gets the force reading from the gauge alongside its unit"""

        # message to get a reading from the gauge
        POLL_MESSAGE = b"\x01\x03\x00\x00\x00\x0d\x84\x0f"
        NUM_RESPONSE_BYTES = 31

        # ask the device for a reading
        poll_time_ns = time.time_ns()
        self.device.write(POLL_MESSAGE)

        # read the response from the gauge
        rx_bytes = self.device.read(NUM_RESPONSE_BYTES)
        response_time_ns = time.time_ns() - poll_time_ns
        response_time_ms = response_time_ns / 1e6

        # decode the received bytes into the reading and units
        reading = self._get_reading_from_rx_bytes(rx_bytes)
        unit = self._get_unit_from_rx_bytes(rx_bytes)

        return reading, unit, response_time_ms


class ForceSensitiveResistor:
    """Class for encapsulating force sensitive resistor subsystem"""

    def __init__(self, device_port):
        self.device = serial.Serial(device_port, baudrate=115200)

    def get_readings(self) -> list[int, float]:
        """Gets and returns a list of readings from the FSR over serial"""

        # # first throw out all of the past bytes to avoid issues
        # # then wait throw out up to the next newline to avoid corruption
        # self.device.read_all()
        # self.device.readline()

        # poll the fsr
        poll_time = time.time_ns()
        self.device.write(b"p")

        # read the response from the fsr
        rx_bytes = self.device.readline()
        response_time_ns = time.time_ns() - poll_time
        response_time_ms = response_time_ns / 1e6

        # load the bytes into a dict
        readings = json.loads(rx_bytes)
        return readings["data"], response_time_ms


if __name__ == "__main__":
    print("FSR Calibration Utility")

    # set working directory to where the script currently is
    file_directory = os.path.dirname(__file__)
    os.chdir(file_directory)

    # create the needed directory for calibration data
    subprocess.call(["mkdir", "-p", "data/calibration/"])

    # set up the first matching device as a force gauge
    device_port = glob.glob("/dev/ttyUSB*")[0]
    gauge = ForceGauge(device_port)

    # set up the first matching device as an fsr
    device_port = glob.glob("/dev/ttyACM*")[0]
    fsr = ForceSensitiveResistor(device_port)

    # print out readings from each device to validate they are connected
    gauge_reading, gauge_units, gauge_response_time_ms = gauge.get_reading()
    print("-" * NUM_SEPARATOR_DASHES)
    print("Force Gauge")
    print(f"Reading      : {gauge_reading} {gauge_units}")
    print(f"Response time: {gauge_response_time_ms:.3f} ms")
    print("-" * NUM_SEPARATOR_DASHES)

    fsr_readings, fsr_response_time_ms = fsr.get_readings()
    print("-" * NUM_SEPARATOR_DASHES)
    print("Force Sensitive Resistors")
    print(f"Readings     : {fsr_readings}")
    print(f"Response time: {fsr_response_time_ms:.3f} ms")
    print("-" * NUM_SEPARATOR_DASHES)

    # TODO: Prompt user for which fsr to calibrate and how long
    # for now just select fsr0
    valid_selection = False
    while not valid_selection:
        fsr_selection = input("Enter the FSR to calibrate: ")
        try:
            fsr_selection = int(fsr_selection)
        except ValueError:
            continue

        if fsr_selection in range(NUM_FSR_CHANNELS):
            valid_selection = True
        else:
            print("Please enter the integer on the FSR to calibrate")

    input("Set gauge to newtons and press enter to start calibration:")
    if gauge.get_reading()[1] != "N":
        raise Exception("Gauge not set to `N`")

    # tell user that calibration will start soon
    print("Calibration starting in 5 seconds!")
    time.sleep(5)

    # write force gauge and fsr readings to csv to allow calculation of curve
    with open(f"data/calibration/fsr{fsr_selection}_{time.time_ns()}.csv", "w") as f:
        # take the start time so we can limit how long calibration runs
        start_time = time.time()

        # write the header for the csv file
        writer = csv.writer(f)
        writer.writerow(["adc", "newtons"])

        while time.time() - start_time < CALIBRATION_TIME:
            # get the force gauge reading and fsr value
            gauge_reading = gauge.get_reading()
            # raise an exception if the user changes the units while measuring
            if gauge_reading[1] != "N":
                raise Exception("Gauge not set to `N`")
            newtons = gauge_reading[0]
            adc = fsr.get_readings()[0][fsr_selection]

            # print them out
            print("-" * NUM_SEPARATOR_DASHES)
            print("Sensor Readings")
            print(f"Gauge: {newtons:.3f}")
            print(f"FSR  : {adc}")

            # write it to the csv file
            writer.writerow([adc, newtons])

    print("Calibration complete!")