DEBUG = True
PORT = 8080
MAX_CSV_AGE = 1 * 60 * 60

# <Audio subsystem constants>
HUB_ADDRESS = "127.0.0.1"
HUB_PORT = 8080
SATELLITE_PORT = 5002

device_index = 2

sleep_time = 1 / 10
dtype = "int16"

file_name = "recording"
file_directory = "recordings/"

timeout = 5e9

device_name = "Satellite 0"
# </Audio subsystem constants>

fsr_url = "http://127.0.0.1:8081/data"
imu_url = "http://127.0.0.1:8082/data"
audio_url = "http://127.0.0.1:5002/data"
