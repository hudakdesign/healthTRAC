#include <ArduinoJson.h>
#include <BLEDevice.h>
#include <FFat.h>
#include <WebServer.h>
#include <WiFi.h>

// ============================================================================
// Toothbrush Bridge Firmware v2 Simple
// - BLE bridge from XIAO toothbrush peripheral
// - HTTP pull model: GET /id, GET /data, GET /status
// - /data is destructive: returns buffered rows, then clears returned rows
// - RAM queue with FFat spillover
// ============================================================================

#define WIFI_SSID "CBI IoT"
#define WIFI_PASSWORD "cbir00lz"

#define DEVICE_ID "TB1"
#define FW_VERSION "toothbrush_bridge_v2_simple_20260505"

#define STATIC_IP "10.0.1.20"
#define STATIC_GATEWAY "10.0.1.1"
#define STATIC_SUBNET "255.255.255.0"
#define STATIC_DNS "8.8.8.8"

#define XIAO_DEVICE_NAME "XIAO-TB"
#define SERVICE_UUID "180F"
#define DATA_CHAR_UUID "2A19"
#define BATTERY_CHAR_UUID "2A1C"

#define SCAN_INTERVAL_MS 5000
#define RECONNECT_INTERVAL_MS 5000

#define RAM_QUEUE_SIZE 1500
#define MAX_BATCH_SAMPLES 1000
#define SAMPLE_INTERVAL_MS 20  // upstream sample cadence from toothbrush_firmware_timer_isr

#define FLASH_PENDING_FILE "/toothbrush_pending.csv"
#define FLASH_TMP_FILE "/toothbrush_pending_tmp.csv"

struct Sample {
  uint64_t timestamp_local_ms;
  int16_t accel_x;
  int16_t accel_y;
  int16_t accel_z;
  uint16_t seq;
} __attribute__((packed));

Sample ramQueue[RAM_QUEUE_SIZE];
int ramHead = 0;
int ramTail = 0;
int ramCount = 0;

Sample responseBatch[MAX_BATCH_SAMPLES];

bool fsAvailable = false;
uint32_t flashPendingSamples = 0;

BLEScan *bleScan = nullptr;
BLEClient *bleClient = nullptr;
BLERemoteCharacteristic *dataChar = nullptr;
BLERemoteCharacteristic *batteryChar = nullptr;

WebServer server(80);

bool xiaoConnected = false;
unsigned long lastScanTime = 0;
unsigned long lastReconnectAttempt = 0;

uint32_t samplesReceived = 0;
uint32_t samplesServed = 0;
uint32_t samplesSpilledToFlash = 0;
uint32_t samplesDropped = 0;
uint32_t ramOverflows = 0;

uint16_t lastSeq = 0;
uint32_t badPacketCount = 0;
uint16_t lastBatteryMv = 0;
uint8_t lastBatteryPercent = 0;
uint8_t lastBatteryState = 0;
unsigned long lastBatteryUpdateMs = 0;

void scanForXIAO();
void connectToXIAO(BLEAdvertisedDevice device);
void dataNotifyCallback(BLERemoteCharacteristic *pChar, uint8_t *data, size_t length, bool isNotify);
void batteryNotifyCallback(BLERemoteCharacteristic *pChar, uint8_t *data, size_t length, bool isNotify);

void connectWiFi();
bool initStorage();
uint32_t countFlashSamples();
bool appendSampleToFlash(const Sample &sample);
bool parseFlashLine(const String &line, Sample &sample);
void dropFlashPrefix(uint32_t linesToDrop);

void enqueueSample(const Sample &sample);
int collectPendingBatch(Sample *out, int maxSamples, bool &hasMore, int &takenFromFlash);

void handleId();
void handleData();
void handleStatus();
void handleNotFound();

class ClientCallbacks : public BLEClientCallbacks {
  void onConnect(BLEClient *pClient) override {
    (void)pClient;
    Serial.println("[BLE] Connected to XIAO");
  }

  void onDisconnect(BLEClient *pClient) override {
    (void)pClient;
    if (xiaoConnected) {
      Serial.println("[BLE] XIAO disconnected");
      xiaoConnected = false;
      dataChar = nullptr;
      batteryChar = nullptr;
    }
  }
};

void setup() {
  Serial.begin(115200);
  delay(1500);

  Serial.println("========================================");
  Serial.println("Health TRAC - Toothbrush Bridge v2");
  Serial.println("========================================");
  Serial.print("FW: ");
  Serial.println(FW_VERSION);

  connectWiFi();
  initStorage();

  BLEDevice::init("Bridge-TB");
  bleScan = BLEDevice::getScan();
  bleScan->setActiveScan(true);
  bleScan->setInterval(100);
  bleScan->setWindow(99);

  server.on("/id", HTTP_GET, handleId);
  server.on("/data", HTTP_GET, handleData);
  server.on("/status", HTTP_GET, handleStatus);
  server.onNotFound(handleNotFound);
  server.begin();

  Serial.print("HTTP server: http://");
  Serial.print(WiFi.localIP());
  Serial.println("/data");
}

void loop() {
  server.handleClient();

  unsigned long now = millis();

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (!xiaoConnected && (now - lastScanTime >= SCAN_INTERVAL_MS)) {
    lastScanTime = now;
    scanForXIAO();
  }

  // If BLE disconnect happened, free and retry creating client occasionally.
  if (!xiaoConnected && bleClient != nullptr && (now - lastReconnectAttempt >= RECONNECT_INTERVAL_MS)) {
    lastReconnectAttempt = now;
    delete bleClient;
    bleClient = nullptr;
  }

  delay(5);
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  WiFi.mode(WIFI_STA);

  IPAddress ip, gw, sn, dns;
  ip.fromString(STATIC_IP);
  gw.fromString(STATIC_GATEWAY);
  sn.fromString(STATIC_SUBNET);
  dns.fromString(STATIC_DNS);
  WiFi.config(ip, gw, sn, dns);

  Serial.print("[WiFi] Connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > 20000) {
      Serial.println("[WiFi] Timeout");
      return;
    }
    delay(500);
    Serial.print(".");
  }

  Serial.print("\n[WiFi] Connected, IP: ");
  Serial.println(WiFi.localIP());
}

void scanForXIAO() {
  if (!bleScan) {
    return;
  }

  Serial.println("[BLE] Scanning for XIAO-TB...");
  BLEScanResults found = bleScan->start(2, false);
  for (int i = 0; i < found.getCount(); i++) {
    BLEAdvertisedDevice d = found.getDevice(i);
    if (d.getName() == XIAO_DEVICE_NAME) {
      Serial.print("[BLE] Found XIAO-TB RSSI=");
      Serial.println(d.getRSSI());
      connectToXIAO(d);
      break;
    }
  }
  bleScan->clearResults();
}

void connectToXIAO(BLEAdvertisedDevice device) {
  if (xiaoConnected) {
    return;
  }

  if (bleClient == nullptr) {
    bleClient = BLEDevice::createClient();
    bleClient->setClientCallbacks(new ClientCallbacks());
  }

  Serial.print("[BLE] Connecting...");
  if (!bleClient->connect(&device)) {
    Serial.println("failed");
    return;
  }
  Serial.println("ok");

  BLERemoteService *service = bleClient->getService(SERVICE_UUID);
  if (!service) {
    Serial.println("[BLE] Service missing");
    bleClient->disconnect();
    return;
  }

  dataChar = service->getCharacteristic(DATA_CHAR_UUID);
  batteryChar = service->getCharacteristic(BATTERY_CHAR_UUID);
  if (!dataChar) {
    Serial.println("[BLE] Data characteristic missing");
    bleClient->disconnect();
    return;
  }

  dataChar->registerForNotify(dataNotifyCallback);
  if (batteryChar) {
    batteryChar->registerForNotify(batteryNotifyCallback);
  }

  xiaoConnected = true;
  Serial.println("[BLE] Ready");
}

void dataNotifyCallback(BLERemoteCharacteristic *pChar, uint8_t *data, size_t length, bool isNotify) {
  (void)pChar;
  (void)isNotify;

  if (length != sizeof(Sample)) {
    badPacketCount++;
    if (badPacketCount <= 5 || badPacketCount % 50 == 0) {
      Serial.print("[BLE] Unexpected sample length: ");
      Serial.println(length);
    }
    return;
  }

  Sample sample;
  memcpy(&sample, data, sizeof(Sample));
  enqueueSample(sample);

  samplesReceived++;
  lastSeq = sample.seq;
}

void batteryNotifyCallback(BLERemoteCharacteristic *pChar, uint8_t *data, size_t length, bool isNotify) {
  (void)pChar;
  (void)isNotify;

  if (length != 4) {
    return;
  }

  lastBatteryMv = (uint16_t)(data[0] | (data[1] << 8));
  lastBatteryPercent = data[2];
  lastBatteryState = data[3];
  lastBatteryUpdateMs = millis();
}

bool initStorage() {
  if (!FFat.begin(true)) {
    fsAvailable = false;
    flashPendingSamples = 0;
    Serial.println("[FFat] mount failed");
    return false;
  }

  fsAvailable = true;
  flashPendingSamples = countFlashSamples();
  Serial.print("[FFat] ready, pending samples: ");
  Serial.println(flashPendingSamples);
  return true;
}

uint32_t countFlashSamples() {
  if (!fsAvailable || !FFat.exists(FLASH_PENDING_FILE)) {
    return 0;
  }

  File file = FFat.open(FLASH_PENDING_FILE, FILE_READ);
  if (!file) {
    return 0;
  }

  uint32_t count = 0;
  while (file.available()) {
    String line = file.readStringUntil('\n');
    if (line.length() > 0) {
      count++;
    }
  }
  file.close();
  return count;
}

bool appendSampleToFlash(const Sample &sample) {
  if (!fsAvailable) {
    return false;
  }

  File file = FFat.open(FLASH_PENDING_FILE, FILE_APPEND);
  if (!file) {
    return false;
  }

  file.print(sample.timestamp_local_ms);
  file.print(',');
  file.print(sample.accel_x);
  file.print(',');
  file.print(sample.accel_y);
  file.print(',');
  file.print(sample.accel_z);
  file.print(',');
  file.print(sample.seq);
  file.print('\n');
  file.close();

  flashPendingSamples++;
  samplesSpilledToFlash++;
  return true;
}

bool parseFlashLine(const String &line, Sample &sample) {
  if (line.length() == 0) {
    return false;
  }

  const int maxLine = 256;
  char buf[maxLine];
  if (line.length() >= maxLine) {
    return false;
  }
  line.toCharArray(buf, maxLine);

  char *saveptr = nullptr;
  char *token = strtok_r(buf, ",", &saveptr);
  if (!token) return false;
  sample.timestamp_local_ms = (uint64_t)strtoull(token, nullptr, 10);

  token = strtok_r(nullptr, ",", &saveptr);
  if (!token) return false;
  sample.accel_x = (int16_t)strtol(token, nullptr, 10);

  token = strtok_r(nullptr, ",", &saveptr);
  if (!token) return false;
  sample.accel_y = (int16_t)strtol(token, nullptr, 10);

  token = strtok_r(nullptr, ",", &saveptr);
  if (!token) return false;
  sample.accel_z = (int16_t)strtol(token, nullptr, 10);

  token = strtok_r(nullptr, ",", &saveptr);
  if (!token) return false;
  sample.seq = (uint16_t)strtoul(token, nullptr, 10);

  return true;
}

void dropFlashPrefix(uint32_t linesToDrop) {
  if (!fsAvailable || !FFat.exists(FLASH_PENDING_FILE) || linesToDrop == 0) {
    return;
  }

  File in = FFat.open(FLASH_PENDING_FILE, FILE_READ);
  if (!in) {
    return;
  }
  File out = FFat.open(FLASH_TMP_FILE, FILE_WRITE);
  if (!out) {
    in.close();
    return;
  }

  uint32_t skipped = 0;
  while (in.available()) {
    String line = in.readStringUntil('\n');
    if (line.length() == 0) {
      continue;
    }
    if (skipped < linesToDrop) {
      skipped++;
      continue;
    }
    out.println(line);
  }

  in.close();
  out.close();
  FFat.remove(FLASH_PENDING_FILE);
  FFat.rename(FLASH_TMP_FILE, FLASH_PENDING_FILE);

  if (linesToDrop > flashPendingSamples) {
    flashPendingSamples = 0;
  } else {
    flashPendingSamples -= linesToDrop;
  }
}

void enqueueSample(const Sample &sample) {
  if (ramCount == RAM_QUEUE_SIZE) {
    ramOverflows++;
    Sample oldest = ramQueue[ramTail];
    bool spilled = appendSampleToFlash(oldest);
    if (!spilled) {
      samplesDropped++;
    }
    ramTail = (ramTail + 1) % RAM_QUEUE_SIZE;
    ramCount--;
  }

  ramQueue[ramHead] = sample;
  ramHead = (ramHead + 1) % RAM_QUEUE_SIZE;
  ramCount++;
}

int collectPendingBatch(Sample *out, int maxSamples, bool &hasMore, int &takenFromFlash) {
  hasMore = false;
  takenFromFlash = 0;
  int count = 0;

  if (fsAvailable && FFat.exists(FLASH_PENDING_FILE) && count < maxSamples) {
    File file = FFat.open(FLASH_PENDING_FILE, FILE_READ);
    if (file) {
      while (file.available() && count < maxSamples) {
        String line = file.readStringUntil('\n');
        if (line.length() == 0) {
          continue;
        }
        Sample s;
        if (parseFlashLine(line, s)) {
          out[count++] = s;
          takenFromFlash++;
        }
      }
      if (file.available()) {
        hasMore = true;
      }
      file.close();
    }
  }

  int toRead = ramCount;
  int idx = ramTail;
  while (toRead > 0 && count < maxSamples) {
    out[count++] = ramQueue[idx];
    idx = (idx + 1) % RAM_QUEUE_SIZE;
    toRead--;
  }
  if (toRead > 0) {
    hasMore = true;
  }

  return count;
}

void handleId() {
  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["fw_version"] = FW_VERSION;
  doc["board"] = "nano_esp32";
  doc["sensor_type"] = "toothbrush";
  doc["channel_count"] = 3;
  doc["sample_interval_ms"] = SAMPLE_INTERVAL_MS;

  JsonArray endpoints = doc["endpoints"].to<JsonArray>();
  endpoints.add("/id");
  endpoints.add("/data");
  endpoints.add("/status");

  String out;
  serializeJson(doc, out);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", out);
}

void handleData() {
  bool hasMore = false;
  int fromFlash = 0;
  int count = collectPendingBatch(responseBatch, MAX_BATCH_SAMPLES, hasMore, fromFlash);

  server.setContentLength(CONTENT_LENGTH_UNKNOWN);
  server.sendHeader("Content-Type", "application/json");
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", "");

  char buf[64];

  server.sendContent("{\"timestamps\":[");
  for (int i = 0; i < count; i++) {
    snprintf(buf, sizeof(buf), "%llu", (unsigned long long)responseBatch[i].timestamp_local_ms);
    server.sendContent(buf);
    if (i < count - 1) {
      server.sendContent(",");
    }
  }

  // sensors[0]=x, sensors[1]=y, sensors[2]=z
  server.sendContent("],\"sensors\":[[");
  for (int i = 0; i < count; i++) {
    snprintf(buf, sizeof(buf), "%d", responseBatch[i].accel_x);
    server.sendContent(buf);
    if (i < count - 1) server.sendContent(",");
  }
  server.sendContent("],[");
  for (int i = 0; i < count; i++) {
    snprintf(buf, sizeof(buf), "%d", responseBatch[i].accel_y);
    server.sendContent(buf);
    if (i < count - 1) server.sendContent(",");
  }
  server.sendContent("],[");
  for (int i = 0; i < count; i++) {
    snprintf(buf, sizeof(buf), "%d", responseBatch[i].accel_z);
    server.sendContent(buf);
    if (i < count - 1) server.sendContent(",");
  }
  server.sendContent("]]}");
  server.sendContent("");

  if (fromFlash > 0) {
    dropFlashPrefix((uint32_t)fromFlash);
  }

  int clearFromRam = count - fromFlash;
  while (clearFromRam > 0 && ramCount > 0) {
    ramTail = (ramTail + 1) % RAM_QUEUE_SIZE;
    ramCount--;
    clearFromRam--;
  }

  samplesServed += (uint32_t)count;

  if (hasMore) {
    Serial.println("[WARN] /data served MAX_BATCH_SAMPLES; backlog remains");
  }
}

void handleStatus() {
  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["fw_version"] = FW_VERSION;
  doc["xiao_connected"] = xiaoConnected;
  doc["wifi_connected"] = (WiFi.status() == WL_CONNECTED);
  doc["wifi_rssi"] = WiFi.RSSI();

  doc["ram_queue_depth"] = ramCount;
  doc["ram_queue_capacity"] = RAM_QUEUE_SIZE;
  doc["flash_pending_samples"] = flashPendingSamples;
  doc["max_batch_samples"] = MAX_BATCH_SAMPLES;

  doc["samples_received"] = samplesReceived;
  doc["samples_served"] = samplesServed;
  doc["samples_spilled_flash"] = samplesSpilledToFlash;
  doc["samples_dropped"] = samplesDropped;
  doc["ram_overflows"] = ramOverflows;
  doc["bad_packet_count"] = badPacketCount;
  doc["last_seq"] = lastSeq;

  doc["sample_interval_ms"] = SAMPLE_INTERVAL_MS;

  doc["battery_mv"] = lastBatteryMv;
  doc["battery_percent"] = lastBatteryPercent;
  doc["battery_state"] = lastBatteryState;
  doc["battery_update_ms"] = lastBatteryUpdateMs;

  String out;
  serializeJson(doc, out);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", out);
}

void handleNotFound() {
  server.send(404, "text/plain", "Not found. Try GET /id, GET /data, or GET /status");
}

