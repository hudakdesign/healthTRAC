from flask import Flask, render_template
import threading
import queue
import requests
import time
import sqlite3
import subprocess
import collections
import json

# Constants
FSR_URL = "http://10.0.1.27/"
NUM_FSRS = 8
TIME_BETWEEN_POLLS = 0.5  # seconds
DATABASE_FILENAME = "data/test.db"
AGGREGATE_CHUNK_LEN = 50
MAX_QUEUE_LEN = (
    100 * 120
)  # do normal calculations and adjust for using aggregate values

# Globals
running = True
fsr_data_queue = queue.Queue(maxsize=MAX_QUEUE_LEN)

# rolling buffer for storing recent values
fsr_data_buffer = collections.deque(
    maxlen=MAX_QUEUE_LEN // AGGREGATE_CHUNK_LEN
)  # DONE: change this to a better value
fsr_data_buffer_lock = threading.Lock()

app = Flask(__name__)

# Architecture:
# Threads:
# producer:
#   makes requests to fsr-subsystem at a fixed rate. parses responses and puts them into a queue
#
# consumer:
#   1. takes data out of the queue, saves it to the db
#   2. next load data into a pandas df
#   3. extract aggregate data from this df (averages for every half second maybe...)
#   4. push aggregate data to rolling buffer
#
# webserver:
#   1. serves dashboard with charts displaying aggregate data from rolling buffers
#   2. serves different debug data pertaining to other subsystems


# producer:
#   makes requests to fsr-subsystem at a fixed rate. parses responses and puts them into a queue
# DONE
def get_fsr_data():
    def queue_individual_polls(data_polls):
        for i in range(len(data_polls["timestamps"])):
            # stores each new data poll to be put in the queue
            new_data_poll = {}

            # set the timestamp
            new_data_poll["timestamp"] = data_polls["timestamps"][i]

            # set the sensor values
            new_data_poll["sensors"] = []
            for j in range(len(data_polls["sensors"])):
                new_data_poll["sensors"].append(data_polls["sensors"][j][i])

            # put the data poll into the queue
            fsr_data_queue.put(new_data_poll)

    while running:
        # make request and get response from FSR_URL
        try:
            r = requests.get(FSR_URL, timeout=1)

            # turn json from request into dict
            data = r.json()
            
            queue_individual_polls(data)
        except:
            print(f"Problem when requesting {FSR_URL}. Trying again")

        # waits until its time to poll again
        time.sleep(TIME_BETWEEN_POLLS)
        
    print("get_fsr_data(): shut down")


# consumer:
#   1. takes data out of the queue, saves it to the db DONE
#   2. DONE: next save it to a temporary buffer which fills up and
#            which when full is used to get an aggregate value
#   3. DONE: send the aggregate value of that chunk to the rolling buffer
def process_fsr_data():
    def add_fsr_data(conn, fsr_data):
        sql = """INSERT INTO fsr_one(timestamp, sensor0, sensor1, sensor2, sensor3, sensor4, sensor5, sensor6, sensor7)
                 VALUES(?,?,?,?,?,?,?,?,?)"""

        cur = conn.cursor()

        cur.execute(sql, fsr_data)

        conn.commit()

    # for now just get the data from the queue and print it as is
    with sqlite3.connect(DATABASE_FILENAME) as conn:
        incoming_datapoints = []

        while running:
            # if something goes wrong (i.e. queue didnt get anything new) then loop again and check if its running
            try:
                new_data_poll = fsr_data_queue.get(timeout=1)

                # prepare for writing to db
                fsr_data = []

                # start with timestamp
                fsr_data.append(new_data_poll["timestamp"])

                # then add sensors
                fsr_data.extend(new_data_poll["sensors"])

                # convert to tuple for db
                fsr_data = tuple(fsr_data)

                # add to db
                add_fsr_data(conn, fsr_data)

                # convert to timestamp, sensor0, sensor1,... format for pandas
                pd_formatted_datapoll = {}
                pd_formatted_datapoll["timestamp"] = new_data_poll["timestamp"]
                pd_formatted_datapoll["sensor0"] = new_data_poll["sensors"][0]
                pd_formatted_datapoll["sensor1"] = new_data_poll["sensors"][1]
                pd_formatted_datapoll["sensor2"] = new_data_poll["sensors"][2]
                pd_formatted_datapoll["sensor3"] = new_data_poll["sensors"][3]
                pd_formatted_datapoll["sensor4"] = new_data_poll["sensors"][4]
                pd_formatted_datapoll["sensor5"] = new_data_poll["sensors"][5]
                pd_formatted_datapoll["sensor6"] = new_data_poll["sensors"][6]
                pd_formatted_datapoll["sensor7"] = new_data_poll["sensors"][7]

                # append instance of pd_formatted_datapoll to incoming_datapoints
                incoming_datapoints.append(pd_formatted_datapoll)

                # get the aggregate data for the chunk if the chunk is full
                if len(incoming_datapoints) >= AGGREGATE_CHUNK_LEN:
                    aggregate_datapoint = get_aggregate_datapoint(incoming_datapoints)
                    incoming_datapoints.clear()
                    # push to rolling buffer
                    with fsr_data_buffer_lock:
                        fsr_data_buffer.append(aggregate_datapoint)
                        # fsr_data_buffer.append(pd_formatted_datapoll)
            except:
                continue
        print("process_fsr_data(): shut down")


# TODO: webserver:
def serve_flask_app():
    app.run(host="0.0.0.0", port=8050, debug=False)


# utility task
# periodically display buffer contents
def periodically_display_buffer_contents():
    while running:
        # lock the buffer
        with fsr_data_buffer_lock:
            # print out the last (most recent) value
            # if there is data in the buffer
            if len(fsr_data_buffer) > 0:
                print(fsr_data_buffer[-1])

        # wait to avoid flooding the terminal
        time.sleep(1)


# gets a datapoint which represents the aggregate of a chunk of data
# for now just returns the last value from the chunk (very basic downsampling)
# TODO: implement better aggregate function
def get_aggregate_datapoint(incoming_datapoints):
    return incoming_datapoints[-1]


def create_database():
    # create data directory
    subprocess.call(["mkdir", "-p", "data"])

    create_table = """CREATE TABLE IF NOT EXISTS fsr_one (
                            poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp INTEGER,
                            sensor0 INTEGER,
                            sensor1 INTEGER,
                            sensor2 INTEGER,
                            sensor3 INTEGER,
                            sensor4 INTEGER,
                            sensor5 INTEGER,
                            sensor6 INTEGER,
                            sensor7 INTEGER
                            );"""

    with sqlite3.connect(DATABASE_FILENAME) as conn:
        cursor = conn.cursor()
        cursor.execute(create_table)


# Routes:
# dashboard (index)
@app.route("/")
def index():
    return render_template("fsr_dashboard.html")


@app.route("/api/fsr")
def fsr_api():
    new_json_dict = {"timestamps": [], "sensors": [[] for _ in range(NUM_FSRS)]}

    # lock buffer while creating the json
    with fsr_data_buffer_lock:
        for i in range(len(fsr_data_buffer)):
            new_json_dict["timestamps"].append(fsr_data_buffer[i]["timestamp"])
            new_json_dict["sensors"][0].append(fsr_data_buffer[i]["sensor0"])
            new_json_dict["sensors"][1].append(fsr_data_buffer[i]["sensor1"])
            new_json_dict["sensors"][2].append(fsr_data_buffer[i]["sensor2"])
            new_json_dict["sensors"][3].append(fsr_data_buffer[i]["sensor3"])
            new_json_dict["sensors"][4].append(fsr_data_buffer[i]["sensor4"])
            new_json_dict["sensors"][5].append(fsr_data_buffer[i]["sensor5"])
            new_json_dict["sensors"][6].append(fsr_data_buffer[i]["sensor6"])
            new_json_dict["sensors"][7].append(fsr_data_buffer[i]["sensor7"])

    new_json = json.dumps(new_json_dict)
    return new_json


def main():
    global running

    print("---Starting FSR Mini Dashboard---")

    # create db (if it doesnt exist)
    create_database()

    # create threads
    get_fsr_data_thread = threading.Thread(target=get_fsr_data)
    process_fsr_data_thread = threading.Thread(target=process_fsr_data)
    display_contents_thread = threading.Thread(
        target=periodically_display_buffer_contents
    )

    # start threads
    get_fsr_data_thread.start()
    process_fsr_data_thread.start()
    # display_contents_thread.start()

    # stop when the server is closed
    serve_flask_app()
    print("main(): shut down")
    running = False


if __name__ == "__main__":
    main()
