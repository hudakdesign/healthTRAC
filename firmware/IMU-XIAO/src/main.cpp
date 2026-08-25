#include <Arduino.h>
#include <Adafruit_TinyUSB.h>
#include <bluefruit.h>
#include <LSM6DS3.h>
#include <DataPoll.h>

// sleep related includes
#include <Adafruit_SPIFlash.h>
#include <LSM6DS3.h>
#include <nrf52840.h>
#include <Wire.h>

// Constants
const TickType_t POLL_FREQUENCY = pdMS_TO_TICKS(10);
const int INACTIVITY_THRESHOLD = 10;
const int INACTIVE_POLLS_BEFORE_SLEEP = 1000;

// Globals
BLEService imuService("88fc1bd0-8154-454a-b2bd-fe4cc329d1d5");
BLECharacteristic imuCharacteristic("547af7ac-aa68-47eb-a0df-d827e39615bf");
BLEDis bledis;

LSM6DS3 myImu;

Adafruit_FlashTransport_QSPI flashTransport;

// Helpers
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
  if (myImu.begin() == 0) {
    Serial.println("Initialize imu: success");
  } else {
    Serial.println("Initialize imu: ERROR");
  }
}

bool checkForInactivity(DataPoll newDataPoll) {
  static DataPoll prevDataPoll(0, 0, 0, 0); // previous starts with zeroes for first interation
  static int inactivityCounter = 0; // counts how many polls the imu has been inactive for

  // check difference between current and previous accel values
  int accelXDifference = abs(newDataPoll.data.accelX - prevDataPoll.data.accelX);
  int accelYDifference = abs(newDataPoll.data.accelY - prevDataPoll.data.accelY);
  int accelZDifference = abs(newDataPoll.data.accelZ - prevDataPoll.data.accelZ);

  // Serial.printf("Prev accel: {%d, %d, %d}\n", prevDataPoll.data.accelX, prevDataPoll.data.accelY, prevDataPoll.data.accelZ);
  // Serial.printf("New  accel: {%d, %d, %d}\n", newDataPoll.data.accelX, newDataPoll.data.accelY, newDataPoll.data.accelZ);

  // update previous to current
  prevDataPoll = newDataPoll;

  // Serial.printf("Accel differences: {%d, %d, %d}\n", accelXDifference, accelYDifference, accelZDifference);

  // if the accel values are close enough (within threshold)
  // then the imu probably isnt moving
  // increment the a counter to indicate that it isnt moving
  // if the accel values arent close enough (out of threshold)
  // reset the counter
  bool inThreshold = false;
  if (accelXDifference < INACTIVITY_THRESHOLD) {
    inThreshold = true;
  }
  if (accelYDifference < INACTIVITY_THRESHOLD) {
    inThreshold = true;
  }
  if (accelZDifference < INACTIVITY_THRESHOLD) {
    inThreshold = true;
  }

  // if its in the threshold then increment
  if (inThreshold) {
    inactivityCounter++;
  } else {
    // if it isnt then reset the counter
    inactivityCounter = 0;
  }
  
  // if the counter reaches a certain number then return true
  if (inactivityCounter >= INACTIVE_POLLS_BEFORE_SLEEP) {
    // Serial.print("currently inactive. polls inactive: ");
    // Serial.println(inactivityCounter);
    return true;
  }

  // otherwise return false
  // Serial.print("currently active. polls inactive: ");
  // Serial.println(inactivityCounter);
  return false;
}

void QSPIF_sleep(void) {
  flashTransport.begin();
  flashTransport.runCommand(0xB9);
  flashTransport.end();
}

void setupWakeUpInterrupt() {
  myImu.settings.gyroEnabled = 0;
  myImu.settings.accelEnabled = 0;
  myImu.begin();

  myImu.writeRegister(LSM6DS3_ACC_GYRO_WAKE_UP_DUR, 0x00); // No duration
  myImu.writeRegister(LSM6DS3_ACC_GYRO_WAKE_UP_THS, 0x02); // Set wake-up threshold
  myImu.writeRegister(LSM6DS3_ACC_GYRO_TAP_CFG1, 0x80);    // Enable interrupts and apply slope filter; latch mode disabled
  myImu.writeRegister(LSM6DS3_ACC_GYRO_CTRL1_XL, 0x70);    // Turn on the accelerometer
                                                           // ODR_XL = 833 Hz, FS_XL = ±2 g
  delay(4);                                                // Delay time per application note
  myImu.writeRegister(LSM6DS3_ACC_GYRO_CTRL1_XL, 0xB0);    // ODR_XL = 1.6 Hz
  myImu.writeRegister(LSM6DS3_ACC_GYRO_CTRL6_G, 0x10);     // High-performance operating mode disabled for accelerometer
  myImu.writeRegister(LSM6DS3_ACC_GYRO_MD1_CFG, 0x20);     // Wake-up interrupt driven to INT1 pin

  // Set up the sense mechanism to generate the DETECT signal to wake from system_off
  // No need to attach a handler, if just waking with the GPIO input.
	pinMode(PIN_LSM6DS3TR_C_INT1, INPUT_PULLDOWN_SENSE);

  return;
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
  // vTaskDelayUntil time to poll again
  static TickType_t lastWakeTime = xTaskGetTickCount();
  vTaskDelayUntil(&lastWakeTime, POLL_FREQUENCY);
  
  // collect new poll data
  uint32_t timestamp = millis();
  int16_t accelX = myImu.readRawAccelX();
  int16_t accelY = myImu.readRawAccelY();
  int16_t accelZ = myImu.readRawAccelZ();

  // encode new poll data
  DataPoll dataPoll(timestamp, accelX, accelY, accelZ);
  uint8_t encodedDataBuffer[sizeof(DataPoll)];
  dataPoll.encodeDataPoll((uint8_t *)&encodedDataBuffer);

  // TODO: Update this logic. Currently polls are being missed because it is taking too long to notify
  if (Bluefruit.connected()) {

    // update characteristic with encoded data
    // notify client
    if (imuCharacteristic.notify(encodedDataBuffer, sizeof(encodedDataBuffer))) {
      Serial.println("imu characteristic updated");
    } else {
      Serial.println("ERROR: something went wrong with sending notification");
    }
  }

  // check for inactivity
  if (checkForInactivity(dataPoll)) {
    // if inactive then setup the wake interrupt
    setupWakeUpInterrupt();

    // make sure all leds are off
    digitalWrite(LED_RED, HIGH);
    digitalWrite(LED_GREEN, HIGH);
    digitalWrite(LED_BLUE, HIGH);

    // and shutdown
    NRF_POWER->SYSTEMOFF = 1;
  }
}