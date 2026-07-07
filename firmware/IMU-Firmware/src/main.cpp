#include <Arduino.h>

#include "LSM6DS3.h"

// Constants:
static const int NUM_ACCELERATION_VALUES = 3;

// polling constants
static const int POLLING_RATE = 100;    // hz
static const int POLLING_TIME_MINS = 5; // how long we need to collect data

static const int POLLING_TIME_MS = POLLING_TIME_MINS * 60 * 1000;       // converted to ms
static const int MS_BETWEEN_POLLS = 1000 / POLLING_RATE;                // how long between polls
static const int MAX_STORED_POLLS = POLLING_TIME_MS / MS_BETWEEN_POLLS; // polling time / how long between polls

// Struct declarations:
struct imuDataPoll
{
  int timestamp;
  float accelerationValues[NUM_ACCELERATION_VALUES];
};

// Globals:
// imu class instance
static LSM6DS3 myIMU(I2C_MODE, 0x6A);

// data storage
static imuDataPoll pollBuffer[MAX_STORED_POLLS];

// put function declarations here:
void plotImuData();

void setup()
{
  // Initialize serial
  Serial.begin(115200);

  // wait for serial to initialize
  delay(2000);

  // configure imu
  if (myIMU.begin() != 0)
  {
    Serial.println("Device error");
  }
  else
  {
    Serial.println("Device OK!");
  }

  // set pin modes
  pinMode(LED_RED, OUTPUT);
}

void loop()
{
  plotImuData();
  delay(MS_BETWEEN_POLLS);
}

// put function definitions here:
void plotImuData()
{
  static float currentXAccel, currentYAccel, currentZAccel = 0;

  currentXAccel = myIMU.readFloatAccelX();
  currentYAccel = myIMU.readFloatAccelY();
  currentZAccel = myIMU.readFloatAccelZ();

  Serial.println(">x_accel:" + (String)currentXAccel);
  Serial.println(">y_accel:" + (String)currentYAccel);
  Serial.println(">z_accel:" + (String)currentZAccel);
}