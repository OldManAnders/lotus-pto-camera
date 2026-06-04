#include "resources/pwm_controller.h"
#include "config.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// ##################################################################################
// ##                              STATIC VARIABLES                                ##
// ##################################################################################
// PWM pin count and objects
static const uint8_t NUM_LEDS    = 3;
static const uint8_t NUM_WIPERS  = 1;
static Servo ledServos[NUM_LEDS];
static Servo wiperServos[NUM_WIPERS];

// Lumen Light pins
static const uint8_t LED_PINS[] = {
  Config::LED0_PIN,
  Config::LED1_PIN,
  Config::LED2_PIN,
};

// Wiper pins
static const uint8_t WIPER_PINS[] = {
  Config::WIPER0_PIN,
};

// Lumen light: 1100 µs = off, 1900 µs = full brightness
static const uint16_t LIGHT_MIN = 1100;
static const uint16_t LIGHT_MAX = 1900;

// Wiper servo: adjust to your servo's physical range
static const uint16_t WIPER_MIN_US = 1000;
static const uint16_t WIPER_MAX_US = 2000;

// ##################################################################################
// ##                             HELPER FUNCTIONS                                 ##
// ##################################################################################
// Map 0-255 brightness value to Lumen microseconds (1100-1900)
static uint16_t brightnessToUs(uint8_t value) {
  return map(value, 0, 255, LIGHT_MIN, LIGHT_MAX);
}

// Map 0-180 degrees to wiper microseconds
static uint16_t degreesToUs(uint8_t degrees) {
  return map(degrees, 0, 180, WIPER_MIN_US, WIPER_MAX_US);
}

// ##################################################################################
// ##                           CONTROLLER DEFINITION                              ##
// ##################################################################################
void PwmController::begin() {
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    ledServos[i].attach(LED_PINS[i], LIGHT_MIN, LIGHT_MAX);
    ledServos[i].writeMicroseconds(LIGHT_MIN); // off
  }
  for (uint8_t i = 0; i < NUM_WIPERS; i++) {
    wiperServos[i].attach(WIPER_PINS[i], WIPER_MIN_US, WIPER_MAX_US);
    wiperServos[i].writeMicroseconds(WIPER_MIN_US);
  }
}

void PwmController::setChannel(uint8_t ch, uint8_t value) {
  // ch 0..NUM_LEDS-1 = lights, ch NUM_LEDS..NUM_LEDS+NUM_WIPERS-1 = wipers
  if (ch < NUM_LEDS) {
    ledServos[ch].writeMicroseconds(brightnessToUs(value));
    Serial.printf("PwmController: LED %u = %u (%u µs)\n", ch, value, brightnessToUs(value));
  } else {
    uint8_t wi = ch - NUM_LEDS;
    if (wi < NUM_WIPERS) {
      wiperServos[wi].writeMicroseconds(degreesToUs(value));
      Serial.printf("PwmController: WIPER %u = %u° (%u µs)\n", wi, value, degreesToUs(value));
    }
  }
}

uint8_t PwmController::getChannel(uint8_t ch) const {
  if (ch < NUM_LEDS) {
    uint16_t us = ledServos[ch].readMicroseconds();
    return map(us, LIGHT_MIN, LIGHT_MAX, 0, 255);
  } else {
    uint8_t wi = ch - NUM_LEDS;
    if (wi < NUM_WIPERS) {
      uint16_t us = wiperServos[wi].readMicroseconds();
      return map(us, WIPER_MIN_US, WIPER_MAX_US, 0, 180);
    }
  }
  return 0;
}

void PwmController::setAll(uint8_t value) {
  for (uint8_t i = 0; i < NUM_LEDS; ++i){setChannel(i, value);}
  for (uint8_t i = 0; i < NUM_WIPERS; ++i){setChannel(NUM_LEDS + i, value);}
}

void PwmController::lightTest() {
  for (int v = 0; v <= 255; ++v) {
    for (uint8_t i = 0; i < NUM_LEDS; ++i)
      ledServos[i].writeMicroseconds(brightnessToUs(v));
    delay(50);
  }
}

void PwmController::lightOff() {
  for (uint8_t i = 0; i < NUM_LEDS; i++)
    ledServos[i].writeMicroseconds(LIGHT_MIN);
}

void PwmController::lightOn() {
  // Half brightness = midpoint between 1100 and 1900 = 1500 µs
  uint16_t halfUs = brightnessToUs(128);
  for (uint8_t i = 0; i < NUM_LEDS; i++)
    ledServos[i].writeMicroseconds(halfUs);
}

void PwmController::wipe() {
  bool wiping = true; // guard handled at provider level, but kept for clarity
  for (uint8_t i = 0; i < NUM_WIPERS; ++i) {
    for (uint8_t a = 0; a <= 180; a++) {
      wiperServos[i].writeMicroseconds(degreesToUs(a));
      delay(20);
    }
    for (uint8_t a = 180; a > 0; a--) {
      wiperServos[i].writeMicroseconds(degreesToUs(a));
      delay(20);
    }
    wiperServos[i].writeMicroseconds(degreesToUs(0)); // ensure return to 0
  }
}

PwmProvider::PwmProvider(PwmController& pwm) : _pwm(pwm) {}

bool PwmProvider::matchesKey(const char* key) const {
  return strncmp(key, "light", 5) == 0 || strncmp(key, "wiper", 5) == 0;
}

bool PwmProvider::handleSet(const char* key, const JsonVariant& value, JsonDocument& reply) {
  uint8_t ch = 0;
  if      (strcmp(key, "light1")   == 0) ch = 0;
  else if (strcmp(key, "light2")   == 0) ch = 1;
  else if (strcmp(key, "light3")   == 0) ch = 2;
  else if (strcmp(key, "wiper") == 0) ch = 3;

  _pwm.setChannel(ch, value.as<uint8_t>());
  reply["success"] = true;
  reply["key"]     = key;
  reply["value"]   = value.as<uint8_t>();
  return true;
}

bool PwmProvider::handleGet(const char* key, JsonDocument& reply) {
  uint8_t ch = 0;
  if      (strcmp(key, "light1")   == 0) ch = 0;
  else if (strcmp(key, "light2")   == 0) ch = 1;
  else if (strcmp(key, "3")   == 0) ch = 2;
  else if (strcmp(key, "wiper") == 0) ch = 3;
  else return false;

  reply["success"] = true;
  reply["key"]     = key;
  reply["value"]   = _pwm.getChannel(ch);
  return true;
}

bool PwmProvider::handleCmd(const char* cmd, const JsonVariant& params, JsonDocument& reply) {
  if (strcmp(cmd, "lightTest") == 0) { _pwm.lightTest(); return true;}
  else if (strcmp(cmd, "lightOff") == 0) { _pwm.lightOff(); return true;}
  else if (strcmp(cmd, "lightOn")  == 0) { _pwm.lightOn(); return true;}
  else if (strcmp(cmd, "wipe")     == 0) { _pwm.wipe(); return true;}
  else if (strcmp(cmd, "setAll")   == 0) {
    _pwm.setAll(params["value"].as<uint8_t>());
  }
  else return false;

  reply["success"] = true;
  reply["cmd"]     = cmd;
  return true;
}