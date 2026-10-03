# Microcontroller firmware

Each rig has an ESP32 board that drives three LED channels and a lens wiper
over HTTP. The host talks to it through `capture/microcontroller.py`; the wire
protocol is in [microcontroller_communication](microcontroller_communication.md).

## Files

- `microcontroller_firmware/config.h` holds all pins, network settings, and
  timeouts. This is the file you edit per rig.
- `microcontroller_firmware/microcontroller_firmware.ino` is the sketch.

## Hardware

The board is an ESP32-C3 WT32-ETH01-EVO with a DM9051 SPI Ethernet PHY. There is no WiFi; all
traffic is HTTP over Ethernet. `config.h` defines the pin map:

| Signal | Pin | Signal | Pin |
|---|---|---|---|
| `ETH_CS` | 9 | `LED1_PIN` | 1 |
| `ETH_CLK` | 7 | `LED2_PIN` | 5 |
| `ETH_MOSI` | 10 | `LED3_PIN` | 4 |
| `ETH_MISO` | 3 | `WIPER_PIN` | 2 |
| `ETH_INT` | 8 | | |
| `ETH_RST` | 6 | | |

The sketch starts SPI with the Ethernet pins and calls
`ETH.begin(ETH_PHY_DM9051, 1, ETH_CS, ETH_INT, ETH_RST, SPI)`.

## Network configuration

`config.h` sets a static address so the host can reach the board at a known IP:

```c
#define USE_STATIC_IP true
static const IPAddress STATIC_IP(192, 168, 1, 101);
static const IPAddress GATEWAY(192, 168, 1, 1);
static const IPAddress SUBNET(255, 255, 255, 0);
static const IPAddress DNS(192, 168, 1, 1);
#define ETH_HOSTNAME "rig1_microcontroller"
#define HTTP_PORT 80
```

The checked-in defaults are rig 1 (`192.168.1.101`, hostname
`rig1_microcontroller`). For each additional rig, change `STATIC_IP` and
`ETH_HOSTNAME`, then keep `config.yaml` in step: `setups.<rig>.microcontroller.ip`
must equal `STATIC_IP` and `setups.<rig>.microcontroller.port` must equal
`HTTP_PORT`.

The host-side network is set up by `network/setup_ethernet.sh`, which puts the
host at `192.168.1.1`. See [getting-started](getting-started.md).

## Timing and safety

- `CMD_TIMEOUT_MS` is 5000. Any LED that is on and receives no new command for
  5 s is reset to 0. The capture loop re-sends LED values during the buffer
  flush, which keeps them on long enough to capture.
- `WDT_TIMEOUT_SEC` is 30. The task watchdog is reset every loop and at each
  end of a wiper sweep. If the loop stalls past 30 s the board panics and
  reboots.
- The wiper sweep is blocking. `WIPER_STEPS` is 100 and `WIPER_DELAY_MS` is 20,
  so a forward and backward sweep takes about 4 s, and the HTTP response is
  sent only after it completes. The host uses a 30 s timeout for this call.
- On Ethernet disconnect or stop, the firmware zeros all LEDs and parks the
  wiper at `WIPER_MIN`.

LED values are 0 to 255 and are driven as servo PWM between
`LED_BRIGHTNESS_MIN_US` (1100) and `LED_BRIGHTNESS_MAX_US` (1900).

## HTTP API

The sketch registers these routes on port 80. The full request and response
detail is in [microcontroller_communication](microcontroller_communication.md).

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Hostname and route listing |
| GET | `/ping` | Heartbeat, returns `{"type":"pong"}` |
| GET | `/status` | LED values and wiper state |
| GET | `/network` | IP, MAC, link speed |
| POST | `/leds` | Set one or more LEDs, 0 to 255 |
| POST | `/wiper` | Run a wiper sweep, blocks until done |
| POST | `/reset` | Zero LEDs and park the wiper |
| POST | `/reboot` | Restart the board |

## Build and flash

Use the Arduino IDE with the Espressif ESP32 board package installed.

1. Install the ESP32 board support in the IDE board manager.
2. Install two libraries from the library manager: `ESP32Servo` and
   `ArduinoJson`. The sketch uses the ArduinoJson 7 API (`JsonDocument`), so
   pick a matching major version. `SPI`, `ETH`, `WebServer`, and `esp_task_wdt`
   ship with the ESP32 core.
3. Select an ESP32-C3 board.
4. Open `microcontroller_firmware/esp32c3wts320ethevo.ino`, edit `config.h` for
   the rig, and upload over USB.
5. Open the serial monitor at 115200 baud. The board prints its hostname, MAC,
   the static IP, and `HTTP server started` once Ethernet comes up.

Arduino IDE expects a sketch file to sit in a folder of the same name. This
repo's sketch is `esp32c3wts320ethevo.ino` inside `microcontroller_firmware/`.
If the IDE rejects the folder name, copy `config.h` and
`esp32c3wts320ethevo.ino` into a folder named `esp32c3wts320ethevo` and open it
from there.

## Verify

With the board on the network, confirm it responds before running a capture:

```bash
curl http://192.168.1.101/ping
curl http://192.168.1.101/status
curl -X POST http://192.168.1.101/leds -H "Content-Type: application/json" -d '{"led1":255}'
curl -X POST http://192.168.1.101/wiper
```

`/ping` returns `{"type":"pong"}`, and `/status` reports the LED values you set.
