#include <Arduino.h>
#include <vector>
#include <NimBLEDevice.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include <network_credentials.h>

// Struct declaration:
// stores a voltage reading alongside when it was taken
struct BatteryReading
{
  uint32_t timestamp;
  float voltage;
};

// Constants:
// nimble
// TODO: refactor from TARGET_SERVICE_NAME TO UUID
static const char *TARGET_SERVICE_NAME = "b1eb8d99-226f-4d60-86bd-02e77ac18b3c";
static const char *TARGET_CHARACTERISTIC_NAME = "12df161a-a7a7-4b7d-8a1b-70979458752c";
static const NimBLEUUID TARGET_SERVICE(TARGET_SERVICE_NAME);
static const NimBLEUUID TARGET_CHARACTERISTIC(TARGET_CHARACTERISTIC_NAME);

// web server
const char *HOSTNAME = "battery-test-esp";
const int SERVER_PORT = 80;
const TickType_t SERIAL_WAIT_DELAY = pdMS_TO_TICKS(2000);
const TickType_t BLINK_RATE = pdMS_TO_TICKS(500);

// Globals:
// nimble
static const NimBLEAdvertisedDevice *advDevice; // this is kind of global and kind of constant
static bool doConnect = false;
static uint32_t scanTimeMs = 5000;

// web server
WiFiServer server(SERVER_PORT);

// stores battery readings
std::vector<BatteryReading> batteryReadings;
QueueHandle_t voltageNotificationQueue = NULL;

// Callbacks:
// only scan callback is necessary
class ScanCallbacks : public NimBLEScanCallbacks
{
  void onResult(const NimBLEAdvertisedDevice *advertisedDevice) override
  {
    Serial.printf("Advertised device found: %s\n", advertisedDevice->toString().c_str());
    if (advertisedDevice->isAdvertisingService(TARGET_SERVICE))
    {
      Serial.printf("Found our service\n");
      // stop scanning before connecting
      NimBLEDevice::getScan()->stop();
      // save device reference in the global for client to use
      advDevice = advertisedDevice;
      // indicate that it is time to connect
      doConnect = true;
    }
  }

  // callback to process results of completed scan or restart
  void onScanEnd(const NimBLEScanResults &results, int reason) override
  {
    Serial.printf("Scan ended, reason: %d, device count: %d; Restarting scan\n", reason, results.getCount());
    NimBLEDevice::getScan()->start(scanTimeMs, false, true);
  }
} scanCallbacks;

// TODO: notify callback
// send notification data to queue, this queue is emptied as soon as possible into the batteryVoltage vector
void notifyCB(NimBLERemoteCharacteristic *pRemoteCharacteristic, uint8_t *pData, size_t length, bool isNotify)
{
  // if length is correct
  if (length == sizeof(uint32_t))
  {
    // decode the incoming value
    uint32_t incomingValue;
    std::memcpy(&incomingValue, pData, sizeof(uint32_t));

    // print the value
    // Serial.printf(">voltageReading:%d|t\n", incomingValue);

    // send it to the queue
    if (xQueueSend(voltageNotificationQueue, (void *)&incomingValue, 0) != pdTRUE) {
      digitalWrite(LED_RED, LOW);
    } else {
      digitalWrite(LED_RED, HIGH);
    }
  }
}

// NOTE: I dont think a connect callback is necessary, but if so then put one here

// Setup helpers:
void setupBluetooth()
{
  Serial.println("Bluetooth Setup:");

  // intialize device and set name
  NimBLEDevice::init("Battery-Test-ESP");

  // set transmit power
  NimBLEDevice::setPower(8);
  // get ptr for controlling scanning
  NimBLEScan *pScan = NimBLEDevice::getScan();

  // set scan callbacks
  pScan->setScanCallbacks(&scanCallbacks, false);

  // set scan interval and window (how often and how long) in ms
  pScan->setInterval(100);
  pScan->setWindow(100);

  // active scan to get response data from advertising devices
  pScan->setActiveScan(true);

  // start scanning for advertisers
  pScan->start(scanTimeMs);
  Serial.printf("Scanning for peripherals\n");
}

void setupWifiServer()
{
  Serial.println("Wifi Setup:");
  Serial.printf("Connecting to %s", SSID);

  WiFi.setHostname(HOSTNAME);
  WiFi.begin(SSID, PASSWORD);

  while (WiFi.status() != WL_CONNECTED)
  {
    // print '.' and blink
    Serial.print(".");

    digitalWrite(LED_GREEN, LOW);
    vTaskDelay(BLINK_RATE);
    digitalWrite(LED_GREEN, HIGH);
    vTaskDelay(BLINK_RATE);
  }

  server.begin();
}

/** Handles the provisioning of clients and connects / interfaces with the server */
bool connectToServer()
{
  NimBLEClient *pClient = nullptr;

  /** Check if we have a client we should reuse first **/
  if (NimBLEDevice::getCreatedClientCount())
  {
    /**
     *  Special case when we already know this device, we send false as the
     *  second argument in connect() to prevent refreshing the service database.
     *  This saves considerable time and power.
     */
    pClient = NimBLEDevice::getClientByPeerAddress(advDevice->getAddress());
    if (pClient)
    {
      if (!pClient->connect(advDevice, false))
      {
        Serial.printf("Reconnect failed\n");
        return false;
      }
      Serial.printf("Reconnected client\n");
    }
    else
    {
      /**
       *  We don't already have a client that knows this device,
       *  check for a client that is disconnected that we can use.
       */
      pClient = NimBLEDevice::getDisconnectedClient();
    }
  }

  /** No client to reuse? Create a new one. */
  if (!pClient)
  {
    if (NimBLEDevice::getCreatedClientCount() >= MYNEWT_VAL(BLE_MAX_CONNECTIONS))
    {
      Serial.printf("Max clients reached - no more connections available\n");
      return false;
    }

    pClient = NimBLEDevice::createClient();

    Serial.printf("New client created\n");

    /**
     *  Set initial connection parameters:
     *  These settings are safe for 3 clients to connect reliably, can go faster if you have less
     *  connections. Timeout should be a multiple of the interval, minimum is 100ms.
     *  Min interval: 12 * 1.25ms = 15, Max interval: 12 * 1.25ms = 15, 0 latency, 150 * 10ms = 1500ms timeout
     */
    pClient->setConnectionParams(12, 12, 0, 150);

    /** Set how long we are willing to wait for the connection to complete (milliseconds), default is 30000. */
    pClient->setConnectTimeout(5 * 1000);

    if (!pClient->connect(advDevice))
    {
      /** Created a client but failed to connect, don't need to keep it as it has no data */
      NimBLEDevice::deleteClient(pClient);
      Serial.printf("Failed to connect, deleted client\n");
      return false;
    }
  }

  if (!pClient->isConnected())
  {
    if (!pClient->connect(advDevice))
    {
      Serial.printf("Failed to connect\n");
      return false;
    }
  }

  Serial.printf("Connected to: %s RSSI: %d\n", pClient->getPeerAddress().toString().c_str(), pClient->getRssi());

  /** Now we can read/write/subscribe the characteristics of the services we are interested in */
  NimBLERemoteService *pSvc = nullptr;
  NimBLERemoteCharacteristic *pChr = nullptr;
  NimBLERemoteDescriptor *pDsc = nullptr;

  // try to find the voltage service
  // and subscribe to notifications
  pSvc = pClient->getService(TARGET_SERVICE_NAME);
  if (pSvc)
  {
    pChr = pSvc->getCharacteristic(TARGET_CHARACTERISTIC_NAME);
    if (pChr)
    {
      if (pChr->canNotify())
      {
        if (!pChr->subscribe(true, notifyCB))
        {
          pClient->disconnect();
          return false;
        }
      }
      else if (pChr->canIndicate())
      {
        /** Send false as first argument to subscribe to indications instead of notifications */
        if (!pChr->subscribe(false, notifyCB))
        {
          pClient->disconnect();
          return false;
        }
      }
    }
  }
  else
  {
    Serial.printf("%s service not found.\n", TARGET_SERVICE_NAME);
  }

  Serial.printf("Done with this device!\n");
  return true;
}

void setup()
{
  // Initialize serial and pins
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);
  vTaskDelay(SERIAL_WAIT_DELAY);

  // Create queue
  // stores 10, 4 byte notifications
  voltageNotificationQueue = xQueueCreate(10, sizeof(uint32_t));

  // Initialize bluetooth
  setupBluetooth();

  // Initialize webserverNimBLE
  setupWifiServer();
}

void loop()
{
  // Web server
  // check for clients every loop
  WiFiClient wifiClient = server.available();

  // if a client connects then prepare and send a response
  if (wifiClient)
  {
    Serial.println("New wifi client");

    // when a client connects: turn on led
    digitalWrite(LED_BUILTIN, HIGH);

    // read and throw out request packet
    while (wifiClient.available())
    {
      wifiClient.read();
    }

    // create and format a json document for sending the values
    JsonDocument doc;
    JsonArray timestamps = doc["timestamps"].to<JsonArray>();
    JsonArray voltages = doc["voltages"].to<JsonArray>();

    // iterate through `batteryReadings` and add the values to the doc
    for (BatteryReading batteryReading : batteryReadings)
    {
      timestamps.add(batteryReading.timestamp);
      voltages.add(batteryReading.voltage);
    }

    // send the http header
    wifiClient.println("HTTP/1.0 200 OK");
    wifiClient.println("Content-Type: application/json");
    wifiClient.println("Connection: close");
    wifiClient.printf("Content-Length: %d\n", measureJson(doc));
    wifiClient.println(); // second newline indicates end of message

    // send the doc
    serializeJson(doc, wifiClient);

    // close the connection and turn off led
    wifiClient.stop();
    digitalWrite(LED_BUILTIN, LOW);
  }

  // Bluetooth
  if (doConnect)
  {
    doConnect = false;
    // if we found device we want to connect to
    if (connectToServer())
    {
      Serial.println("Success! we should now be getting notifications, scanning for more");
    }
    else
    {
      Serial.println("Failed to connect, starting scan");
    }

    NimBLEDevice::getScan()->start(scanTimeMs, false, true);
  }

  // receive incoming notifications as they come
  // push them to the vector
  uint32_t receivedVoltage;
  if (xQueueReceive(voltageNotificationQueue, (void *)&receivedVoltage, 0) == pdTRUE) {
    // indicate that the queue now isnt full
    digitalWrite(LED_RED, HIGH);
    Serial.printf(">voltageReading:%d|t\n", receivedVoltage);

    BatteryReading currentBatteryReading;
    currentBatteryReading.timestamp = millis();
    currentBatteryReading.voltage = receivedVoltage;

    batteryReadings.push_back(currentBatteryReading);
  }

  // static uint32_t nextPollTime = millis();
  // if (millis() >= nextPollTime) {
  //   nextPollTime =+ 1000 * 60; // (60 seconds)

  //   BatteryReading currBatteryReading;
  //   currBatteryReading.timestamp =
  // }
}