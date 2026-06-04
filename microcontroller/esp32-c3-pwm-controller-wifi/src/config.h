#ifndef CONFIG_H
#define CONFIG_H

#define TRANSPORT_WIFI // → use onboard WiFi (default)
// #define TRANSPORT_ETHERNET // → use wired Ethernet (W5x00 / ENC28J60 via SPI)

#define USE_BMP280_SENSOR // → include BMP280 temperature/pressure sensor support
namespace Config {
  //-------------------Network configuration-----------------------//
  constexpr uint16_t SERVER_PORT = 80;
  constexpr unsigned long TIMEOUT_MS = 100000;

  // WIFI SPECIFIC CONFIGURATION (Only used when 'TRANSPORT_WIFI' is set)
  static const char* WIFI_SSID = "LOTUS-PTO-server";
  static const char* WIFI_PASS = "lotusnet123";

  // Ethernet specific configuration (Only used when 'TRANSPORT_ETH' is set)
  static constexpr bool ETH_USE_DHCP = true;
  static constexpr int ETH_CS_PIN = 5;
  // Unique MAC address for the Ethernet module.
  static constexpr uint8_t ETH_MAC[6]  = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED }; 
  // Static IP configuration (ignored when ETH_USE_DHCP == true).
  static constexpr uint8_t ETH_IP[4]   = { 192, 168,   10, 100 };
  static constexpr uint8_t ETH_DNS[4]  = {   8,   8,   8,   8 };
  static constexpr uint8_t ETH_GW[4]   = { 192, 168,   10,   1 };
  static constexpr uint8_t ETH_MASK[4] = { 255, 255, 255,   0 };

  // ------------------- I2C Resources -------------------------//
  // I2C Pins
  constexpr uint8_t I2C_SDA_PIN = 19; // (IO06) GPIO pin used for I2C SDA  
  constexpr uint8_t I2C_SCL_PIN = 18; // (IO07) GPIO pin used for I2C SCL

  // BMP280 climate sensor (temperature + pressure only)
  constexpr uint8_t BMP280_I2C_ADDRESS = 0x76; // I2C address of the BMP280 sensor
  constexpr uint8_t BME280_I2C_ADDRESS = BMP280_I2C_ADDRESS; // backwards compatibility for legacy BME280 code

  //-------------------------PWM Resources-------------------------//
  // LED PWM setup
  constexpr uint32_t LED_PWM_FREQUENCY = 5000; // Hz
  constexpr uint8_t LED_PWM_RESOLUTION = 8; // bits (0-255) WE DO NOT SUPPORT ANY OTHER BIT RESOLUTIONS
  //Light0
  constexpr uint8_t LED0_PIN = 5; //(IO02) GPIO pin used for light0 PWM
  constexpr uint8_t LED0_CHANNEL = 1; // PWM Generator channel for light0
  //Light1
  constexpr uint8_t LED1_PIN = 4; //(IO04) GPIO pin used for light1 PWM
  constexpr uint8_t LED1_CHANNEL = 2; // PWM Generator channel for light1
  //Light2
  constexpr uint8_t LED2_PIN = 2; //(IO05) GPIO pin used for light2 PWM
  constexpr uint8_t LED2_CHANNEL = 3; // PWM Generator channel for light2

  // WIPER PWM setup
  constexpr uint32_t WIPER_PWM_FREQUENCY = 50; // Hz
  constexpr uint8_t WIPER_PWM_RESOLUTION = 8; // bits (0-255) WE DO NOT SUPPORT ANY OTHER BIT RESOLUTIONS
  // WIPER0
  constexpr uint8_t WIPER0_PIN = 1; //(IO01) GPIO pin used for wiper PWM
  constexpr uint8_t WIPER0_CHANNEL= 4; //PWM Generator channel

  // Debugging
  //static const int ONBOARD_LED_PIN = 8; //Standard led pin for esp32-c3-super-mini
  // currently the LED will be on when a client is connected and off when nothing is connected
}

#endif // CONFIG_H
