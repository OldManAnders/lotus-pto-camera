# Configuration

`config.yaml` is the single configuration file for the CLI, the GUI, and the
scheduled service. `main.py` loads it (override with `--config`), `gui_capture.py`
loads it from its Config File field, and the tools take their filters from the
command line rather than this file.

The file has five top-level keys: `DEFAULT`, `network`, `setups`,
`camera_configs`, and `light_configs`.

## Anchors and the singular/plural gotcha

`DEFAULT` holds two YAML anchors:

```yaml
DEFAULT:
  camera_config: &default_camera_settings
    Width: 3548
    ...
  light_config: &default_light_settings
    led1: 100
    led2: 100
    led3: 100
```

The anchor under `DEFAULT.camera_config` is singular. The map of named camera
presets at the top level is `camera_configs`, plural. They are different things:
`DEFAULT.camera_config` only exists to define the anchor, while
`camera_configs` is the list of presets you select with `-c`. Every preset
merges the anchor and overrides only what changes:

```yaml
camera_configs:
  default:
    <<: *default_camera_settings
  20pAutoExp:
    <<: *default_camera_settings
    AutoTargetBrightness: 0.2
```

The same pattern applies to `light_configs` and `*default_light_settings`.

## Camera settings

Each entry in `camera_configs` is a set of Basler GenICam values. The capture
path reads these keys and applies them to the camera. The node names and valid
ranges are documented in [basler_camera_nodes](basler_camera_nodes.md).

| Key | Meaning |
|---|---|
| `Width`, `Height` | Image size in pixels. |
| `OffsetX`, `OffsetY` | Top-left corner of the image region. |
| `PixelFormat` | Pixel format, for example `BayerRG8`. |
| `BslColorSpace` | Basler color space, for example `sRgb`. |
| `LUTEnable` | Enables the camera lookup table. |
| `ExposureTime` | Exposure in microseconds when auto exposure is off. |
| `Gain` | Gain in dB when auto gain is off. |
| `AcquisitionFrameRateEnable`, `AcquisitionFrameRate` | Frame rate limit. The rate is only applied when `AcquisitionFrameRateEnable` is true. |
| `AutoTargetBrightness` | Target brightness for the auto functions, 0.0 to 1.0. |
| `AutoFunction` | Auto function profile, `MinimizeGain` or `MinimizeExposureTime`. Applied to the camera node `AutoFunctionProfile`. |
| `ExposureAuto` | `Off`, `Once`, or `Continuous`. |
| `AutoExposureTimeLowerLimit`, `AutoExposureTimeUpperLimit` | Bounds for auto exposure, in microseconds. |
| `GainAuto` | `Off`, `Once`, or `Continuous`. |
| `AutoGainLowerLimit`, `AutoGainUpperLimit` | Bounds for auto gain. |
| `BalanceWhiteAuto` | `Off`, `Once`, or `Continuous`. |
| `AutoROIWidth`, `AutoROIHeight`, `AutoROIOffsetX`, `AutoROIOffsetY` | Region the auto functions sample. Applied to the `AutoFunctionROI*` nodes. |

The checked-in `default` preset is 3548x3548 at `BayerRG8` with continuous auto
exposure and white balance. `20pAutoExp`, `30pAutoExp`, and `40pAutoExp` are the
same preset with `AutoTargetBrightness` set to 0.2, 0.3, and 0.4. The `sample*`
presets are 850x850 crops used by the processing tools; their `OffsetX/Y` come
from `tools/get_crop_coordinates.py`.

## Lighting settings

Each entry in `light_configs` sets three LED strengths from 0 to 255:

```yaml
light_configs:
  demoAll:
    <<: *default_light_settings
    led1: 175
    led2: 175
    led3: 175
```

Values are clamped to 0 to 255 before they are sent. The firmware turns an LED
off after 5 s without a new command, so the capture loop re-sends the values
while it flushes the buffer.

The GUI can also take manual LED values instead of a named preset. Those steps
are written to the filename as `manual-<led1>-<led2>-<led3>` and are not looked
up in `light_configs`.

## Rigs

`setups` maps a rig name to its hardware. `main.py` and the GUI take the rig
name as their first argument.

```yaml
setups:
  rig1:
    camera:
      ip: 192.168.1.11
      switch_port: 1
      serial: null
      settings: *default_camera_settings
    microcontroller:
      ip: 192.168.1.101
      switch_port: 2
      port: 80
    light:
      settings: *default_light_settings
```

- `camera.ip` is the camera's address on the private network.
- `camera.switch_port` is the PoE switch port the camera is plugged into. The
  controller powers this port on before a run and off after.
- `camera.serial` is the camera serial number. It may be null.
- `camera.settings` and `light.settings` hold the rig's default blocks.
- `microcontroller.ip` and `microcontroller.port` are the board's HTTP address,
  and must match `STATIC_IP` and `HTTP_PORT` in the firmware `config.h`.
- `microcontroller.switch_port` is the PoE port for the board.

The checked-in file defines `rig1`, `rig2`, and `rig3` (cameras `.11` to `.13`,
microcontrollers `.101` to `.103`, switch ports 1 to 6) plus an `any` entry with
no camera assigned, for microcontroller-only work.

The capture path selects presets from `camera_configs` and `light_configs`, so
the per-rig `settings` blocks are the place to record a rig's defaults.

## Network

```yaml
network:
  camera_switch_mac: "58:d6:1f:7c:65:03"
  microcontroller_switch_mac: "58:d6:1f:7c:65:03"
  unifi:
    host: "https://192.168.1.1:8443"
    username: "aau"
    password: "aau"
    verify_ssl: false
```

`camera_switch_mac` and `microcontroller_switch_mac` are the MAC addresses of
the PoE switches. In the checked-in file both point at the same switch. The
`unifi` block is passed straight to the controller client. `verify_ssl` is false
for the self-signed certificate on a local controller. These credentials also
appear in `network/probe_unifi.sh`, which you can use to confirm they work.

## Filename rules

Every capture is saved as:

```
YYYYMMDD-HHMMSS_<rig>_<camera_config>_<light_config>.png
```

`utils/parsing.py` and every tool that reads images depend on this format. The
parser matches:

```
^(?P<date>\d{8})-(?P<time>\d{6})_(?P<rig>.+)_(?P<camera_config>[^_]+)_(?P<lighting_config>.+)$
```

The `camera_config` token matches `[^_]+`, so it cannot contain an underscore.
The rig and lighting tokens use `.+`, but the rig pattern is greedy, so keep all
three tokens underscore-free. A light config named `demo_all` would break
parsing even though the pattern technically accepts it. Use hyphens or camel
case, as the checked-in names do.

The `light_config` token is both the preset looked up in `light_configs` and the
name written to the file. Manual GUI lighting uses `manual-<led1>-<led2>-<led3>`
and skips the lookup.

## Adding a rig or preset

To add a rig:

1. Add a block under `setups` with the camera and microcontroller addresses and
   switch ports.
2. Add the switch to `network` if it is a new switch.
3. Flash the microcontroller with a matching `STATIC_IP` and `ETH_HOSTNAME` in
   `config.h`, then confirm it with `curl http://<ip>/ping`.

To add a camera or light preset, add an entry under `camera_configs` or
`light_configs` that merges the matching anchor. Give it a name with no
underscores, then use it in a `-c <camera> <light>` pair.
