#include <Arduino.h>
#include <DataPoll.h>

// Constants

// Globals

// Callback declarations

void setup() {
  // initialize serial

  // initialize imu

  // initialize NimBLE

  // set power level

  // create ble server and set its callbacks

  // intialize stream server and set overflow callback

  // create advertising instance
}

void loop() {
  // wait until time for next poll

  // handle receive buffer overflows

  // check if a client is subscribed

    // populate DataPoll with current sensor data

    // convert to array of bytes

    // print byte array over bleStream
}