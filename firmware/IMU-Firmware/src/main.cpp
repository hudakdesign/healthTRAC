#include <Arduino.h>

#include "LSM6DS3.h"

// Create instance of imu class
LSM6DS3 myIMU(I2C_MODE, 0x6A);

// put function declarations here:
int plotImuData();

void setup() {
  // Initialize serial
  Serial.begin(115200);

  // give some time to initialize
  delay(2000);
}

void loop() {
  // put your main code here, to run repeatedly:
  plotImuData();
}

// put function definitions here:
int plotImuData() {
  static float currentXAccel, currentYAccel, currentZAccel = 0;

  currentXAccel = myIMU.readFloatAccelX();
  currentYAccel = myIMU.readFloatAccelY();
  currentZAccel = myIMU.readFloatAccelZ();

  Serial.println(">x_accel:" + (String)currentXAccel);
  Serial.println(">y_accel:" + (String)currentYAccel);
  Serial.println(">z_accel:" + (String)currentZAccel);
}