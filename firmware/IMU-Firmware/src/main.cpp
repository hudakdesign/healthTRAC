#include <Arduino.h>

#include "LSM6DS3.h"

// Constants:
static const int NUM_ACCELERATION_VALUES = 3;

// polling constants
static const int POLLING_RATE = 100;     // hz
static const int POLLING_TIME_SECS = 10; // how long we need to collect data

static const int POLLING_TIME_MS = POLLING_TIME_SECS * 1000;            // converted to ms
static const int MS_BETWEEN_POLLS = 1000 / POLLING_RATE;                // how long between polls
static const int MAX_QUEUED_POLLS = POLLING_TIME_MS / MS_BETWEEN_POLLS; // polling time / how long between polls

// ble server constants
static const int BLINK_RATE = 250;

// Struct declarations:
struct imuDataPoll
{
  int timestamp;
  float accelerationValues[NUM_ACCELERATION_VALUES];
};

// Globals:
// imu class instance
static LSM6DS3 myIMU(I2C_MODE, 0x6A);

// queue handle
static QueueHandle_t pollQueue;

// put function declarations here:
// void plotImuData();
imuDataPoll getImuData();
// void printStoredDataPoll(int);

// Tasks:
// Get data from IMU and push to queue,
// then wait until it is time for the next poll
void collectSensorData(void *parameters)
{
  static imuDataPoll newPoll;

  // populate the new poll
  newPoll = getImuData();

  // push that poll to the queue
  if (xQueueSend(pollQueue, (void *)&newPoll, 0) != pdTRUE) {
    // if the queue is full, turn on the red led
    digitalWrite(LED_RED, HIGH);
  } else {
    digitalWrite(LED_RED, LOW);
  }

  // wait for next poll
  vTaskDelay(pdMS_TO_TICKS(POLLING_TIME_MS));
}

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
  pinMode(LED_BLUE, OUTPUT);

  // create poll queue
  pollQueue = xQueueCreate(MAX_QUEUED_POLLS, sizeof(imuDataPoll));

  // create producer thread
  xTaskCreate(collectSensorData,
              "Data Collection Thread",
              4096,
              NULL,
              2, // higher priority than consumer thread (it should always collect on time)
              NULL);

  // create consumer thread
  // not yet implemented
}

// This will become the bluetooth server (consumer part)
// for now it blinks blue to represent "blue"tooth
void loop()
{
  digitalWrite(LED_BLUE, HIGH);
  vTaskDelay(pdMS_TO_TICKS(BLINK_RATE));
  digitalWrite(LED_BLUE, LOW);
  vTaskDelay(pdMS_TO_TICKS(BLINK_RATE));
}

// // put function definitions here:
// void plotImuData()
// {
//   static float currentXAccel, currentYAccel, currentZAccel = 0;

//   currentXAccel = myIMU.readFloatAccelX();
//   currentYAccel = myIMU.readFloatAccelY();
//   currentZAccel = myIMU.readFloatAccelZ();

//   Serial.println(">x_accel:" + (String)currentXAccel);
//   Serial.println(">y_accel:" + (String)currentYAccel);
//   Serial.println(">z_accel:" + (String)currentZAccel);
// }

// returns populated imu datapoll
inline imuDataPoll getImuData()
{
  imuDataPoll newPoll;

  // set timestamp
  newPoll.timestamp = millis();

  // get accel values
  newPoll.accelerationValues[0] = myIMU.readFloatAccelX();
  newPoll.accelerationValues[1] = myIMU.readFloatAccelY();
  newPoll.accelerationValues[2] = myIMU.readFloatAccelZ();

  return newPoll;
}