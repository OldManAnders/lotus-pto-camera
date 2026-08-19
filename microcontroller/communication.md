# Microcontroller Communication Overview
The ESP32-C3 board (Ethernet, DM9051 PHY) hosts an HTTP server on port 80. 
This file documents the routes the firmware implements — see `esp32c3wts320ethevo/esp32c3wts320ethevo.ino` and `esp32c3wts320ethevo/config.h`. 

## Firmware behavior
- Transport is HTTP over Ethernet only (no WiFi). The board uses a static IP from `config.h` (default `192.168.1.101`, hostname `rig1_microcontroller`).
- POST bodies are `application/json`.
- LED values are `0–255`, clamped, and driven as servo PWM (`brightnessToUs`, 1100–1900 µs).
- LED auto-timeout: any non-zero LED is reset to `0` after `CMD_TIMEOUT_MS` (5000 ms) with no further LED command (`checkTimeouts()` in the loop). Keep an LED lit by re-sending `/leds` before the timeout.
- `/wiper` is blocking: the eased forward+backward sweep (~4 s at 100 steps × 20 ms × 2 phases) runs synchronously and the HTTP response is only sent after it completes.
- `/leds` and `/reset` respond with the same JSON as `/status` (`handleStatus()`).

## Endpoints

| Method | Path      | Description                                  | Response                          |
|--------|-----------|----------------------------------------------|-----------------------------------|
| GET    | `/`       | Root: hostname + route listing               | `text/plain`                      |
| GET    | `/ping`   | Heartbeat check                              | `{"type":"pong"}`                 |
| GET    | `/status` | Current LED values + wiper state             | `{"led1":0,"led2":0,"led3":0,"wiperActive":false}` |
| GET    | `/network`| Ethernet status                              | `text/plain` (IP, MAC, link speed)|
| POST   | `/leds`   | Set one or more LEDs (0–255)                 | status JSON                       |
| POST   | `/wiper`  | Trigger wiper sweep (blocks until done)      | `{"wiper":"done"}`                |
| POST   | `/reset`  | Zero all LEDs, wiper to minimum position     | status JSON                       |
| POST   | `/reboot` | Reboot the board                             | `{"status":"Rebooting..."}`       |

Unknown paths return `404` with `{"error":"not_found"}`.

## POST body examples

### `/leds`
```json
{"led1":255}
{"led1":255,"led2":128,"led3":0}
```
Any subset of `led1`/`led2`/`led3` may be given; omitted LEDs are left unchanged. Values are clamped to `0–255`. 
Bad requests return `400` with `{"error":"missing body"}`, `{"error":"invalid json"}`, or `{"error":"no LED values specified"}`.

### `/wiper`
No body. Responds `{"wiper":"done"}` after the sweep finishes, or `{"wiper":"already_running"}` if a sweep is already in progress.

### `/reset` & `/reboot`
Does not return a body.

## Python handler
`microcontroller/microcontroller_handler.py` wraps the endpoints using `requests`. 
Construct with `MicrocontrollerHandler(ip, port=80, timeout=5, heartbeat_interval=10, name="NA,NA", verbose=False)`. 
HTTP failures are logged (via `utils/logging_config.py`) and return `None`; they do not raise.

| Method                              | Endpoint used                    | Notes                                      |
|-------------------------------------|----------------------------------|--------------------------------------------|
| `is_alive()`                        | GET `/ping`                      | True only if `{"type":"pong"}`             |
| `get_status()`                      | GET `/status`                    | Returns LED values + wiper state           |
| `set_leds(led1=None, led2=None, led3=None)` | POST `/leds`             | `None` keys omitted, values clamped 0–255  |
| `wipe()`                            | POST `/wiper`                    | Uses a 30 s timeout (sweep blocks)         |
| `reset_all()`                       | POST `/reset`                    |                                            |

## Issuing commands without the Python handler
Use the microcontroller IP from `config.yaml` (`setups.<rig>.microcontroller.ip`, default in `config.h` is `192.168.1.101`).

### using 'curl' in a terminal
```bash
# Heartbeat
curl http://192.168.1.101/ping

# Current LED + wiper state
curl http://192.168.1.101/status

# Network info (IP, MAC, link speed)
curl http://192.168.1.101/network

# Turn LED 1 on full
curl -X POST http://192.168.1.101/leds -H "Content-Type: application/json" -d '{"led1":255}'

# Set all three LEDs
curl -X POST http://192.168.1.101/leds -H "Content-Type: application/json" -d '{"led1":255,"led2":128,"led3":0}'

# Wiper sweep (command blocks until the sweep finishes)
curl -X POST http://192.168.1.101/wiper

# Reset outputs to zero
curl -X POST http://192.168.1.101/reset

# Reboot the board
curl -X POST http://192.168.1.101/reboot
```

### PowerShell (Windows dev machine)
```powershell
# Heartbeat / status
Invoke-RestMethod http://192.168.1.101/ping
Invoke-RestMethod http://192.168.1.101/status

# Set LED 1 to full
Invoke-RestMethod -Method Post -Uri http://192.168.1.101/leds `
  -ContentType "application/json" -Body '{"led1":255}'

# Trigger wiper sweep
Invoke-RestMethod -Method Post -Uri http://192.168.1.101/wiper
```