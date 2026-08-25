#include <Arduino.h>
#include <Adafruit_TinyUSB.h>
#include <bluefruit.h>
#include <LSM6DS3.h>
#include <DataPoll.h>

// Globals
BLEService imuService("88fc1bd0-8154-454a-b2bd-fe4cc329d1d5");
BLECharacteristic imuCharacteristic("547af7ac-aa68-47eb-a0df-d827e39615bf");

bool checkForInactivity(DataPoll newDataPoll) {
  return false;
}

void setup() {
  // serial
  Serial.begin(115200);

  // leds
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);

  // wait for serial to initialize
  digitalWrite(LED_RED, LOW);
  delay(1000);
  digitalWrite(LED_RED, HIGH);
  digitalWrite(LED_GREEN, LOW);
  delay(1000);
  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_BLUE, LOW);
  delay(1000);
  digitalWrite(LED_BLUE, HIGH);
  Serial.println("---IMU Server---");

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