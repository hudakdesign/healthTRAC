#include <Arduino.h>
#include <Adafruit_TinyUSB.h>

#include "LSM6DS3.h"

// Constants:
static const uint32_t BAUD_RATE = 115200;
static const int POLL_QUEUE_LEN = 1000;
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
  myImu.begin();

  // create queue for data polls
  pollQueue = xQueueCreate(POLL_QUEUE_LEN, sizeof(imuPoll));

  // start tasks
  xTaskCreate(imuDataCollector, "IMU Data Collector", 90, NULL, 1, &imuDataCollectorHandle); // stack calc: (1024 - 953) / 0.8 = 88.75
  xTaskCreate(imuDataPrinter, "IMU Data Printer", 350, NULL, 1, &imuDataPrinterHandle); // stack calc (1024 - 749) / 0.8 = 343.75
}

// used for getting high watermarks
void loop()
{
  Serial.print(">collectionHighWaterMark:");
  Serial.print(uxTaskGetStackHighWaterMark(imuDataCollectorHandle));
  Serial.println("|t");

  Serial.print(">printingHighWaterMark:");
  Serial.print(uxTaskGetStackHighWaterMark(imuDataPrinterHandle));
  Serial.println("|t");

  vTaskDelay(pdMS_TO_TICKS(1000));
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

void imuDataPrinter(void *parameters) {
  static imuPoll currPoll;
  while (1) {
    if (xQueueReceive(pollQueue, (void *)&currPoll, 0) == pdTRUE) {
      Serial.print(">xAccel:");
      Serial.println(currPoll.xAccel);
      Serial.print(">yAccel:");
      Serial.println(currPoll.yAccel);
      Serial.print(">zAccel:");
      Serial.println(currPoll.zAccel);
    }

    vTaskDelay(pdMS_TO_TICKS(POLL_RATE_MS / 2));
  }
}