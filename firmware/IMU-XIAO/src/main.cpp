#include <Arduino.h>
#include <NimBLEDevice.h>
#include <LSM6DS3.h>
#include <DataPoll.h>

// Constants
const char *SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E";
const char *CHARACTERISTIC_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E";

// Globals
NimBLEStreamServer bleStream;
LSM6DS3 myImu(I2C_MODE, 0x6A);

struct RxOverflowStats
{
  uint32_t droppedOld{0};
  uint32_t droppedNew{0};
} g_rxOverflowStats;

// Callback declarations
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

void setup()
{
  // initialize serial

  // initialize imu

  // initialize NimBLE

  // set power level

  // create ble server and set its callbacks

  // intialize stream server and set overflow callback

  // create advertising instance
}

void loop()
{
  // wait until time for next poll

  // handle receive buffer overflows

  // check if a client is subscribed {

  // populate DataPoll with current sensor data

  // convert to array of bytes

  // print byte array over bleStream }
}