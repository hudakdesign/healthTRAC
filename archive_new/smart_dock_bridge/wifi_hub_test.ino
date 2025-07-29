/*
 * HealthTRAC - WiFi Hub Connection Test
 *
 * This sketch does only one thing: It connects to WiFi and then
 * repeatedly tries to open a TCP connection to the hub server.
 * This will confirm if the network path is open and working.
 */

#include <WiFi.h>

// --- Configuration ---
const char* WIFI_SSID     = "CBI IoT";
const char* WIFI_PASSWORD = "cbir00lz";
const char* HUB_HOST      = "10.0.1.3"; // Your Ubuntu VM's IP
const int   HUB_PORT      = 5555;

WiFiClient client;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- WiFi Hub Connection Test ---");

  // Connect to WiFi
  Serial.print("Connecting to WiFi network: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi Connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  Serial.print("\nAttempting to connect to Hub at ");
  Serial.print(HUB_HOST);
  Serial.print(":");
  Serial.println(HUB_PORT);

  // Use our WiFi client to connect to the hub
  if (client.connect(HUB_HOST, HUB_PORT)) {
    Serial.println("✅✅✅ SUCCESS! Connected to the Hub server!");
    client.println("Hello from Arduino!"); // Send a test message
    delay(100);
    client.stop();
    Serial.println("Disconnected from Hub.");
  } else {
    Serial.println("❌❌❌ FAILURE! Could not connect to the Hub server.");
    Serial.println("Check: 1. Is the hub_server.py script running?");
    Serial.println("       2. Is the Ubuntu firewall blocking port 5555?");
    Serial.println("       3. Are the IP address and port correct?");
  }

  Serial.println("Waiting 5 seconds before the next test...");
  delay(5000);
}