#ifndef HTTP_SERVER_H
#define HTTP_SERVER_H

#include <Arduino.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <vector>
#include "config.h"
#include "resources/resource_provider.h"

class NetworkManager;  // Forward declaration

class HttpServer {
public:
  HttpServer(NetworkManager* networkManager) 
    : _server(Config::SERVER_PORT), _networkManager(networkManager) {}

  void addProvider(ResourceProvider* provider) {
    _providers.push_back(provider);
  }

  // Call once in setup() after WiFi is connected
  void begin() {
    static bool initialised = false;
    if (initialised) return;
    initialised = true;

    // GET / -- serve the control panel UI
    _server.on("/", HTTP_GET, [this]() {
      _server.sendHeader("Cache-Control", "no-cache");
      _server.send(200, "text/html", _ui);
    });

    // GET /status
    _server.on("/status", HTTP_GET, [this]() {
      JsonDocument doc;
      doc["ssid"] = _networkManager->getSSID();
      doc["ip"]   = _networkManager->getLocalIP();
      doc["rssi"] = _networkManager->getSignalStrength();
      _appendSensorReadings(doc);
      _send(200, doc);
    });

    // GET /favicon.ico
    _server.on("/favicon.ico", HTTP_GET, [this]() {
      _server.send(204, "image/x-icon", "");
    });

    // GET /sensor
    _server.on("/sensor", HTTP_GET, [this]() {
      JsonDocument doc;
      if (!_appendSensorReadings(doc)) {
        doc["success"] = false;
        doc["error"] = "sensor unavailable";
        _send(503, doc);
        return;
      }
      _send(200, doc);
    });

    // GET /ping
    _server.on("/ping", HTTP_GET, [this]() {
      JsonDocument doc;
      doc["type"] = "pong";
      _send(200, doc);
    });

    // POST /get  body: ["light1", "light2"]
    _server.on("/get", HTTP_POST, [this]() {
      JsonDocument req;
      if (deserializeJson(req, _server.arg("plain"))) {
        return _error("invalid JSON");
      }
      if (!req.is<JsonArray>()) return _error("expected array");

      JsonDocument reply;
      JsonObject data = reply["data"].to<JsonObject>();
      for (JsonVariant v : req.as<JsonArray>()) {
        const char* key = v.as<const char*>();
        bool handled = false;
        for (ResourceProvider* p : _providers) {
          if (p->matchesKey(key)) {
            JsonDocument keyReply;
            if (p->handleGet(key, keyReply)) {
              data[key] = keyReply["value"];
              handled = true;
            }
            break;
          }
        }
        if (!handled) {
          return _error(String("unknown key: ") + key);
        }
      }
      reply["success"] = true;
      _send(200, reply);
    });

    // POST /set  body: {"light1": 128, "wiper0": 90}
    _server.on("/set", HTTP_POST, [this]() {
      JsonDocument req;
      if (deserializeJson(req, _server.arg("plain"))) {
        return _error("invalid JSON");
      }
      if (!req.is<JsonObject>()) return _error("expected object");

      for (JsonPair kv : req.as<JsonObject>()) {
        const char* key = kv.key().c_str();
        bool handled = false;
        for (ResourceProvider* p : _providers) {
          if (p->matchesKey(key)) {
            JsonDocument keyReply;
            handled = p->handleSet(key, kv.value(), keyReply);
            break;
          }
        }
        if (!handled) {
          return _error(String("unknown key: ") + key);
        }
      }
      JsonDocument reply;
      reply["success"] = true;
      _send(200, reply);
    });

    // POST /cmd  body: {"cmd": "lightOn"} or {"cmd": "setAll", "params": {"value": 128}}
    _server.on("/cmd", HTTP_POST, [this]() {
      JsonDocument req;
      if (deserializeJson(req, _server.arg("plain"))) {
        return _error("invalid JSON");
      }
      const char* cmd = req["cmd"] | "";
      if (strlen(cmd) == 0) return _error("missing cmd");

      JsonVariant params = req["params"];
      bool handled = false;
      for (ResourceProvider* p : _providers) {
        JsonDocument cmdReply;
        if (p->handleCmd(cmd, params, cmdReply)) { handled = true; }
      }
      if (!handled) return _error(String("unknown cmd: ") + cmd);

      JsonDocument reply;
      reply["success"] = true;
      _send(200, reply);
    });

    _server.onNotFound([this]() {
      _error("not found");
    });

    _server.begin();
    Serial.println("HTTP server started on port " + String(Config::SERVER_PORT));
    Serial.println("IP: " + _networkManager->getLocalIP());
  }

  // Call every loop()
  void loop() {
    _server.handleClient();
  }

private:
  WebServer _server;
  NetworkManager* _networkManager;
  std::vector<ResourceProvider*> _providers;

  // Embedded UI — served at GET /
  const char* _ui = R"~~~(
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LOTUS CAMERA SENSOR CONTROLLER</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@300;400;600&display=swap');

  :root {
    --bg:       #0c1210;
    --surface:  #121a14;
    --border:   #1c2e20;
    --accent:   #52c97a;
    --accent2:  #ff8c69;
    --warn:     #f0c040;
    --text:     #d0e8d8;
    --muted:    #486050;
    --on:       #52c97a;
    --off:      #1c2e20;
    --radius:   6px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Barlow', sans-serif;
    font-weight: 300;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* ── Header ── */
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 32px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }

  .logo {
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
    letter-spacing: 0.25em;
    color: var(--accent);
    text-transform: uppercase;
  }

  .logo span { color: var(--muted); }

  .status-bar {
    display: flex;
    align-items: center;
    gap: 20px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--muted);
  }

  .status-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--muted);
    display: inline-block;
    margin-right: 6px;
    transition: background 0.3s;
  }
  .status-dot.online { background: var(--accent); box-shadow: 0 0 8px var(--accent); }
  .status-dot.offline { background: var(--accent2); box-shadow: 0 0 8px var(--accent2); }

  #ip-label { color: var(--text); }

  /* ── Main grid ── */
  main {
    flex: 1;
    padding: 32px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: auto auto;
    gap: 20px;
    max-width: 900px;
    width: 100%;
    margin: 0 auto;
  }

  /* ── Panel ── */
  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
  }

  .panel-title {
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.3em;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .panel-title::before {
    content: '';
    display: block;
    width: 3px; height: 12px;
    background: var(--accent);
  }

  /* ── Channel rows ── */
  .channel {
    display: grid;
    grid-template-columns: 72px 1fr 52px;
    align-items: center;
    gap: 14px;
    margin-bottom: 18px;
  }

  .channel:last-child { margin-bottom: 0; }

  .ch-label {
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .ch-label span {
    display: block;
    font-size: 9px;
    color: var(--off);
    margin-top: 2px;
    letter-spacing: 0.05em;
  }

  input[type=range] {
    -webkit-appearance: none;
    width: 100%;
    height: 3px;
    background: var(--border);
    border-radius: 0;
    outline: none;
    cursor: pointer;
    position: relative;
  }

  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 14px; height: 14px;
    background: var(--accent);
    border-radius: 0;
    cursor: pointer;
    box-shadow: 0 0 10px var(--accent);
    transition: transform 0.1s;
  }

  input[type=range]::-webkit-slider-thumb:active { transform: scale(1.3); }

  input[type=range]::-moz-range-thumb {
    width: 14px; height: 14px;
    background: var(--accent);
    border: none; border-radius: 0;
    cursor: pointer;
  }

  .ch-value {
    font-family: 'Share Tech Mono', monospace;
    font-size: 14px;
    color: var(--accent);
    text-align: right;
    min-width: 40px;
  }

  /* Wiper uses degrees */
  .wiper-row .ch-value::after { content: '°'; font-size: 10px; color: var(--muted); }

  /* ── Commands ── */
  .cmd-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .cmd-btn {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    padding: 12px 16px;
    cursor: pointer;
    border-radius: var(--radius);
    transition: border-color 0.15s, color 0.15s, background 0.15s;
    text-align: left;
    position: relative;
    overflow: hidden;
  }

  .cmd-btn::before {
    content: '▶';
    margin-right: 8px;
    font-size: 8px;
    color: var(--muted);
    transition: color 0.15s;
  }

  .cmd-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(0, 229, 255, 0.04);
  }

  .cmd-btn:hover::before { color: var(--accent); }

  .cmd-btn:active { background: rgba(0, 229, 255, 0.1); }

  .cmd-btn.danger:hover {
    border-color: var(--accent2);
    color: var(--accent2);
    background: rgba(255, 107, 53, 0.04);
  }

  .cmd-btn.danger:hover::before { color: var(--accent2); }

  /* ── Set All ── */
  .set-all-row {
    display: grid;
    grid-template-columns: 1fr 52px auto;
    align-items: center;
    gap: 14px;
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
  }

  .apply-btn {
    background: var(--accent);
    border: none;
    color: var(--bg);
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    padding: 10px 16px;
    cursor: pointer;
    border-radius: var(--radius);
    font-weight: 600;
    transition: opacity 0.15s, transform 0.1s;
    white-space: nowrap;
  }

  .apply-btn:hover { opacity: 0.85; }
  .apply-btn:active { transform: scale(0.97); }

  /* ── Toast ── */
  #toast {
    position: fixed;
    bottom: 28px; right: 28px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--text);
    padding: 12px 18px;
    border-radius: var(--radius);
    opacity: 0;
    transform: translateY(8px);
    transition: opacity 0.2s, transform 0.2s;
    pointer-events: none;
    z-index: 100;
    letter-spacing: 0.1em;
  }

  #toast.show { opacity: 1; transform: translateY(0); }
  #toast.error { border-left-color: var(--accent2); }

  /* ── Footer ── */
  footer {
    padding: 14px 32px;
    border-top: 1px solid var(--border);
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: var(--muted);
    display: flex;
    justify-content: space-between;
    letter-spacing: 0.1em;
  }
</style>
</head>
<body>

<header>
  <div class="logo">LOTUS <span>//</span> SENSOR CONTROLLER</div>
  <div class="status-bar">
    <div>
      <span class="status-dot" id="status-dot"></span>
      <span id="status-label">CONNECTING</span>
    </div>
    <div id="ip-label">—</div>
    <div id="rssi-label">—</div>
  </div>
</header>

<main>

  <!-- LIGHTS panel -->
  <div class="panel">
    <div class="panel-title">Lights</div>

    <div class="channel" id="row-light1">
      <div class="ch-label">Light 0<span>IO02</span></div>
      <input type="range" min="0" max="255" value="0" id="light1"
             oninput="onSlider('light1', this.value)">
      <div class="ch-value" id="val-light1">0</div>
    </div>

    <div class="channel" id="row-light2">
      <div class="ch-label">Light 1<span>IO04</span></div>
      <input type="range" min="0" max="255" value="0" id="light2"
             oninput="onSlider('light2', this.value)">
      <div class="ch-value" id="val-light2">0</div>
    </div>

    <div class="channel" id="row-light3">
      <div class="ch-label">Light 2<span>IO05</span></div>
      <input type="range" min="0" max="255" value="0" id="light3"
             oninput="onSlider('light3', this.value)">
      <div class="ch-value" id="val-light3">0</div>
    </div>

    <!-- Set All -->
    <div class="set-all-row">
      <input type="range" min="0" max="255" value="0" id="all-lights"
             oninput="document.getElementById('val-all-lights').textContent = this.value">
      <div class="ch-value" id="val-all-lights">0</div>
      <button class="apply-btn" onclick="setAll('lights')">SET ALL</button>
    </div>
  </div>

  <!-- WIPERS panel -->
  <div class="panel">
    <div class="panel-title">Wipers</div>

    <div class="channel wiper-row" id="row-wiper0">
      <div class="ch-label">WIPER 0<span>IO01</span></div>
      <input type="range" min="0" max="180" value="0" id="wiper0"
             oninput="onSlider('wiper0', this.value)">
      <div class="ch-value" id="val-wiper">0</div>
    </div>
  </div>

  <!-- BMP280 sensor panel -->
  <div class="panel">
    <div class="panel-title">BMP280 Sensor</div>

    <div class="channel">
      <div class="ch-label">Temperature<span>°C</span></div>
      <div class="ch-value" id="sensor-temperature">—</div>
    </div>
    <div class="channel">
      <div class="ch-label">Pressure<span>hPa</span></div>
      <div class="ch-value" id="sensor-pressure">—</div>
    </div>
  </div>

  <!-- COMMANDS panel (spans full width) -->
  <div class="panel" style="grid-column: 1 / -1;">
    <div class="panel-title">Commands</div>
    <div class="cmd-grid">
      <button class="cmd-btn" onclick="sendCmd('lightOn')">Light On</button>
      <button class="cmd-btn danger" onclick="sendCmd('lightOff')">Light Off</button>
      <button class="cmd-btn" onclick="sendCmd('lightTest')">Light Test</button>
      <button class="cmd-btn" onclick="sendCmd('wipe')">Wipe</button>
    </div>
  </div>

</main>

<footer>
  <span>LOTUS CONTROLLER v1.0</span>
  <span id="last-update">—</span>
</footer>

<div id="toast"></div>

<script>
  // ── Config ──────────────────────────────────────────────────
  const DEBOUNCE_MS = 120;  // ms to wait after slider stops before sending

  // ── State ───────────────────────────────────────────────────
  const timers = {};

  // ── Slider handler (debounced) ──────────────────────────────
  function onSlider(key, rawValue) {
    const value = parseInt(rawValue);
    document.getElementById('val-' + key).textContent = value;

    clearTimeout(timers[key]);
    timers[key] = setTimeout(() => sendSet({ [key]: value }), DEBOUNCE_MS);
  }

  // ── Set All (lights only) ────────────────────────────────────
  function setAll(group) {
    if (group === 'lights') {
      const v = parseInt(document.getElementById('all-lights').value);
      sendCmd('setAll', { value: v });
      // Sync light sliders to match
      ['light1','light2','light3'].forEach(id => {
        document.getElementById(id).value = v;
        document.getElementById('val-' + id).textContent = v;
      });
    }
  }

  // ── API calls ────────────────────────────────────────────────
  async function sendSet(obj) {
    try {
      const res = await fetch('/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(obj)
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);
      toast('SET ' + Object.keys(obj).join(', ').toUpperCase());
    } catch(e) {
      toast('ERROR: ' + e.message, true);
    }
  }

  async function sendCmd(cmd, params) {
    try {
      const body = params ? { cmd, params } : { cmd };
      const res = await fetch('/cmd', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);
      toast('CMD ' + cmd.toUpperCase());
    } catch(e) {
      toast('ERROR: ' + e.message, true);
    }
  }

  // ── Poll status every 3s ─────────────────────────────────────
  async function pollStatus() {
    try {
      const res = await fetch('/status');
      const data = await res.json();
      document.getElementById('status-dot').className   = 'status-dot online';
      document.getElementById('status-label').textContent = 'ONLINE';
      document.getElementById('ip-label').textContent   = data.ip;
      document.getElementById('rssi-label').textContent = data.rssi + ' dBm';
      document.getElementById('last-update').textContent =
        'LAST UPDATE ' + new Date().toLocaleTimeString();

      const sensor = data.sensor || {};
      document.getElementById('sensor-temperature').textContent =
        sensor.temperature !== undefined ? sensor.temperature.toFixed(1) + '°C' : '—';
      document.getElementById('sensor-pressure').textContent =
        sensor.pressure !== undefined ? sensor.pressure.toFixed(1) + ' hPa' : '—';
    } catch {
      document.getElementById('status-dot').className   = 'status-dot offline';
      document.getElementById('status-label').textContent = 'OFFLINE';
    }
  }

  // ── Toast ────────────────────────────────────────────────────
  let toastTimer;
  function toast(msg, isError = false) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'show' + (isError ? ' error' : '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.className = '', 2200);
  }

  // ── Init ─────────────────────────────────────────────────────
  pollStatus();
  setInterval(pollStatus, 3000);
</script>
</body>
</html>
)~~~";

  bool _appendSensorReadings(JsonDocument& doc) {
    for (ResourceProvider* p : _providers) {
      JsonDocument sensorReply;
      if (!p->handleGet("sensor.all", sensorReply)) continue;
      JsonObject sensor = doc["sensor"].to<JsonObject>();
      sensor["temperature"] = sensorReply["temperature"]["value"] | 0.0f;
      sensor["humidity"]    = sensorReply["humidity"]["value"] | 0.0f;
      sensor["pressure"]    = sensorReply["pressure"]["value"] | 0.0f;
      return true;
    }
    return false;
  }

  void _send(int code, JsonDocument& doc) {
    String out;
    serializeJson(doc, out);
    _server.send(code, "application/json", out);
  }

  void _error(const String& msg) {
    JsonDocument doc;
    doc["success"] = false;
    doc["error"]   = msg;
    _send(400, doc);
  }
};

#endif // HTTP_SERVER_H
