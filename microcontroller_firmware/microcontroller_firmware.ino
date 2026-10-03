#include <SPI.h>
#include <ETH.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>
#include <esp_task_wdt.h>
#include "config.h"

bool ethConnected = false;
WebServer server(HTTP_PORT);

Servo led1, led2, led3, wiper;
Servo* leds[3] = {&led1, &led2, &led3};

unsigned long lastCmd[3] = {0, 0, 0};
int ledValues[3] = {0, 0, 0};
bool wiperActive = false;

// Helper functions
uint16_t brightnessToUs(uint8_t value) {
  return map(value, 0, 255, LED_BRIGHTNESS_MIN_US, LED_BRIGHTNESS_MAX_US);
}

void setLedValue(int index, int value) {
  value = constrain(value, 0, 255);
  ledValues[index] = value;
  leds[index]->writeMicroseconds(brightnessToUs(value));
  lastCmd[index] = millis();
}

// Run a full forward+backward wiper sweep, blocking until it completes.
void doWiperSweep() {
  Serial.println("Wiper started");
  int range = WIPER_MAX - WIPER_MIN;
  for (int phase = 0; phase < 2; phase++) {
    for (int step = 0; step <= WIPER_STEPS; step++) {
      float t = (float)step / WIPER_STEPS;
      float eased = t < 0.5 ? 2 * t * t : 1 - pow(-2 * t + 2, 2) / 2;

      int pos;
      if (phase == 0) {
        pos = WIPER_MIN + (int)(eased * range);
      } else {
        pos = WIPER_MAX - (int)(eased * range);
      }
      wiper.write(pos);
      delay(WIPER_DELAY_MS);
    }
    esp_task_wdt_reset(); //Reset watchdog at the extrema of every wipe
  }

  wiperActive = false;
  Serial.println("Wiper done");
}

// Safety / hardware control
void resetAllOutputs() {
  Serial.println("Resetting all outputs to zero");
  for (int i = 0; i < 3; i++) {
    ledValues[i] = 0;
    leds[i]->writeMicroseconds(brightnessToUs(0));
  }
  wiper.write(WIPER_MIN);
  wiperActive = false;
}

void checkTimeouts() {
  unsigned long now = millis();
  for (int i = 0; i < 3; i++) {
    if (ledValues[i] != 0 && (now - lastCmd[i] > CMD_TIMEOUT_MS)) {
      ledValues[i] = 0;
      leds[i]->writeMicroseconds(brightnessToUs(0));
      Serial.printf("LED%d timeout, reset to 0\n", i + 1);
    }
  }
}

// HTTP API handlers
void handleNetworkStatus() {
  String body = "==== Network Status ====\n";
  body += "IP Address : " + ETH.localIP().toString() + "\n";
  body += "MAC Address: " + ETH.macAddress() + "\n";
  body += "Link Speed : " + String(ETH.linkSpeed()) + "\n";
  server.send(200, "text/plain", body);
}

void handleRoot() {
  server.send(200, "text/plain", String(ETH_HOSTNAME) + "\n==== GET====\n/status\n/ping\n==== POST ====\n/leds\n/wiper\n/reset");
}

void handleReboot() {
  server.send(200, "application/json", "{\"status\":\"Rebooting...\"}");
  ESP.restart();
}

void handleStatus() {
  String body = "{";
  body += "\"led1\":" + String(ledValues[0]) + ",";
  body += "\"led2\":" + String(ledValues[1]) + ",";
  body += "\"led3\":" + String(ledValues[2]) + ",";
  body += "\"wiperActive\":" + String(wiperActive ? "true" : "false") + "}";
  server.send(200, "application/json", body);
}

void handlePing() {
  server.send(200, "application/json", "{\"type\":\"pong\"}");
}

// POST /leds — body: {"led1": 0-255, "led2": 0-255, "led3": 0-255}
// Any subset of keys may be provided; omitted LEDs are left unchanged.
void handleLeds() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"missing body\"}");
    return;
  }

  JsonDocument doc;
  DeserializationError jsonErr = deserializeJson(doc, server.arg("plain"));
  if (jsonErr) {
    server.send(400, "application/json", "{\"error\":\"invalid json\"}");
    return;
  }

  bool changed = false;
  if (!doc["led1"].isNull()) {
    setLedValue(0, doc["led1"].as<int>());
    changed = true;
  }
  if (!doc["led2"].isNull()) {
    setLedValue(1, doc["led2"].as<int>());
    changed = true;
  }
  if (!doc["led3"].isNull()) {
    setLedValue(2, doc["led3"].as<int>());
    changed = true;
  }

  if (!changed) {
    server.send(400, "application/json", "{\"error\":\"no LED values specified\"}");
    return;
  }

  handleStatus();
}

// POST /wiper — trigger a wiper sweep. Blocks until the sweep finishes
// (forward + backward), so the HTTP response is only sent once it's done.
void handleWiper() {
  if (wiperActive) {
    server.send(200, "application/json", "{\"wiper\":\"already_running\"}");
    return;
  }

  doWiperSweep();
  server.send(200, "application/json", "{\"wiper\":\"done\"}");
}

// POST /reset — reset all LEDs to 0 and wiper to its minimum position.
void handleReset() {
  resetAllOutputs();
  handleStatus();
}

// Ethernet event handler
void onEthEvent(arduino_event_id_t event) {
  switch (event) {
    case ARDUINO_EVENT_ETH_START:
      Serial.println("ETH started");
      ETH.setHostname(ETH_HOSTNAME);
      if (USE_STATIC_IP) {
        ETH.config(STATIC_IP, GATEWAY, SUBNET, DNS);
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


// Initial setup
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println(String(ETH_HOSTNAME) + " booting");

  // Configure Watchdog
  esp_task_wdt_config_t wdt_config = {
    .timeout_ms = WDT_TIMEOUT_SEC * 1000,
    .idle_core_mask = (1 << 0),
    .trigger_panic = true
  };
  esp_task_wdt_reconfigure(&wdt_config);
  esp_task_wdt_add(NULL);
  Serial.printf("Watchdog enabled (%d sec)\n", WDT_TIMEOUT_SEC);

  // Initialize LEDs and Servo and set to default state (off/min_wipe_position)
  led1.attach(LED1_PIN);
  led2.attach(LED2_PIN);
  led3.attach(LED3_PIN);
  wiper.attach(WIPER_PIN);
  for (int i = 0; i < 3; i++) {
    leds[i]->writeMicroseconds(brightnessToUs(0));
  }
  wiper.write(WIPER_MIN);

  // Attach ethernet event handler
  Network.onEvent(onEthEvent);

  // Initialize Ethernet
  SPI.begin(ETH_CLK, ETH_MISO, ETH_MOSI, ETH_CS);
  ETH.begin(ETH_PHY_DM9051, 1, ETH_CS, ETH_INT, ETH_RST, SPI);

  // Print MAC address
  Serial.print("MAC: ");
  Serial.println(ETH.macAddress());

  // Connect HTTP routes
  server.on("/", HTTP_GET, handleRoot);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/network", HTTP_GET, handleNetworkStatus);
  server.on("/ping", HTTP_GET, handlePing);
  server.on("/leds", HTTP_POST, handleLeds);
  server.on("/wiper", HTTP_POST, handleWiper);
  server.on("/reset", HTTP_POST, handleReset);
  server.on("/reboot", HTTP_POST, handleReboot);
  server.onNotFound([]() {
    server.send(404, "application/json", "{\"error\":\"not_found\"}");
  });

  // Start the server
  server.begin();
  Serial.println("HTTP server started");
}

// Main loop
void loop() {
  esp_task_wdt_reset();
  server.handleClient();
  checkTimeouts();
  delay(10);
}
