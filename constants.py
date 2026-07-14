DEBUG = False
PORT = 5002
MAX_CSV_AGE = 1 * 60 * 60

# <Audio subsystem constants>
HUB_ADDRESS = "10.0.1.5"
HUB_PORT = PORT
SATELLITE_PORT = 5003

device_index = 0

sleep_time = 1 / 10
dtype = "int16"
MIC_DIAGNOSTIC_FREQUENCY = 60
MIC_DIAGNOSTIC_LENGTH = 10 * MIC_DIAGNOSTIC_FREQUENCY
NUM_CHANNELS = 6


file_name = "recording"
file_directory = "recordings/"

timeout = 5e9

device_name = "Satellite 0"
# </Audio subsystem constants>

fsr_url = "http://10.0.1.50/data"
imu_url = "http://127.0.0.1:8082/data"
audio_url = "http://127.0.0.1:5002/data"
