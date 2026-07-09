from flask import Flask, render_template
import threading
import queue
import requests
import json
import time

# Constants
MAX_QUEUE_LEN = 5000
FSR_URL = "http://10.0.1.27/"
TIME_BETWEEN_POLLS = 5  # seconds

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
#   1. takes data out of the queue, saves it to the db
#   2. next load data into a pandas df
#   3. extract aggregate data from this df (averages for every half second maybe...)
#   4. push aggregate data to rolling buffer
def process_fsr_data():
    global running

    # for now just get the data from the queue and print it as is
    while running:
        new_data_poll = fsr_data_queue.get()
        print(f"Data poll: {new_data_poll}")


# webserver:
def serve_flask_app():
    pass


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
