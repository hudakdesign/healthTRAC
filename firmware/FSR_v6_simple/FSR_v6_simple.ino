#include <Arduino.h>
#include <ArduinoJson.h>
#include <FFat.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <WiFi.h>
#include "soc/rtc_cntl_reg.h"
#include "soc/soc.h"

// ==========================================================================
// FSR Bridge v6 Simple
// - 100 Hz sampling
// - Destructive GET /data returning {timestamps, sensors}
// - GET /id and GET /status
// - RAM-first buffer with optional FFat spillover
// ==========================================================================

#define WIFI_SSID "CBI IoT"
#define WIFI_PASSWORD "cbir00lz"

#define HUB_IP "10.0.1.2"
#define HUB_TIME_API "http://" HUB_IP ":8080/api/time"

#define DEVICE_ID "FSR1"
#define FW_VERSION "fsr_v6_simple_20260505"

#define STATIC_IP "10.0.1.10"
#define STATIC_GATEWAY "10.0.1.1"
#define STATIC_SUBNET "255.255.255.0"
#define STATIC_DNS "8.8.8.8"

#ifndef FSR_CHANNEL_COUNT
#define FSR_CHANNEL_COUNT 8
#endif

const unsigned long SAMPLE_INTERVAL_MS = 10;      // 100 Hz
const unsigned long TIME_SYNC_INTERVAL_MS = 30000;
const unsigned long TIME_SYNC_RETRY_MS = 5000;
const unsigned long MAX_SYNC_AGE_MS = 180000;

const uint8_t kMaxFsrChannels = 16;
const uint8_t kMuxAddressableChannels = 16;
const uint8_t kConfiguredChannels = FSR_CHANNEL_COUNT < 1 ? 1 : FSR_CHANNEL_COUNT;
const uint8_t kActiveChannels = kConfiguredChannels > kMuxAddressableChannels ? kMuxAddressableChannels : kConfiguredChannels;

const uint8_t kSelPins = 4;
const byte selPins[kSelPins] = {8, 9, 10, 11};
const int readPin = A0;
const int enablePin = A7;

const uint8_t kCalibrationSamples = 20;
const uint16_t kCalibrationMargin = 50;
const uint16_t kMinThreshold = 100;
int16_t channelBaseline[kMaxFsrChannels] = {0};
uint16_t channelThresholds[kMaxFsrChannels] = {0};
byte setCalibPin = 2;
byte calibBtnPin = 3;
bool calibState = HIGH;

// 100 Hz * 12 sec
const int RAM_QUEUE_SIZE = 1200;
const int MAX_BATCH_SAMPLES = 1200;

struct Sample {
  uint32_t localMs;
  uint16_t rawAdc[kMaxFsrChannels];
};

Sample ramQueue[RAM_QUEUE_SIZE];
int ramHead = 0;
int ramTail = 0;
int ramCount = 0;

Sample responseBatch[MAX_BATCH_SAMPLES];

const char *FLASH_PENDING_FILE = "/fsr_simple_pending.csv";
const char *FLASH_TMP_FILE = "/fsr_simple_pending_tmp.csv";
bool fsAvailable = false;
uint32_t flashPendingSamples = 0;

bool timeSynced = false;
double clockModelA = 1.0;
int64_t clockModelBMs = 0;
uint32_t lastSyncLocalMs = 0;
int64_t lastSyncHubMs = 0;
bool hasPriorSyncPoint = false;
uint32_t lastSyncRttMs = 0;
uint32_t lastSyncSuccessMs = 0;
uint32_t syncFailureCount = 0;

uint32_t totalSamplesCollected = 0;
uint32_t totalSamplesServed = 0;
uint32_t samplesSpilledToFlash = 0;
uint32_t samplesDropped = 0;
uint32_t ramOverflows = 0;

unsigned long lastSampleTime = 0;
unsigned long lastTimeSyncAttempt = 0;

WebServer server(80);

void setMuxChannel(int channel);
void calibrateBaselines();
void readFsrs(int chanVals[]);
bool connectWiFi();
bool syncTimeFromHub();
double hubTimestampFromLocal(uint32_t localMs);
const char *clockSyncStatus(unsigned long now);

bool initStorage();
uint32_t countFlashSamples();
bool appendSampleToFlash(const Sample &sample);
bool parseFlashLine(const String &line, Sample &sample);
void dropFlashPrefix(uint32_t linesToDrop);

void enqueueSample(int chanVals[]);
int collectPendingBatch(Sample *out, int maxSamples, bool &hasMore, int &takenFromFlash);

void handleId();
void handleData();
void handleStatus();
void handleNotFound();

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  delay(1000);

  Serial.println("========================================");
  Serial.println("Health TRAC - FSR Bridge v6 Simple");
  Serial.println("========================================");
  Serial.print("FW: ");
  Serial.println(FW_VERSION);
  Serial.print("Device ID: ");
  Serial.println(DEVICE_ID);
  Serial.print("Channels: ");
  Serial.println(kActiveChannels);

  for (uint8_t i = 0; i < kSelPins; i++) {
    pinMode(selPins[i], OUTPUT);
    digitalWrite(selPins[i], LOW);
  }
  pinMode(readPin, INPUT);
  pinMode(enablePin, OUTPUT);
  digitalWrite(enablePin, LOW);
  pinMode(setCalibPin, INPUT_PULLUP);
  pinMode(calibBtnPin, INPUT_PULLUP);

  for (uint8_t ch = 0; ch < kActiveChannels; ch++) {
    channelThresholds[ch] = kMinThreshold;
  }

  calibrateBaselines();
  initStorage();
  connectWiFi();
  syncTimeFromHub();

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

  unsigned long syncAge = now - lastTimeSyncAttempt;
  unsigned long interval = timeSynced ? TIME_SYNC_INTERVAL_MS : TIME_SYNC_RETRY_MS;
  if (syncAge >= interval) {
    syncTimeFromHub();
  }

  if (now - lastSampleTime < SAMPLE_INTERVAL_MS) {
    return;
  }
  lastSampleTime = now;

  calibState = digitalRead(setCalibPin);
  int chanVals[kMaxFsrChannels];
  readFsrs(chanVals);

  if (calibState == LOW) {
    for (uint8_t ch = 0; ch < kActiveChannels; ch++) {
      Serial.print(chanVals[ch]);
      if (ch < kActiveChannels - 1) {
        Serial.print(",");
      }
    }
    Serial.println();
    return;
  }

  enqueueSample(chanVals);
}

void setMuxChannel(int channel) {
  for (uint8_t i = 0; i < kSelPins; i++) {
    digitalWrite(selPins[i], bitRead(channel, i));
  }
}

void readFsrs(int chanVals[]) {
  for (uint8_t ch = 0; ch < kActiveChannels; ch++) {
    setMuxChannel(ch);
    delayMicroseconds(50);
    chanVals[ch] = analogRead(readPin);
  }
  for (uint8_t ch = kActiveChannels; ch < kMaxFsrChannels; ch++) {
    chanVals[ch] = 0;
  }
}

void calibrateBaselines() {
  Serial.println("Calibrating (do NOT press any FSR)...");
  long sums[kMaxFsrChannels] = {0};

  for (uint8_t s = 0; s < kCalibrationSamples; s++) {
    for (uint8_t ch = 0; ch < kActiveChannels; ch++) {
      setMuxChannel(ch);
      delayMicroseconds(200);
      analogRead(readPin);
      delayMicroseconds(100);
      sums[ch] += analogRead(readPin);
    }
    delay(20);
  }

  Serial.println("  Ch  Baseline  Threshold");
  for (uint8_t ch = 0; ch < kActiveChannels; ch++) {
    channelBaseline[ch] = (int16_t)(sums[ch] / kCalibrationSamples);
    uint16_t t = (uint16_t)channelBaseline[ch] + kCalibrationMargin;
    if (t < kMinThreshold) {
      t = kMinThreshold;
    }
    channelThresholds[ch] = t;
    Serial.printf("  %2d   %4d      %4d\n", ch + 1, channelBaseline[ch], channelThresholds[ch]);
  }
  Serial.println("Calibration done.");
}

bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  WiFi.mode(WIFI_STA);
  WiFi.setTxPower(WIFI_POWER_2dBm);

  IPAddress ip, gw, sn, dns;
  ip.fromString(STATIC_IP);
  gw.fromString(STATIC_GATEWAY);
  sn.fromString(STATIC_SUBNET);
  dns.fromString(STATIC_DNS);
  WiFi.config(ip, gw, sn, dns);

  Serial.print("WiFi connecting to: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > 20000) {
      Serial.println("WiFi timeout");
      return false;
    }
    delay(500);
    Serial.print(".");
  }

  Serial.print("\nWiFi connected, IP: ");
  Serial.println(WiFi.localIP());
  return true;
}

bool syncTimeFromHub() {
  lastTimeSyncAttempt = millis();

  if (WiFi.status() != WL_CONNECTED) {
    timeSynced = false;
    return false;
  }

  uint32_t localRequestStartMs = millis();
  HTTPClient http;
  http.begin(HUB_TIME_API);
  int httpCode = http.GET();

  if (httpCode != HTTP_CODE_OK) {
    http.end();
    syncFailureCount++;
    return false;
  }

  String payload = http.getString();
  http.end();

  JsonDocument doc;
  if (deserializeJson(doc, payload)) {
    syncFailureCount++;
    return false;
  }

  uint64_t hubMs = 0;
  if (!doc["timestamp_ns"].isNull()) {
    hubMs = doc["timestamp_ns"].as<uint64_t>() / 1000000ULL;
  } else if (!doc["timestamp_s"].isNull()) {
    hubMs = (uint64_t)(doc["timestamp_s"].as<double>() * 1000.0);
  } else {
    syncFailureCount++;
    return false;
  }

  uint32_t localResponseEndMs = millis();
  lastSyncRttMs = localResponseEndMs - localRequestStartMs;
  uint32_t localMidpointMs = localRequestStartMs + (lastSyncRttMs / 2);

  if (hasPriorSyncPoint && localMidpointMs > lastSyncLocalMs + 1000U) {
    double localDelta = (double)localMidpointMs - (double)lastSyncLocalMs;
    double hubDelta = (double)hubMs - (double)lastSyncHubMs;
    double candidateA = hubDelta / localDelta;
    if (candidateA > 0.95 && candidateA < 1.05) {
      clockModelA = 0.9 * clockModelA + 0.1 * candidateA;
    }
  }

  double newOffset = (double)hubMs - (clockModelA * (double)localMidpointMs);
  clockModelBMs = (int64_t)(newOffset >= 0.0 ? newOffset + 0.5 : newOffset - 0.5);
  lastSyncLocalMs = localMidpointMs;
  lastSyncHubMs = (int64_t)hubMs;
  hasPriorSyncPoint = true;
  timeSynced = true;
  syncFailureCount = 0;
  lastSyncSuccessMs = millis();
  return true;
}

double hubTimestampFromLocal(uint32_t localMs) {
  if (!timeSynced) {
    return localMs / 1000.0;
  }
  double hubEstimate = (clockModelA * (double)localMs) + (double)clockModelBMs;
  int64_t hubMs = (int64_t)(hubEstimate >= 0.0 ? hubEstimate + 0.5 : hubEstimate - 0.5);
  if (hubMs < 0) {
    hubMs = 0;
  }
  return hubMs / 1000.0;
}

const char *clockSyncStatus(unsigned long now) {
  if (!timeSynced || lastSyncSuccessMs == 0) {
    return "unsynced";
  }
  if (now - lastSyncSuccessMs > MAX_SYNC_AGE_MS) {
    return "stale";
  }
  if (syncFailureCount > 0) {
    return "degraded";
  }
  return "ok";
}

bool initStorage() {
  if (!FFat.begin(true)) {
    fsAvailable = false;
    flashPendingSamples = 0;
    Serial.println("FFat mount failed; spillover disabled");
    return false;
  }

  fsAvailable = true;
  flashPendingSamples = countFlashSamples();
  Serial.print("FFat ready, pending flash samples: ");
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

  file.print(sample.localMs);
  for (uint8_t ch = 0; ch < kActiveChannels; ch++) {
    file.print(',');
    file.print(sample.rawAdc[ch]);
  }
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

  const int maxLine = 512;
  char buf[maxLine];
  if (line.length() >= maxLine) {
    return false;
  }
  line.toCharArray(buf, maxLine);

  char *saveptr = nullptr;
  char *token = strtok_r(buf, ",", &saveptr);
  if (!token) {
    return false;
  }
  sample.localMs = (uint32_t)strtoul(token, nullptr, 10);

  for (uint8_t ch = 0; ch < kActiveChannels; ch++) {
    token = strtok_r(nullptr, ",", &saveptr);
    if (!token) {
      return false;
    }
    sample.rawAdc[ch] = (uint16_t)strtoul(token, nullptr, 10);
  }

  for (uint8_t ch = kActiveChannels; ch < kMaxFsrChannels; ch++) {
    sample.rawAdc[ch] = 0;
  }

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

void enqueueSample(int chanVals[]) {
  Sample sample;
  sample.localMs = millis();
  for (uint8_t ch = 0; ch < kMaxFsrChannels; ch++) {
    sample.rawAdc[ch] = (uint16_t)chanVals[ch];
  }

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
  totalSamplesCollected++;
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
        Sample sample;
        if (parseFlashLine(line, sample)) {
          out[count++] = sample;
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
  doc["sensor_type"] = "fsr";
  doc["channel_count"] = kActiveChannels;
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
    snprintf(buf, sizeof(buf), "%lu", (unsigned long)responseBatch[i].localMs);
    server.sendContent(buf);
    if (i < count - 1) {
      server.sendContent(",");
    }
  }

  server.sendContent("],\"sensors\":[");
  for (uint8_t ch = 0; ch < kActiveChannels; ch++) {
    server.sendContent("[");
    for (int i = 0; i < count; i++) {
      snprintf(buf, sizeof(buf), "%u", responseBatch[i].rawAdc[ch]);
      server.sendContent(buf);
      if (i < count - 1) {
        server.sendContent(",");
      }
    }
    server.sendContent("]");
    if (ch < kActiveChannels - 1) {
      server.sendContent(",");
    }
  }
  server.sendContent("]}");
  server.sendContent("");

  // Destructive clear of exactly what was retrieved.
  if (fromFlash > 0) {
    dropFlashPrefix((uint32_t)fromFlash);
  }

  int clearFromRam = count - fromFlash;
  while (clearFromRam > 0 && ramCount > 0) {
    ramTail = (ramTail + 1) % RAM_QUEUE_SIZE;
    ramCount--;
    clearFromRam--;
  }

  totalSamplesServed += (uint32_t)count;

  if (hasMore) {
    Serial.println("[WARN] /data served MAX_BATCH_SAMPLES; backlog remains");
  }
}

void handleStatus() {
  unsigned long now = millis();

  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["fw_version"] = FW_VERSION;
  doc["uptime_ms"] = now;
  doc["channel_count"] = kActiveChannels;

  doc["ram_queue_depth"] = ramCount;
  doc["ram_queue_capacity"] = RAM_QUEUE_SIZE;
  doc["flash_pending_samples"] = flashPendingSamples;
  doc["max_batch_samples"] = MAX_BATCH_SAMPLES;

  doc["samples_collected"] = totalSamplesCollected;
  doc["samples_served"] = totalSamplesServed;
  doc["samples_spilled_flash"] = samplesSpilledToFlash;
  doc["samples_dropped"] = samplesDropped;
  doc["ram_overflows"] = ramOverflows;

  doc["clock_sync_status"] = clockSyncStatus(now);
  doc["clock_sync_age_ms"] = lastSyncSuccessMs == 0 ? 0 : (now - lastSyncSuccessMs);
  doc["clock_rtt_ms"] = lastSyncRttMs;
  doc["wifi_rssi"] = WiFi.RSSI();
  doc["sample_interval_ms"] = SAMPLE_INTERVAL_MS;

  JsonArray thr = doc["thresholds"].to<JsonArray>();
  for (uint8_t ch = 0; ch < kActiveChannels; ch++) {
    thr.add(channelThresholds[ch]);
  }

  String out;
  serializeJson(doc, out);
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", out);
}

void handleNotFound() {
  server.send(404, "text/plain", "Not found. Try GET /id, GET /data, or GET /status");
}

