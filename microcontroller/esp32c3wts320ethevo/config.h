#pragma once

// ===== Hardware pin configuration =====
#define ETH_CS    9
#define ETH_CLK   7
#define ETH_MOSI  10
#define ETH_MISO  3
#define ETH_INT   8
#define ETH_RST   6

#define LED1_PIN   1
#define LED2_PIN   5
#define LED3_PIN   4
#define WIPER_PIN  2

// ===== Network configuration =====
#define USE_STATIC_IP true
static const IPAddress STATIC_IP(192, 168, 1, 101);
static const IPAddress GATEWAY(192, 168, 1, 1);
static const IPAddress SUBNET(255, 255, 255, 0);
static const IPAddress DNS(192, 168, 1, 1);
#define ETH_HOSTNAME "rig1_microcontroller"
#define HTTP_PORT 80

// Timeout in milliseconds before returning to zero
#define CMD_TIMEOUT_MS 5000

// Watchdog timeout (seconds)
#define WDT_TIMEOUT_SEC 30

// ===== Wiper settings =====
#define WIPER_MIN  0
#define WIPER_MAX  100
#define WIPER_DELAY_MS 20
#define WIPER_STEPS 100

// ===== LED servo pwm frequency mapping =====
#define LED_MIN 0
#define LED_MAX 255
#define LED_BRIGHTNESS_MIN_US 1100
#define LED_BRIGHTNESS_MAX_US 1900
