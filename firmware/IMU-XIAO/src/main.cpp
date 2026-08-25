#include <Arduino.h>
#include <DataPoll.h>

bool checkForInactivity(DataPoll newDataPoll) {
  return false;
}

void setup() {
  // serial

  // leds

  // bluefruit

  // imu
}

void loop() {
  // vTaskDelayUntil time to poll again
  
  // collect new poll data
  // encode new poll data
  // update characteristic with encoded data
  // notify client

  // check for inactivity
  // if inactive then setup the wake interrupt
  // and shutdown
}