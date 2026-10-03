# LOTUS-PTO Camera System
Automated image-capture system for the LOTUS-PTO project. Dedicated capture rigs photograph samples under controlled lighting on a private `192.168.1.x` network, and the collected time-series images are processed into composites and timelapses for analysis.

Each rig is made up of:
- **Basler ace 2 GigE camera** — powered over PoE, controlled via pypylon. Camera features/settings reference: [`docs/basler_camera_nodes.md`](docs/basler_camera_nodes.md).
- **ESP32-C3 microcontroller** — drives three LED channels and a lens wiper over HTTP. Firmware lives in [`microcontroller_firmware/`](microcontroller_firmware/); full HTTP API: [`docs/microcontroller_communication.md`](docs/microcontroller_communication.md).

All rigs are controlled from a centralized setup which is made up of:
- **UniFi switch** — powers cameras/microcontrollers and cycles PoE ports on/off.
- **Capture machine** — run scheduled captures and store images; [`tools/`](docs/tools_overview.md) turns them into composites and timelapses.

For Setup and installation see the Getting Started guide and Configuration guide below
- [`docs/getting-started.md`](docs/getting-started.md): host setup, config, and a first capture.
- [`docs/configuration.md`](docs/configuration.md): full `config.yaml` reference.

## Repository layout
| Path | Description |
| --- | --- |
| `main.py` | CLI entry point |
| `gui_capture.py` | Tkinter GUI wrapper around `CaptureController` |
| `capture/` | `CaptureController`, `CameraHandler` (pypylon) and `MicrocontrollerHandler` (HTTP) |
| `config.yaml` | Central config: rigs, camera/light presets, network |
| `microcontroller_firmware/` | ESP32-C3 firmware |
| `utils/` | Logging, UniFi PoE control, image filename parsing |
| `network/` | Ethernet / network setup scripts |
| `systemd/` | Service, timer, and install script for scheduled capture |
| `tools/` | Data processing scripts (see docs/tools_overview.md) |

## How a capture works
`main.py` runs one rig through a fixed sequence:
1. Log into the UniFi API and power on the camera's PoE port (10 s warmup).
2. Connect to the camera (pypylon, IP-based) and the microcontroller (HTTP).
3. Trigger servo motor to wipe the lens.
4. For each requested (camera config, light config) pair: set the LEDs, load the camera settings, flush the buffer so auto-exposure converges, capture and save the image.
5. Turn the LEDs off, close the camera, and power off the PoE port.

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

## Additional Documentation
- [`docs/firmware.md`](docs/firmware.md): ESP32-C3 build, flash, and per-rig `config.h`.
- [`docs/operations.md`](docs/operations.md): systemd schedule, logs, and troubleshooting.
- [`docs/basler_camera_nodes.md`](docs/basler_camera_nodes.md): camera features reference doc.
- [`docs/microcontroller_communication.md`](docs/microcontroller_communication.md): microcontroller HTTP API.
- [`docs/tools_overview.md`](docs/tools_overview.md): data processing tools.
- [`docs/architecture.md`](docs/architecture.md): call flow and object model.