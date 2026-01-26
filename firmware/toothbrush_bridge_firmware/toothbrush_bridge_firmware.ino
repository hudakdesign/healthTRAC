#include <ArduinoJson.h>
#include <BLEDevice.h>
#include <FFat.h>
#include <WiFi.h>

// ============================================================================
// CONFIGURATION
// ============================================================================

// WiFi configuration
// #define WIFI_SSID "ZungaWorldWide"
// #define WIFI_PASSWORD "t0mat0es"
#define WIFI_SSID "CBI IoT"
#define WIFI_PASSWORD "cbir00lz"

// Hub configuration
#define HUB_IP "192.168.0.142" // Update to your hub's actual IP
#define HUB_TCP_PORT 5555
#define HUB_TIME_API "http://192.168.0.142:5000/api/time"

// BLE configuration
#define XIAO_DEVICE_NAME "XIAO-TB"
#define SERVICE_UUID "180F"
#define TIME_SYNC_CHAR_UUID "2A1A"
#define DATA_CHAR_UUID "2A19"
#define ACK_CHAR_UUID "2A1B"
#define BATTERY_CHAR_UUID "2A1C"

// FFat buffering
#define BUFFER_FILE "/toothbrush_buffer.jsonl"
#define MAX_BUFFER_SIZE 1000000 // 1MB max buffered JSON

// Sample structure (must match XIAO firmware)
struct Sample {
  uint64_t timestamp_local;
  int16_t accel_x;
  int16_t accel_y;
  int16_t accel_z;
  uint16_t seq;
} __attribute__((packed));

// ============================================================================
// GLOBAL VARIABLES
// ============================================================================

// BLE
BLEScan *bleScan;
BLEClient *bleClient = nullptr;
BLERemoteCharacteristic *timeSyncChar = nullptr;
BLERemoteCharacteristic *dataChar = nullptr;
BLERemoteCharacteristic *ackChar = nullptr;
BLERemoteCharacteristic *batteryChar = nullptr;

// Network
WiFiClient tcpClient;
bool xiaoConnected = false;
bool tcpConnected = false;

// Time sync
uint64_t timeOffset = 0; // xiao_time + offset = hub_time
uint64_t lastTimeSyncRequest = 0;

// Scanning
unsigned long lastScanTime = 0;
unsigned long lastReconnectAttempt = 0;
#define SCAN_INTERVAL_MS 5000      // Scan every 5 seconds
#define RECONNECT_INTERVAL_MS 5000 // Try reconnecting every 5 seconds

// Stats
uint32_t samplesReceived = 0;
uint32_t samplesSent = 0;
uint32_t samplesBuffered = 0;
bool fsAvailable = false;

// ============================================================================
// FORWARD DECLARATIONS
// ============================================================================
void scanForXIAO();
void connectToXIAO(BLEAdvertisedDevice device);
void dataNotifyCallback(BLERemoteCharacteristic *pChar, uint8_t *data,
                        size_t length, bool isNotify);
void batteryNotifyCallback(BLERemoteCharacteristic *pChar, uint8_t *data,
                           size_t length, bool isNotify);
void performTimeSync();
void bufferSample(String json);
void flushBuffer();
void connectWiFi();
bool connectToHub();

// Callback class
class ClientCallbacks : public BLEClientCallbacks {
  void onConnect(BLEClient *pClient) { Serial.println("→ Connected to XIAO"); }

  void onDisconnect(BLEClient *pClient) {
    if (xiaoConnected) {
      Serial.println("→ XIAO disconnected remotely");
      xiaoConnected = false;

      // Notify hub that XIAO disconnected
      if (tcpConnected && tcpClient.connected()) {
        StaticJsonDocument<200> doc;
        doc["type"] = "xiao_disconnected";
        doc["sensor"] = "toothbrush";
        doc["device_id"] = "C8:0B:FB:24:C1:65";

        String json;
        serializeJson(doc, json);
        tcpClient.println(json);
      }
    }
  }
};

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println("========================================");
  Serial.println("Health TRAC - Toothbrush Bridge");
  Serial.println("Nano ESP32-S3 (FFat Version)");
  Serial.println("========================================");

  // Initialize FFat
  Serial.print("Initializing FFat... ");

  if (!FFat.begin(true)) { // true = formatOnFail
    Serial.println("mount failed, formatting also failed");
    fsAvailable = false;
  } else {
    Serial.println("mounted");
    fsAvailable = true;
    size_t total = FFat.totalBytes();
    size_t used = FFat.usedBytes();
    Serial.printf("✓ FFat ready (%d KB total, %d KB used)\n", total / 1024,
                  used / 1024);

    // Clear old buffer on startup
    if (FFat.exists(BUFFER_FILE)) {
      FFat.remove(BUFFER_FILE);
      Serial.println("  Cleared old buffer file");
    }
  }

  if (!fsAvailable) {
    Serial.println("⚠️  WARNING: Storage unavailable - samples will be dropped "
                   "if hub offline");
    Serial.println("   Ensure Partition Scheme is 'Default' or includes FatFS");
  }

  // Connect to WiFi
  connectWiFi();

  // Connect to hub
  connectToHub();

  // Initialize BLE
  BLEDevice::init("Bridge-ESP32");
  bleScan = BLEDevice::getScan();
  bleScan->setActiveScan(true);
  bleScan->setInterval(100);
  bleScan->setWindow(99);

  Serial.println("✓ BLE initialized");
  Serial.println("✓ System ready - scanning for XIAO");
  Serial.println();
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  unsigned long now = millis();

  // Track connection state changes
  static bool wasConnected = false;
  bool isConnected = tcpClient.connected();

  // Periodic scanning if not connected to XIAO
  if (!xiaoConnected && (now - lastScanTime >= SCAN_INTERVAL_MS)) {
    lastScanTime = now;
    scanForXIAO();
  }

  // Check TCP connection status
  if (!isConnected) {
    if (tcpConnected) {
      Serial.println("→ TCP connection lost");
      tcpConnected = false;
    }

    // Only attempt reconnection periodically
    if (now - lastReconnectAttempt >= RECONNECT_INTERVAL_MS) {
      lastReconnectAttempt = now;
      if (connectToHub()) {
        tcpConnected = true;
      }
    }
  } else {
    tcpConnected = true;

    // If hub just reconnected, flush buffered samples
    if (!wasConnected && fsAvailable) {
      Serial.println("→ Hub reconnected, checking for buffered samples...");
      flushBuffer();
    }
  }

  wasConnected = isConnected;
  delay(10);
}

void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.print("WiFi connected, IP: ");
  Serial.println(WiFi.localIP());
}

bool connectToHub() {
  if (tcpClient.connect(HUB_IP, HUB_TCP_PORT)) {
    Serial.println("✓ TCP connected to hub");

    // Send handshake
    StaticJsonDocument<256> doc;
    doc["type"] = "handshake";
    doc["sensor"] = "toothbrush";
    doc["device_id"] = "C8:0B:FB:24:C1:65";

    String json;
    serializeJson(doc, json);
    tcpClient.println(json);

    return true;
  } else {
    // Silent fail - will retry in 5 seconds
    return false;
  }
}

// ============================================================================
// BLE FUNCTIONS
// ============================================================================

void scanForXIAO() {
  Serial.println("Scanning for XIAO toothbrush...");

  BLEScanResults foundDevices = bleScan->start(2, false); // 2 second scan

  for (int i = 0; i < foundDevices.getCount(); i++) {
    BLEAdvertisedDevice device = foundDevices.getDevice(i);

    if (device.getName() == XIAO_DEVICE_NAME) {
      Serial.print("Found XIAO! RSSI: ");
      Serial.println(device.getRSSI());
      connectToXIAO(device);
      break;
    }
  }

  bleScan->clearResults();
}

void connectToXIAO(BLEAdvertisedDevice device) {
  Serial.print("Connecting to XIAO... ");

  bleClient = BLEDevice::createClient();
  bleClient->setClientCallbacks(new ClientCallbacks());

  if (bleClient->connect(&device)) {
    Serial.println("connected");
    xiaoConnected = true;

    // Get service
    BLERemoteService *service = bleClient->getService(SERVICE_UUID);
    if (!service) {
      Serial.println("ERROR: Service not found");
      bleClient->disconnect();
      xiaoConnected = false;
      return;
    }

    // Get characteristics
    timeSyncChar = service->getCharacteristic(TIME_SYNC_CHAR_UUID);
    dataChar = service->getCharacteristic(DATA_CHAR_UUID);
    ackChar = service->getCharacteristic(ACK_CHAR_UUID);
    batteryChar = service->getCharacteristic(BATTERY_CHAR_UUID);

    if (!timeSyncChar)
      Serial.println("❌ Time Sync Char not found");
    if (!dataChar)
      Serial.println("❌ Data Char not found");
    if (!ackChar)
      Serial.println("❌ ACK Char not found");
    if (!batteryChar)
      Serial.println("❌ Battery Char not found");

    if (!timeSyncChar || !dataChar || !ackChar || !batteryChar) {
      Serial.println("ERROR: Characteristics not found");
      bleClient->disconnect();
      xiaoConnected = false;
      return;
    }

    // Register for notifications on data characteristic
    dataChar->registerForNotify(dataNotifyCallback);

    // Register for notifications on battery characteristic
    batteryChar->registerForNotify(batteryNotifyCallback);

    // Perform time sync
    performTimeSync();

    // Notify hub that XIAO connected
    if (tcpConnected && tcpClient.connected()) {
      StaticJsonDocument<200> doc;
      doc["type"] = "xiao_connected";
      doc["sensor"] = "toothbrush";
      doc["device_id"] = "C8:0B:FB:24:C1:65";
      doc["rssi"] = device.getRSSI();

      String json;
      serializeJson(doc, json);
      tcpClient.println(json);
    }

    Serial.println("✓ Ready to receive data");
  } else {
    Serial.println("connection failed");
    xiaoConnected = false;
  }
}

// ============================================================================
// DATA PROCESSING
// ============================================================================

void batteryNotifyCallback(BLERemoteCharacteristic *pChar, uint8_t *data,
                           size_t length, bool isNotify) {
  if (length != 4) {
    Serial.println("ERROR: Invalid battery packet length");
    return;
  }

  uint16_t voltage_mv = data[0] | (data[1] << 8);
  uint8_t percent = data[2];
  uint8_t state = data[3];

  float voltage = voltage_mv / 1000.0;

  Serial.printf("Battery Update: %.2fV (%d%%) State: %d\n", voltage, percent,
                state);

  if (tcpConnected && tcpClient.connected()) {
    StaticJsonDocument<200> doc;
    doc["type"] = "battery";
    doc["sensor"] = "toothbrush";
    doc["device_id"] = "C8:0B:FB:24:C1:65";
    doc["voltage"] = voltage;
    doc["percent"] = percent;
    doc["state"] = state;
    doc["timestamp"] = millis(); // Simple timestamp

    String json;
    serializeJson(doc, json);
    tcpClient.println(json);
  }
}

void dataNotifyCallback(BLERemoteCharacteristic *pChar, uint8_t *data,
                        size_t length, bool isNotify) {
  // Debug: confirm callback is being called
  static uint32_t callbackCount = 0;
  if (callbackCount == 0) {
    Serial.println("→ Data callback invoked!");
  }
  callbackCount++;

  if (length != 16) {
    Serial.print("ERROR: Unexpected data length: ");
    Serial.println(length);
    return;
  }

  // NOTE: Removed end-of-transfer marker check
  // The XIAO doesn't send a marker; it just disconnects when done.
  // The previous 0xFF check was potentially causing false disconnects.

  // Parse sample
  Sample sample;
  memcpy(&sample, data, sizeof(Sample));

  samplesReceived++;

  // Translate timestamp
  uint64_t hub_timestamp = sample.timestamp_local + timeOffset;

  // Convert to g
  float accel_x = sample.accel_x / 8192.0;
  float accel_y = sample.accel_y / 8192.0;
  float accel_z = sample.accel_z / 8192.0;

  // Create JSON
  StaticJsonDocument<256> doc;
  doc["type"] = "data"; // Add type for hub identification
  doc["sensor"] = "toothbrush";
  doc["device_id"] = "C8:0B:FB:24:C1:65";
  doc["timestamp_hub"] = hub_timestamp / 1000.0;
  doc["timestamp_local"] = sample.timestamp_local;
  doc["accel_x"] = accel_x;
  doc["accel_y"] = accel_y;
  doc["accel_z"] = accel_z;
  doc["seq"] = sample.seq;

  String json;
  serializeJson(doc, json);

  // Send directly to hub if connected, otherwise buffer to FFat
  if (tcpConnected && tcpClient.connected()) {
    // ✅ Primary path: direct to hub
    tcpClient.println(json);
    samplesSent++;

    if (samplesReceived % 100 == 0) {
      Serial.print("→ Sent ");
      Serial.print(samplesReceived);
      Serial.println(" samples to hub");
    }
  } else {
    // ⚠️ Fallback path: buffer to FFat
    if (fsAvailable) {
      if (samplesReceived == 1) {
        Serial.println("→ Hub offline, buffering samples to Storage");
      }

      bufferSample(json);

      if (samplesReceived % 100 == 0) {
        Serial.print("→ Buffered ");
        Serial.print(samplesReceived);
        Serial.print(" samples to Storage (");
        Serial.print(samplesBuffered);
        Serial.println(" total in buffer)");
      }
    } else {
      // ❌ Worst case: drop sample
      static unsigned long lastWarning = 0;
      if (millis() - lastWarning > 5000) {
        Serial.println("⚠️  WARNING: Hub offline and Storage unavailable - "
                       "samples being dropped!");
        lastWarning = millis();
      }
    }
  }
}

void performTimeSync() {
  Serial.println("Performing time sync...");

  // Get current hub time (millis for now, could query NTP server)
  uint64_t hub_time = millis();
  uint64_t xiao_receive_time = hub_time; // Approximation

  // Send time sync to XIAO
  timeSyncChar->writeValue((uint8_t *)&hub_time, 8);

  // Calculate offset (simplified - assumes instant transmission)
  timeOffset = hub_time - xiao_receive_time;

  Serial.print("Time offset: ");
  Serial.println((long)timeOffset);
}

void bufferSample(String json) {
  if (!fsAvailable) {
    return;
  }

  File file = FFat.open(BUFFER_FILE, FILE_APPEND);
  if (file) {
    file.println(json);
    file.close();
    samplesBuffered++;
  } else {
    static unsigned long lastError = 0;
    if (millis() - lastError > 5000) {
      Serial.println("ERROR: Failed to open FFat buffer file");
      lastError = millis();
    }
  }
}

void flushBuffer() {
  if (!fsAvailable) {
    return;
  }

  if (!FFat.exists(BUFFER_FILE)) {
    Serial.println("  No buffered samples to flush");
    return;
  }

  File file = FFat.open(BUFFER_FILE, FILE_READ);
  if (!file) {
    Serial.println("✗ ERROR: Failed to open buffer file for reading");
    return;
  }

  size_t fileSize = file.size();
  Serial.print("  Flushing buffered samples (");
  Serial.print(fileSize / 1024);
  Serial.println(" KB)...");

  int flushed = 0;
  unsigned long startTime = millis();

  while (file.available() && tcpClient.connected()) {
    String line = file.readStringUntil('\n');
    if (line.length() > 0) {
      tcpClient.println(line);
      flushed++;

      if (flushed % 100 == 0) {
        Serial.print("  Flushed ");
        Serial.print(flushed);
        Serial.println(" samples...");
      }

      delay(1); // Rate limiting to avoid overwhelming TCP
    }
  }

  file.close();

  // Only delete buffer if fully flushed
  if (!file.available() && tcpClient.connected()) {
    FFat.remove(BUFFER_FILE);
    unsigned long elapsed = millis() - startTime;
    Serial.print("✓ Flushed ");
    Serial.print(flushed);
    Serial.print(" buffered samples (");
    Serial.print(elapsed / 1000);
    Serial.println(" seconds)");
    samplesBuffered = 0;
  } else {
    Serial.print("⚠️  WARNING: Partial flush - ");
    Serial.print(flushed);
    Serial.println(" samples sent, buffer file retained");
  }
}
