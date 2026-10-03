# LOTUS-PTO Camera System

Automated image-capture system for the LOTUS-PTO project. Dedicated capture rigs photograph samples under controlled lighting on a private `192.168.1.x` network, and the collected time-series images are processed into composites and timelapses for analysis.

Each rig is made up of:
- **Basler ace 2 GigE camera** — powered over PoE, controlled via pypylon. Camera features/settings reference: [`docs/basler_camera_nodes.md`](docs/basler_camera_nodes.md).
- **ESP32-C3 microcontroller** — drives three LED channels and a lens wiper over HTTP. Firmware lives in [`microcontroller/esp32c3wts320ethevo/`](microcontroller/esp32c3wts320ethevo/); full HTTP API: [`docs/microcontroller_communication.md`](docs/microcontroller_communication.md).
- **UniFi switch** — powers cameras/microcontrollers and cycles PoE ports on/off.
- **Capture machine** — run scheduled captures and store images; [`tools/`](tools/README.md) turns them into composites and timelapses.

## Repository layout
```
main.py                     CLI entry point
gui_capture.py              Tkinter GUI wrapper around CaptureController
capture/                    CaptureController + CameraHandler (pypylon) + MicrocontrollerHandler (HTTP)
config.yaml                 Central config: rigs, camera/light presets, network
microcontroller/            ESP32-C3 firmware
utils/                      Logging, UniFi PoE control, image filename parsing
network/                    Ethernet / network setup scripts
systemd/                    Service, timer, and install script for scheduled capture
tools/                      Data processing scripts (see tools/README.md)
```

## How a capture works

`main.py` runs one rig through a fixed sequence:

1. Log into the UniFi API and power on the camera's PoE port (10 s warmup).
2. Connect to the camera (pypylon, IP-based) and the microcontroller (HTTP).
3. Trigger servo motor to wipe the lens.
4. For each requested (camera config, light config) pair: set the LEDs, load the camera settings, flush the buffer so auto-exposure converges, capture and save the image.
5. Turn the LEDs off, close the camera, and power off the PoE port.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Note:** `pypylon` requires the [Basler Pylon SDK](https://www.baslerweb.com/en/products/software/) installed on the host; the pip install alone is not enough.

### Configuration (`config.yaml`)

- `setups` — rig definitions (camera IP, PoE switch port, microcontroller IP/port).
- `camera_configs` — named camera presets (note the plural; the YAML anchor inside `DEFAULT` is `camera_config`).
- `light_configs` — named lighting presets (LED strengths 0–255).
- `network` — UniFi controller address/credentials and switch MAC.

Named presets inherit from `DEFAULT` via YAML anchors, so a preset only needs to override what changes.

## Running a capture

CLI — one or more `-c <camera_config> <light_config>` pairs:

```bash
python3 main.py rig1 -c default default -c 20pAutoExp demoAll
```

Defaults to a single `default default` capture if no `-c` pairs are given. See `python3 main.py -h` for options (output path, disable camera/microcontroller, log level, capture delay, config path).

GUI:

```bash
python3 gui_capture.py
```

Scheduled captures — installed as a systemd service/timer (fires every 10 minutes):

```bash
sudo ./systemd/setup.sh     # see systemd/ for manual install and debugging
```

## Output

Images are saved as `YYYYMMDD-HHMMSS_SETUPNAME_CAMERACONFIG_LIGHTINGCONFIG.png` under `<output_path>/images/YYYY-MM-DD/`.

Example: `20260601-143022_rig1_default_demoAll.png`

`utils/parsing.py` and the tools depend on this exact filename format, so the rig, camera config, and lighting config tokens must not contain underscores. Manual LED captures from the GUI encode the lighting config as `manual-<led1>-<led2>-<led3>` (hyphens, not underscores).

The GUI writes each run into a session subdirectory, `<output_path>/<session>/images/YYYY-MM-DD/`, which keeps manual captures separate from the scheduled automatic captures (which write straight into the automatic output root). Pointing the GUI's Output Folder at that automatic root is a deliberate choice to intermingle them.

## Data processing

`tools/` contains composites, timelapses, crop selection, and camera-node dump scripts. Full usage is documented in [`tools/README.md`](tools/README.md):
- `make_composits.py` — mean/median/percentile composite images.
- `timelapse_generator.py` + `timelapse_generator_gui.py` — filtered timelapse videos.
- `basler_export_nodes.py` — export GenICam nodes to XML/YAML/Markdown.
- `get_crop_coordinates.py` — interactive crop-region selector to retrieve coordinates for crops and camera_configs
- `generate_crops.sh` — batch timelapse generation for predefined crops.
- `sync_push.sh` — sync captured image sets to another machine.

## Further reading
- [`docs/basler_camera_nodes.md`](docs/basler_camera_nodes.md) — camera feature reference.
- [`docs/microcontroller_communication.md`](docs/microcontroller_communication.md) — microcontroller HTTP API.
- [`tools/README.md`](tools/README.md) — data processing tools.