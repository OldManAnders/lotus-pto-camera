#ifndef NETWORK_MANAGER_H
#define NETWORK_MANAGER_H

#include <Arduino.h>
#include "config.h"

#if defined(TRANSPORT_ETHERNET)
  #include <Ethernet.h>
#else
  #include <WiFi.h>
#endif

class NetworkManager {
public:
  NetworkManager();

  // Initialize and connect to network (blocks until first connection)
  void begin();

  // Check if currently connected to network
  bool isConnected() const;

  // Handle periodic reconnection attempts (call from loop())
  void maintain();

  // Get the local IP address as a string
  String getLocalIP() const;

  // Get SSID/network name (WiFi only)
  String getSSID() const;

  // Get signal strength in dBm (WiFi only)
  int getSignalStrength() const;

private:
  unsigned long _lastReconnectAttempt;
  bool _serverStarted;
  static constexpr unsigned long RECONNECT_INTERVAL_MS = 5000;

  // Internal connection handlers
  void _connectNetworkWiFi();
  void _maintainNetworkWiFi();

#if defined(TRANSPORT_ETHERNET)
  void _connectNetworkEthernet();
  void _maintainNetworkEthernet();
#endif
};

#endif // NETWORK_MANAGER_H
