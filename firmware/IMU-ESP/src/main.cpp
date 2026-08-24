
/** NimBLE_Client Demo:
 *
 *  Demonstrates many of the available features of the NimBLE client library.
 *
 *  Created: on March 24 2020
 *      Author: H2zero
 */

#include <Arduino.h>
#include <NimBLEDevice.h>
#include <WiFi.h>
#include <ArduinoJson.h>
#include <StreamUtils.h>
#include <DataPoll.h>
#include "network_credentials.h"

// Constants
const char* HOSTNAME = "imu-alpha";
const int BLINK_RATE = 500;
const int POLL_QUEUE_LEN = 1000;
const int SERVER_PORT = 80;
const int BUFFER_STREAM_SIZE = 1024;

// Globals
static const NimBLEAdvertisedDevice* advDevice;
static bool                          doConnect  = false;
static uint32_t                      scanTimeMs = 5000; /** scan time in milliseconds, 0 = scan forever */

// queue for storing DataPolls
static QueueHandle_t pollQueue;

// used for managing webserver
WiFiServer server(SERVER_PORT);

/**  None of these are required as they will be handled by the library with defaults. **
 **                       Remove as you see fit for your needs                        */

/** Define a class to handle the callbacks when scan events are received */
class ScanCallbacks : public NimBLEScanCallbacks {
    void onResult(const NimBLEAdvertisedDevice* advertisedDevice) override {
        Serial.printf("Advertised Device found: %s\n", advertisedDevice->toString().c_str());
        if (advertisedDevice->isAdvertisingService(NimBLEUUID("BAAD"))) {
            Serial.printf("Found Our Service\n");
            /** stop scan before connecting */
            NimBLEDevice::getScan()->stop();
            /** Save the device reference in a global for the client to use*/
            advDevice = advertisedDevice;
            /** Ready to connect now */
            doConnect = true;
        }
    }

    /** Callback to process the results of the completed scan or restart it */
    void onScanEnd(const NimBLEScanResults& results, int reason) override {
        Serial.printf("Scan Ended, reason: %d, device count: %d; Restarting scan\n", reason, results.getCount());
        NimBLEDevice::getScan()->start(scanTimeMs, false, true);
    }
} scanCallbacks;

/** Notification / Indication receiving handler callback */
void notifyCB(NimBLERemoteCharacteristic* pRemoteCharacteristic, uint8_t* pData, size_t length, bool isNotify) {
    std::string str  = (isNotify == true) ? "Notification" : "Indication";
    str             += " from ";
    str             += pRemoteCharacteristic->getClient()->getPeerAddress().toString();
    str             += ": Service = " + pRemoteCharacteristic->getRemoteService()->getUUID().toString();
    str             += ", Characteristic = " + pRemoteCharacteristic->getUUID().toString();
    str             += ", Value = " + std::string((char*)pData, length);
    Serial.printf("%s\n", str.c_str());

    // Decode pData and plot the decoded data
    Serial.printf("RX BYTES LENGTH: %d\n", length);

    // if the right amount of bytes were sent then decode the message
    // otherwise print an error message
    if (length == 12) {
      // Decode bytes in pData
      DataPoll incomingDataPoll(pData);
      Serial.println();
      Serial.printf(">timestamp: %d|t\n", incomingDataPoll.data.timestamp);
      Serial.printf(">accelX: %d\n", incomingDataPoll.data.accelX);
      Serial.printf(">accelY: %d\n", incomingDataPoll.data.accelY);
      Serial.printf(">accelZ: %d\n", incomingDataPoll.data.accelZ);

      // send object to the queue for being shared with the webserver
      if (xQueueSend(pollQueue, (void *)&incomingDataPoll, 0) != pdTRUE) {
        // if the queue is full then turn on the red led
        digitalWrite(LED_RED, LOW);
      } else {
        // otherwise turn it off
        digitalWrite(LED_RED, HIGH);
      }
    } else {
      Serial.printf("ERROR: Incorrect number of bytes in notification (expected: 12; actual: %d)", length);
    }
    // DataPoll incomingDataPoll(pData);

}

/** Handles the provisioning of clients and connects / interfaces with the server */
bool connectToServer() {
    NimBLEClient* pClient = nullptr;

    /** Check if we have a client we should reuse first **/
    if (NimBLEDevice::getCreatedClientCount()) {
        /**
         *  Special case when we already know this device, we send false as the
         *  second argument in connect() to prevent refreshing the service database.
         *  This saves considerable time and power.
         */
        pClient = NimBLEDevice::getClientByPeerAddress(advDevice->getAddress());
        if (pClient) {
            if (!pClient->connect(advDevice, false)) {
                Serial.printf("Reconnect failed\n");
                return false;
            }
            Serial.printf("Reconnected client\n");
        } else {
            /**
             *  We don't already have a client that knows this device,
             *  check for a client that is disconnected that we can use.
             */
            pClient = NimBLEDevice::getDisconnectedClient();
        }
    }

    /** No client to reuse? Create a new one. */
    if (!pClient) {
        if (NimBLEDevice::getCreatedClientCount() >= MYNEWT_VAL(BLE_MAX_CONNECTIONS)) {
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

        if (!pClient->connect(advDevice)) {
            /** Created a client but failed to connect, don't need to keep it as it has no data */
            NimBLEDevice::deleteClient(pClient);
            Serial.printf("Failed to connect, deleted client\n");
            return false;
        }
    }

    if (!pClient->isConnected()) {
        if (!pClient->connect(advDevice)) {
            Serial.printf("Failed to connect\n");
            return false;
        }
    }

    Serial.printf("Connected to: %s RSSI: %d\n", pClient->getPeerAddress().toString().c_str(), pClient->getRssi());

    /** Now we can read/write/subscribe the characteristics of the services we are interested in */
    NimBLERemoteService*        pSvc = nullptr;
    NimBLERemoteCharacteristic* pChr = nullptr;
    NimBLERemoteDescriptor*     pDsc = nullptr;

    pSvc = pClient->getService("DEAD");
    if (pSvc) {
        pChr = pSvc->getCharacteristic("BEEF");
    }

    if (pChr) {
        if (pChr->canRead()) {
            Serial.printf("%s Value: %s\n", pChr->getUUID().toString().c_str(), pChr->readValue().c_str());
        }

        if (pChr->canWrite()) {
            if (pChr->writeValue("Tasty")) {
                Serial.printf("Wrote new value to: %s\n", pChr->getUUID().toString().c_str());
            } else {
                pClient->disconnect();
                return false;
            }

            if (pChr->canRead()) {
                Serial.printf("The value of: %s is now: %s\n", pChr->getUUID().toString().c_str(), pChr->readValue().c_str());
            }
        }

        if (pChr->canNotify()) {
            if (!pChr->subscribe(true, notifyCB)) {
                pClient->disconnect();
                return false;
            }
        } else if (pChr->canIndicate()) {
            /** Send false as first argument to subscribe to indications instead of notifications */
            if (!pChr->subscribe(false, notifyCB)) {
                pClient->disconnect();
                return false;
            }
        }
    } else {
        Serial.printf("DEAD service not found.\n");
    }

    pSvc = pClient->getService("BAAD");
    if (pSvc) {
        pChr = pSvc->getCharacteristic("F00D");
        if (pChr) {
            if (pChr->canRead()) {
                Serial.printf("%s Value: %s\n", pChr->getUUID().toString().c_str(), pChr->readValue().c_str());
            }

            pDsc = pChr->getDescriptor(NimBLEUUID("C01D"));
            if (pDsc) {
                Serial.printf("Descriptor: %s  Value: %s\n", pDsc->getUUID().toString().c_str(), pDsc->readValue().c_str());
            }

            if (pChr->canWrite()) {
                if (pChr->writeValue("No tip!")) {
                    Serial.printf("Wrote new value to: %s\n", pChr->getUUID().toString().c_str());
                } else {
                    pClient->disconnect();
                    return false;
                }

                if (pChr->canRead()) {
                    Serial.printf("The value of: %s is now: %s\n",
                                  pChr->getUUID().toString().c_str(),
                                  pChr->readValue().c_str());
                }
            }

            if (pChr->canNotify()) {
                if (!pChr->subscribe(true, notifyCB)) {
                    pClient->disconnect();
                    return false;
                }
            } else if (pChr->canIndicate()) {
                /** Send false as first argument to subscribe to indications instead of notifications */
                if (!pChr->subscribe(false, notifyCB)) {
                    pClient->disconnect();
                    return false;
                }
            }
        }
    } else {
        Serial.printf("BAAD service not found.\n");
    }

    Serial.printf("Done with this device!\n");
    return true;
}

void setup() {
    Serial.begin(115200);
    pinMode(LED_BUILTIN, OUTPUT);
    pinMode(LED_RED, OUTPUT);
    pinMode(LED_GREEN, OUTPUT);
    pinMode(LED_BLUE, OUTPUT);

    Serial.printf("Starting NimBLE Client\n");

    pollQueue = xQueueCreate(POLL_QUEUE_LEN, sizeof(DataPoll));

    /** Initialize NimBLE and set the device name */
    NimBLEDevice::init("NimBLE-Client");

    /**
     * Set the IO capabilities of the device, each option will trigger a different pairing method.
     *  BLE_HS_IO_KEYBOARD_ONLY   - Passkey pairing
     *  BLE_HS_IO_DISPLAY_YESNO   - Numeric comparison pairing
     *  BLE_HS_IO_NO_INPUT_OUTPUT - DEFAULT setting - just works pairing
     */
    // NimBLEDevice::setSecurityIOCap(BLE_HS_IO_KEYBOARD_ONLY); // use passkey
    // NimBLEDevice::setSecurityIOCap(BLE_HS_IO_DISPLAY_YESNO); //use numeric comparison

    /**
     * 2 different ways to set security - both calls achieve the same result.
     *  no bonding, no man in the middle protection, BLE secure connections.
     *  These are the default values, only shown here for demonstration.
     */
    // NimBLEDevice::setSecurityAuth(false, false, true);
    // NimBLEDevice::setSecurityAuth(BLE_SM_PAIR_AUTHREQ_BOND | BLE_SM_PAIR_AUTHREQ_MITM | BLE_SM_PAIR_AUTHREQ_SC);

    /** Optional: set the transmit power */
    NimBLEDevice::setPower(3); /** 3dbm */
    NimBLEScan* pScan = NimBLEDevice::getScan();

    /** Set the callbacks to call when scan events occur, no duplicates */
    pScan->setScanCallbacks(&scanCallbacks, false);

    /** Set scan interval (how often) and window (how long) in milliseconds */
    pScan->setInterval(100);
    pScan->setWindow(100);

    /**
     * Active scan will gather scan response data from advertisers
     *  but will use more energy from both devices
     */
    pScan->setActiveScan(true);

    /** Start scanning for advertisers */
    pScan->start(scanTimeMs);
    Serial.printf("Scanning for peripherals\n");

    // TODO: Configure wifi 
    Serial.println("Wifi Setup");
    Serial.print("Connecting to ");
    Serial.println(SSID);
    WiFi.setHostname(HOSTNAME);
    WiFi.begin(SSID, PASSWORD);
    while (WiFi.status() != WL_CONNECTED)
    {
      // blinky and print .
      digitalWrite(LED_GREEN, LOW);
      vTaskDelay(pdMS_TO_TICKS(BLINK_RATE));
      digitalWrite(LED_GREEN, HIGH);
      vTaskDelay(pdMS_TO_TICKS(BLINK_RATE));

      Serial.print(".");
    }

    // start up the webserver
    server.begin();

}

void loop() {
    /** Loop here until we find a device we want to connect to */
    static DataPoll currDataPoll(0, 0, 0, 0);

    // delay(10);

    // Manage bluetooth:
    if (doConnect) {
        doConnect = false;
        /** Found a device we want to connect to, do it now */
        if (connectToServer()) {
            Serial.printf("Success! we should now be getting notifications, scanning for more!\n");
        } else {
            Serial.printf("Failed to connect, starting scan\n");
        }

        NimBLEDevice::getScan()->start(scanTimeMs, false, true);
    }

    // Manage webserver
    WiFiClient wifiClient = server.available();

    // if a client connects then prepare and send a response
    if (wifiClient) {

    Serial.println("New client");

    // When a new client connects: turn led on
    digitalWrite(LED_BUILTIN, HIGH);

    while (wifiClient.available()) {
      wifiClient.read();
    }

    // Create and format json document for sending values
    JsonDocument doc;
    JsonArray timestamps = doc["timestamps"].to<JsonArray>();

    // create array for sensor readings
    JsonArray sensors = doc["sensors"].to<JsonArray>();

    // create array entry for each sensor
    JsonArray sensors0 = sensors.add<JsonArray>();
    JsonArray sensors1 = sensors.add<JsonArray>();
    JsonArray sensors2 = sensors.add<JsonArray>();

    int counter = 0;
    // read in values from the queue
    // append them to their corresponding json arrays
    // increment the counter to avoid potential memory leak
    while ((xQueueReceive(pollQueue, (void *)&currDataPoll, 0) == pdTRUE) && counter < POLL_QUEUE_LEN) {
      timestamps.add(currDataPoll.data.timestamp);
      sensors0.add(currDataPoll.data.accelX);
      sensors1.add(currDataPoll.data.accelY);
      sensors2.add(currDataPoll.data.accelZ);

      counter++;
    }

    // Write response headers
    wifiClient.println("HTTP/1.0 200 OK");
    wifiClient.println("Content-Type: application/json");
    wifiClient.println("Connection: close");
    wifiClient.print("Content-Length: ");
    wifiClient.println(measureJson(doc));
    wifiClient.println();

    // Write buffered doc
    WriteBufferingStream bufferedWiFiClient(wifiClient, BUFFER_STREAM_SIZE);
    serializeJson(doc, bufferedWiFiClient);
    bufferedWiFiClient.flush();

    wifiClient.stop();

    // when the client disconnects: turn off the led
    digitalWrite(LED_BUILTIN, LOW);
  }
}