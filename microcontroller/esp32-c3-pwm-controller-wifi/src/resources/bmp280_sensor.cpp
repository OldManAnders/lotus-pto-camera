#include "resources/bmp280_sensor.h"
#include "config.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Adafruit_BMP280.h>
#include <Adafruit_Sensor.h>

// ##################################################################################
// ##                              STATIC VARIABLES                                ##
// ##################################################################################
static Adafruit_BMP280 bmp; // Uses Wire (I2C) by default
static constexpr uint8_t BMP280_I2C_ADDRESS = Config::BMP280_I2C_ADDRESS;

// ##################################################################################
// ##                             SENSOR DEFINITION                                ##
// ##################################################################################
bool Bmp280Sensor::begin() {
  _ready = bmp.begin(BMP280_I2C_ADDRESS);
  if (!_ready) {
    Serial.printf("Bmp280Sensor: sensor not found at 0x%02X\n", BMP280_I2C_ADDRESS);
  } else {
    Serial.printf("Bmp280Sensor: sensor ready at 0x%02X\n", BMP280_I2C_ADDRESS);
  }
  return _ready;
}

bool Bmp280Sensor::read() {
  if (!_ready) return false;

  _temperature = bmp.readTemperature();        // °C
  _pressure    = bmp.readPressure() / 100.0f;  // Pa → hPa

  //Serial.printf(
  //  "Bmp280Sensor: T=%.2f°C  P=%.2fhPa\n",
  //  _temperature, _pressure
  //);
  return true;
}

float Bmp280Sensor::getTemperature() const { return _temperature; }
float Bmp280Sensor::getPressure()    const { return _pressure; }
bool  Bmp280Sensor::isReady()        const { return _ready; }

// ##################################################################################
// ##                            PROVIDER DEFINITION                               ##
// ##################################################################################
Bmp280Provider::Bmp280Provider(Bmp280Sensor& sensor) : _sensor(sensor) {}

bool Bmp280Provider::matchesKey(const char* key) const {
  return strncmp(key, "sensor", 6) == 0;
}

// Read-only sensor — SET is not supported
bool Bmp280Provider::handleSet(const char* key, const JsonVariant& value, JsonDocument& reply) {
  reply["success"] = false;
  reply["error"]   = "BMP280 is read-only; SET not supported";
  return false;
}

bool Bmp280Provider::handleGet(const char* key, JsonDocument& reply) {
  if (!_sensor.isReady()) {
    reply["success"] = false;
    reply["error"]   = "sensor not initialised";
    return false;
  }

  // Refresh readings before responding
  _sensor.read();

  if (strcmp(key, "sensor.temperature") == 0) {
    reply["success"] = true;
    reply["key"]     = key;
    reply["value"]   = _sensor.getTemperature();
    reply["unit"]    = "°C";
    return true;
  }

  if (strcmp(key, "sensor.pressure") == 0) {
    reply["success"] = true;
    reply["key"]     = key;
    reply["value"]   = _sensor.getPressure();
    reply["unit"]    = "hPa";
    return true;
  }

  if (strcmp(key, "sensor.all") == 0) {
    reply["success"] = true;
    reply["key"]     = key;
    _fillAllReadings(reply);
    return true;
  }

  return false; // unknown key
}

bool Bmp280Provider::handleCmd(const char* cmd, const JsonVariant& params, JsonDocument& reply) {
  if (strcmp(cmd, "sensor.read") == 0) {
    if (!_sensor.isReady()) {
      reply["success"] = false;
      reply["error"]   = "sensor not initialised";
      return false;
    }
    bool ok = _sensor.read();
    reply["success"] = ok;
    reply["cmd"]     = cmd;
    if (ok) {
      _fillAllReadings(reply);
    } else {
      reply["error"] = "read failed";
    }
    return true;
  }

  return false; // unknown command
}

void Bmp280Provider::_fillAllReadings(JsonDocument& reply) const {
  reply["temperature"]["value"] = _sensor.getTemperature();
  reply["temperature"]["unit"]  = "°C";
  reply["pressure"]["value"]    = _sensor.getPressure();
  reply["pressure"]["unit"]     = "hPa";
}
