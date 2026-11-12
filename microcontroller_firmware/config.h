#pragma once

// ===== Hardware pin configuration (Seengreat RP2350-MINI(ETH), W5500 over SPI) =====
// ETH_* are board-fixed per the schematic (internal-only, not on headers) — do not change.
#define ETH_MISO  16
#define ETH_CS    17
#define ETH_SCK   18
#define ETH_MOSI  19
#define ETH_RST   20   // on-board pull-up; driver resets the W5500 in software — leave unconfigured
#define ETH_INT   21   // W5500 INTn, wired internally; enables interrupt-driven RX
#define SPI_HZ    4000000

// Servo outputs. GP4-GP7 are reserved for the two I2C headers; GP25 is the onboard WS2812.
#define WIPER_PIN 0
#define LED3_PIN  1
#define LED2_PIN  2
#define LED1_PIN  3

// Pulse range. Matches ESP32Servo's DEFAULT_uS_LOW/HIGH so wiper travel and
// parked position are unchanged from the ESP32-C3 build.
#define SERVO_US_MIN 544
#define SERVO_US_MAX 2400

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

// Watchdog timeout (seconds). NOTE: the RP2350 hardware WDT load register is
// 24-bit at 1 us/tick, so the maximum is ~16.78 s; larger values clamp silently.
#define WDT_TIMEOUT_SEC 15

// Ethernet link polling interval (ms) for the disconnect safety reset
#define LINK_POLL_MS 500

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
