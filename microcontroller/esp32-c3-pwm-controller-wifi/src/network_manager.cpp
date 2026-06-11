#include "network_manager.h"

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
  //WiFi.disconnect(true);
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
}

#if defined(TRANSPORT_ETHERNET)
void NetworkManager::_connectNetworkEthernet() {
  static bool ethInitialised = false;
  if (!ethInitialised) {
    // Initialize SPI with your specific hardware pins
    SPI.begin(Config::ETH_SCK_PIN, Config::ETH_MISO_PIN, Config::ETH_MOSI_PIN, Config::ETH_CS_PIN);
    Ethernet.init(Config::ETH_CS_PIN);
    ethInitialised = true;
  }

  Serial.print("Connecting to Ethernet (Initializing hardware)");
  
  // Start the hardware configuration
  bool ok = Config::ETH_USE_DHCP
    ? Ethernet.begin(const_cast<uint8_t*>(Config::ETH_MAC)) != 0
    : (Ethernet.begin(
        const_cast<uint8_t*>(Config::ETH_MAC),
        IPAddress(Config::ETH_IP),
        IPAddress(Config::ETH_DNS),
        IPAddress(Config::ETH_GW),
        IPAddress(Config::ETH_MASK)
      ), true);

  // If the hardware initialization failed entirely (e.g., bad SPI wiring)
  if (!ok) {
    Serial.println("\nEthernet hardware initialization failed — check config and wiring");
    return;
  }

  // Progress monitoring: Wait for link status and an IP address
  Serial.print("\nWaiting for Ethernet link and IP");
  unsigned long start = millis();
  constexpr unsigned long timeout = 15000; 
  while (!isConnected() || Ethernet.localIP() == IPAddress(0,0,0,0) || Ethernet.localIP() == IPAddress(255,255,255,255)) { // <-- Add this check
         
    if (millis() - start > timeout) {
      Serial.println("\nEthernet timeout — check cable connection or DHCP server");
      break;
    }
    delay(500);
    Serial.print('.');
  }

  // Double check that our final IP address is entirely valid
  if (isConnected() && Ethernet.localIP() != IPAddress(0,0,0,0) && Ethernet.localIP() != IPAddress(255,255,255,255)) {
    Serial.println("\nEthernet connected: " + Ethernet.localIP().toString());
  } 
  else {
    Serial.println("\nEthernet failed to secure a valid IP layout.");
  }
}
#endif

void NetworkManager::_maintainNetworkWiFi() {
  if (isConnected()) {
    _serverStarted = true;
    return;
  }
  else  {
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
  }
}

#endif
