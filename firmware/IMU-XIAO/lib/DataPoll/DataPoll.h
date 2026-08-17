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
    long timestamp;
    float accelX, accelY, accelZ;
  } data;

  // Creates DataPoll object with provided parameters
  DataPoll(long timestamp, float accelX, float accelY, float accelZ)
  {
    data.timestamp = timestamp;
    data.accelX = accelX;
    data.accelY = accelY;
    data.accelZ = accelZ;
  }

  // Decodes array of encoded data poll bytes into DataPoll object
  // Example:
  //   ```
  //   char encodedDataBuffer[sizeof(myDataPoll.data)];
  //   myDataPoll.encodeDataPoll((char *)&encodedDataBuffer);
  //   DataPoll receivedDataPoll = DataPoll(encodedDataBuffer);
  //   ```
  DataPoll(char *encodedDataPoll)
  {
    std::memcpy(&data, encodedDataPoll, sizeof(data));
  }

  // Encodes data as bytes and stores it in buffer that is passed by reference
  // Example:
  //   ```
  //   DataPoll myDataPoll = DataPoll(123, 0.05, -0.12, 1.14);
  //   char encodedDataBuffer[sizeof(myDataPoll.data)];
  //   myDataPoll.encodeDataPoll((char *)&encodedDataBuffer);
  //   ```
  int encodeDataPoll(char *encodedDataBuffer)
  {
    std::memcpy(encodedDataBuffer, &data, sizeof(data));
    return 0;
  }
};

#endif