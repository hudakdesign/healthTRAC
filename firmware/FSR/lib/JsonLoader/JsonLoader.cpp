#include "JsonLoader.h"

const char *LOAD_JSON_READY = "loadJson";
const char *LOAD_JSON_SUCCESS = "success";
const char *LOAD_JSON_FAILURE = "failure";

int mountFilesystem() {
    // try to mount filesystem
    // format and return 1 if it fails
    if (!FFat.begin(1)) {
        return 1;
    }

    // if nothing goes wrong then return 0
    return 0;
}

int loadJson(const char *filename, JsonDocument &doc) {
  // open file for reading
  File file = FFat.open(filename);

  // deserialize the json document
  DeserializationError error = deserializeJson(doc, file);
  // if there is an error deserializing then return 1
  if (error)
  {
    return 1;
  }

  // if nothing went wrong then return 0
  return 0;
}

int loadJsonFromSerial(JsonDocument &doc) {
  // prints out message to indicate readiness to receive json
  Serial.println(LOAD_JSON_READY);

  // deserialize the incoming json from serial
  DeserializationError error = deserializeJson(doc, Serial);
  // if there is an error deserializing then print failure message
  // and return 1
  if (error)
  {
    Serial.println(LOAD_JSON_FAILURE);
    return 1;
  }

  // if nothing went wrong then print success message
  Serial.println(LOAD_JSON_SUCCESS);

  // and return 0
  return 0;
}

int saveJson(const char *filename, const JsonDocument &doc) {
  // delete the file if it exists
  FFat.remove(filename);

  // open file for writing
  File file = FFat.open(filename, FILE_WRITE);
  // if the file fails to open, then return 1
  if (!file)
  {
    return 1;
  }

  // try to write the json to the file
  if (serializeJson(doc, file) == 0)
  {
    // return 2 if something goes wrong
    return 2;
  }

  // if nothing went wrong then return 0
  return 0;
}