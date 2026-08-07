#include <Arduino.h>
#include <NimBLEDevice.h>
#include <LSM6DS3.h>
#include <DataPoll.h>

// Constants
const char *DEVICE_NAME = "IMU-XIAO";
const char *SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E";
const char *CHARACTERISTIC_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E";
const int8_t POWER_LEVEL = 8;
const TickType_t POLL_FREQUENCY = pdMS_TO_TICKS(10);

// Globals
NimBLEStreamServer bleStream;
LSM6DS3 myImu(I2C_MODE, 0x6A);

struct RxOverflowStats
{
  uint32_t droppedOld{0};
  uint32_t droppedNew{0};
} g_rxOverflowStats;

// Callback declarations
// overflow callback
NimBLEStream::RxOverflowAction onRxOverflow(const uint8_t *data, size_t len, void *userArg)
{
  auto *stats = static_cast<RxOverflowStats *>(userArg);
  if (stats)
  {
    stats->droppedOld++;
  }

  // keep newest bytes
  (void)data;
  (void)len;
  return NimBLEStream::DROP_OLDER_DATA;
}

// server callbacks
class ServerCallbacks : public NimBLEServerCallbacks
{
  void onConnect(NimBLEServer *pServer, NimBLEConnInfo &connInfo) override
  {
    Serial.printf("Client connected: %s\n", connInfo.getAddress().toString().c_str());
    // TEST: update connection parameters for better throughput
    pServer->updateConnParams(connInfo.getConnHandle(), 12, 24, 0, 200);
  }

  void onDisconnect(NimBLEServer *pServer, NimBLEConnInfo &connInfo, int reason) override
  {
    Serial.printf("Client disconnected: (reason: %d) restarting advertising\n", reason);
    NimBLEDevice::startAdvertising();
  }

  void onMTUChange(uint16_t MTU, NimBLEConnInfo &connInfo) override
  {
    Serial.printf("MTU updated: %u for connection ID: %u\n", MTU, connInfo.getConnHandle());
  }

} serverCallbacks;

void setup()
{
  int errorCount = 0;

  // initialize serial
  Serial.begin(115200);
  delay(2000);
  Serial.println("IMU-XIAO Setup");

  // initialize imu
  if (myImu.begin() == 0)
  {
    Serial.println("Initialize IMU: success");
  }
  else
  {
    Serial.println("Initialize IMU: ERROR");
    errorCount++;
  }

  // initialize NimBLE
  NimBLEDevice::init(DEVICE_NAME);

  // set power level
  if (NimBLEDevice::setPower(POWER_LEVEL))
  {
    Serial.println("Set Power Level: success");
  }
  else
  {
    Serial.println("Set Power Level: ERROR");
    errorCount++;
  }

  // create ble server and set its callbacks
  NimBLEServer *pServer = NimBLEDevice::createServer();
  pServer->setCallbacks(&serverCallbacks);

  // intialize stream server and set overflow callback
  if (bleStream.begin(NimBLEUUID(SERVICE_UUID),
                      NimBLEUUID(CHARACTERISTIC_UUID),
                      1024,
                      1024,
                      false))
  {
    Serial.println("Create BLE Stream: success");
  }
  else
  {
    Serial.println("Create BLE Stream: ERROR");
    errorCount++;
  }

  // create advertising instance
  NimBLEAdvertising *pAdvertising = NimBLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setName(DEVICE_NAME);
  pAdvertising->enableScanResponse(true);
  pAdvertising->start();

  Serial.printf("Setup completed with %d detected errors\n", errorCount);
}

void loop()
{
  // wait until time for next poll
  // set last wake time for polling
  static TickType_t lastWakeTime = xTaskGetTickCount();
  vTaskDelayUntil(&lastWakeTime, POLL_FREQUENCY);

  // handle receive buffer overflows
  static uint32_t lastDroppedOld = 0;
  static uint32_t lastDroppedNew = 0;
  if (g_rxOverflowStats.droppedOld != lastDroppedOld || g_rxOverflowStats.droppedNew != lastDroppedNew)
  {
    lastDroppedOld = g_rxOverflowStats.droppedOld;
    lastDroppedNew = g_rxOverflowStats.droppedNew;
    Serial.printf("RX overflow handled (drop-old=%lu, drop-new=%lu)\n", lastDroppedOld, lastDroppedNew);
  }

  // check if a client is subscribed {
  if (bleStream.ready())
  {
    // populate DataPoll with current sensor data
    DataPoll dataPoll;
    dataPoll.timestamp = millis();
    dataPoll.accelX = myImu.readFloatAccelX();
    dataPoll.accelY = myImu.readFloatAccelY();
    dataPoll.accelZ = myImu.readFloatAccelZ();

    // FIXME: for now just send as strings to be printed
    bleStream.print(">timestamp:");
    bleStream.print(dataPoll.timestamp);
    bleStream.println("|t");

    bleStream.print(">accelX:");
    bleStream.println(dataPoll.accelX, 3);
    bleStream.print(">accelY:");
    bleStream.println(dataPoll.accelY, 3);
    bleStream.print(">accelZ:");
    bleStream.println(dataPoll.accelZ, 3);

    // TODO: Convert to byte array
    // // convert to array of bytes

    // // print byte array over bleStream }
  }
}