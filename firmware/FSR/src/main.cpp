#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include <StreamUtils.h>
#include "network_credentials.h"

// Configure to use synthetic data or not
#define USE_SYNTHETIC_DATA false

// Configure cores:
static const BaseType_t PRO_CPU = 0;
static const BaseType_t APP_CPU = 1;

// Pin numbers:
// mux
static const int SELECTION_PINS[] = {8, 9, 10, 11};
static const int MUX_OUTPUT_PIN = A0;
static const int NUM_CHANNELS = 16;

// Settings:
static const int NUM_FSRS = 8;
static const int POLL_RATE_HZ = 100;                                               // 100 hz
static const TickType_t POLL_FREQUENCY_TICKS = pdMS_TO_TICKS(1000 / POLL_RATE_HZ); // ticks between polls
static const int POLL_SECONDS_STORED = 20;                                         // store up to 10 seconds of polls
static const int POLL_QUEUE_LEN = POLL_RATE_HZ * POLL_SECONDS_STORED;              // stores 10 seconds of polls at 100 hz

static const int PRODUCER_THREAD_STACK_SIZE = 2048;
static const int BUFFER_STREAM_SIZE = 1024;
static const int MONITOR_SPEED = 115200;
static const int START_DELAY = 2000;
static const int BLINK_RATE = 250;

// network hostname
const char *HOSTNAME = "fsr-alpha";

// server settings:
const int TIMEOUT_TIME = 2000;
const int SERVER_PORT = 80;

// declare WiFiServer
WiFiServer server(SERVER_PORT);

// Struct declaration
struct dataPoll
{
  int timestamp;         // timestamp when polls were taken
  int sensorReadings[8]; // values from each fsr
};

// Globals:
static QueueHandle_t pollQueue;

String header; // variable to store http request
unsigned long currentTime = millis();
unsigned long previousTime = 0;

// Declaring utility functions:
int getSyntheticSensorValue(int, int);
void setMuxChannel(int);
int getMuxOutput(int, int);
int getKBit(int, int);

// Tasks:
// Task: every 10 ms, get data from each sensor
// Higher priority (this will always execute when it needs to)
void collectSensorData(void *parameters)
{
  TickType_t collectionLastWakeTime;
  BaseType_t collectionWasDelayed;

  struct dataPoll data; // initializes struct instance for thread

  collectionLastWakeTime = xTaskGetTickCount();
  while (1)
  {
    collectionWasDelayed = xTaskDelayUntil(&collectionLastWakeTime, POLL_FREQUENCY_TICKS);

    // get timestamp for when this poll is being taken
    data.timestamp = millis();

    // loop through each sensor checking their values
    for (int i = 0; i < NUM_FSRS; i++)
    {
// get the value

// store it in the data struct
#if USE_SYNTHETIC_DATA
      data.sensorReadings[i] = getSyntheticSensorValue(data.timestamp, i); // code for when no fsr attached
#else
      data.sensorReadings[i] = getMuxOutput(i, MUX_OUTPUT_PIN);
#endif

      // Serial.print(data.sensor_readings[i]);
      // Serial.print(" ");
    }
    // Serial.println();

    // copy it to the queue because it is now ready
    if (xQueueSend(pollQueue, (void *)&data, 0) != pdTRUE)
    {
      // Serial.println("Queue full"); // for now print out debug data to confirm that queue fills up
      digitalWrite(LED_RED, LOW); // rgb led uses low for turning on
    }
    else
    {
      digitalWrite(LED_RED, HIGH);
    }

    // wait until it is time for the next poll TODO: Delete me
    // vTaskDelay(1000 / POLL_RATE_HZ / portTICK_PERIOD_MS); // 1000 / 100: 100hz (every 10 ms)
  }
}

// Main (runs as own task with priority 1 on core 1)

void setup()
{
  // Initialize serial
  Serial.begin(MONITOR_SPEED);

  // set led pin to output
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);

  // configure selection pins
  for (int i; i < (sizeof(SELECTION_PINS) / sizeof(int)); i++)
  {
    pinMode(SELECTION_PINS[i], OUTPUT);
  }

  // wait to start
  vTaskDelay(START_DELAY / portTICK_PERIOD_MS);
  Serial.println();
  Serial.println("--FSR Concurrent Firmware--");

  // create the queue
  pollQueue = xQueueCreate(POLL_QUEUE_LEN, sizeof(struct dataPoll));

  // set up the network connection:
  Serial.print("Connecting to ");
  Serial.println(SSID);
  WiFi.setHostname(HOSTNAME);
  WiFi.begin(SSID, PASSWORD);
  while (WiFi.status() != WL_CONNECTED)
  {
    // blinky and print .
    digitalWrite(LED_GREEN, LOW);
    vTaskDelay(BLINK_RATE / portTICK_PERIOD_MS);
    digitalWrite(LED_GREEN, HIGH);
    vTaskDelay(BLINK_RATE / portTICK_PERIOD_MS);

    Serial.print(".");
  }

  // print connection details
  Serial.println("");
  Serial.println("WiFi connected.");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  Serial.print("Hostname: ");
  Serial.println(WiFi.getHostname());

  server.begin(); // starts up the webserver

  // start data collection task
  xTaskCreatePinnedToCore(collectSensorData,
                          "Collect Sensor Data",
                          PRODUCER_THREAD_STACK_SIZE,
                          NULL,
                          2, // priority 2 to make sure it is running on time
                          NULL,
                          PRO_CPU);
}

// This loop will handle the webserver sending information from the queue
void loop()
{
  static struct dataPoll newData;

  // wait for incoming connection
  WiFiClient client = server.available();

  if (!client)
  {
    return;
  }

  Serial.println("New client");

  // when a new client connects: turn led on
  digitalWrite(LED_BUILTIN, HIGH);

  // read the request (ignore contents)
  while (client.available())
  {
    client.read();
  }

  // NOTE: only fill up to certain point to avoid memory leak
  // allocate temporary json document
  JsonDocument doc; // TODO: switch to static json document (come back to me)

  // creates portion for timestamps
  JsonArray timestamps = doc["timestamps"].to<JsonArray>();

  // creates portion for sensors
  JsonArray sensors = doc["sensors"].to<JsonArray>();

  // create an array entry for each sensor
  JsonArray sensors0 = sensors.add<JsonArray>();
  JsonArray sensors1 = sensors.add<JsonArray>();
  JsonArray sensors2 = sensors.add<JsonArray>();
  JsonArray sensors3 = sensors.add<JsonArray>();
  JsonArray sensors4 = sensors.add<JsonArray>();
  JsonArray sensors5 = sensors.add<JsonArray>();
  JsonArray sensors6 = sensors.add<JsonArray>();
  JsonArray sensors7 = sensors.add<JsonArray>();

  int counter = 0;

  // // read in values from the queue
  // // append them to their corresponding json arrays
  // // increment the counter to avoid potential memory leak
  while ((xQueueReceive(pollQueue, (void *)&newData, 0) == pdTRUE) && counter < POLL_QUEUE_LEN)
  { // while an item is successfully received and less than set amount of entries are stored
    // add them to the json arrays
    timestamps.add(newData.timestamp);
    sensors0.add(newData.sensorReadings[0]);
    sensors1.add(newData.sensorReadings[1]);
    sensors2.add(newData.sensorReadings[2]);
    sensors3.add(newData.sensorReadings[3]);
    sensors4.add(newData.sensorReadings[4]);
    sensors5.add(newData.sensorReadings[5]);
    sensors6.add(newData.sensorReadings[6]);
    sensors7.add(newData.sensorReadings[7]);

    counter++;
  }

  // Write response headers
  client.println("HTTP/1.0 200 OK");
  client.println("Content-Type: application/json");
  client.println("Connection: close");
  client.print("Content-Length: ");
  client.println(measureJson(doc));
  client.println();

  // Write buffered doc
  WriteBufferingStream bufferedWiFiClient(client, BUFFER_STREAM_SIZE);
  serializeJson(doc, bufferedWiFiClient);
  bufferedWiFiClient.flush();

  client.stop();

  // when the client disconnects: turn off the led
  digitalWrite(LED_BUILTIN, LOW);
}

// Utility Functions:
// Return synthetic data output
int getSyntheticSensorValue(int timestamp, int idx)
{
  return (int)((sin((timestamp * (idx + 1) * 0.0001) + 1)) * 4096 / 2); // returns int value simulating fsr output
}

// sets selection pins to tell mux which channel to provide
void setMuxChannel(int channel)
{
  // Serial.println("1");
  // convert channel number to binary (4-bits)
  // loop through each selection pin, and assign them based on selection bit
  for (int i = 0; i < (sizeof(SELECTION_PINS) / sizeof(int)); i++)
  {
    // Serial.println("2");
    // if the i'th bit of channel is 1:
    if (getKBit(channel, i))
    {
      // set the selection pin to high
      digitalWrite(SELECTION_PINS[i], HIGH);
    }
    else
    {
      // otherwise set the selection pin to low
      digitalWrite(SELECTION_PINS[i], LOW);
    }
  }
}

// gets the analog output of the mux
int getMuxOutput(int channel, int output_pin)
{
  setMuxChannel(channel);
  return analogRead(output_pin);
}

// extracts the k'th bit from n
int getKBit(int n, int k)
{
  // Serial.println("3");
  int mask = 1 << k;
  int masked_n = n & mask;
  return masked_n >> k;
}