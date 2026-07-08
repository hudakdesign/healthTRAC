#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include <StreamUtils.h>

// Configure cores:
static const BaseType_t proCpu = 0;
static const BaseType_t appCpu = 1;

// Pin numbers:
// mux
static const int selectionPins[] = {8, 9, 10, 11};
static const int muxOutputPin = A0;
static const int numChannels = 16;

// Settings:
static const int numFsrs = 8;
static const int pollRate = 100;                                  // 100 hz
static const int pollSecondsStored = 20;                         // store up to 10 seconds of polls
static const int pollQueueLen = pollRate * pollSecondsStored; // stores 10 seconds of polls at 100 hz



// network credentials:
const char *ssid = "CBI IoT";
const char *password = "cbir00lz";
const char *hostname = "fsr-alpha";

// server settings:
const int timeoutTime = 2000;
const int serverPort = 80;
WiFiServer server(serverPort);

// Struct declaration
struct dataPoll
{
  int timestamp;          // timestamp when polls were taken
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
  struct dataPoll data; // initializes struct instance for thread

  while (1)
  {
    // get timestamp for when this poll is being taken
    data.timestamp = millis();

    // loop through each sensor checking their values
    for (int i = 0; i < numFsrs; i++)
    {
      // get the value

      // store it in the data struct
      // data.sensorReadings[i] = getMuxOutput(i, muxOutputPin);
      data.sensorReadings[i] = getSyntheticSensorValue(data.timestamp, i); // code for when no fsr attached
      // Serial.print(data.sensor_readings[i]);
      // Serial.print(" ");
    }
    // Serial.println();

    // copy it to the queue because it is now ready
    if (xQueueSend(pollQueue, (void *)&data, 0) != pdTRUE)
    {
      // Serial.println("Queue full"); // for now print out debug data to confirm that queue fills up
      digitalWrite(LED_RED, LOW); // rgb led uses low for turning on
    } else {
      digitalWrite(LED_RED, HIGH);
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
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(LED_RED, OUTPUT);

  // configure selection pins
  for (int i; i < (sizeof(selectionPins) / sizeof(int)); i++)
  {
    pinMode(selectionPins[i], OUTPUT);
  }

  // wait to start
  vTaskDelay(2000 / portTICK_PERIOD_MS);
  Serial.println();
  Serial.println("--FSR Concurrent Firmware--");

  // create the queue
  pollQueue = xQueueCreate(pollQueueLen, sizeof(struct dataPoll));

  // set up the network connection:
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.setHostname(hostname);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED)
  {
    // blinky and print .
    digitalWrite(LED_BUILTIN, HIGH);
    vTaskDelay(250 / portTICK_PERIOD_MS);
    digitalWrite(LED_BUILTIN, LOW);
    vTaskDelay(250 / portTICK_PERIOD_MS);

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
                          proCpu);
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
  while ((xQueueReceive(pollQueue, (void *)&newData, 0) == pdTRUE) && counter < pollQueueLen * 2)
  { // while an item is successfully received and less than set amount of entries are stored
    // add them to the json arrays
    timestampValues.add(newData.timestamp);
    sensorValues0.add(newData.sensorReadings[0]);
    sensorValues1.add(newData.sensorReadings[1]);
    sensorValues2.add(newData.sensorReadings[2]);
    sensorValues3.add(newData.sensorReadings[3]);
    sensorValues4.add(newData.sensorReadings[4]);
    sensorValues5.add(newData.sensorReadings[5]);
    sensorValues6.add(newData.sensorReadings[6]);
    sensorValues7.add(newData.sensorReadings[7]);

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
  WriteBufferingStream bufferedWiFiClient(client, 1024 * 1); // normally 32kb
  serializeJson(doc, bufferedWiFiClient);
  bufferedWiFiClient.flush();

  client.stop(); // higher priority than main (data must be collected on time)
  
  // when the client disconnects: turn off the led
  digitalWrite(LED_BUILTIN, LOW);
}

// Utility Functions:
// Return synthetic data output
int getSyntheticSensorValue(int timestamp, int idx)
{
  return 16;
  // return (int)((sin(timestamp * (idx + 1) * 0.01) + 1) * 4096 / 2); // returns int value simulating fsr output
}

// sets selection pins to tell mux which channel to provide
void setMuxChannel(int channel)
{
  // Serial.println("1");
  // convert channel number to binary (4-bits)
  // loop through each selection pin, and assign them based on selection bit
  for (int i = 0; i < (sizeof(selectionPins) / sizeof(int)); i++)
  {
    // Serial.println("2");
    // if the i'th bit of channel is 1:
    if (getKBit(channel, i))
    {
      // set the selection pin to high
      digitalWrite(selectionPins[i], HIGH);
    }
    else
    {
      // otherwise set the selection pin to low
      digitalWrite(selectionPins[i], LOW);
    }
  }
}

// gets the analog output of the mux
int getMuxOutput(int channel, int output_pin) {
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