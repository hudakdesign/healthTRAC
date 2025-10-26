#include <Arduino.h>
#include <LSM6DS3.h>
#include <Wire.h>
#include <bluefruit.h>

// IMU
LSM6DS3 imu(I2C_MODE, 0x6A);
#define SAMPLE_RATE_HZ 20
const unsigned long SAMPLE_PERIOD_MS = 1000 / SAMPLE_RATE_HZ;

// BLE
BLEService customService = BLEService("180F");
BLECharacteristic dataChar = BLECharacteristic("2A19");

unsigned long lastNotify = 0;
unsigned long lastSample = 0;

void setup() {
  Serial.begin(115200);
  delay(5000);

  if (imu.begin() != 0) {
    Serial.println("IMU init failed");
    while(1);
  }
  
  Bluefruit.begin();
  Bluefruit.setTxPower(4);
  Bluefruit.setName("XIAO-TB");
  
  // BLE setup
  customService.begin();
  dataChar.setProperties(CHR_PROPS_READ | CHR_PROPS_NOTIFY);
  dataChar.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  dataChar.setFixedLen(12);
  dataChar.begin();

  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(customService);
  Bluefruit.Advertising.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(160, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);

  Serial.println("BLE advertising started");
}

void loop() {
  static unsigned long lastPrint = 0;
  unsigned long now = millis();

  if (now - lastSample >= SAMPLE_PERIOD_MS) {  // send every 200ms
    // Read accelerometer data

    float x = imu.readFloatAccelX();
    float y = imu.readFloatAccelY();
    float z = imu.readFloatAccelZ();

    if (Bluefruit.connected()) {
      uint8_t buffer[12];
      memcpy(buffer, &x, 4);
      memcpy(buffer + 4, &y, 4);
      memcpy(buffer + 8, &z, 4);
      dataChar.notify(buffer, 12);
    }

    // Print to serial
    Serial.print("Accel: ");
    Serial.print(x, 3);
    Serial.print(", ");
    Serial.print(y, 3);
    Serial.print(", ");
    Serial.println(z, 3);

    lastSample = now;
    }
}
