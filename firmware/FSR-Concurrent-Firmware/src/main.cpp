#include <Arduino.h>
#include <WiFi.h>

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

// network credentials:
const char* ssid = "CBI IoT";
const char* password = "cbir00lz";
const char* hostname = "fsr-alpha";

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


// Utility Functions:
// provides synthetic data for testing purposes
int getSyntheticSensorValue(int timestamp, int idx)
{
  return (int)((sin(timestamp * (idx + 1) * 0.01) + 1) * 4096 / 2); // returns int value simulating fsr output
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
  while (WiFi.status() != WL_CONNECTED) {
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
                          2, // higher priority than main (data must be collected on time)
                          NULL,
                          app_cpu);
}

// This loop will handle the webserver sending information from the queue
void loop() {
  WiFiClient client = server.available(); // Listen for incoming clients
 
  if (client) { // If a new client connects
    current_time = millis();
    previous_time = current_time;
    Serial.println("New Client.");
    String currentLine = ""; // String for incoming data
 
    while (client.connected() && current_time - previous_time <= timeout_time) { // loop while the client is connected
      current_time = millis();
 
      if (client.available()) { // If theres bytes to read from the client
        char c = client.read(); // read a byte
        Serial.write(c); // print the byte to serial monitor
        header += c; // add the byte to the header
        
        if (c == '\n') { // if the byte is a newline character
          // if the current line is blank, theres two newlines in a row
          // that indicates the end of the client HTTP request
          // time to respond
          if (currentLine.length() == 0) {
            Serial.println("Sending a response :)");
 
            // HTTP headers always start with a response code (e.g. HTTP/1.1 200 OK)
            // and a content-type so the client knows what's coming, then a blank line:
            // <HTTP header>
            client.println("HTTP/1.1 200 OK"); // Response code
            client.println("Content-type:text/html"); // content-type
            client.println("Connection: close"); // indicates to client that server will immediately terminate connection
            // </HTTP header>

            // print out json data to the client
            
 
            // // <Making decisions off of client header>
            // // turn the led on/off
            // if (header.indexOf("GET /toggleLed") >= 0) { // if this specific line appears in the request then toggle the led
            //   if (internalLedState == 0) { // if its off, turn it on
            //     internalLedState = 1;
            //     digitalWrite(LED_BUILTIN, HIGH);
            //     Serial.println("Internal Led: On");
            //   } else { // if its on, turn it off
            //     internalLedState = 0;
            //     digitalWrite(LED_BUILTIN, LOW);
            //     Serial.println("Internal Led: Off");
            //   }
            // }
 
 
            // if (header.indexOf("GET /internalLed/on") >= 0) { // if this specific line appears in the request
            //   Serial.println("Internal Led: on"); // logs to serial
            //   internalLedState = 1; // sets the state for logic
            //   digitalWrite(LED_BUILTIN, HIGH); // sets the pin to high
            // } else if (header.indexOf("GET /internalLed/off") >= 0) { // same as previous
            //   Serial.println("Internal Led: off"); // logs to serial
            //   internalLedState = 0; // sets state for logic
            //   digitalWrite(LED_BUILTIN, LOW); // sets pin to low
            // }
            // // </Making decisions off of client header>
 
            client.println(); // use another newline to indicate the end of the HTTP response
 
            break; // break out of the while loop
 
          } else { // if you got a newline, then clear currentline
            currentLine = "";
          }
        } else if (c != '\r') { // if you got anything else other than carriage return,
          currentLine += c;     // add to end of currentLine
        }
      }
    }
    header = ""; // Clear the header in memory
    
    client.stop(); // Close the connection
 
    Serial.println("Client disconnected.");
    Serial.println("");
 
    Serial.print("Time to process request: ");// DEBUG INFO FOR PERFORMANCE MEASUREMENTS
    Serial.print(millis() - previous_time);
    Serial.println("ms");
  } else { // otherwise use this time to populate json
    
  }
}
 