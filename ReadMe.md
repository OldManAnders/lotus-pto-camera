# LOTUS-PTO: Basler ace 2 python controller
## Setup
### Python venv
1. ```python3 -m venv venv```
2. ```source venv/bin/activate```
3. ```pip install -r requirements.txt```

### Systemd service and timer
This project includes a systemd service wrapper for scheduled capture runs.

- `systemd/lotus-capture.sh`: Bash launcher used by the service.
- `systemd/lotus-capture.service`: systemd service unit.
- `systemd/lotus-capture.timer`: systemd timer unit.
- `systemd/setup.sh`: helper script to install and enable the service/timer.

#### Install with helper script
Review `systemd/lotus-capture.service` for any path updates, then run:

```bash
sudo ./systemd/setup.sh
```

#### Manual install

```bash
sudo cp ./systemd/lotus-capture.service /etc/systemd/system/
sudo cp ./systemd/lotus-capture.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lotus-capture.timer
```

#### Debugging
- `systemctl list-timers --all`
- `journalctl -u lotus-capture.service`
- `sudo systemctl start lotus-capture.service`


## Configuration

### Main config file
The main configuration file is `config.yaml`.

Key sections:
- `DEFAULT`: default camera and light settings.
- `setups`: rig definitions with camera and microcontroller network details.
- `camera_configs`: named camera presets.
- `light_configs`: named lighting presets.
- `network`: Unifi / PoE controller configuration.

### Notes
- `light_configs` is the correct key for named lighting presets.
- Named presets inherit values from `DEFAULT` unless overridden.
- `main.py` loads `setups`, `camera_configs`, and `light_configs` to control capture behavior.

## Execution
### CLI capture
Use `main.py` for command-line capture control.

```bash
python3 main.py <rig> -c <camera_config> <light_config> [-c <camera_config> <light_config> ...]
```

Example:

```bash
python3 main.py rig1 -c default default
```

Common options:
- `--config ./config.yaml`
- `--output_path /home/aau/lotus-data/`
- `--disable_camera`
- `--disable_microcontroller`
- `--log_level debug`
- `--capture_delay 1`

If no `-c` pairs are provided, the script defaults to `default default`.

Output image names follows the following format:
```
YYMMDD-HHMMSS_SETUPNAME_CAMERACONFIG_LIGHTINGCONFIG.png"
```
 

### GUI capture interface
Launch the capture GUI:

```bash
python3 gui_capture.py
```

### Tool helpers
See [tools/README.md](tools/README.md) for helper-script documentation.
Current helper scripts include:
- `tools/basler_export_nodes.py`
- `tools/make_composits.py`
- `tools/timelapse_generator.py`
