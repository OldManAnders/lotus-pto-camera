#include <SPI.h>
#include <ETH.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <esp_task_wdt.h>
#include "config.h"

bool ethConnected = false;
WebServer server(80);

Servo led1, led2, led3, wiper;
Servo* leds[3] = {&led1, &led2, &led3};

unsigned long lastCmd[3] = {0, 0, 0};
int ledValues[3] = {0, 0, 0};

bool wiperActive = false;

void resetAllOutputs() {
  Serial.println("Resetting all outputs to zero");
  for (int i = 0; i < 3; i++) {
    ledValues[i] = 0;
    leds[i]->write(0);
  }
  wiper.write(WIPER_MIN);
  wiperActive = false;
}

void onEthEvent(arduino_event_id_t event) {
  switch (event) {
    case ARDUINO_EVENT_ETH_START:
      Serial.println("ETH started");
      ETH.setHostname("eth01-evo");
      if (USE_STATIC_IP) {
        ETH.config(staticIP, gateway, subnet, dns);
        Serial.println("Using static IP");
      }
      break;
    case ARDUINO_EVENT_ETH_CONNECTED:
      Serial.println("ETH connected");
      break;
    case ARDUINO_EVENT_ETH_GOT_IP:
      Serial.print("ETH got IP: ");
      Serial.println(ETH.localIP());
      Serial.print("Speed: ");
      Serial.print(ETH.linkSpeed());
      Serial.println(" Mbps");
      ethConnected = true;
      break;
    case ARDUINO_EVENT_ETH_DISCONNECTED:
      Serial.println("ETH disconnected");
      ethConnected = false;
      resetAllOutputs();
      break;
    case ARDUINO_EVENT_ETH_STOP:
      Serial.println("ETH stopped");
      ethConnected = false;
      resetAllOutputs();
      break;
    default:
      break;
  }
}

void runWiper() {
  Serial.println("Wiper started");
  
  int range = WIPER_MAX - WIPER_MIN;
  int WIPER_STEPS = 100;  // Total WIPER_STEPS for smooth motion
  
  // Sweep min to max with ease-in-out
  for (int i = 0; i <= WIPER_STEPS; i++) {
    esp_task_wdt_reset();
    float t = (float)i / WIPER_STEPS;
    // Ease-in-out: smooth acceleration and deceleration
    float eased = t < 0.5 ? 2 * t * t : 1 - pow(-2 * t + 2, 2) / 2;
    int pos = WIPER_MIN + (int)(eased * range);
    wiper.write(pos);
    delay(WIPER_DELAY);
  }
  
  // Sweep max to min with ease-in-out
  for (int i = 0; i <= WIPER_STEPS; i++) {
    esp_task_wdt_reset();
    float t = (float)i / WIPER_STEPS;
    float eased = t < 0.5 ? 2 * t * t : 1 - pow(-2 * t + 2, 2) / 2;
    int pos = WIPER_MAX - (int)(eased * range);
    wiper.write(pos);
    delay(WIPER_DELAY);
  }
  
  Serial.println("Wiper done");
  wiperActive = false;
}

static uint16_t brightnessToUs(uint8_t value) {
  return map(value, LED_MIN, LED_MAX, 1100, 1900);
}

void handleNotFound() {
  String path = server.uri();
  
  // Handle /wiper endpoint
  if (path == "/wiper") {
    if (!wiperActive) {
      wiperActive = true;
      server.send(200, "text/plain", "Wiper started");
      runWiper();
    } else {
      server.send(200, "text/plain", "Wiper already running");
    }
    return;
  }
  // Parse /ledX/value pattern
  if (path.startsWith("/led") && path.length() > 5) {
    int ledNum = path.charAt(4) - '0';  // Get LED number (1, 2, or 3)
    if (ledNum >= 1 && ledNum <= 3 && path.charAt(5) == '/') {
      String valueStr = path.substring(6);
      int value = valueStr.toInt();
      value = constrain(value, 0, 255);
      value = brightnessToUs(value);
      
      int idx = ledNum - 1;
      ledValues[idx] = value;
      leds[idx]->write(value);
      lastCmd[idx] = millis();
      
      Serial.printf("LED%d set to %d\n", ledNum, value);
      server.send(200, "text/plain", "OK");
      return;
    }
  }
  server.send(404, "text/plain", "Not Found");
}

void checkTimeouts() {
  unsigned long now = millis();
  for (int i = 0; i < 3; i++) {
    if (ledValues[i] != 0 && (now - lastCmd[i] > CMD_TIMEOUT)) {
      ledValues[i] = 0;
      leds[i]->write(0);
      Serial.printf("LED%d timeout, reset to 0\n", i + 1);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("ETH01-EVO Servo LED Controller");

  // Initialize watchdog (reconfigure if already initialized)
  esp_task_wdt_config_t wdt_config = {
    .timeout_ms = WDT_TIMEOUT * 1000,
    .idle_core_mask = (1 << 0),
    .trigger_panic = true
  };
  esp_task_wdt_reconfigure(&wdt_config);
  esp_task_wdt_add(NULL);
  Serial.printf("Watchdog enabled (%d sec)\n", WDT_TIMEOUT);

  // Attach servos
  led1.attach(LED1_PIN);
  led2.attach(LED2_PIN);
  led3.attach(LED3_PIN);
  wiper.attach(WIPER_PIN);
  led1.write(0);
  led2.write(0);
  led3.write(0);
  wiper.write(WIPER_MIN);

  Network.onEvent(onEthEvent);

  SPI.begin(ETH_CLK, ETH_MISO, ETH_MOSI, ETH_CS);
  ETH.begin(ETH_PHY_DM9051, 1, ETH_CS, ETH_INT, ETH_RST, SPI);

  Serial.print("MAC: ");
  Serial.println(ETH.macAddress());

  server.onNotFound(handleNotFound);
  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  esp_task_wdt_reset();
  server.handleClient();
  checkTimeouts();
  delay(10);
}
