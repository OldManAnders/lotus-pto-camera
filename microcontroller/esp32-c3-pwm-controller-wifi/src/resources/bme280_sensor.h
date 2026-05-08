#ifndef BME280_CONTROLLER_H
#define BME280_CONTROLLER_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include "resources/resource_provider.h"

// ##################################################################################
// ##                            CONTROLLER INTERFACE                              ##
// ##################################################################################
/**
 * Wraps the Adafruit BME280 library.
 * Handles sensor initialisation and provides typed read methods.
 * Readings are cached on each call to read() to avoid hammering I2C.
 */
class Bme280Sensor {
public:
  /**
   * Initialise the BME280. Call once from setup().
   * @param i2cAddr  I2C address of the sensor (default 0x76; some modules use 0x77).
   * @return true if the sensor was found and initialised successfully.
   */
  bool begin();

  /**
   * Sample all three channels and cache the results.
   * Call this before any getter if you want a fresh reading.
   * Returns false when the sensor is not ready / not initialised.
   */
  bool read();

  /** Cached temperature in °C (call read() first). */
  float getTemperature() const;

  /** Cached relative humidity in % (call read() first). */
  float getHumidity() const;

  /** Cached pressure in hPa (call read() first). */
  float getPressure() const;

  /** True after a successful begin(). */
  bool isReady() const;

private:
  bool  _ready       = false;
  float _temperature = 0.0f;
  float _humidity    = 0.0f;
  float _pressure    = 0.0f;
};

// ##################################################################################
// ##                             PROVIDER INTERFACE                               ##
// ##################################################################################
/**
 * ResourceProvider wrapper for Bme280Sensor.
 *
 * Supported GET keys:
 *   "sensor.temperature"  – current temperature in °C
 *   "sensor.humidity"     – current relative humidity in %
 *   "sensor.pressure"     – current pressure in hPa
 *   "sensor.all"          – all three values in one reply
 *
 * Supported commands (handleCmd):
 *   "sensor.read"         – force a fresh sensor read, reply contains all values
 *
 * SET operations are not applicable for a read-only sensor and always return false.
 */
class Bme280Provider : public ResourceProvider {
public:
  explicit Bme280Provider(Bme280Sensor& sensor);

  bool matchesKey(const char* key) const override;
  bool handleSet(const char* key, const JsonVariant& value, JsonDocument& reply) override;
  bool handleGet(const char* key, JsonDocument& reply) override;
  bool handleCmd(const char* cmd, const JsonVariant& params, JsonDocument& reply) override;

private:
  Bme280Sensor& _sensor;

  /** Populate reply with all three readings (assumes read() already called). */
  void _fillAllReadings(JsonDocument& reply) const;
};

#endif // BME280_CONTROLLER_H
