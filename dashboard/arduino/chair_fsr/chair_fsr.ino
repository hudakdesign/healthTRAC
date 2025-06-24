// chair_fsr.ino
// -------------
// Reads a force-sensitive resistor (FSR) on analog pin A0.
// Adjusts the sampling rate based on a force threshold:
//   • Idle mode: low rate when force is below or equal to threshold
//   • Active mode: high rate when force exceeds threshold
// Streams timestamped readings over Serial at 115200 baud in CSV format.

const int FSR_PIN         = A0;      // analog input pin for FSR
const int THRESHOLD       = 300;     // ADC value threshold (0–1023), calibrate as needed
const int IDLE_RATE_HZ    = 2;       // sampling rate (Hz) when FSR ≤ THRESHOLD
const int ACTIVE_RATE_HZ  = 50;      // sampling rate (Hz) when FSR > THRESHOLD

unsigned long lastSampleTime = 0;    // timestamp of last sample (millis)
int currentRateHz = IDLE_RATE_HZ;    // current sampling rate, starts in idle mode

void setup() {
  // Initialize USB serial at 115200 baud
  Serial.begin(115200);
  // Configure the FSR pin as an input
  pinMode(FSR_PIN, INPUT);
}

void loop() {
  // Get current time in milliseconds since Arduino reset
  unsigned long now = millis();
  // Compute the interval between samples in milliseconds
  unsigned long interval = 1000UL / currentRateHz;

  // Check if it's time to take the next sample
  if (now - lastSampleTime >= interval) {
    lastSampleTime = now;

    // Read raw ADC value from the FSR (0–1023)
    int rawValue = analogRead(FSR_PIN);

    // Update sampling rate based on threshold
    if (rawValue > THRESHOLD) {
      // Force exceeded threshold: switch to active (high) rate
      currentRateHz = ACTIVE_RATE_HZ;
    } else {
      // Force below or equal threshold: switch to idle (low) rate
      currentRateHz = IDLE_RATE_HZ;
    }

    // Transmit CSV: "<timestamp_ms>,<raw_adc>"
    Serial.print(now);
    Serial.print(",");
    Serial.println(rawValue);
  }

  // (Optional) Add other non-blocking tasks here
}