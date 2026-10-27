#include <Arduino.h>
#include <RingBuf.h>
#include <ArduinoJson.h>

// Constants
static const int SELECTION_PINS[] = {8, 9, 10, 11};
static const int MUX_OUTPUT_PIN = A0;
static const int NUM_CHANNELS = 8;
static const int RING_BUF_SIZE = 50;

// Structures
// stores readings from the fsrs at a point in time
struct fsrReadings
{
  int data[NUM_CHANNELS];
};

// Globals
static RingBuf<fsrReadings, RING_BUF_SIZE> fsrReadingsBuffer;

// extracts the k'th bit from n
int getKBit(int n, int k)
{
  // Serial.println("3");
  int mask = 1 << k;
  int masked_n = n & mask;
  return masked_n >> k;
}

// sets selection pins to tell mux which channel to provide
void setMuxChannel(int channel)
{
  // Serial.println("1");
  // convert channel number to binary (4-bits)
  // loop through each selection pin, and assign them based on selection bit
  for (int i = 0; i < (sizeof(SELECTION_PINS) / sizeof(int)); i++)
  {
    // Serial.println("2");
    // if the i'th bit of channel is 1:
    if (getKBit(channel, i))
    {
      // set the selection pin to high
      digitalWrite(SELECTION_PINS[i], HIGH);
    }
    else
    {
      // otherwise set the selection pin to low
      digitalWrite(SELECTION_PINS[i], LOW);
    }
  }

  delayMicroseconds(1);
}

// gets the analog output of the mux
int getMuxOutput(int channel, int output_pin)
{
  setMuxChannel(channel);
  return analogRead(output_pin);
}

fsrReadings getAverageBufferReadings()
{
  fsrReadings averageFsrReadings = fsrReadingsBuffer[0];

  // Add up all of the readings
  for (int i = 1; i < fsrReadingsBuffer.size(); i++)
  {
    fsrReadings fsrReadingToAdd = fsrReadingsBuffer[i];

    // Add each of the channels
    for (int j = 0; j < NUM_CHANNELS; j++)
    {
      averageFsrReadings.data[j] += fsrReadingToAdd.data[j];
    }
  }

  // Divide by the size for each channel (get the average)
  for (int i = 0; i < NUM_CHANNELS; i++)
  {
    averageFsrReadings.data[i] = averageFsrReadings.data[i] / fsrReadingsBuffer.size();
  }

  // Return the average
  return averageFsrReadings;
}

void setup()
{
  Serial.begin(115200);

  // configure selection pins
  for (int i = 0; i < (sizeof(SELECTION_PINS) / sizeof(int)); i++)
  {
    pinMode(SELECTION_PINS[i], OUTPUT);
  }

  // configure mux output pin (funnily set to input)
  pinMode(MUX_OUTPUT_PIN, INPUT);
}

void loop()
{
  // fill an fsrReadings struct with data and push it to the buffer
  fsrReadings currentFsrReadings;
  for (int i = 0; i < NUM_CHANNELS; i++)
  {
    currentFsrReadings.data[i] = getMuxOutput(i, MUX_OUTPUT_PIN);
  }

  // push it to the buffer
  fsrReadingsBuffer.pushOverwrite(currentFsrReadings);

  // check if a poll has been requested
  if (Serial.available())
  {
    char rxChar = Serial.read();

    // Responds with channel index sent over serial
    switch (rxChar)
    {
    case 'p':
      int averageStartTime = micros();

      // when polled, output the average for each fsr reading in the buffer
      fsrReadings averageReadings = getAverageBufferReadings();
      int timeToAverage = micros() - averageStartTime;

      // create json document
      JsonDocument doc;
      JsonArray data = doc["data"].to<JsonArray>();
      doc["timeToAverageUs"] = timeToAverage;

      // add each average reading to the document
      for (int i = 0; i < NUM_CHANNELS; i++)
      {
        data.add(averageReadings.data[i]);
      }

      // print out the json over serial
      serializeJson(doc, Serial);
      Serial.println();
    }
  }

  delay(1);
}