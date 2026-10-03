# Getting started

This walks through bringing up a capture machine and taking a first image with the CLI. For the scheduled service, see [operations](operations.md). For the
ESP32 board, see [firmware](firmware.md). For the config file in full, see
[configuration](configuration.md).

## What you need

A capture machine is a Linux host on the private `192.168.1.0/24` network with:

- A Basler ace 2 GigE camera, powered over PoE. (We use Synology switch to powercycle, reducing heat-generation)
- An ESP32-C3 microcontroller running the [firmware](firmware.md), one per rig.
- A UniFi controller (local or reachable) and a PoE switch.
- The capture host's network interface cabled to said switch.

Software on the host:
- Python 3 with `venv`.
- The [Basler Pylon SDK](https://www.baslerweb.com/en/products/software/).
  `pypylon` is a binding to the SDK; `pip install` alone does not provide the
  runtime.
- `ffmpeg` for the timelapse and composite tools.
- `python3-tk` for the capture and timelapse GUIs.
- `jq` and `column` for `network/probe_unifi.sh`.
- Docker if you want to run the UniFi controller on the same host.

**Note:** `pypylon` requires the [Basler Pylon SDK](https://www.baslerweb.com/en/products/software/) installed on the host; the pip install alone is not enough.

The scheduled service assumes the repo is checked out at
`/home/aau/lotus-pto-camera` and writes to `/home/aau/lotus-data/`. If your
paths differ, edit `systemd/lotus-capture.service`, `systemd/lotus-capture.sh`,
and the CLI defaults in `main.py`.

## Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` pins the Python packages. System packages (Pylon SDK,
`ffmpeg`, `tkinter`, `jq`) are installed separately.

## Host network provisioning
The `network/` scripts set up the capture host side. They are templates with
hardcoded interface names (`enp6s0`), addresses, and paths. Check each value
against your machine before running it.

`network/setup_ethernet.sh` creates an nmcli connection named `local-lotusnet`
on `enp6s0` with the static address `192.168.1.1/24` and brings it up. The host
is the `.1` address on the private network.

```bash
sudo ./network/setup_ethernet.sh
```

`network/setup_ip_tables.sh` adds a NAT masquerade rule for `enp6s0` and saves
it with `iptables-persistent`, so the rule survives a reboot.

```bash
sudo ./network/setup_ip_tables.sh
```

`network/start_unifi_controller.sh` runs the `jacobalberty/unifi` controller in
Docker with host networking and its config volume at `/home/aau/unifi/`.

```bash
./network/start_unifi_controller.sh
```

`network/probe_unifi.sh` logs into the controller, lists connected clients and
infrastructure devices, and tests the device endpoints. Use it to confirm the
controller address, credentials, and that the switch is visible. The login
address and credentials are set at the top of the script.

## Configure

Copy or edit `config.yaml`. At minimum set:

- `setups.<rig>.camera.ip` and `setups.<rig>.camera.switch_port`.
- `setups.<rig>.microcontroller.ip` and `setups.<rig>.microcontroller.port`.
- `network.unifi.host`, `network.unifi.username`, `network.unifi.password`.
- `network.camera_switch_mac` to the MAC of your PoE switch.

The rigs in the checked-in file (`rig1`, `rig2`, `rig3`) map camera IPs
`192.168.1.11-13` to microcontroller IPs `192.168.1.101-103` and switch ports
1 to 6. See [configuration](configuration.md) for every field and the filename
rules the tools depend on.

## First capture

With the config set and the camera cabled to the switch, run one capture:

```bash
python3 main.py rig1 -c default default
```

The CLI powers the camera's PoE port on and waits 10 s for it to boot, opens
the camera and microcontroller, wipes the lens, then for each `-c` pair sets the
lights, loads the camera preset, flushes the frame buffer so auto-exposure and
white balance settle, and saves one image. When the run ends it turns the LEDs
off, closes the camera, and powers the PoE port off.

Images land under `<output_path>/images/YYYY-MM-DD/`. The default output path is
`/home/aau/lotus-data/`. Pass `--output_path` to write elsewhere:

```bash
python3 main.py rig1 -c default default --output_path ~/lotus-data/
```

Useful options:

- `--disable_camera` and `--disable_microcontroller` skip those devices. The
  PoE power-off step still talks to the UniFi controller, so it must be
  reachable even in a dry run.
- `--log_level` sets verbosity (`debug`, `info`, `warning`, `error`, `critical`).
- `--capture_delay` inserts a delay in seconds between captures.
- `--config` points at a different config file.

Check that a file matching
`YYYYMMDD-HHMMSS_rig1_default_default.png` exists in today's folder. If the
camera or microcontroller does not respond, the run logs the failure and exits
non-zero; see [operations](operations.md) for the event catalog and
troubleshooting.

## GUI

For interactive work, `gui_capture.py` builds a sequence of steps and runs them
through the same controller:

```bash
python3 gui_capture.py
```

Manual LED steps are written as `manual-<led1>-<led2>-<led3>`, and each run is
saved under a session subdirectory.

## Next steps

- [configuration](configuration.md) for `config.yaml`.
- [operations](operations.md) for the scheduled service and logs.
- [firmware](firmware.md) to build and flash the microcontroller.
- [tools_overview](tools_overview.md) to process captured images.
- [architecture](architecture.md) for the call flow and object model.
