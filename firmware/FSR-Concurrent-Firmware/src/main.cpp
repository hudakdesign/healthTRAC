#include <Arduino.h>

#if CONFIG_FREERTOS_UNICORE
static const BaseType_t app_cpu = 0;
#else
static const BaseType_t app_cpu = 1;
#endif

// Settings:
static const int num_fsrs = 8;
static const int poll_rate = 100;                                  // 100 hz
static const int poll_seconds_stored = 10;                         // store up to 10 seconds of polls
static const int poll_queue_len = poll_rate * poll_seconds_stored; // stores 10 seconds of polls at 100 hz

// Struct declaration
struct dataPoll
{
  int timestamp;          // timestamp when polls were taken
  int sensor_readings[8]; // values from each fsr
};

// Globals:
static QueueHandle_t poll_queue;

// Utility Functions:
// provides synthetic data for testing purposes
int getSyntheticSensorValue(int timestamp, int idx) {
  return (int) ((sin(timestamp * (idx + 1) * 0.01) + 1) * 4096 / 2); // returns int value simulating fsr output
}

// Tasks:
// Task: every 10 ms, get data from each sensor
// Higher priority (this will always execute when it needs to)
void collectSensorData(void *parameters)
{
  struct dataPoll data; // initializes struct instance for thread

  while (1)
  {
    // get timestamp for when this poll is being taken
    data.timestamp = millis();

    // loop through each sensor checking their values
    for (int i = 0; i < num_fsrs; i++)
    {
      // get the value

      // store it in the data struct
      data.sensor_readings[i] = getSyntheticSensorValue(data.timestamp, i);
      Serial.print(data.sensor_readings[i]);
      Serial.print(" ");
    }
    Serial.println();

    // copy it to the queue because it is now ready
    if (xQueueSend(poll_queue, (void *)&data, 0) != pdTRUE) {
      Serial.println("Queue full"); // for now print out debug data to confirm that queue fills up
    }

    // wait until it is time for the next poll
    vTaskDelay(1000 / 100 / portTICK_PERIOD_MS); // 1000 / 100: 100hz (every 10 ms)
  }
}

// Main (runs as own task with priority 1 on core 1)

void setup()
{
  // Initialize serial
  Serial.begin(115200);

  // wait to start
  vTaskDelay(2000 / portTICK_PERIOD_MS);
  Serial.println();
  Serial.println("--FSR Concurrent Firmware--");

  // create the queue
  poll_queue = xQueueCreate(poll_queue_len, sizeof(struct dataPoll));

  // start data collection task
  xTaskCreatePinnedToCore(collectSensorData,
                          "Collect Sensor Data",
                          2048,
                          NULL,
                          2, // higher priority than main (data must be collected on time)
                          NULL,
                          app_cpu);
}

void loop()
{
  Serial.print(millis());
  Serial.println("firmware is running");
  vTaskDelay(1000 / portTICK_PERIOD_MS);
}