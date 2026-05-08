#include "resources/bme280_sensor.h"
#include "config.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Adafruit_BME280.h>
#include <Adafruit_Sensor.h>

// ##################################################################################
// ##                              STATIC VARIABLES                                ##
// ##################################################################################
static Adafruit_BME280 bme; // Uses Wire (I2C) by default
static constexpr uint8_t BME280_I2C_ADDRESS = Config::BME280_I2C_ADDRESS;

// ##################################################################################
// ##                             SENSOR DEFINITION                                ##
// ##################################################################################
bool Bme280Sensor::begin() {
  _ready = bme.begin(BME280_I2C_ADDRESS);
  if (!_ready) {
    Serial.printf("Bme280Sensor: sensor not found at 0x%02X\n", BME280_I2C_ADDRESS);
  } else {
    Serial.printf("Bme280Sensor: sensor ready at 0x%02X\n", BME280_I2C_ADDRESS);
  }
  return _ready;
}

bool Bme280Sensor::read() {
  if (!_ready) return false;

  _temperature = bme.readTemperature();        // °C
  _humidity    = bme.readHumidity();           // %
  _pressure    = bme.readPressure() / 100.0f;  // Pa → hPa

  Serial.printf(
    "Bme280Sensor: T=%.2f°C  H=%.2f%%  P=%.2fhPa\n",
    _temperature, _humidity, _pressure
  );
  return true;
}

float Bme280Sensor::getTemperature() const { return _temperature; }
float Bme280Sensor::getHumidity()    const { return _humidity; }
float Bme280Sensor::getPressure()    const { return _pressure; }
bool  Bme280Sensor::isReady()        const { return _ready; }

// ##################################################################################
// ##                            PROVIDER DEFINITION                               ##
// ##################################################################################
Bme280Provider::Bme280Provider(Bme280Sensor& sensor) : _sensor(sensor) {}

bool Bme280Provider::matchesKey(const char* key) const {
  return strncmp(key, "sensor", 6) == 0;
}

// Read-only sensor — SET is not supported
bool Bme280Provider::handleSet(const char* key, const JsonVariant& value, JsonDocument& reply) {
  reply["success"] = false;
  reply["error"]   = "BME280 is read-only; SET not supported";
  return false;
}

bool Bme280Provider::handleGet(const char* key, JsonDocument& reply) {
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

  if (strcmp(key, "sensor.humidity") == 0) {
    reply["success"] = true;
    reply["key"]     = key;
    reply["value"]   = _sensor.getHumidity();
    reply["unit"]    = "%";
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

bool Bme280Provider::handleCmd(const char* cmd, const JsonVariant& params, JsonDocument& reply) {
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

void Bme280Provider::_fillAllReadings(JsonDocument& reply) const {
  reply["temperature"]["value"] = _sensor.getTemperature();
  reply["temperature"]["unit"]  = "°C";
  reply["humidity"]["value"]    = _sensor.getHumidity();
  reply["humidity"]["unit"]     = "%";
  reply["pressure"]["value"]    = _sensor.getPressure();
  reply["pressure"]["unit"]     = "hPa";
}
