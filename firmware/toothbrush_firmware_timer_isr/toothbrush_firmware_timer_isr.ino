#include <Arduino.h>
#include <LSM6DS3.h>
#include <Wire.h>
#include <bluefruit.h>
#include <nrf_gpio.h>
#include <nrf_power.h>
#include <nrf_timer.h>

// ============================================================================
// TIMER INTERRUPT TOOTHBRUSH FIRMWARE v1
// ============================================================================
// Key features:
// - Hardware timer fires every 20ms for GUARANTEED 50 Hz sampling
// - Timer ISR reads IMU and stores to buffer (~500μs)
// - Main loop handles BLE sending (can block without affecting sampling)
// - Buffer drains continuously during recording when BLE is ready
// - Full drain until buffer empty after recording stops
// ============================================================================

LSM6DS3 imu(I2C_MODE, 0x6A);

// CORRECT PIN: INT1 is connected to P0.11 = Arduino digital pin 18
#define IMU_INT1_PIN 18

// RGB LED pins (common anode: LOW=ON, HIGH=OFF)
#define LED_RED 11
#define LED_GREEN 13
#define LED_BLUE 12

// LSM6DS3 Registers
#define LSM6DS3_ACC_GYRO_TAP_CFG 0x58
#define LSM6DS3_ACC_GYRO_WAKE_UP_THS 0x5B
#define LSM6DS3_ACC_GYRO_WAKE_UP_DUR 0x5C
#define LSM6DS3_ACC_GYRO_MD1_CFG 0x5E
#define LSM6DS3_ACC_GYRO_WAKE_UP_SRC 0x1B

// Thresholds
#define MOTION_THRESHOLD_G 0.1
#define IDLE_TIMEOUT_MS 10000                      // 10 seconds
#define SAMPLE_RATE_HZ 50                          // 50 Hz for jerk analysis
#define SAMPLE_INTERVAL_MS (1000 / SAMPLE_RATE_HZ) // 20ms

// Timer configuration
// Using TIMER3 (TIMER0/1/2 used by system)
#define SAMPLE_TIMER NRF_TIMER3
#define SAMPLE_TIMER_IRQn TIMER3_IRQn
#define SAMPLE_TIMER_IRQHandler TIMER3_IRQHandler

// Battery
#ifndef VBAT_ENABLE
#define VBAT_ENABLE 14
#endif
#ifndef PIN_VBAT
#define PIN_VBAT 31
#endif

#define BATTERY_READ_INTERVAL_MS 5000
unsigned long lastBatteryReadTime = 0;
float batteryVoltage = 0.0;
uint8_t batteryPercent = 0;

// Buffer - 6000 samples = 2 min at 50 Hz (96 KB RAM)
#define MAX_SAMPLES 6000
struct Sample {
  uint64_t timestamp_local;
  int16_t accel_x;
  int16_t accel_y;
  int16_t accel_z;
  uint16_t seq;
} __attribute__((packed));

Sample sampleBuffer[MAX_SAMPLES];
volatile uint16_t bufferHead = 0;
volatile uint16_t bufferTail = 0;
volatile uint16_t bufferCount = 0;
volatile uint16_t sequenceNumber = 0;

// Motion tracking (accessed from ISR)
volatile unsigned long lastMotionTime = 0;
volatile bool timerRunning = false;

// State
enum State { IDLE, RECORDING };
volatile State currentState = IDLE;

// BLE
BLEService toothbrushService = BLEService("180F");
BLECharacteristic timeSyncChar = BLECharacteristic("2A1A");
BLECharacteristic dataChar = BLECharacteristic("2A19");
BLECharacteristic ackChar = BLECharacteristic("2A1B");
BLECharacteristic batteryChar = BLECharacteristic("2A1C");
uint16_t activeConnHandle = BLE_CONN_HANDLE_INVALID;
bool bleInitialized = false;

// Interrupt
volatile bool motionInterruptFired = false;

// Debug
unsigned long lastDebugTime = 0;

// LED Helper functions
void setLEDOff() {
  digitalWrite(LED_RED, HIGH);
  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_BLUE, HIGH);
}

void setLEDRecording() {
  digitalWrite(LED_RED, LOW);
  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_BLUE, HIGH);
}

void setLEDConnected() { digitalWrite(LED_BLUE, LOW); }

void setLEDDisconnected() { digitalWrite(LED_BLUE, HIGH); }

// ============================================================================
// FORWARD DECLARATIONS
// ============================================================================
void connectCallback(uint16_t conn_handle);
void disconnectCallback(uint16_t conn_handle, uint8_t reason);
void timeSyncCallback(uint16_t conn_handle, BLECharacteristic *chr,
                      uint8_t *data, uint16_t len);
void ackCallback(uint16_t conn_handle, BLECharacteristic *chr, uint8_t *data,
                 uint16_t len);
bool sendNextSample();
void readBatteryVoltage();
void sendBatteryStatus();
void handleIdle(unsigned long now);
void handleRecording(unsigned long now);
void startRecordingMode();
void stopRecordingMode();
void configureWakeInterrupt();
void clearIMUInterrupt();
void enterDeepSleep();
void motionISR();
bool isUSBConnected();
void startSampleTimer();
void stopSampleTimer();

// ============================================================================
// TIMER INTERRUPT HANDLER - GUARANTEED 50 Hz SAMPLING
// ============================================================================

extern "C" void TIMER3_IRQHandler(void) {
  if (SAMPLE_TIMER->EVENTS_COMPARE[0]) {
    SAMPLE_TIMER->EVENTS_COMPARE[0] = 0; // Clear event

    if (!timerRunning)
      return;

    // Quick sample - must be fast (< 1ms)
    unsigned long now = millis();

    // Read accelerometer
    float x = imu.readFloatAccelX();
    float y = imu.readFloatAccelY();
    float z = imu.readFloatAccelZ();
    float magnitude = sqrt(x * x + y * y + z * z);

    // Store in buffer
    Sample *sample = &sampleBuffer[bufferHead];
    sample->timestamp_local = (uint64_t)now;
    sample->accel_x = (int16_t)(x * 8192.0);
    sample->accel_y = (int16_t)(y * 8192.0);
    sample->accel_z = (int16_t)(z * 8192.0);
    sample->seq = sequenceNumber++;

    bufferHead = (bufferHead + 1) % MAX_SAMPLES;
    if (bufferCount < MAX_SAMPLES) {
      bufferCount++;
    } else {
      bufferTail = (bufferTail + 1) % MAX_SAMPLES; // Overwrite oldest
    }

    // Update motion time
    if (magnitude > (1.0 + MOTION_THRESHOLD_G) ||
        magnitude < (1.0 - MOTION_THRESHOLD_G)) {
      lastMotionTime = now;
    }
  }
}

void startSampleTimer() {
  // Configure TIMER3 for 50 Hz (20ms) interrupt
  SAMPLE_TIMER->MODE = TIMER_MODE_MODE_Timer;
  SAMPLE_TIMER->BITMODE = TIMER_BITMODE_BITMODE_32Bit;
  SAMPLE_TIMER->PRESCALER = 4; // 16 MHz / 2^4 = 1 MHz

  // 20ms = 20000 ticks at 1 MHz
  SAMPLE_TIMER->CC[0] = 20000;

  // Enable compare interrupt and auto-clear
  SAMPLE_TIMER->SHORTS = TIMER_SHORTS_COMPARE0_CLEAR_Msk;
  SAMPLE_TIMER->INTENSET = TIMER_INTENSET_COMPARE0_Msk;

  // Enable IRQ
  NVIC_SetPriority(SAMPLE_TIMER_IRQn,
                   2); // Higher than BLE (lower number = higher priority)
  NVIC_EnableIRQ(SAMPLE_TIMER_IRQn);

  timerRunning = true;
  SAMPLE_TIMER->TASKS_START = 1;

  Serial.println("✓ Sample timer started (50 Hz)");
}

void stopSampleTimer() {
  timerRunning = false;
  SAMPLE_TIMER->TASKS_STOP = 1;
  SAMPLE_TIMER->TASKS_CLEAR = 1;
  NVIC_DisableIRQ(SAMPLE_TIMER_IRQn);

  Serial.println("✓ Sample timer stopped");
}

// ============================================================================
// USB DETECTION
// ============================================================================

bool isUSBConnected() {
  return (NRF_POWER->USBREGSTATUS & POWER_USBREGSTATUS_VBUSDETECT_Msk) != 0;
}

// ============================================================================
// MOTION ISR
// ============================================================================

void motionISR() { motionInterruptFired = true; }

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Initialize RGB LED pins
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);
  setLEDOff();

  // Check power source EARLY
  bool usbConnected =
      (NRF_POWER->USBREGSTATUS & POWER_USBREGSTATUS_VBUSDETECT_Msk) != 0;

  // Safety blink only on USB
  if (usbConnected) {
    for (int i = 0; i < 30; i++) {
      digitalWrite(LED_GREEN, i % 2);
      delay(100);
    }
    setLEDOff();
  } else {
    setLEDRecording();
    delay(100);
    setLEDOff();
  }

  Serial.begin(115200);
  if (usbConnected) {
    unsigned long startTime = millis();
    while (!Serial && (millis() - startTime < 3000)) {
      delay(100);
    }
    delay(500);
  }

  Serial.println("========================================");
  Serial.println("Health TRAC - Timer ISR v1");
  Serial.println("XIAO nRF52840 Sense");
  Serial.println("Guaranteed 50 Hz via hardware timer");
  Serial.println("========================================");

  Serial.print("Power: ");
  Serial.println(usbConnected ? "USB (debug mode)" : "BATTERY (deep sleep)");

  // Check wake reason
  uint32_t resetReason = NRF_POWER->RESETREAS;
  NRF_POWER->RESETREAS = 0xFFFFFFFF;

  bool wokeFromGPIO = (resetReason & POWER_RESETREAS_OFF_Msk) != 0;
  Serial.print("Wake: ");
  if (wokeFromGPIO)
    Serial.println("Motion interrupt ✓");
  else if (resetReason == 0)
    Serial.println("Power-on");
  else
    Serial.println("Reset");

  // Initialize IMU
  if (imu.begin() != 0) {
    Serial.println("ERROR: IMU init failed");
    while (1)
      delay(100);
  }
  Serial.println("✓ IMU initialized");

  // Battery
  pinMode(VBAT_ENABLE, OUTPUT);
  digitalWrite(VBAT_ENABLE, LOW);
  analogReference(AR_DEFAULT);
  analogReadResolution(12);
  readBatteryVoltage();
  Serial.print("✓ Battery: ");
  Serial.print(batteryVoltage);
  Serial.print("V (");
  Serial.print(batteryPercent);
  Serial.println("%)");

  // Configure wake interrupt
  configureWakeInterrupt();

  // Setup INT1 pin
  pinMode(IMU_INT1_PIN, INPUT_PULLDOWN);
  clearIMUInterrupt();
  delay(100);

  // Attach motion interrupt
  attachInterrupt(digitalPinToInterrupt(IMU_INT1_PIN), motionISR, RISING);
  motionInterruptFired = false;
  Serial.println("✓ Interrupt ready");

  // Decide startup behavior
  if (wokeFromGPIO) {
    Serial.println("→ Motion wake - starting RECORDING");
    setLEDRecording();
    startRecordingMode();
    currentState = RECORDING;
  } else if (!usbConnected) {
    Serial.println("→ Battery mode - checking for motion...");

    bool motionDetected = false;
    for (int i = 0; i < 20 && !motionDetected; i++) {
      float x = imu.readFloatAccelX();
      float y = imu.readFloatAccelY();
      float z = imu.readFloatAccelZ();
      float magnitude = sqrt(x * x + y * y + z * z);

      if (magnitude > (1.0 + MOTION_THRESHOLD_G) ||
          magnitude < (1.0 - MOTION_THRESHOLD_G)) {
        motionDetected = true;
        Serial.print("  Motion detected: ");
        Serial.print(magnitude, 2);
        Serial.println("g");
      } else {
        delay(100);
      }
    }

    if (motionDetected) {
      Serial.println("→ Motion on boot - starting RECORDING");
      setLEDRecording();
      startRecordingMode();
      currentState = RECORDING;
    } else {
      Serial.println("→ No motion - entering deep sleep");
      delay(100);
      enterDeepSleep();
    }
  } else {
    Serial.println("→ USB mode - waiting for motion");
    currentState = IDLE;
  }

  Serial.println();
}

// ============================================================================
// MAIN LOOP - BLE Sending & State Management
// ============================================================================

void loop() {
  unsigned long now = millis();

  switch (currentState) {
  case IDLE:
    handleIdle(now);
    break;

  case RECORDING:
    handleRecording(now);
    break;
  }
}

// ============================================================================
// IDLE HANDLER
// ============================================================================

void handleIdle(unsigned long now) {
  static unsigned long lastPollTime = 0;
  if (now - lastPollTime >= 100) {
    lastPollTime = now;

    float x = imu.readFloatAccelX();
    float y = imu.readFloatAccelY();
    float z = imu.readFloatAccelZ();
    float magnitude = sqrt(x * x + y * y + z * z);

    // Debug every 3 seconds
    if (now - lastDebugTime >= 3000) {
      lastDebugTime = now;
      Serial.print("[IDLE] Accel=");
      Serial.print(magnitude, 2);
      Serial.println("g");
    }

    bool motionByPolling = (magnitude > (1.0 + MOTION_THRESHOLD_G) ||
                            magnitude < (1.0 - MOTION_THRESHOLD_G));

    if (motionInterruptFired || motionByPolling) {
      motionInterruptFired = false;
      Serial.println("\n>>> MOTION! Starting RECORDING...");

      clearIMUInterrupt();
      setLEDRecording();
      startRecordingMode();
      currentState = RECORDING;
    }
  }
}

// ============================================================================
// RECORDING HANDLER - Main loop handles BLE sending
// ============================================================================

void handleRecording(unsigned long now) {
  // Timer ISR handles sampling - we just do BLE and state management here

  // Send samples opportunistically (non-blocking attempts)
  // Main loop can freely block on BLE - timer ensures sampling continues
  if (Bluefruit.connected() && bufferCount > 0) {
    // Try to send multiple samples per loop
    for (int i = 0; i < 10 && bufferCount > 0; i++) {
      if (!sendNextSample()) {
        break; // BLE busy
      }
    }
  }

  // Status update
  static uint16_t lastLoggedSeq = 0;
  if (sequenceNumber >= lastLoggedSeq + 100) {
    lastLoggedSeq = sequenceNumber;
    Serial.print("Logged ");
    Serial.print(sequenceNumber);
    Serial.print(" samples (buffer: ");
    Serial.print(bufferCount);
    Serial.println(")");
  }

  // Battery update
  if (now - lastBatteryReadTime >= BATTERY_READ_INTERVAL_MS) {
    lastBatteryReadTime = now;
    readBatteryVoltage();
    if (Bluefruit.connected()) {
      sendBatteryStatus();
    }
  }

  // Check idle timeout
  if (now - lastMotionTime > IDLE_TIMEOUT_MS) {
    stopRecordingMode();
  }
}

// ============================================================================
// START/STOP RECORDING
// ============================================================================

void startRecordingMode() {
  if (!bleInitialized) {
    Serial.println("Initializing BLE...");

    Bluefruit.begin();
    Bluefruit.autoConnLed(false);
    Bluefruit.setTxPower(4);
    Bluefruit.setName("XIAO-TB");
    Bluefruit.Periph.setConnectCallback(connectCallback);
    Bluefruit.Periph.setDisconnectCallback(disconnectCallback);

    toothbrushService.begin();

    timeSyncChar.setProperties(CHR_PROPS_WRITE);
    timeSyncChar.setPermission(SECMODE_NO_ACCESS, SECMODE_OPEN);
    timeSyncChar.setFixedLen(8);
    timeSyncChar.setWriteCallback(timeSyncCallback);
    timeSyncChar.begin();

    dataChar.setProperties(CHR_PROPS_READ | CHR_PROPS_NOTIFY);
    dataChar.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
    dataChar.setFixedLen(16);
    dataChar.begin();

    ackChar.setProperties(CHR_PROPS_WRITE);
    ackChar.setPermission(SECMODE_NO_ACCESS, SECMODE_OPEN);
    ackChar.setFixedLen(1);
    ackChar.setWriteCallback(ackCallback);
    ackChar.begin();

    batteryChar.setProperties(CHR_PROPS_READ | CHR_PROPS_NOTIFY);
    batteryChar.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
    batteryChar.setFixedLen(4);
    batteryChar.begin();

    bleInitialized = true;
    Serial.println("✓ BLE initialized");
  }

  Bluefruit.Advertising.clearData();
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(toothbrushService);
  Bluefruit.Advertising.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(80, 80);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);

  Serial.println("✓ BLE advertising");

  // Reset buffer
  bufferHead = 0;
  bufferTail = 0;
  bufferCount = 0;
  sequenceNumber = 0;
  lastMotionTime = millis();

  // Start the hardware timer for 50 Hz sampling
  startSampleTimer();

  Serial.println("✓ RECORDING");
  Serial.println();
}

void stopRecordingMode() {
  Serial.println();
  Serial.println("→ No motion detected. Stopping timer...");

  // Stop the sampling timer
  stopSampleTimer();

  Serial.print("Total samples: ");
  Serial.println(sequenceNumber);

  // Drain all remaining samples
  if (Bluefruit.connected()) {
    Serial.println("→ Draining buffer to bridge...");

    while (bufferCount > 0 && Bluefruit.connected()) {
      if (!sendNextSample()) {
        delay(5);
      }
      if (bufferCount % 500 == 0 && bufferCount > 0) {
        Serial.print("   ");
        Serial.print(bufferCount);
        Serial.println(" remaining...");
      }
    }

    if (bufferCount == 0) {
      Serial.println("✓ All data sent!");
    } else {
      Serial.print("⚠️  ");
      Serial.print(bufferCount);
      Serial.println(" samples remain");
    }
  } else {
    Serial.print("⚠️  No bridge - ");
    Serial.print(bufferCount);
    Serial.println(" samples in buffer");
  }

  // Disconnect
  if (activeConnHandle != BLE_CONN_HANDLE_INVALID) {
    Bluefruit.Advertising.restartOnDisconnect(false);
    Bluefruit.disconnect(activeConnHandle);
    delay(200);
  }
  Bluefruit.Advertising.stop();

  setLEDOff();

  if (isUSBConnected()) {
    Serial.println("→ USB mode - back to IDLE");
    clearIMUInterrupt();
    delay(100);
    motionInterruptFired = false;
    currentState = IDLE;
    lastDebugTime = 0;
  } else {
    Serial.println("→ Battery mode - deep sleep");
    delay(100);
    enterDeepSleep();
  }
}

// ============================================================================
// DEEP SLEEP
// ============================================================================

void enterDeepSleep() {
  Serial.println("Entering System OFF...");
  delay(50);
  Serial.end();

  detachInterrupt(digitalPinToInterrupt(IMU_INT1_PIN));
  clearIMUInterrupt();

  int retries = 20;
  while (digitalRead(IMU_INT1_PIN) == HIGH && retries-- > 0) {
    clearIMUInterrupt();
    delay(50);
  }

  nrf_gpio_cfg_sense_input(g_ADigitalPinMap[IMU_INT1_PIN],
                           NRF_GPIO_PIN_PULLDOWN, NRF_GPIO_PIN_SENSE_HIGH);

  NRF_POWER->SYSTEMOFF = 1;
  while (1)
    __WFE();
}

// ============================================================================
// IMU WAKE INTERRUPT CONFIG
// ============================================================================

void configureWakeInterrupt() {
  Serial.println("Configuring wake interrupt...");

  imu.writeRegister(LSM6DS3_ACC_GYRO_TAP_CFG, 0x90);
  imu.writeRegister(LSM6DS3_ACC_GYRO_WAKE_UP_THS, 0x02);
  imu.writeRegister(LSM6DS3_ACC_GYRO_WAKE_UP_DUR, 0x00);
  imu.writeRegister(LSM6DS3_ACC_GYRO_MD1_CFG, 0x20);

  delay(100);
  clearIMUInterrupt();

  float x = imu.readFloatAccelX();
  float y = imu.readFloatAccelY();
  float z = imu.readFloatAccelZ();
  float mag = sqrt(x * x + y * y + z * z);
  Serial.print("  Test accel: ");
  Serial.print(mag, 2);
  Serial.println("g");

  Serial.println("✓ Wake interrupt configured");
}

void clearIMUInterrupt() {
  uint8_t src;
  imu.readRegister(&src, LSM6DS3_ACC_GYRO_WAKE_UP_SRC);
}

// ============================================================================
// BLE CALLBACKS
// ============================================================================

void connectCallback(uint16_t conn_handle) {
  Serial.println("→ Bridge connected");
  activeConnHandle = conn_handle;
  setLEDConnected();
}

void disconnectCallback(uint16_t conn_handle, uint8_t reason) {
  Serial.println("→ Bridge disconnected");
  if (activeConnHandle == conn_handle) {
    activeConnHandle = BLE_CONN_HANDLE_INVALID;
  }
  setLEDDisconnected();
}

void timeSyncCallback(uint16_t conn_handle, BLECharacteristic *chr,
                      uint8_t *data, uint16_t len) {
  if (len == 8) {
    uint64_t hub_time;
    memcpy(&hub_time, data, 8);
    Serial.print("Time sync: ");
    Serial.println((unsigned long)hub_time);
  }
}

void ackCallback(uint16_t conn_handle, BLECharacteristic *chr, uint8_t *data,
                 uint16_t len) {}

// ============================================================================
// DATA TRANSMISSION
// ============================================================================

bool sendNextSample() {
  if (bufferCount == 0)
    return false;

  Sample *sample = &sampleBuffer[bufferTail];

  if (dataChar.notify((uint8_t *)sample, sizeof(Sample))) {
    bufferTail = (bufferTail + 1) % MAX_SAMPLES;
    bufferCount--;

    static uint16_t sentCount = 0;
    sentCount++;
    if (sentCount % 100 == 0) {
      Serial.print("Sent ");
      Serial.print(sentCount);
      Serial.print(" (buffer: ");
      Serial.print(bufferCount);
      Serial.println(")");
    }
    if (bufferCount == 0)
      sentCount = 0;
    return true;
  }
  return false;
}

// ============================================================================
// BATTERY
// ============================================================================

void readBatteryVoltage() {
  int adcValue = analogRead(PIN_VBAT);
  float adcVoltage = (adcValue * 3.6) / 4095.0;
  batteryVoltage = adcVoltage * 2.961;

  if (batteryVoltage >= 4.2)
    batteryPercent = 100;
  else if (batteryVoltage <= 3.0)
    batteryPercent = 0;
  else
    batteryPercent = (uint8_t)((batteryVoltage - 3.0) / 1.2 * 100);
}

void sendBatteryStatus() {
  uint16_t voltage_mv = (uint16_t)(batteryVoltage * 1000);
  uint8_t data[4] = {(uint8_t)(voltage_mv & 0xFF),
                     (uint8_t)((voltage_mv >> 8) & 0xFF), batteryPercent, 1};
  batteryChar.notify(data, 4);
}
