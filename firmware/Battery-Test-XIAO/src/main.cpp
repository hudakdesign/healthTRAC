//----------------------------------------------------------------------------------------------
// Board Library : Seeed nRF52 Borads 1.1.1
// Board Select  : Seeed nRF52 Borads / Seeed XIAO nRF52840 Sense
//----------------------------------------------------------------------------------------------
#include <Arduino.h>
#include <Adafruit_TinyUSB.h> // for Serial.print()
#include <bluefruit.h>

// Arduino15\packages\Seeeduino\hardware\nrf52\1.1.4\variants\Seeed_XIAO_nRF52840_Sense\variant.cpp
#define PIN_VBAT (32)        // D32 battery voltage
#define PIN_VBAT_ENABLE (14) // D14 LOW:read anable
#define PIN_HICHG (22)       // D22 charge current setting LOW:100mA HIGH:50mA
#define PIN_CHG (23)         // D23 charge indicatore LOW:charge HIGH:no charge

// Constants
const float FULL_BATTERY_VOLTAGE = 4.2;
const float DEAD_BATTERY_VOLTAGE = 2.75;
const int8_t TRANSMIT_POWER = 8;

// Globals
BLEService voltageService("b1eb8d99-226f-4d60-86bd-02e77ac18b3c");
BLECharacteristic voltageCharacteristic("12df161a-a7a7-4b7d-8a1b-70979458752c");

BLEDis bledis; // DIS (Device Information Service) helper class instance
BLEBas blebas; // BAS (BAttery Service) helper class instance

void setupBluetooth()
{
  Serial.println("Initializing bluetooth");
  Bluefruit.setName("Toothbrush Accelerometer");
  Bluefruit.setTxPower(TRANSMIT_POWER);
  Bluefruit.begin();

  Serial.println("Setting callbacks");
  // Bluefruit.Periph.setConnectCallback(NULL);
  // Bluefruit.Periph.setDisconnectCallback(NULL);

  Serial.println("Configuring DIS");
  bledis.setManufacturer("Seeed Studio");
  bledis.setModel("XIAO nRF52840 Sense");
  bledis.begin();

  Serial.println("Configuring BAS");
  blebas.begin();
  blebas.write(100);

  Serial.println("Configuring voltage service");
  voltageService.begin();

  voltageCharacteristic.setProperties(CHR_PROPS_NOTIFY);
  voltageCharacteristic.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  voltageCharacteristic.begin();

  Serial.println("Setting up advertising");
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();

  Bluefruit.Advertising.addService(voltageService);

  Bluefruit.setName("XIAO");
  Bluefruit.Advertising.addName();

  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);

  Serial.println("Bluetooth is advertising");
}

// // takes in reference to voltage reading
// // sets voltage characteristic to byte representation of voltage
// void updateVoltageCharacteristic(uint32_t* voltageReading) {
//   voltageCharacteristic.write((void *) voltageReading, sizeof(uint32_t));
// }

void setup()
{
  Serial.begin(115200);
  delay(2000);

  // set up leds
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);

  //  pinMode(PIN_VBAT, INPUT);         // unnecessary
  pinMode(PIN_VBAT_ENABLE, OUTPUT);
  pinMode(PIN_HICHG, OUTPUT);
  pinMode(PIN_CHG, INPUT);

  digitalWrite(PIN_VBAT_ENABLE, LOW); // VBAT read enable
  digitalWrite(PIN_HICHG, LOW);       // charge current 100mA

  // initialise ADC wireing_analog_nRF52.c:73
  analogReference(AR_DEFAULT); // default 0.6V*6=3.6V 　wireing_analog_nRF52.c:73
  analogReadResolution(12);    // wireing_analog_nRF52.c:39

  setupBluetooth();
}

void loop()
{
  // blink led rapidly to keep busy
  digitalWrite(LED_RED, !digitalRead(LED_RED));

  int vbatt = analogRead(PIN_VBAT);

  // TODO: only send notification every minute
  static uint32_t nextNotificationTimestamp = millis();

  if (millis() >= nextNotificationTimestamp)
  {
    // update next notification timestamp
    nextNotificationTimestamp += 60 * 1000; // 60 seconds

    // notify w/ voltage characteristic
    uint32_t testVoltage = vbatt;
    if (voltageCharacteristic.notify((void *)&testVoltage, sizeof(uint32_t)))
    {
      Serial.printf("voltage characteristic updated\n");
    }
    else
    {
      Serial.printf("ERROR: something went wrong with sending notification\n");
    }
  }
}
