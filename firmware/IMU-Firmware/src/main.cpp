#include <Arduino.h>
#include <Adafruit_TinyUSB.h>

#include "LSM6DS3.h"

// Constants:
static const int BAUD_RATE = 115200;
static const int POLL_QUEUE_LEN = 100;
static const int POLL_RATE_HZ = 100;
static const int POLL_RATE_MS = 1000 / POLL_RATE_HZ;

// Struct Declarations:
struct imuPoll
{
  int timestamp;
  float xAccel;
  float yAccel;
  float zAccel;
};

// Globals:
static LSM6DS3 myImu(I2C_MODE, 0x6A);

// handles
static QueueHandle_t pollQueue;
static TaskHandle_t imuDataCollectorHandle;
static TaskHandle_t imuDataPrinterHandle;

// Tasks:
// queue imu data
void imuDataCollector(void *parameters);

// print imu data from queue to plot
void imuDataPrinter(void *parameters);

void setup()
{
  Serial.begin(BAUD_RATE);
  pinMode(LED_RED, OUTPUT);

  // create queue for data polls
  pollQueue = xQueueCreate(POLL_QUEUE_LEN, sizeof(imuPoll));

  // start tasks
  xTaskCreate(imuDataCollector, "IMU Data Collector", 256, NULL, 1, NULL);
}

// used for getting high watermarks
void loop()
{
}

void imuDataCollector(void *parameters)
{
  static imuPoll currPoll;

  while (1)
  {
    currPoll.timestamp = millis();
    currPoll.xAccel = myImu.readFloatAccelX();
    currPoll.yAccel = myImu.readFloatAccelY();
    currPoll.zAccel = myImu.readFloatAccelZ();

    if (xQueueSend(pollQueue, (void *)&currPoll, 0) != pdTRUE)
    {
      // if its full then turn on the led
      digitalWrite(LED_RED, LOW);
    }
    else
    {
      digitalWrite(LED_RED, HIGH);
    }

    vTaskDelay(pdMS_TO_TICKS(POLL_RATE_MS));
  }
}