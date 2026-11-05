#ifndef JSON_LOADER_H
#define JSON_LOADER_H

#include "ArduinoJson.h"
#include "FS.h"
#include "FFat.h"

// Mounts FFat filesystem and formats if it fails
int mountFilesystem();

// Takes in a filename, and a reference to a json document
// and populates the document from the file
// returns error codes
int loadJson(const char *filename, JsonDocument &doc);

// Takes in reference to json document
// populates json document from serial
// returns error codes
int loadJsonFromSerial(JsonDocument &doc);

// Takes in a filename and a json document
// saves the json document to the specified file (overwrites existing)
// returns error codes
int saveJson(const char *filename, const JsonDocument &doc);

#endif