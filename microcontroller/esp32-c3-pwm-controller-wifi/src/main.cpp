#include <Arduino.h>
#include "config.h"
#include "http_server.h"
#include "resources/pwm_controller.h"
#include "resources/bmp280_sensor.h"

#if defined(TRANSPORT_ETHERNET)
  #include <Ethernet.h>
#else
  #include <WiFi.h>
#endif

static PwmController*  pwm            = nullptr;
static PwmProvider*    pwmProvider    = nullptr;
static Bmp280Sensor*   bmp280Sensor   = nullptr;
static Bmp280Provider* bmp280Provider = nullptr;
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
    Serial.print("Connecting to WiFi");
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED) {
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
  connectNetwork();  // blocks until first connection

  Serial.println("Starting http server");
  httpServer  = new HttpServer();
  if (pwmProvider != nullptr) {
    httpServer->addProvider(pwmProvider);
  }
  if (bmp280Provider != nullptr) {
    httpServer->addProvider(bmp280Provider);
  }
  httpServer->begin();

  _serverStarted = true;
}

void loop() {
  #if defined(TRANSPORT_ETHERNET)
    Ethernet.maintain();  // renew DHCP lease when needed
  #endif

  // Refresh sensor readings
  if (bmp280Sensor != nullptr && bmp280Sensor->isReady()) {
    bmp280Sensor->read();
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
  }
  httpServer->loop();
}
