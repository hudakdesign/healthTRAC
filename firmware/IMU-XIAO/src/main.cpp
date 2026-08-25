#include <Arduino.h>
#include <Adafruit_TinyUSB.h>
#include <bluefruit.h>
#include <LSM6DS3.h>
#include <DataPoll.h>

// Globals
BLEService imuService("88fc1bd0-8154-454a-b2bd-fe4cc329d1d5");
BLECharacteristic imuCharacteristic("547af7ac-aa68-47eb-a0df-d827e39615bf");
BLEDis bledis;

LSM6DS3 myImu;

// Helpers
bool checkForInactivity(DataPoll newDataPoll) {
  return false;
}

void setupBluetooth() {
  Serial.println("Starting bluetooth");
  Bluefruit.begin();

  // set connect callbacks
  // TODO: add actual callbacks
  Bluefruit.Periph.setConnectCallback(NULL);
  Bluefruit.Periph.setDisconnectCallback(NULL);

  // configure device information
  bledis.setManufacturer("Seeed Studio");
  bledis.setModel("XIAO nRF52840-Sense");
  bledis.begin();

  Serial.println("Starting IMU (bluetooth) service");
  imuService.begin();

  // configure the characteristic
  imuCharacteristic.setProperties(CHR_PROPS_NOTIFY);
  imuCharacteristic.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  imuCharacteristic.begin();

  // configure and start advertising
  // advertising packet
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();

  // include imu service uuid
  Bluefruit.Advertising.addService(imuService);

  Bluefruit.setName("XIAO");
  Bluefruit.Advertising.addName();

  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);
}

void setupIMU() {
  myImu.begin();
}

void setup() {
  // serial:
  Serial.begin(115200);

  // leds:
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);

  // wait for serial to initialize
  digitalWrite(LED_RED, LOW);
  delay(1000);
  digitalWrite(LED_RED, HIGH);
  digitalWrite(LED_GREEN, LOW);
  delay(1000);
  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_BLUE, LOW);
  delay(1000);
  digitalWrite(LED_BLUE, HIGH);
  Serial.println("---IMU Server---");

  // bluefruit
  setupBluetooth();

  // imu
  setupIMU();

  // indicate that setup finished
  Serial.println("Finished setup");
}

void loop() {
  // DEBUG BEGIN
  delay(1000);
  if (Bluefruit.connected()) {
    uint8_t imuData[12] = {0x01, 0x02, 0x03, 0x04,
                           0x05, 0x06, 0x07, 0x08,
                           0x09, 0x0A, 0x0B, 0x0C};
    if (imuCharacteristic.notify(imuData, sizeof(imuData))) {
      Serial.println("imu Characteristic updated");
    } else {
      Serial.println("ERROR: something went wrong with sending notification");
    }
  }
  // DEBUG END

  // vTaskDelayUntil time to poll again
  
  // collect new poll data
  // encode new poll data
  // update characteristic with encoded data
  // notify client

  // check for inactivity
  // if inactive then setup the wake interrupt
  // and shutdown
}