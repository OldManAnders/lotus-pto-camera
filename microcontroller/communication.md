# Server -> SBC/Microcontroller communication overview
## Overview
Communication between the server and SBCs/Microcontrollers happens over HTTP REST using JSON serialized objects.
The device hosts a WebServer on port 80. All request and response bodies are `application/json`.

For detailed READMEs look at the respective project folders

---

## Endpoints

| Method | Path      | Description                        |
|--------|-----------|------------------------------------|
| GET    | `/ping`   | Heartbeat check                    |
| GET    | `/status` | Device network status              |
| POST   | `/get`    | Retrieve one or more values        |
| POST   | `/set`    | Set one or more values             |
| POST   | `/cmd`    | Run a named command                |

---

## Examples

### Heartbeat (`/ping`)
Request:
```
GET /ping
```
Response:
```json
{"type": "pong"}
```

---

### Device status (`/status`)
Request:
```
GET /status
```
Response:
```json
{"ssid": "MyNetwork", "ip": "192.168.1.100", "rssi": -62}
```

---

### Retrieve values (`/get`)
Request body is a JSON array of key names.

Request (get channel 1):
```
POST /get
["light.1"]
```
Response (success):
```json
{"success": true, "data": {"light.1": 128}}
```

Request (get multiple channels):
```
POST /get
["light.1", "light.2", "wiper"]
```
Response (success):
```json
{"success": true, "data": {"light.1": 128, "light.2": 0, "wiper": 90}}
```

Error (unknown key):
```json
{"success": false, "error": "unknown key: light.9"}
```

---

### Set values (`/set`)
Request body is a JSON object. Multiple keys can be set in a single request and are processed sequentially.

Request (set channel 1):
```
POST /set
{"light.1": 128}
```
Response (success):
```json
{"success": true}
```

Request (set multiple channels):
```
POST /set
{"light.1": 128, "light.2": 255, "wiper": 90}
```
Response (success):
```json
{"success": true}
```

Error (unknown key):
```json
{"success": false, "error": "unknown key: light.9"}
```

---

### Run a command (`/cmd`)
Request body contains a `cmd` string and an optional `params` object.

Request (no params):
```
POST /cmd
{"cmd": "lightOn"}
```
Response (success):
```json
{"success": true, "cmd": "lightOn"}
```

Request (with params):
```
POST /cmd
{"cmd": "setAll", "params": {"value": 200}}
```
Response (success):
```json
{"success": true, "cmd": "setAll"}
```

Error (unknown command):
```json
{"success": false, "error": "unknown cmd: badcmd"}
```

Valid commands:
```
lightOn      — set all lights to half brightness
lightOff     — turn all lights off
lightTest    — ramp all lights from 0 to full brightness
wipe         — sweep wiper servo 0° → 180° → 0°
setAll       — set all light channels to a value  (requires params: {"value": 0-255})
```

---

## Valid keys

| Key       | Range   | Description  |
|-----------|---------|--------------|
| `light.1` | 0–255   | LED channel 0 |
| `light.2` | 0–255   | LED channel 1 |
| `light.3` | 0–255   | LED channel 2 |
| `wiper`   | 0–180   | Wiper servo position in degrees |

---

## Errors
All error responses follow the same shape:
```json
{"success": false, "error": "<description>"}
```

| Error                  | Cause                                      |
|------------------------|--------------------------------------------|
| `invalid JSON`         | Request body could not be parsed           |
| `expected array`       | `/get` body was not a JSON array           |
| `expected object`      | `/set` body was not a JSON object          |
| `missing cmd`          | `/cmd` body had no `cmd` field             |
| `unknown key: <key>`   | Key not handled by any provider            |
| `unknown cmd: <cmd>`   | Command not recognised                     |
| `not found`            | No route matched the requested path        |
