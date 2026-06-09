#include <Arduino.h>
#include "config.h"
#include "network_manager.h"
#include "http_server.h"
#include "resources/pwm_controller.h"
#include "resources/bmp280_sensor.h"

static PwmController*  pwm            = nullptr;
static PwmProvider*    pwmProvider    = nullptr;
static Bmp280Sensor*   bmp280Sensor   = nullptr;
static Bmp280Provider* bmp280Provider = nullptr;
static NetworkManager* networkManager = nullptr;
static HttpServer*     httpServer     = nullptr;

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println("Initializing PWM controller");
  pwm = new PwmController();
  pwm->begin();
  pwmProvider = new PwmProvider(*pwm);

  #if defined(USE_BMP280_SENSOR)
    Serial.println("Initializing BMP280 sensor");
    bmp280Sensor = new Bmp280Sensor();
    if (bmp280Sensor->begin()) {
      bmp280Provider = new Bmp280Provider(*bmp280Sensor);
      Serial.println("BMP280 initialized successfully");
    } else {
      Serial.println("BMP280 initialization failed — check wiring and I2C address");
    }
  #endif
  
  Serial.println("Connecting to network");
  networkManager = new NetworkManager();
  networkManager->begin();

  Serial.println("Starting http server");
  httpServer = new HttpServer(networkManager);
  if (pwmProvider != nullptr) {
    httpServer->addProvider(pwmProvider);
  }
  if (bmp280Provider != nullptr) {
    httpServer->addProvider(bmp280Provider);
  }
  httpServer->begin();
}

void loop() {
  // Refresh sensor readings
  if (bmp280Sensor != nullptr && bmp280Sensor->isReady()) {
    bmp280Sensor->read();
  }

  networkManager->maintain();

  if (!networkManager->isConnected()) return;  // stay dark until link is back

  httpServer->loop();
}