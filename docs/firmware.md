# Microcontroller firmware

Each rig has an RP2350 board (Seengreat RP2350-MINI(ETH): RP2350A + W5500) that
drives three LED channels and a lens wiper over HTTP. The host talks to it
through `capture/microcontroller.py`; the wire protocol is in
[microcontroller_communication](microcontroller_communication.md).

## Files

- `microcontroller_firmware/config.h` holds all pins, network settings, and
  timeouts. This is the file you edit per rig.
- `microcontroller_firmware/microcontroller_firmware.ino` is the sketch.
- `microcontroller_firmware/sketch.yaml` pins the build for `arduino-cli` and the
  Arduino IDE: board `Raspberry Pi Pico 2`, platform `rp2040:rp2040`, and the
  `ArduinoJson` version. See [Build and flash](#build-and-flash).

## Hardware

The board is a Seengreat RP2350-MINI(ETH): an RP2350A with a W5500 SPI Ethernet
controller. There is no WiFi; all traffic is HTTP over Ethernet. `config.h`
defines the pin map:

| Signal | GPIO | Signal | GPIO |
|---|---|---|---|
| `ETH_MISO` | 16 | `WIPER_PIN` | 0 |
| `ETH_CS` | 17 | `LED3_PIN` | 1 |
| `ETH_SCK` | 18 | `LED2_PIN` | 2 |
| `ETH_MOSI` | 19 | `LED1_PIN` | 3 |
| `ETH_RST` | 20 | | |
| `ETH_INT` | 21 | | |

GP4/GP5 are I2C0 SDA/SCL and GP6/GP7 are I2C1 SDA/SCL; keep them free. GP25 is
the onboard WS2812 LED. The ETH_* pins (GP16-GP21) are wired to the W5500 inside
the board and are not on the headers — do not change them. `ETH_RST` has an
on-board pull-up and the driver resets the W5500 in software, so the sketch never
drives it. `ETH_INT` is the W5500 interrupt line and enables interrupt-driven RX.

The board is powered from 5 V (USB-C or the 5 V pads). It is **not**
PoE-powered, so it needs its own 5 V supply even though it stays cabled to the
switch for data.

The sketch sets the SPI pins, then hands them to the W5500 lwIP driver:

```cpp
Wiznet5500lwIP eth(ETH_CS, SPI, ETH_INT);

SPI.setRX(ETH_MISO);
SPI.setTX(ETH_MOSI);
SPI.setSCK(ETH_SCK);
SPI.setCS(ETH_CS);
eth.begin();
```

The W5500 is driven by the arduino-pico lwIP driver; there is no ESP-IDF `ETH`
object. lwIP is serviced from `loop()`, which runs about every 10 ms.

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

The sketch applies these with
`eth.config(STATIC_IP, GATEWAY, SUBNET, DNS)` and `eth.hostname(ETH_HOSTNAME)`,
both before `eth.begin()`. It does not wait for link-up: the HTTP server starts
immediately, so the routes answer as soon as the cable is live.

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
- `WDT_TIMEOUT_SEC` is 15. This is the RP2350 **hardware** watchdog: expiry
  resets the chip, with no task panic or backtrace. The WDT load register is
  24-bit at 1 us per tick, so the maximum representable timeout is about
  16.78 s — do not raise the define above that, larger values clamp silently.
  It is fed every loop and at each end of a wiper sweep.
- The wiper sweep is blocking. `WIPER_STEPS` is 100 and `WIPER_DELAY_MS` is 20,
  so a forward and backward sweep takes about 4 s, and the HTTP response is
  sent only after it completes. The host uses a 30 s timeout for this call.
  Because `loop()` does not run during the sweep, no other HTTP request is
  serviced until it ends.
- If the Ethernet link drops, `pollLink()` detects it within `LINK_POLL_MS`
  (500 ms), zeros all LEDs and parks the wiper at `WIPER_MIN`.
- Servos are attached with an explicit 544-2400 us pulse range
  (`SERVO_US_MIN`/`SERVO_US_MAX`) to preserve the wiper travel from the
  ESP32-C3 build. The arduino-pico `Servo` default (1000-2000 us) would move the
  parked position.

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
| GET | `/network` | IP, MAC, link state |
| POST | `/leds` | Set one or more LEDs, 0 to 255 |
| POST | `/wiper` | Run a wiper sweep, blocks until done |
| POST | `/reset` | Zero LEDs and park the wiper |
| POST | `/reboot` | Restart the board |

## Build and flash

The sketch targets the arduino-pico core (by Earle Philhower) and board
`Raspberry Pi Pico 2`. `microcontroller_firmware/sketch.yaml` pins the board
(`rp2040:rp2040:rpipico2`), the platform version and the `ArduinoJson` version,
so `arduino-cli` and the IDE both default to the right target. Either tool
works; `arduino-cli` is the standard for command-line builds.

### Install the toolchain with arduino-cli

1. Install the official `arduino-cli` release binary (Linux x86_64 shown):

   ```bash
   mkdir -p ~/.local/bin
   curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh \
     | BINDIR=~/.local/bin sh
   arduino-cli version
   ```

   Do **not** use the `arduino-cli` snap. Its bundled glibc is older than the
   rp2040 ARM toolchain requires, and every compile fails with
   `arm-none-eabi-g++: ... version 'GLIBC_2.28' not found`. If the snap is
   installed, remove it or make sure the official binary comes first in `PATH`.

2. Build from the repo root:

   ```bash
   arduino-cli compile microcontroller_firmware
   ```

   No board-manager URL or manual installs are needed first: `sketch.yaml` names
   the platform index URL, so `arduino-cli` installs the pinned platform and
   library on the first run. The output ends with the flash/RAM usage, for
   example `Sketch uses 134364 bytes (3%) of program storage space`.

   To get a flashable image instead of a build cache:

   ```bash
   arduino-cli compile --output-dir build microcontroller_firmware
   # build/microcontroller_firmware.ino.uf2
   ```

   If you upgrade the core or `ArduinoJson`, bump the pinned versions in
   `sketch.yaml`. To build without the profile, install the dependencies
   explicitly and pass the board:

   ```bash
   arduino-cli config add board_manager.additional_urls \
     https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json
   arduino-cli core update-index
   arduino-cli core install rp2040:rp2040
   arduino-cli lib install ArduinoJson
   arduino-cli compile --fqbn rp2040:rp2040:rpipico2 microcontroller_firmware
   ```

### Install the toolchain with the Arduino IDE

1. Install the Arduino IDE 2.x.
2. Add this board manager URL under Preferences > Additional boards manager
   URLs:
   `https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json`
3. In Boards Manager, install the "Raspberry Pi Pico/RP2040/RP2350" package.
4. In Library Manager, install `ArduinoJson` (v7; the sketch uses the
   `JsonDocument` API). `SPI`, `Servo`, `WebServer` and the W5500 lwIP driver
   ship with the board package.
5. Select Tools > Board > Raspberry Pi Pico/RP2040/RP2350 > Raspberry Pi Pico 2.

### Flash

1. Edit `config.h` for the rig.
2. Hold BOOT, plug in USB-C, then release. An `RP2350` mass-storage volume
   appears.
3. Copy the generated `.uf2` onto that volume. The board reboots into the
   sketch.
4. Open the serial monitor at 115200 baud. The board prints its hostname,
   `Watchdog enabled (15 sec)`, `IP: ...`, `MAC: ...` and
   `HTTP server started`, then `ETH connected` once the link is up.

The sketch file name matches its directory, so the IDE opens
`microcontroller_firmware/` directly — no copying or renaming.

## Verify

With the board on the network, confirm it responds before running a capture:

```bash
curl http://192.168.1.101/ping
curl http://192.168.1.101/status
curl http://192.168.1.101/network
curl -X POST http://192.168.1.101/leds -H "Content-Type: application/json" -d '{"led1":255}'
curl -X POST http://192.168.1.101/wiper
```

`/ping` returns `{"type":"pong"}`, and `/status` reports the LED values you set.
`/network` reports the address, the MAC derived from the RP2350 unique ID, and
the link state:

```
==== Network Status ====
IP Address : 192.168.1.101
MAC Address: 02:00:...
Link       : up
```
