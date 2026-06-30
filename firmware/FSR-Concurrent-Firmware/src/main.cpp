#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include <StreamUtils.h>

// Configure cores:
static const BaseType_t pro_cpu = 0;
static const BaseType_t app_cpu = 1;

// Settings:
static const int num_fsrs = 8;
static const int poll_rate = 100;                                  // 100 hz
static const int poll_seconds_stored = 60;                         // store up to 10 seconds of polls
static const int poll_queue_len = poll_rate * poll_seconds_stored; // stores 10 seconds of polls at 100 hz

// pin numbers:
static const int led_pin = 13;

// network credentials:
const char *ssid = "CBI IoT";
const char *password = "cbir00lz";
const char *hostname = "fsr-alpha";

// server settings:
const int timeout_time = 2000;
const int server_port = 80;
WiFiServer server(server_port);

// Struct declaration
struct dataPoll
{
  int timestamp;          // timestamp when polls were taken
  int sensor_readings[8]; // values from each fsr
};

// Globals:
static QueueHandle_t poll_queue;

String header; // variable to store http request
unsigned long current_time = millis();
unsigned long previous_time = 0;

// Declaring utility functions:
int getSyntheticSensorValue(int, int);

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
    if (xQueueSend(poll_queue, (void *)&data, 0) != pdTRUE)
    {
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

  // set led pin to output
  pinMode(led_pin, OUTPUT);

  // wait to start
  vTaskDelay(2000 / portTICK_PERIOD_MS);
  Serial.println();
  Serial.println("--FSR Concurrent Firmware--");

  // create the queue
  poll_queue = xQueueCreate(poll_queue_len, sizeof(struct dataPoll));

  // set up the network connection:
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.setHostname(hostname);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED)
  {
    vTaskDelay(500);
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
                          2048,
                          NULL,
                          1, // priority doesnt matter, this is the only thing running on procore
                          NULL,
                          pro_cpu);
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
  digitalWrite(led_pin, HIGH);

  // read the request (ignore contents)
  while (client.available())
  {
    client.read();
  }

  // NOTE: only fill up to certain point to avoid memory leak
  // allocate temporary json document
  JsonDocument doc; // TODO: switch to static json document (come back to me)

  // create the timestamps array
  JsonArray timestampValues = doc["timestamps"].to<JsonArray>();
  JsonArray sensorValues0 = doc["sensor0"].to<JsonArray>();
  JsonArray sensorValues1 = doc["sensor1"].to<JsonArray>();
  JsonArray sensorValues2 = doc["sensor2"].to<JsonArray>();
  JsonArray sensorValues3 = doc["sensor3"].to<JsonArray>();
  JsonArray sensorValues4 = doc["sensor4"].to<JsonArray>();
  JsonArray sensorValues5 = doc["sensor5"].to<JsonArray>();
  JsonArray sensorValues6 = doc["sensor6"].to<JsonArray>();
  JsonArray sensorValues7 = doc["sensor7"].to<JsonArray>();

  // counter to avoid memory leak
  int counter = 0;

  // read in values from the queue
  // append them to their corresponding json arrays
  // increment the counter to avoid potential memory leak
  while ((xQueueReceive(poll_queue, (void *)&newData, 0) == pdTRUE) && counter < poll_queue_len)
  { // while an item is successfully received and less than set amount of entries are stored
    // add them to the json arrays
    timestampValues.add(newData.timestamp);
    sensorValues0.add(newData.sensor_readings[0]);
    sensorValues1.add(newData.sensor_readings[1]);
    sensorValues2.add(newData.sensor_readings[2]);
    sensorValues3.add(newData.sensor_readings[3]);
    sensorValues4.add(newData.sensor_readings[4]);
    sensorValues5.add(newData.sensor_readings[5]);
    sensorValues6.add(newData.sensor_readings[6]);
    sensorValues7.add(newData.sensor_readings[7]);

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
  WriteBufferingStream bufferedWiFiClient(client, 1024 * 32);
  serializeJson(doc, bufferedWiFiClient);
  bufferedWiFiClient.flush();

  client.stop(); // higher priority than main (data must be collected on time)
  
  // when the client disconnects: turn off the led
  digitalWrite(led_pin, LOW);
}

// Utility Functions:
// Return synthetic data output
int getSyntheticSensorValue(int timestamp, int idx)
{
  return (int)((sin(timestamp * (idx + 1) * 0.01) + 1) * 4096 / 2); // returns int value simulating fsr output
}