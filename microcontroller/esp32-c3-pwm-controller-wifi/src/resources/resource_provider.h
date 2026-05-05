#ifndef RESOURCE_PROVIDER_H
#define RESOURCE_PROVIDER_H

#include <Arduino.h>
#include <ArduinoJson.h>

/**
    This is the base interface for handling modules
    The idea is that all modules/sensors will implement this interface,
    so the message handler can have a standard method of communication, 
    and we can dynamically add/remove modules.
 */
class ResourceProvider {
public:
  virtual ~ResourceProvider() {}
  // Return true if this provider is responsible for the given key (e.g. "pwm" or "sensor.temp").
  virtual bool matchesKey(const char* key) const = 0;

  // Handle a set operation for `key` -> `value`. Return true if handled.
  virtual bool handleSet(const char* key, const JsonVariant& value, JsonDocument& reply) = 0;

  // Handle a get operation for `key`. Return true if handled and fill `reply`.
  virtual bool handleGet(const char* key, JsonDocument& reply) = 0;

  // Handle a command; `params` may be null. Return true if handled.
  virtual bool handleCmd(const char* cmd, const JsonVariant& params, JsonDocument& reply) = 0;
};

#endif // RESOURCE_PROVIDER_H
