// Library for encoding and decoding data polls as strings to allow efficient
// transmission over bluetooth low energy
#ifndef DATA_POLL_H
#define DATA_POLL_H

#include <cstring>

class DataPoll
{
public:
  // Stores poll data for the DataPoll object
  struct
  {
    uint32_t timestamp;
    int16_t accelX, accelY, accelZ;
  } data;

  // Creates DataPoll object with provided parameters
  DataPoll(uint32_t timestamp, int16_t accelX, int16_t accelY, int16_t accelZ)
  {
    data.timestamp = timestamp;
    data.accelX = accelX;
    data.accelY = accelY;
    data.accelZ = accelZ;
  }

  // Decodes array of encoded data poll bytes into DataPoll object
  // Example:
  //   ```
  //   uint8_t encodedDataBuffer[sizeof(myDataPoll.data)];
  //   myDataPoll.encodeDataPoll((uint8_t *)&encodedDataBuffer);
  //   DataPoll receivedDataPoll = DataPoll(encodedDataBuffer);
  //   ```
  DataPoll(uint8_t *encodedDataPoll)
  {
    std::memcpy(&data, encodedDataPoll, sizeof(data));
  }

  // Encodes data as bytes and stores it in buffer that is passed by reference
  // Example:
  //   ```
  //   DataPoll myDataPoll = DataPoll(123, 0.05, -0.12, 1.14);
  //   uint8_t encodedDataBuffer[sizeof(myDataPoll.data)];
  //   myDataPoll.encodeDataPoll((uint8_t *)&encodedDataBuffer);
  //   ```
  int encodeDataPoll(uint8_t *encodedDataBuffer)
  {
    std::memcpy(encodedDataBuffer, &data, sizeof(data));
    return 0;
  }
};

#endif