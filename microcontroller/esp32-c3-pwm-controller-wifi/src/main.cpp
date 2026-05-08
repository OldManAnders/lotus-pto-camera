#include <Arduino.h>
#include <ArduinoOTA.h>
#include "config.h"
#include "http_server.h"
#include "resources/pwm_controller.h"
#include "resources/bme280_sensor.h"

#if defined(TRANSPORT_ETHERNET)
  #include <Ethernet.h>
#else
  #include <WiFi.h>
#endif

static PwmController*  pwm            = nullptr;
static PwmProvider*    pwmProvider    = nullptr;
static Bme280Sensor*   bme280Sensor   = nullptr;
static Bme280Provider* bme280Provider = nullptr;
static HttpServer*     httpServer     = nullptr;

static unsigned long _lastReconnectAttempt = 0;
static bool          _serverStarted        = false;
static constexpr unsigned long RECONNECT_INTERVAL_MS = 5000;

static bool networkConnected() {
#if defined(TRANSPORT_ETHERNET)
  return Ethernet.linkStatus() != LinkOFF;
#else
  return WiFi.status() == WL_CONNECTED;
#endif
}

static void connectNetwork() {
  #if defined(TRANSPORT_ETHERNET)
    static bool ethInitialised = false;
    if (!ethInitialised) {
      Ethernet.init(Config::ETH_CS_PIN);
      ethInitialised = true;
    }

    bool ok = Config::ETH_USE_DHCP
      ? Ethernet.begin(const_cast<uint8_t*>(Config::ETH_MAC)) != 0
      : (Ethernet.begin(
          const_cast<uint8_t*>(Config::ETH_MAC),
          IPAddress(Config::ETH_IP),
          IPAddress(Config::ETH_DNS),
          IPAddress(Config::ETH_GW),
          IPAddress(Config::ETH_MASK)
        ), true);

    delay(200);
    if (ok && networkConnected()) {
      Serial.println("Ethernet connected: " + Ethernet.localIP().toString());
    } else {
      Serial.println("Ethernet failed — check cable and config");
    }

  #else
    WiFi.mode(WIFI_STA);
    WiFi.disconnect(true);
    delay(100);
    digitalWrite(Config::ONBOARD_LED_PIN, HIGH);
    Serial.print("Connecting to WiFi");
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED) {
      digitalWrite(Config::ONBOARD_LED_PIN, HIGH);
      if (millis() - start > 15000) {
          Serial.println("\nWiFi timeout — check credentials");
          // optionally restart: ESP.restart();
          break;
      }
      delay(500);
      Serial.print('.');
    };
    Serial.println("\nWiFi connected: " + WiFi.localIP().toString());
  #endif
}

static void maintainNetwork() {
  if (networkConnected()) return;

  // Link just dropped
  _serverStarted = false;

  unsigned long now = millis();
  if (now - _lastReconnectAttempt < RECONNECT_INTERVAL_MS) return;
  _lastReconnectAttempt = now;

  #if defined(TRANSPORT_ETHERNET)
    Serial.println("Ethernet lost — retrying");
    bool ok = Config::ETH_USE_DHCP
      ? Ethernet.begin(const_cast<uint8_t*>(Config::ETH_MAC)) != 0
      : (Ethernet.maintain(), true);  // maintain() handles static IP renewal
    if (ok && networkConnected()) {
      Serial.println("Ethernet restored: " + Ethernet.localIP().toString());
    }
  #else
    Serial.println("WiFi lost — reconnecting");
    WiFi.disconnect(true);
    delay(100);
    WiFi.begin(Config::WIFI_SSID, Config::WIFI_PASS);
  #endif
}

static void setupOTA() {
  ArduinoOTA.setHostname(Config::HOSTNAME);  // optional, shows in IDE
  ArduinoOTA.setPassword(Config::OTAAUTH);

  ArduinoOTA.onStart([]() {
    Serial.println("OTA starting...");
  });
  ArduinoOTA.onEnd([]() {
    Serial.println("OTA done — rebooting");
  });
  ArduinoOTA.onError([](ota_error_t e) {
    Serial.printf("OTA error [%u]\n", e);
  });

  ArduinoOTA.begin();
  Serial.println("OTA ready");
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("Connecting to network");
  connectNetwork();  // blocks until first connection
  setupOTA();

  Serial.println("Initializing PWM controller");
  pwm = new PwmController();
  pwm->begin();
  pwmProvider = new PwmProvider(*pwm);

  Serial.println("Initializing BME280 sensor");
  bme280Sensor = new Bme280Sensor();
  if (bme280Sensor->begin()) {
    bme280Provider = new Bme280Provider(*bme280Sensor);
    Serial.println("BME280 initialized successfully");
  } else {
    Serial.println("BME280 initialization failed — check wiring and I2C address");
  }

  Serial.println("Starting http server");
  httpServer  = new HttpServer();
  if (pwmProvider != nullptr) {
    httpServer->addProvider(pwmProvider);
  }
  if (bme280Provider != nullptr) {
    httpServer->addProvider(bme280Provider);
  }
  httpServer->begin();

  _serverStarted = true;
}

void loop() {
  ArduinoOTA.handle();   // add this line at the top
  #if defined(TRANSPORT_ETHERNET)
    Ethernet.maintain();  // renew DHCP lease when needed
  #endif

  // Refresh sensor readings
  if (bme280Sensor != nullptr && bme280Sensor->isReady()) {
    bme280Sensor->read();
  }

  maintainNetwork();

  if (!networkConnected()) return;  // stay dark until link is back

  // Re-announce IP after reconnect
  if (!_serverStarted) {
    Serial.println("Network restored — server back on: " + 
      #if defined(TRANSPORT_ETHERNET)
        Ethernet.localIP().toString()
      #else
        WiFi.localIP().toString()
      #endif
    );
    _serverStarted = true;
    digitalWrite(Config::ONBOARD_LED_PIN, HIGH);
  }
  httpServer->loop();
}
