# Operations

The field machine captures on a schedule with systemd and writes a daily CSV
log. This covers the service, the log format and events, and common failures.

## systemd units

Three files in `systemd/` run the schedule:

- `lotus-capture.service` runs one capture pass. It is `Type=oneshot`, runs as
  `root`, sets `WorkingDirectory=/home/aau/lotus-pto-camera`, and executes
  `systemd/lotus-capture.sh`.
- `lotus-capture.timer` fires the service every 10 minutes
  (`OnCalendar=*:0/10`) and sets `Persistent=true`, so a run missed during
  reboot starts when the machine comes back.
- `setup.sh` copies both units to `/etc/systemd/system/`, reloads the daemon,
  and enables the timer.

Install or update the units:

```bash
sudo ./systemd/setup.sh
```

The equivalent manual steps are `cp` the two unit files to
`/etc/systemd/system/`, `sudo systemctl daemon-reload`, then
`sudo systemctl enable --now lotus-capture.timer`.

## What a scheduled run does

`lotus-capture.sh` sets up the log directory, redirects all stdout and stderr to
the day's log file, changes into the repo, and runs `main.py` from the venv. One
run captures a fixed set of ten pairs: `default` and `20pAutoExp` against
`demoLed1Full`, `demoLed2Full`, `demoLed3Full`, `demoAll`, and `lightsOff`. It
writes to `/home/aau/lotus-data/` with `--log_level debug`.

Run a pass by hand to test:

```bash
sudo systemctl start lotus-capture.service
```

The script hardcodes `/home/aau/lotus-pto-camera` and `/home/aau/lotus-data/`.
Change those in `systemd/lotus-capture.sh` and `systemd/lotus-capture.service`
if your paths differ.

## Logs

The service writes to `<output>/logs/YYYY-MM-DD.log`, with
`<output>` defaulting to `/home/aau/lotus-data/`. The shell creates the
directory and redirects the whole run's stdout and stderr into it, so both the
shell lines and the Python log records land in the same file. The file is the
record to read. `journalctl -u lotus-capture.service` shows unit start and stop
events and any output written before the redirect, which is useful for failures
that happen early.

Every row is CSV with these columns:

```
timestamp,level,logger,component,event,details
```

- `timestamp` is `YYYY-MM-DD HH:MM:SS`.
- `level` is `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.
- `logger` is the logger name, such as `main`, `capture.microcontroller`,
  `utils.unifi_poe_controller`, or `<rig>,Camera`.
- `component` is the rig name for capture code, `Unifi` for the controller
  client, and `system` for shell lines.
- `event` is a short machine-readable tag. The shell puts its message text here.
- `details` is free text and is quoted when it contains a comma.

`details` may contain `|` separators where the code flattens a traceback.

## Event catalog

Controller and orchestration (component is the rig name):

| Event | Level | Meaning |
|---|---|---|
| `logger_initialization` | DEBUG | Log level set. |
| `unifi_initialization` | DEBUG | Connecting to the UniFi controller. |
| `unifi_initialization_failure` | ERROR | Controller client could not be created. |
| `config_loading` | ERROR | Unknown rig or unknown named preset. |
| `poe_control` | INFO | Powering a PoE port on or off. |
| `poe_control_success` | DEBUG | Power-off state verified. |
| `poe_control_failure` | ERROR | PoE set or verification failed. |
| `poe_camera_warmup` | DEBUG | Waiting 10 s for the camera to boot. |
| `exception` | ERROR | `start_rig` failed, with a flattened traceback. |
| `wiper` | DEBUG | Lens wipe starting. |
| `camera_temperature` | DEBUG | Camera temperature reading. |
| `camera_temperature_failed` | WARNING | Temperature read failed. |
| `capture` | INFO | Starting a capture step. |
| `lights_set` | INFO | LED values applied, with the board's reply. |
| `capture_failed` | ERROR | No frame captured, save skipped. |
| `camera_close_failed` | ERROR | Camera close raised during teardown. |
| `lights` | DEBUG | LEDs turned off after the run. |

Process level (`main.py`):

| Event | Level | Meaning |
|---|---|---|
| `config_parsing` | WARNING | No `-c` pairs given, using `default default`. |
| `interrupted` | WARNING | Stopped with Ctrl-C, exit code 130. |
| `abort` | ERROR | Uncaught exception, exit code 1. |
| `poe_control_failure` | ERROR | PoE power-off during shutdown failed. |

Camera (`capture/camera.py`):

| Event | Level | Meaning |
|---|---|---|
| `camera_handler_initialized` | DEBUG | Handler created. |
| `camera_not_found` | ERROR | Camera could not be opened. |
| `camera_settings_updated` | DEBUG | Preset applied. |
| `settings_update_error` | ERROR | Applying a preset failed. |
| `image_saved` | DEBUG | Image written to disk. |
| `grab_failed` | ERROR | Grab returned no frame. |
| `capture_error` | ERROR | Grab raised, reconnect attempted. |
| `camera_reconnected` | INFO | Reconnect succeeded. |
| `reconnect_failed` | ERROR | Reconnect failed. |
| `reconnect_no_config` | WARNING | Reconnected with no preset to restore. |
| `camera_sleep`, `camera_wake` | DEBUG | Standby entered or left. |
| `camera_stopped` | INFO | Camera closed. |
| `bad_config_type` | ERROR | Preset was neither a dict nor a path. |

Microcontroller (`capture/microcontroller.py`):

| Event | Level | Meaning |
|---|---|---|
| `microcontroller_initialized` | DEBUG | Handler created. |
| `get_request` | DEBUG | GET request sent. |
| `http_get_failed`, `http_post_failed` | ERROR | HTTP request failed; returns `None`. |
| `ping` | DEBUG or ERROR | Heartbeat succeeded or failed. |
| `set_leds_error` | WARNING or ERROR | No LED values, or the request failed. |
| `wipe_error`, `reset_error` | ERROR | Wiper or reset request failed. |

UniFi controller (`utils/unifi_poe_controller.py`, component `Unifi`):

| Event | Level | Meaning |
|---|---|---|
| `unifi_interface` | DEBUG, INFO, or ERROR | Login attempt, session started, or login failed. |
| `unifi_hardware` | ERROR | Switch MAC not found. |
| `poe_control` | DEBUG | Port override being set or verified. |
| `poe_control_success` | INFO | Port state verified. |
| `poe_control_failure` | ERROR | Controller rejected the update or verification timed out. |

Shell (`lotus-capture.sh`, component `system`):

| Event | Level | Meaning |
|---|---|---|
| `Routine capture service started` | INFO | A scheduled pass began. |

## Monitoring

```bash
systemctl status lotus-capture.timer
systemctl list-timers lotus-capture.timer
journalctl -u lotus-capture.service -f
tail -f /home/aau/lotus-data/logs/$(date +%F).log
```

## Troubleshooting

Start with the log file or `journalctl` and find the failing event.

- `config_loading` with "Unknown rig": the rig name passed to `main.py` is not a
  key under `setups`. The message lists the available rigs.
- `unifi_initialization_failure` or `unifi_interface` error: the controller host
  or credentials in `network.unifi` are wrong, or the controller is down. Check
  with `network/probe_unifi.sh`.
- `unifi_hardware` "Switch not found": `network.camera_switch_mac` does not
  match a device the controller reports.
- `poe_control_failure` "not verified" or "Verification timed out": the switch
  port index is wrong, the camera is unplugged, or the PoE budget is exceeded.
- `camera_not_found`: the camera IP is wrong, its PoE port did not come up, or
  the 10 s warmup was too short. Confirm the camera pings from the host.
- `http_get_failed` or `http_post_failed`: the microcontroller is unreachable.
  Check its IP against `config.h` and `curl http://<ip>/ping`.
- `grab_failed` or `capture_error`: the camera dropped a frame. The handler
  tries to reconnect and restore the last preset; `reconnect_failed` means that
  did not work.
- `capture_failed`: a step produced no frame and was skipped. The rest of the
  sequence continues.

A dry run with `--disable_camera --disable_microcontroller` still contacts the
UniFi controller during shutdown, because powering the PoE port off is
unconditional. The controller must be reachable for the run to finish cleanly.
