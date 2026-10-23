"""Script for simultaneously collecting data from FSR and force gauge"""

import csv
import glob
import json
import struct
import time

import serial


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
    num_dashes = 40

    print("FSR Calibration Utility")

    # set up the first matching device as a force gauge
    device_port = glob.glob("/dev/ttyUSB*")[0]
    gauge = ForceGauge(device_port)

    # set up the first matching device as an fsr
    device_port = glob.glob("/dev/ttyACM*")[0]
    fsr = ForceSensitiveResistor(device_port)

    # print out readings from each device to validate they are connected
    gauge_reading, gauge_units, gauge_response_time_ms = gauge.get_reading()
    print("-" * num_dashes)
    print("Force Gauge")
    print(f"Reading      : {gauge_reading} {gauge_units}")
    print(f"Response time: {gauge_response_time_ms:.3f} ms")
    print("-" * num_dashes)

    fsr_readings, fsr_response_time_ms = fsr.get_readings()
    print("-" * num_dashes)
    print("Force Sensitive Resistors")
    print(f"Readings     : {fsr_readings}")
    print(f"Response time: {fsr_response_time_ms:.3f} ms")
    print("-" * num_dashes)

    # TODO: Prompt user for which fsr to calibrate and how long
    # for now just select fsr0
    fsr_selection = 0
    calibration_time = 10  # seconds

    input("Set gauge to newtons and press enter to start calibration:")
    if gauge.get_reading()[1] != "N":
        raise Exception("Gauge not set to `N`")

    # tell user that calibration will start soon
    print("Calibration starting in 5 seconds!")
    time.sleep(5)

    # write force gauge and fsr readings to csv to allow calculation of curve
    with open(f"calibration_data_{time.time_ns()}.csv", "w") as f:
        # take the start time so we can limit how long calibration runs
        start_time = time.time()

        # write the header for the csv file
        writer = csv.writer(f)
        writer.writerow(["adc", "newtons"])

        while time.time() - start_time < calibration_time:
            # get the force gauge reading and fsr value
            newtons = gauge.get_reading()[0]
            adc = fsr.get_readings()[0][fsr_selection]

            # print them out
            print("-" * num_dashes)
            print("Sensor Readings")
            print(f"Gauge: {newtons:.3f}")
            print(f"FSR  : {adc}")
            

            # write it to the csv file
            writer.writerow([adc, newtons])

    print("Calibration complete!")

    # # Setup
    # available_devices = glob.glob("/dev/ttyUSB*")
    # if len(available_devices) == 0:
    #     raise Exception("Please Connect Force Gauge")

    # # ask which port the force gauge is using
    # print("Available Devices:")
    # for i, available_device in enumerate(available_devices):
    #     print(f"[{i}]: {available_device}")

    # print("Selecting device [0]")
    # force_gauge = ForceGauge(available_devices[0])
    # print(force_gauge.get_reading())

    # available_devices = glob.glob("/dev/ttyACM*")
    # if len(available_devices) == 0:
    #     raise Exception("Please Connect FSR")

    # print("Available Devices:")
    # for i, available_device in enumerate(available_devices):
    #     print(f"[{i}]: {available_device}")

    # print("Selecting device [0]")
    # fsr = ForceSensitiveResistor(available_devices[0])
    # print(fsr.get_readings())

    # # Calibration
    # # TODO: allow doing per-fsr calibration
    # # for now only uses fsr0
    # print("Prepare to calibrate in 5 seconds!")
    # time.sleep(5)
    # print("Calibration Started")
    # num_calibration_polls = 100
    # sleep_time = 10 / num_calibration_polls

    # with open("calibration_data.csv", "w") as f:
    #     data_writer = csv.writer(f)
    #     data_writer.writerow(["adc", "newtons"])
    #     for _ in range(num_calibration_polls):
    #         # get force gauge reading and check that units are right
    #         force_gauge_reading = force_gauge.get_reading()
    #         if force_gauge_reading[1] != "N":
    #             raise Exception("Please set gauge to `N`")
    #         newtons = force_gauge_reading[0]

    #         # get the adc reading from the fsr
    #         # select fsr0
    #         adc = fsr.get_readings()[0]
    #         print(adc)

    #         # log the readings to csv
    #         data_writer.writerow([adc, newtons])

    #         # wait for a moment
    #         time.sleep(sleep_time)
