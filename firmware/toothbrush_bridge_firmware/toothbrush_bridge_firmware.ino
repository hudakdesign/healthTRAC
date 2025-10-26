#include <BLEDevice.h>
#include <WiFi.h>
#include <ArduinoJson.h>

// WiFi configuration
#define WIFI_SSID "CBI IoT"
#define WIFI_PASSWORD "cbir00lz"

// Hub configuration
#define HUB_IP "10.0.1.3"  // Put your hub's IP here
#define HUB_TCP_PORT 5555

// BLE configuration
#define XIAO_DEVICE_NAME "XIAO-TB"
#define SERVICE_UUID "180F"
#define DATA_CHAR_UUID "2A19"

// Global variables
BLEScan* bleScan;
BLEClient* bleClient = nullptr;
BLERemoteCharacteristic* dataChar = nullptr;
WiFiClient tcpClient;

bool xiaoConnected = false;
bool tcpConnected = false;

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println("Health TRAC - Basic Toothbrush Bridge");

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

  Serial.println("Setup complete - scanning for XIAO toothbrush");
}

void loop() {
  // If not connected to XIAO, scan for it
  if (!xiaoConnected) {
    scanForXIAO();
    delay(5000); // Scan every 5 seconds
  }

  // If TCP connection lost, reconnect
  if (!tcpClient.connected()) {
    tcpConnected = false;
    Serial.println("TCP connection lost, reconnecting...");
    connectToHub();
  }

  delay(100);
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

void connectToHub() {
  Serial.print("Connecting to hub: ");
  Serial.print(HUB_IP);
  Serial.print(":");
  Serial.println(HUB_TCP_PORT);

  if (tcpClient.connect(HUB_IP, HUB_TCP_PORT)) {
    Serial.println("TCP connected");
    tcpConnected = true;

    // Send handshake
    StaticJsonDocument<256> doc;
    doc["type"] = "handshake";
    doc["sensor"] = "toothbrush";
    doc["device_id"] = "XIAO-TB-TEST";

    String json;
    serializeJson(doc, json);
    tcpClient.println(json);
  } else {
    Serial.println("TCP connection failed");
  }
}

void scanForXIAO() {
  Serial.println("Scanning for XIAO toothbrush...");

  BLEScanResults foundDevices = bleScan->start(5, false);

  for (int i = 0; i < foundDevices.getCount(); i++) {
    BLEAdvertisedDevice device = foundDevices.getDevice(i);

    if (device.getName() == XIAO_DEVICE_NAME) {
      Serial.print("Found XIAO! RSSI: ");
      Serial.println(device.getRSSI());
      connectToXIAO(device);
      break;
    }
  }
}

void connectToXIAO(BLEAdvertisedDevice device) {
  Serial.print("Connecting to XIAO via BLE... ");

  bleClient = BLEDevice::createClient();

  if (bleClient->connect(&device)) {
    Serial.println("Connected!");
    xiaoConnected = true;

    // Get service and characteristic
    BLERemoteService* service = bleClient->getService(SERVICE_UUID);
    if (service) {
      dataChar = service->getCharacteristic(DATA_CHAR_UUID);

      if (dataChar) {
        // Register for notifications
        dataChar->registerForNotify(dataNotifyCallback);
        Serial.println("Subscribed to data notifications");
      }
    }
  } else {
    Serial.println("Connection failed");
    xiaoConnected = false;
  }
}

static void dataNotifyCallback(BLERemoteCharacteristic* pChar, uint8_t* data, size_t length, bool isNotify) {
  if (length >= 12) {
    // Extract accelerometer values
    float accelX, accelY, accelZ;
    memcpy(&accelX, &data[0], 4);
    memcpy(&accelY, &data[4], 4);
    memcpy(&accelZ, &data[8], 4);

    // Create JSON
    StaticJsonDocument<256> doc;
    doc["sensor"] = "toothbrush";
    doc["device_id"] = "XIAO-TB-TEST";
    doc["timestamp_hub"] = millis() / 1000.0; // Temporary timestamp
    doc["accel_x"] = accelX;
    doc["accel_y"] = accelY;
    doc["accel_z"] = accelZ;

    // Send to hub
    String json;
    serializeJson(doc, json);

    if (tcpConnected) {
      tcpClient.println(json);
      Serial.println("Data sent to hub");
    } else {
      Serial.println("TCP not connected, data lost");
    }
  }
}