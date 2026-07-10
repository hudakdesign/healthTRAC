from flask import Flask, render_template
import threading
import queue
import requests
import time
import sqlite3
import subprocess
import collections
import pandas

# Constants
MAX_QUEUE_LEN = 5000
FSR_URL = "http://10.0.1.27/"
TIME_BETWEEN_POLLS = 0.5  # seconds
DATABASE_FILENAME = "data/test.db"

# Globals
running = True
fsr_data_queue = queue.Queue(maxsize=MAX_QUEUE_LEN)

# rolling buffer for storing recent values
fsr_data_buffer = collections.deque(maxlen=MAX_QUEUE_LEN) # TODO: change this to a better value
fsr_data_buffer_lock = threading.Lock()

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
        r = requests.get(FSR_URL)

        # turn json from request into dict
        data = r.json()

        # timer = time.time()
        # turn this data into individual polls and put into queue
        queue_individual_polls(data)
        # print how much time queueing these took
        # print(f"Time to queue: {time.time() - timer}")

        # waits until its time to poll again
        time.sleep(TIME_BETWEEN_POLLS)


# consumer:
#   1. takes data out of the queue, saves it to the db DONE
#   2. next push the data to a rolling buffer DONE
def process_fsr_data():
    def add_fsr_data(conn, fsr_data):
        sql = '''INSERT INTO fsr_one(timestamp, sensor0, sensor1, sensor2, sensor3, sensor4, sensor5, sensor6, sensor7)
                 VALUES(?,?,?,?,?,?,?,?,?)'''
        
        cur = conn.cursor()

        cur.execute(sql, fsr_data)

        conn.commit()

    # for now just get the data from the queue and print it as is
    with sqlite3.connect(DATABASE_FILENAME) as conn:
        while running:
            new_data_poll = fsr_data_queue.get()

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

            # push to rolling buffer
            with fsr_data_buffer_lock:
                fsr_data_buffer.append(new_data_poll)


# webserver: TODO
def serve_flask_app():
    pass

# utility task
# periodically display buffer contents
def periodically_display_buffer_contents():
    while running:
        # lock the buffer
        with fsr_data_buffer_lock:
            # print out the last (most recent) value
            # if there is data in the buffer
            if (len(fsr_data_buffer) > 0):
                print(fsr_data_buffer[-1])
        
        # wait to avoid flooding the terminal
        time.sleep(1)

# small scale prototype
# task gets data out of rolling buffer and
# loads it into a pandas df
# then it prints out averages based on the data
def get_aggregate_data():
    pass
    # while running:
        # lock the buffer



def create_database():
    # create data directory
    subprocess.call(["mkdir", "-p", "data"])

    create_table = '''CREATE TABLE IF NOT EXISTS fsr_one (
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
                            );'''

    with sqlite3.connect(DATABASE_FILENAME) as conn:
        cursor = conn.cursor()
        cursor.execute(create_table)

def main():
    global running

    print("---Starting FSR Mini Dashboard---")

    # create db (if it doesnt exist)
    create_database()

    # create threads
    get_fsr_data_thread = threading.Thread(target=get_fsr_data)
    process_fsr_data_thread = threading.Thread(target=process_fsr_data)
    display_contents_thread = threading.Thread(target=periodically_display_buffer_contents)


    # start threads
    get_fsr_data_thread.start()
    process_fsr_data_thread.start()
    display_contents_thread.start()

    # stop if enter is pressed
    input("")
    running = False


if __name__ == "__main__":
    main()
