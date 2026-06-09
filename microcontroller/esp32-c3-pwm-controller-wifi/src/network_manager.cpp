#include "network_manager.h"
#include <ESPmDNS.h>

NetworkManager::NetworkManager()
  : _lastReconnectAttempt(0), _serverStarted(false) {}

void NetworkManager::begin() {
#if defined(TRANSPORT_ETHERNET)
  _connectNetworkEthernet();
#else
  _connectNetworkWiFi();
#endif
}

bool NetworkManager::isConnected() const {
#if defined(TRANSPORT_ETHERNET)
  return Ethernet.linkStatus() != LinkOFF;
#else
  return WiFi.status() == WL_CONNECTED;
#endif
}

void NetworkManager::maintain() {
#if defined(TRANSPORT_ETHERNET)
  _maintainNetworkEthernet();
#else
  _maintainNetworkWiFi();
#endif
}

String NetworkManager::getLocalIP() const {
#if defined(TRANSPORT_ETHERNET)
  return Ethernet.localIP().toString();
#else
  return WiFi.localIP().toString();
#endif
}

String NetworkManager::getSSID() const {
#if defined(TRANSPORT_ETHERNET)
  return "Ethernet";
#else
  return WiFi.SSID();
#endif
}

int NetworkManager::getSignalStrength() const {
#if defined(TRANSPORT_ETHERNET)
  return 0;  // Not applicable for Ethernet
#else
  return WiFi.RSSI();
#endif
}

void NetworkManager::_connectNetworkWiFi() {
  // Ensure DHCP hostname is set before connecting
  WiFi.setHostname(Config::HOSTNAME);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(100);
  Serial.print("Connecting to WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > 15000) {
      Serial.println("\nWiFi timeout — check credentials");
      break;
    }
    delay(500);
    Serial.print('.');
  }
  Serial.println("\nWiFi connected: " + WiFi.localIP().toString());
  // Start mDNS so the device is reachable at hostname.local
  if (!MDNS.begin(Config::HOSTNAME)) {
    Serial.println("Warning: mDNS begin failed");
  }
}

#if defined(TRANSPORT_ETHERNET)
void NetworkManager::_connectNetworkEthernet() {
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
  if (ok && isConnected()) {
    Serial.println("Ethernet connected: " + Ethernet.localIP().toString());
    // Start mDNS so the device is reachable at hostname.local
    if (!MDNS.begin(Config::HOSTNAME)) {
      Serial.println("Warning: mDNS begin failed");
    }
  } else {
    Serial.println("Ethernet failed — check cable and config");
  }
}
#endif

void NetworkManager::_maintainNetworkWiFi() {
  if (isConnected()) {
    if (!_serverStarted) {
      // start mDNS once when connection is (re)established
      if (!MDNS.begin(Config::HOSTNAME)) {
        Serial.println("Warning: mDNS begin failed");
      }
    }
    _serverStarted = true;
    return;
  }

  // Link just dropped
  _serverStarted = false;

  unsigned long now = millis();
  if (now - _lastReconnectAttempt < RECONNECT_INTERVAL_MS) return;
  _lastReconnectAttempt = now;

  Serial.println("WiFi lost — reconnecting");
  WiFi.disconnect(true);
  delay(100);
  // Ensure DHCP hostname is set before reconnecting
  WiFi.setHostname(Config::HOSTNAME);
  WiFi.begin(Config::WIFI_SSID, Config::WIFI_PASS);
}
#if defined(TRANSPORT_ETHERNET)

void NetworkManager::_maintainNetworkEthernet() {
  if (isConnected()) {
    _serverStarted = true;
    return;
  }

  // Link just dropped
  _serverStarted = false;

  unsigned long now = millis();
  if (now - _lastReconnectAttempt < RECONNECT_INTERVAL_MS) return;
  _lastReconnectAttempt = now;

  Serial.println("Ethernet lost — retrying");
  bool ok = Config::ETH_USE_DHCP
    ? Ethernet.begin(const_cast<uint8_t*>(Config::ETH_MAC)) != 0
    : (Ethernet.maintain(), true);
  if (ok && isConnected()) {
    Serial.println("Ethernet restored: " + Ethernet.localIP().toString());
    if (!MDNS.begin(Config::HOSTNAME)) {
      Serial.println("Warning: mDNS begin failed");
    }
  }
}

#endif
