
/*
 * Smart Dock Bridge for HealthTRAC
 * ESP32 bridge that detects toothbrush docking and initiates sync
 *
 * Features:
 * - RSSI-based proximity detection (-55dBm threshold)
 * - Waits for BLE advertisement (appears 30 min after docking)
 * - Downloads logged data and forwards to hub via WiFi
 * - Returns to low-power scanning after sync
 */

#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEClient.h>
#include <BLEScan.h>
#include <WiFi.h>
#include <ArduinoJson.h>

// Configuration - UPDATE THESE VALUES
const char* WIFI_SSID = "ZungaWorldWide";        // Your current WiFi name
const char* WIFI_PASSWORD = "t0mat0es"; // Your WiFi password
const char* HUB_HOST = "192.168.0.193";          // Ubuntu VM IP (run 'hostname -I' to find)
const int HUB_PORT = 5555;

// ===== TESTING CONFIGURATION =====
#define TEST_MODE 1  // Set to 0 for production

#if TEST_MODE
  const int SCAN_DURATION = 2;           // 2 seconds instead of 5
  const int DOCK_WAIT_TIME = 30000;     // 30 seconds instead of 30 minutes
  const int LOOP_DELAY = 1000;          // 1 second instead of 5
  const int SYNC_TIMEOUT = 30000;       // 30 seconds max download
#else
  const int SCAN_DURATION = 5;
  const int DOCK_WAIT_TIME = 1800000;   // 30 minutes
  const int LOOP_DELAY = 5000;
  const int SYNC_TIMEOUT = 60000;
#endif
// =================================

// MetaMotion Configuration
const char* TARGET_MAC = "C8:0B:FB:24:C1:65";  // Your MetaMotion MAC
const int RSSI_THRESHOLD = -55;  // Proximity threshold for docking

// MetaMotion UUIDs
static BLEUUID SERVICE_UUID("326a9000-85cb-9195-d9dd-464cfbbae75a");
static BLEUUID COMMAND_UUID("326a9001-85cb-9195-d9dd-464cfbbae75a");
static BLEUUID NOTIFY_UUID("326a9006-85cb-9195-d9dd-464cfbbae75a");

// MetaMotion Commands
const uint8_t CMD_LOGGING_STOP[] = {0x0b, 0x01, 0x00};
const uint8_t CMD_LOGGING_LENGTH[] = {0x0b, 0x08};
const uint8_t CMD_LOGGING_DOWNLOAD[] = {0x0b, 0x06, 0x01};
const uint8_t CMD_LOGGING_DROP[] = {0x0b, 0x09};
const uint8_t CMD_LOGGING_START[] = {0x0b, 0x01, 0x01};
const uint8_t CMD_BLE_DISCONNECT[] = {0x11, 0x01, 0x00};  // Disable advertising after sync

// Global State
BLEClient* pClient = nullptr;
BLEScan* pBLEScan = nullptr;
WiFiClient wifiClient;

bool deviceDocked = false;
bool syncInProgress = false;
unsigned long lastDockTime = 0;
unsigned long lastSyncTime = 0;

// Download state
uint32_t totalEntries = 0;
uint32_t entriesReceived = 0;
float syncStartTime = 0;

// Data buffer
struct AccelData {
  float timestamp;
  float x, y, z;
};
std::vector<AccelData> dataBuffer;

// Notification handler for BLE data
static void notifyCallback(BLERemoteCharacteristic* pChar, uint8_t* data, size_t length, bool isNotify) {
  if (length < 2) return;

  // Check if this is logging data
  if (data[0] == 0x0b) {
    if (data[1] == 0x08 && length >= 6) {
      // Log length response
      totalEntries = data[2] | (data[3] << 8) | (data[4] << 16) | (data[5] << 24);
      Serial.printf("Log contains %d entries\n", totalEntries);

    } else if (data[1] == 0x07 && length >= 11) {
      // Log readout data
      uint32_t entryId = data[2] | (data[3] << 8) | (data[4] << 16) | (data[5] << 24);
      uint32_t epochTicks = data[6] | (data[7] << 8) | (data[8] << 16) | (data[9] << 24);

      // Check if this is accelerometer data
      if (length >= 18 && data[10] == 0x02) {
        // Parse accelerometer values
        int16_t rawX = data[12] | (data[13] << 8);
        int16_t rawY = data[14] | (data[15] << 8);
        int16_t rawZ = data[16] | (data[17] << 8);

        float x = rawX / 16384.0f;
        float y = rawY / 16384.0f;
        float z = rawZ / 16384.0f;

        // Calculate timestamp (approximate)
        float timestamp = syncStartTime - (totalEntries - entryId) * 0.01f;

        // Add to buffer
        dataBuffer.push_back({timestamp, x, y, z});
        entriesReceived++;

        // Show progress
        if (entriesReceived % 100 == 0) {
          float progress = (float)entriesReceived / totalEntries * 100;
          Serial.printf("Download progress: %.1f%% (%d/%d)\n", progress, entriesReceived, totalEntries);
        }
      }

    } else if (data[1] == 0x0a) {
      // Download complete
      Serial.println("Log download complete");
    }
  }
}

// Connect to WiFi
void connectWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
}

// Send data to hub
bool sendToHub(const AccelData& data) {
  if (!wifiClient.connected()) {
    Serial.println("Connecting to hub...");
    if (!wifiClient.connect(HUB_HOST, HUB_PORT)) {
      Serial.println("Hub connection failed");
      return false;
    }

    // Send sensor identification
    wifiClient.println("SENSOR:ACCELEROMETER_BRIDGE");
    delay(100);

    // Read acknowledgment
    if (wifiClient.available()) {
      String ack = wifiClient.readStringUntil('\n');
      Serial.println("Hub: " + ack);
    }
  }

  // Create JSON data
  StaticJsonDocument<200> doc;
  doc["timestamp"] = data.timestamp;
  doc["x"] = data.x;
  doc["y"] = data.y;
  doc["z"] = data.z;
  doc["bridged"] = true;  // Mark as bridged data

  String json;
  serializeJson(doc, json);
  wifiClient.println(json);

  return true;
}

// BLE scan callback
class DockScanCallbacks: public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice advertisedDevice) {
    String addr = advertisedDevice.getAddress().toString();

    // Check if it's our target device
    if (addr.equalsIgnoreCase(TARGET_MAC)) {
      int rssi = advertisedDevice.getRSSI();

      Serial.printf("Found MetaMotion - RSSI: %d dBm", rssi);

      // Check proximity
      if (rssi > RSSI_THRESHOLD) {
        Serial.println(" (DOCKED)");

        if (!deviceDocked) {
          deviceDocked = true;
          lastDockTime = millis();
          Serial.println("Toothbrush docked - waiting for sync readiness...");
        }

        // Check if device is advertising (ready for sync)
        if (deviceDocked && !syncInProgress) {
          // Device only advertises when ready (30 min after docking)
          Serial.println("MetaMotion is advertising - ready for sync!");

          // Stop scan and start sync
          pBLEScan->stop();
          syncInProgress = true;
        }
      } else {
        Serial.println(" (too far)");

        if (deviceDocked && rssi < RSSI_THRESHOLD - 10) {
          // Device moved away
          deviceDocked = false;
          Serial.println("Toothbrush removed from dock");
        }
      }
    }
  }
};

// Download logged data from MetaMotion
bool syncLoggedData() {
  Serial.println("Starting data sync...");

  // Create client
  pClient = BLEDevice::createClient();

  // Connect to MetaMotion
  if (!pClient->connect(BLEAddress(TARGET_MAC))) {
    Serial.println("Failed to connect");
    delete pClient;
    return false;
  }

  Serial.println("Connected to MetaMotion");

  // Get service
  BLERemoteService* pService = pClient->getService(SERVICE_UUID);
  if (pService == nullptr) {
    Serial.println("Failed to find service");
    pClient->disconnect();
    delete pClient;
    return false;
  }

  // Get characteristics
  BLERemoteCharacteristic* pCommand = pService->getCharacteristic(COMMAND_UUID);
  BLERemoteCharacteristic* pNotify = pService->getCharacteristic(NOTIFY_UUID);

  if (pCommand == nullptr || pNotify == nullptr) {
    Serial.println("Failed to find characteristics");
    pClient->disconnect();
    delete pClient;
    return false;
  }

  // Register for notifications
  pNotify->registerForNotify(notifyCallback);
  delay(500);

  // Stop logging
  pCommand->writeValue((uint8_t*)CMD_LOGGING_STOP, sizeof(CMD_LOGGING_STOP));
  delay(500);

  // Get log length
  totalEntries = 0;
  pCommand->writeValue((uint8_t*)CMD_LOGGING_LENGTH, sizeof(CMD_LOGGING_LENGTH));
  delay(1000);

  if (totalEntries == 0) {
    Serial.println("No data to sync");

    // Disable advertising to save battery
    pCommand->writeValue((uint8_t*)CMD_BLE_DISCONNECT, sizeof(CMD_BLE_DISCONNECT));
    delay(100);

    pClient->disconnect();
    delete pClient;
    return true;
  }

  // Start download
  Serial.printf("Downloading %d entries...\n", totalEntries);
  entriesReceived = 0;
  dataBuffer.clear();
  dataBuffer.reserve(totalEntries);
  syncStartTime = millis() / 1000.0f;  // Convert to seconds

  pCommand->writeValue((uint8_t*)CMD_LOGGING_DOWNLOAD, sizeof(CMD_LOGGING_DOWNLOAD));

  // Wait for download to complete
  unsigned long downloadStart = millis();
  unsigned long timeout = 60000 + (totalEntries * 10);  // Scale timeout with data size

  while (entriesReceived < totalEntries && millis() - downloadStart < timeout) {
    delay(10);
  }

  if (entriesReceived >= totalEntries) {
    Serial.printf("Download complete: %d entries\n", entriesReceived);

    // Send all data to hub
    Serial.println("Sending data to hub...");
    int sent = 0;

    for (const auto& data : dataBuffer) {
      if (sendToHub(data)) {
        sent++;
        if (sent % 100 == 0) {
          Serial.printf("Sent %d/%d to hub\n", sent, dataBuffer.size());
        }
      }
      delay(5);  // Small delay to avoid overwhelming hub
    }

    Serial.printf("Sent %d entries to hub\n", sent);

    // Clear device log
    pCommand->writeValue((uint8_t*)CMD_LOGGING_DROP, sizeof(CMD_LOGGING_DROP));
    delay(500);

    // Restart logging
    pCommand->writeValue((uint8_t*)CMD_LOGGING_START, sizeof(CMD_LOGGING_START));
    delay(100);

    // Disable advertising to save battery
    pCommand->writeValue((uint8_t*)CMD_BLE_DISCONNECT, sizeof(CMD_BLE_DISCONNECT));
    delay(100);

  } else {
    Serial.printf("Download timeout: got %d/%d entries\n", entriesReceived, totalEntries);
  }

  // Disconnect
  pClient->disconnect();
  delete pClient;

  // Close hub connection
  if (wifiClient.connected()) {
    wifiClient.stop();
  }

  return true;
}

void setup() {
  Serial.begin(115200);
  Serial.println("HealthTRAC Smart Dock Bridge");
  Serial.println("=============================");

  // Connect to WiFi
  connectWiFi();

  // Initialize BLE
  BLEDevice::init("HealthTRAC Bridge");

  // Create BLE scanner
  pBLEScan = BLEDevice::getScan();
  pBLEScan->setAdvertisedDeviceCallbacks(new DockScanCallbacks());
  pBLEScan->setActiveScan(true);  // Active scan for more info
  pBLEScan->setInterval(100);
  pBLEScan->setWindow(99);

  Serial.println("Setup complete. Scanning for toothbrush...");
}

void loop() {
  // Handle different states
  if (syncInProgress) {
    // Perform sync
    bool success = syncLoggedData();

    if (success) {
      Serial.println("Sync completed successfully");
      lastSyncTime = millis();
    } else {
      Serial.println("Sync failed");
    }

    // Reset state
    syncInProgress = false;
    deviceDocked = false;

    // Wait a bit before resuming scan
    delay(5000);

  } else {
    // Scan for devices
    Serial.println("Scanning for MetaMotion...");
    BLEScanResults* foundDevices = pBLEScan->start(SCAN_DURATION, false);

    Serial.printf("Scan complete. Found %d devices\n", foundDevices->getCount());
    pBLEScan->clearResults();

    // Status update
    if (deviceDocked) {
      unsigned long dockDuration = (millis() - lastDockTime) / 1000;
      Serial.printf("Device docked for %lu seconds (waiting for 30 min mark)\n", dockDuration);
    }

    if (lastSyncTime > 0) {
      unsigned long timeSinceSync = (millis() - lastSyncTime) / 1000 / 60;
      Serial.printf("Last sync: %lu minutes ago\n", timeSinceSync);
    }

    // Short delay between scans
    delay(5000);
  }
}