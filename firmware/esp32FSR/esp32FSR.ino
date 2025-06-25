/**
 * ESP32 FSR Firmware for HealthTRAC
 * Reads force sensitive resistor and streams via USB serial
 */

#define FSR_PIN 34  // Analog pin for FSR (GPIO34 = ADC1_CH6)
#define LED_PIN 2   // Built-in LED

// Sampling configuration
const int IDLE_RATE_MS = 500;    // 2 Hz when idle
const int ACTIVE_RATE_MS = 20;   // 50 Hz when active
const int FORCE_THRESHOLD = 100; // ADC threshold for activity
const int AVG_SAMPLES = 5;       // Number of samples to average

// State
bool streaming = false;
unsigned long lastSample = 0;
int currentRate = IDLE_RATE_MS;
float lastValue = 0;

// Moving average buffer
int avgBuffer[AVG_SAMPLES];
int avgIndex = 0;

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(FSR_PIN, INPUT);

  // Initialize averaging buffer
  for (int i = 0; i < AVG_SAMPLES; i++) {
    avgBuffer[i] = 0;
  }

  // Wait for serial
  while (!Serial) {
    delay(10);
  }

  Serial.println("# ESP32 FSR Ready");
  Serial.println("# Commands: START, STOP");
}

void loop() {
  // Check for commands
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "START") {
      streaming = true;
      digitalWrite(LED_PIN, HIGH);
      Serial.println("# Streaming started");
    }
    else if (cmd == "STOP") {
      streaming = false;
      digitalWrite(LED_PIN, LOW);
      Serial.println("# Streaming stopped");
    }
    else if (cmd == "INFO") {
      Serial.println("# ESP32 FSR Sensor");
      Serial.print("# Streaming: ");
      Serial.println(streaming ? "Yes" : "No");
      Serial.print("# Rate: ");
      Serial.print(1000.0 / currentRate);
      Serial.println(" Hz");
    }
  }

  // Sample if streaming
  if (streaming && (millis() - lastSample >= currentRate)) {
    lastSample = millis();

    // Read multiple samples for averaging
    int sum = 0;
    for (int i = 0; i < AVG_SAMPLES; i++) {
      sum += analogRead(FSR_PIN);
      delayMicroseconds(100);
    }
    int avgValue = sum / AVG_SAMPLES;

    // Update moving average
    avgBuffer[avgIndex] = avgValue;
    avgIndex = (avgIndex + 1) % AVG_SAMPLES;

    // Calculate smoothed value
    sum = 0;
    for (int i = 0; i < AVG_SAMPLES; i++) {
      sum += avgBuffer[i];
    }
    float smoothedValue = (float)sum / AVG_SAMPLES;

    // Adjust sample rate based on activity
    if (abs(smoothedValue - lastValue) > FORCE_THRESHOLD || smoothedValue > FORCE_THRESHOLD) {
      currentRate = ACTIVE_RATE_MS;
    } else {
      currentRate = IDLE_RATE_MS;
    }

    lastValue = smoothedValue;

    // Send data: timestamp,value
    float timestamp = millis() / 1000.0;
    Serial.print(timestamp, 3);
    Serial.print(",");
    Serial.println(smoothedValue, 1);
  }
}