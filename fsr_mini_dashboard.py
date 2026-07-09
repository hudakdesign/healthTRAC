from flask import Flask, render_template
import threading
import queue
import requests
import json
import time
import sqlite3

# Constants
MAX_QUEUE_LEN = 5000
FSR_URL = "http://10.0.1.27/"
TIME_BETWEEN_POLLS = 5  # seconds
DATABASE_FILENAME = "data/test.db"

# Globals
running = True
fsr_data_queue = queue.Queue(maxsize=MAX_QUEUE_LEN)

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
    global running

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

        timer = time.time()
        # turn this data into individual polls and put into queue
        queue_individual_polls(data)
        # print how much time queueing these took
        print(f"Time to queue: {time.time() - timer}")

        # waits until its time to poll again
        time.sleep(TIME_BETWEEN_POLLS)


# consumer:
#   1. takes data out of the queue, saves it to the db TODO
#   2. next load data into a pandas df TODO
#   3. extract aggregate data from this df (averages for every half second maybe...) TODO
#   4. push aggregate data to rolling buffer TODO
def process_fsr_data():
    global running

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

            print(f"Data poll: {new_data_poll}")
            print(f"Data poll -> db compatible {fsr_data}")


# webserver: TODO
def serve_flask_app():
    pass

def create_database():
    create_table = '''CREATE TABLE IF NOT EXISTS fsr_one (
                            poll_id INT AUTO_INCREMENT PRIMARY KEY,
                            timestamp INT,
                            sensor0 INT,
                            sensor1 INT,
                            sensor2 INT,
                            sensor3 INT,
                            sensor4 INT,
                            sensor5 INT,
                            sensor6 INT,
                            sensor7 INT
                            );'''

    with sqlite3.connect(DATABASE_FILENAME) as conn:
        cursor = conn.cursor()
        cursor.execute(create_table)

def main():
    global running

    print("---Starting FSR Mini Dashboard---")

    # create threads
    get_fsr_data_thread = threading.Thread(target=get_fsr_data)
    process_fsr_data_thread = threading.Thread(target=process_fsr_data)

    # start threads
    get_fsr_data_thread.start()
    process_fsr_data_thread.start()

    # stop if enter is pressed
    input("")
    running = False



if __name__ == "__main__":
    main()
