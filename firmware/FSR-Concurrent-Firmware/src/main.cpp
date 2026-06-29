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

// Tasks:
// Task: every 10 ms, get data from each sensor
void collectSensorData(void *parameters)
{
}

// Main (runs as own task with priority 1 on core 1)

void setup()
{
  // Initialize serial
  Serial.begin(115200);

  // put your setup code here, to run once:
  int result = myFunction(2, 3);
}

void loop()
{
  // put your main code here, to run repeatedly:
}

// put function definitions here:
int myFunction(int x, int y)
{
  return x + y;
}