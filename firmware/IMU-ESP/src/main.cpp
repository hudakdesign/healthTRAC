/**
 *  NimBLE_Stream_Client Example:
 *
 *  Demonstrates using NimBLEStreamClient to connect to a BLE GATT server
 *  and communicate using the Arduino Stream interface.
 *
 *  This allows you to use familiar methods like print(), println(),
 *  read(), and available() over BLE, similar to how you would use Serial.
 *
 *  This example connects to the NimBLE_Stream_Server example.
 *
 *  Created: November 2025
 *      Author: NimBLE-Arduino Contributors
 */

#include <Arduino.h>
#include <NimBLEDevice.h>
#include <DataPoll.h>

// Service and Characteristic UUIDs (must match the server)
#define SERVICE_UUID "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"

// Create the stream client instance
NimBLEStreamClient bleStream;

struct RxOverflowStats
{
  uint32_t droppedOld{0};
  uint32_t droppedNew{0};
};

RxOverflowStats g_rxOverflowStats;
uint32_t scanTime = 5000; // Scan duration in milliseconds

DataPoll myDataPoll = DataPoll(0, 0, 0, 0);

NimBLEStream::RxOverflowAction onRxOverflow(const uint8_t *data, size_t len, void *userArg)
{
  auto *stats = static_cast<RxOverflowStats *>(userArg);
  if (stats)
  {
    stats->droppedOld++;
  }

  // For status/telemetry streams, prioritize newest packets.
  (void)data;
  (void)len;
  return NimBLEStream::DROP_OLDER_DATA;
}

// Connection state variables
static bool doConnect = false;
static bool connected = false;
static const NimBLEAdvertisedDevice *pServerDevice = nullptr;
static NimBLEClient *pClient = nullptr;

/** Scan callbacks to find the server */
class ScanCallbacks : public NimBLEScanCallbacks
{
  void onResult(const NimBLEAdvertisedDevice *advertisedDevice) override
  {
    Serial.printf("Advertised Device: %s\n", advertisedDevice->toString().c_str());

    // Check if this device advertises our service
    if (advertisedDevice->isAdvertisingService(NimBLEUUID(SERVICE_UUID)))
    {
      Serial.println("Found our stream server!");
      pServerDevice = advertisedDevice;
      NimBLEDevice::getScan()->stop();
      doConnect = true;
    }
  }

  void onScanEnd(const NimBLEScanResults &results, int reason) override
  {
    Serial.println("Scan ended");
    if (!doConnect && !connected)
    {
      Serial.println("Server not found, restarting scan...");
      NimBLEDevice::getScan()->start(scanTime, false, true);
    }
  }
} scanCallbacks;

/** Client callbacks for connection/disconnection events */
class ClientCallbacks : public NimBLEClientCallbacks
{
  void onConnect(NimBLEClient *pClient) override
  {
    Serial.println("Connected to server");
    // Update connection parameters for better throughput
    pClient->updateConnParams(12, 24, 0, 200);
  }

  void onDisconnect(NimBLEClient *pClient, int reason) override
  {
    Serial.printf("Disconnected from server, reason: %d\n", reason);
    connected = false;
    bleStream.end();

    // Restart scanning
    Serial.println("Restarting scan...");
    NimBLEDevice::getScan()->start(scanTime, false, true);
  }
} clientCallbacks;

/** Connect to the BLE Server and set up the stream */
bool connectToServer()
{
  Serial.printf("Connecting to: %s\n", pServerDevice->getAddress().toString().c_str());

  // Create or reuse a client
  pClient = NimBLEDevice::getClientByPeerAddress(pServerDevice->getAddress());
  if (!pClient)
  {
    pClient = NimBLEDevice::createClient();
    if (!pClient)
    {
      Serial.println("Failed to create client");
      return false;
    }
    pClient->setClientCallbacks(&clientCallbacks, false);
    pClient->setConnectionParams(12, 24, 0, 200);
    pClient->setConnectTimeout(5000);
  }

  // Connect to the remote BLE Server
  if (!pClient->connect(pServerDevice))
  {
    Serial.println("Failed to connect to server");
    return false;
  }

  Serial.println("Connected! Discovering services...");

  // Get the service and characteristic
  NimBLERemoteService *pRemoteService = pClient->getService(SERVICE_UUID);
  if (!pRemoteService)
  {
    Serial.println("Failed to find our service UUID");
    pClient->disconnect();
    return false;
  }
  Serial.println("Found the stream service");

  NimBLERemoteCharacteristic *pRemoteCharacteristic = pRemoteService->getCharacteristic(CHARACTERISTIC_UUID);
  if (!pRemoteCharacteristic)
  {
    Serial.println("Failed to find our characteristic UUID");
    pClient->disconnect();
    return false;
  }
  Serial.println("Found the stream characteristic");

  /**
   * Initialize the stream client with the remote characteristic
   * subscribeNotify=true means we'll receive notifications in the RX buffer
   */
  if (!bleStream.begin(pRemoteCharacteristic, true))
  {
    Serial.println("Failed to initialize BLE stream!");
    pClient->disconnect();
    return false;
  }

  bleStream.setRxOverflowCallback(onRxOverflow, &g_rxOverflowStats);

  Serial.println("BLE Stream initialized successfully!");
  connected = true;
  return true;
}

void blinkAndWait(int numSeconds)
{
  pinMode(LED_RED, OUTPUT);

  for (int i = 0; i < numSeconds; i++)
  {
    digitalWrite(LED_RED, LOW);
    delay(500);
    digitalWrite(LED_RED, HIGH);
    delay(500);
  }
}

void setup()
{
  Serial.begin(115200);
  blinkAndWait(10);

  Serial.println("Starting NimBLE Stream Client");

  /** Initialize NimBLE */
  NimBLEDevice::init("NimBLE-StreamClient");

  /**
   * Create the BLE scan instance and set callbacks
   * Configure scan parameters
   */
  NimBLEScan *pScan = NimBLEDevice::getScan();
  pScan->setScanCallbacks(&scanCallbacks, false);
  pScan->setActiveScan(true);

  /** Start scanning for the server */
  Serial.println("Scanning for BLE Stream Server...");
  pScan->start(scanTime, false, true);
}

void loop()
{
  static uint32_t lastDroppedOld = 0;
  static uint32_t lastDroppedNew = 0;
  if (g_rxOverflowStats.droppedOld != lastDroppedOld || g_rxOverflowStats.droppedNew != lastDroppedNew)
  {
    lastDroppedOld = g_rxOverflowStats.droppedOld;
    lastDroppedNew = g_rxOverflowStats.droppedNew;
    Serial.printf("RX overflow handled (drop-old=%lu, drop-new=%lu)\n", lastDroppedOld, lastDroppedNew);
  }

  // If we found a server, try to connect
  if (doConnect)
  {
    doConnect = false;
    if (connectToServer())
    {
      Serial.println("Stream ready for communication!");
    }
    else
    {
      Serial.println("Failed to connect to server, restarting scan...");
      pServerDevice = nullptr;
      NimBLEDevice::getScan()->start(scanTime, false, true);
    }
  }

  // If we're connected, demonstrate the stream interface
  if (connected && bleStream)
  {
    // Check if we received any data from the server
    if (bleStream.available())
    {
      // Read bytes from stream until buffer is full
      // When buffer is full, wait for a newline before
      // decoding the buffer and printing the contents

      // FIXME: Bug likely involving encoding / decoding after stream
      // Timestamp decodes but is wrong, accel values are all zero

      char encodedDataBuffer[sizeof(myDataPoll.data)];

      // While the stream is available and within the buffer
      int i = 0;
      while (bleStream.available() && (i < sizeof(encodedDataBuffer) / sizeof(char)))
      {
        char c = bleStream.read();
        encodedDataBuffer[i] = c;
        i++;
      }

      while (bleStream.available() && (bleStream.read() != '\n')) {
        // Throw out stream values before and including the newline
        // after the buffer fills
      }

      // Decode the data buffer into a DataPoll object
      myDataPoll = DataPoll((char *)&encodedDataBuffer);

      // Print out the contents
      Serial.print(">timestamp:");
      Serial.print(myDataPoll.data.timestamp);
      Serial.println("|t");

      Serial.print(">accelX: ");
      Serial.println(myDataPoll.data.accelX);

      Serial.print(">accelY: ");
      Serial.println(myDataPoll.data.accelY);

      Serial.print(">accelZ: ");
      Serial.println(myDataPoll.data.accelZ);
    }
  }

  delay(10);
}
