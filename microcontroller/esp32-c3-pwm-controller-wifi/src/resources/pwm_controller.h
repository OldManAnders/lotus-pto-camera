#ifndef PWM_CONTROLLER_H
#define PWM_CONTROLLER_H

#include <Arduino.h>
#include "resources/resource_provider.h"
#include <ArduinoJson.h>

// Controller interface
class PwmController {
public:
  void begin();
  void setChannel(uint8_t ch, uint8_t value);
  uint8_t getChannel(uint8_t ch) const;
  void setAll(uint8_t value);
  void lightTest();
  void lightOff();
  void lightOn();
  void wipe();

};

// Provider Interface
class PwmProvider : public ResourceProvider {
public:
  explicit PwmProvider(PwmController& pwm);
  bool matchesKey(const char* key) const override;
  bool handleSet(const char* key, const JsonVariant& value, JsonDocument& reply) override;
  bool handleGet(const char* key, JsonDocument& reply) override;
  bool handleCmd(const char* cmd, const JsonVariant& params, JsonDocument& reply) override;

private:
  PwmController& _pwm;
};

#endif // PWM_CONTROLLER_H
