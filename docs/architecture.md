# Architecture

Diagrams for the LOTUS-PTO camera system. Generated from a trace of the
source (not only the code graph); verify against the implementation before
relying on any single path.

- [Capture sequence](#capture-sequence) — runtime call flow for a capture run.
- [UML class structure](#uml-class-structure) — capture-side object model.
- [Shared utilities and offline tools](#shared-utilities-and-offline-tools) — processing-side classes.
- [Module dependencies](#module-dependencies) — import graph.
- [Community structure (code graph)](#community-structure-code-graph) — graph-derived clusters and critical flows.

## Capture sequence

Canonical path: `main.py` CLI. Both entry points (`main.py` and
`gui_capture.py`) drive the same `CaptureController.run_capture_sequence`;
the CLI passes `capture_delay=args.capture_delay` while the GUI passes 0.

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant E as Entry (main.py / CameraGuiApp)
    participant CC as CaptureController
    participant UH as UnifiPoEController
    participant SW as UniFi Switch (HTTPS API)
    participant CH as CameraHandler
    participant BC as Basler camera (pypylon)
    participant MH as MicrocontrollerHandler
    participant ESP as ESP32-C3 (HTTP port 80)
    participant FS as Filesystem (images/)
    participant LOG as logging_config (CSV)

    U->>E: python main.py rig1 -c cam light
    E->>CC: CaptureController(rig, config, enable_camera, enable_microcontroller, output_path, log_level)
    CC->>LOG: configure_logging(level) + get_logger("main", component=rig)
    CC->>CC: get_subconfig("setups"), validate rig name
    CC->>UH: UnifiConfig(**network.unifi) then UnifiPoEController(...)
    UH->>SW: POST /api/login, GET /api/self/sites
    UH-->>CC: session + site ready

    E->>CC: start_rig()
    CC->>UH: set_poe(camera_switch_mac, switch_port, enabled=True)
    UH->>SW: GET stat/device, PUT rest/device (port_overrides poe_mode=auto)
    loop poll every 2s, up to 60s
        UH->>SW: GET stat/device (read port_table.poe_enable)
    end
    UH-->>CC: {success: True}
    CC->>CC: time.sleep(10) (camera warmup)
    CC->>CH: CameraHandler(ip, name, output_folder)
    CH->>BC: InstantCamera.CreateFirstDevice(ip) then Open()
    CC->>MH: MicrocontrollerHandler(ip, port, name)

    E->>CC: prepare_for_capture()
    CC->>MH: wipe()
    MH->>ESP: POST /wiper (timeout 30s)
    ESP-->>MH: 200 OK
    CC->>CH: read_temperature()
    CC->>LOG: debug("camera_temperature", ...)

    loop each (camera_config, light_config) pair
        CC->>MH: set_leds(**light_config)
        MH->>ESP: POST /leds {led1,led2,led3}
        ESP-->>MH: applied (servo PWM)
        CC->>CH: load_config(camera_config)
        CH->>BC: set GenICam nodes (Width, ExposureTime, AutoFunction, ...)
        Note over CC,CH: flush buffer 3x(set_leds + 5x capture_image)
        CC->>CH: capture_image(cam_config, light_config)
        CH->>BC: StartGrabbingMax(1) then RetrieveResult(5000ms)
        BC-->>CH: grabResult
        CH->>CH: convert_to_bgr() via ImageFormatConverter
        CH-->>CC: img (BGR ndarray)
        CC->>CH: save_image(img, cam_config, light_config)
        CH->>FS: cv2.imwrite(output/images/YYYY-MM-DD/YYYYMMDD-HHMMSS_rig_cam_light.png)
        CC->>CC: time.sleep(capture_delay) (CLI only)
    end

    CC->>CH: close()
    CC->>MH: set_leds(0, 0, 0)
    MH->>ESP: POST /leds {0,0,0}
    Note over E,CC: finally block runs unconditionally
    E->>CC: power_off_camera()
    CC->>UH: set_poe(..., enabled=False)
    UH->>SW: PUT port_overrides poe_mode=off, then verify
```

Error paths:

- `start_rig()` catches any exception, logs an `exception` event, and re-raises
  as `RuntimeError`; the `main.py` top-level handler logs `abort` and calls
  `sys.exit(1)`.
- `capture_image()` catches grab exceptions and calls `try_reconnect()`,
  returning `None`; the caller skips the save.
- `power_off_camera()` swallows its own exceptions, but it always talks to
  UniFi — so the controller must be reachable even with
  `--disable_camera --disable_microcontroller`.

## UML class structure

Capture-side object model.

```mermaid
classDiagram
    direction LR

    class CameraGuiApp {
        -config : dict
        -sequence : list
        -cc : CaptureController
        +load_config(path)
        +add_step()
        +run_sequence_threaded()
        +run_sequence()
    }

    class CaptureController {
        +name : str
        +rig : dict
        +config : dict
        +output_path : str
        +camera_handler : CameraHandler
        +microcontroller_handler : MicrocontrollerHandler
        +unifi : UnifiPoEController
        +set_log_level(level)
        +setup_unifi_api(network_conf)
        +get_subconfig(kind)
        +get_named_config(kind, name)
        +start_rig()
        +power_on_camera()
        +power_off_camera()
        +prepare_for_capture()
        +run_capture_sequence(steps, capture_delay)
        +shutdown_capture()
    }

    class CameraHandler {
        +camera : pylon.InstantCamera
        +converter : pylon.ImageFormatConverter
        +output_folder : str
        +load_config(config)
        +capture_image(cam, light)
        +save_image(img, cam, light)
        +convert_to_bgr(grab)
        +try_reconnect()
        +close()
    }

    class MicrocontrollerHandler {
        +ip : str
        +port : int
        +timeout : int
        +is_alive() bool
        +set_leds(l1, l2, l3)
        +get_status()
        +wipe()
        +reset_all()
    }

    class UnifiPoEController {
        +config : UnifiConfig
        +session : requests.Session
        +site : str
        +set_poe(mac, port, enabled, verify)
        +get_switch(mac)
        -_login()
        -_get_site()
    }

    class UnifiConfig {
        <<dataclass>>
        +host : str
        +username : str
        +password : str
        +verify_ssl : bool
    }

    CameraGuiApp ..> CaptureController : constructs
    CaptureController *-- CameraHandler : creates
    CaptureController *-- MicrocontrollerHandler : creates
    CaptureController *-- UnifiPoEController : creates
    UnifiPoEController *-- UnifiConfig : configured by
```

## Shared utilities and offline tools

```mermaid
classDiagram
    direction TB

    class logging_config {
        <<module>>
        +configure_logging(level, logfile)
        +get_logger(name, component)
    }

    class CSVFormatter {
        +format(record) str
    }

    class parsing {
        <<module>>
        +FILENAME_PATTERN
        +parse_filename(path)
        +parse_images(dir)
        +filter_records(...)
    }

    class ImageRecord {
        <<dataclass>>
        +path : Path
        +camera_rig : str
        +timestamp : datetime
        +camera_config : str
        +lighting_config : str
        +timestamp_as_string
    }

    class CompositeMethod {
        <<abstract>>
        +composite(images) ndarray
    }
    class MeanComposite
    class MedianComposite
    class PercentileComposite {
        +percentile : float
    }

    class TimeBin {
        +label()
    }
    class TimelapseGenerator {
        +export(records, output, fps, ...)
    }
    class TimelapseGuiApp {
        +scan_options()
        +preview_threaded()
        +generate_threaded()
    }

    logging_config --> CSVFormatter : builds
    parsing --> ImageRecord : produces
    CompositeMethod <|-- MeanComposite
    CompositeMethod <|-- MedianComposite
    CompositeMethod <|-- PercentileComposite
    TimelapseGuiApp ..> TimelapseGenerator : uses
    TimelapseGenerator ..> parsing : reads
    TimeBin ..> ImageRecord : groups
```

## Module dependencies

Import direction between top-level modules.

```mermaid
flowchart LR
    main["main.py"]
    gui["gui_capture.py"]
    ctrl["capture/controller.py"]
    cam["capture/camera.py"]
    mcu["capture/microcontroller.py"]
    unifi["utils/unifi_poe_controller.py"]
    log["utils/logging_config.py"]
    parse["utils/parsing.py"]
    tools["tools/*"]

    gui --> ctrl
    main --> ctrl
    ctrl --> cam
    ctrl --> mcu
    ctrl --> unifi
    ctrl --> log
    cam --> log
    mcu --> log
    unifi --> log
    tools --> parse
```

## Capture pipeline

Both entry points call `CaptureController.run_capture_sequence(steps,
capture_delay=0)`. Each `CaptureStep` carries a `camera_config` lookup name,
a `light_config` filename token, and optional manual `leds`. The CLI passes
`capture_delay=args.capture_delay` (default 1 s); the GUI passes 0.

Filenames use one schema for both entry points:
`YYYYMMDD-HHMMSS_<rig>_<camera_config>_<light_config>.png`. The GUI writes each
run under a session subdirectory (`<output>/<session>/images/YYYY-MM-DD/`) and
encodes manual LED lighting configs as `manual-<led1>-<led2>-<led3>`, so the
rig/camera-config/lighting-config tokens stay underscore-free and parse
correctly with `utils/parsing.py`.

## Community structure (code graph)

Graph-derived view of the same system, produced by `code-review-graph` from a
structural parse (Tree-sitter) of the source. Unlike the traced diagrams above,
this is a statistical clustering — treat it as a map of coupling, not as a
definitive call path, and verify against the implementation.

Snapshot: **209 nodes, 2054 edges, 25 files**, risk medium (0.67), 9 test gaps.

| Community | Source | Nodes | Cohesion | Role |
|---|---|---|---|---|
| `tools-section` | `tools/` | 100 | 0.14 | Hardware / motor control (`MicrocontrollerHandler`, `set_leds`, `wipe`, `reset_all`) |
| `capture-capture` | `capture/` | 35 | 0.25 | Camera pipeline (`CameraHandler`, `CaptureController`) |
| `lotus-pto-camera-section` | `gui_capture.py` | 25 | 0.23 | Tkinter GUI + sequence orchestration |
| `utils-telemetry` | `utils/` | 22 | 0.14 | Logging / telemetry helpers |

```mermaid
flowchart LR
    subgraph GUI["lotus-pto-camera-section · 25 nodes<br/>gui_capture.py"]
        G1["CameraGuiApp"]
        G2["_run_sequence_safe"]
        G3["run_sequence_threaded"]
    end

    subgraph CAP["capture-capture · 35 nodes<br/>capture/"]
        C1["CaptureController"]
        C2["CameraHandler"]
        C3["capture_image"]
    end

    subgraph TOOLS["tools-section · 100 nodes<br/>tools/"]
        T1["MicrocontrollerHandler"]
        T2["set_leds / wipe / reset_all"]
    end

    subgraph UTIL["utils-telemetry · 22 nodes<br/>utils/"]
        U1["logging / telemetry"]
    end

    G2 --> C1
    C1 --> C2
    C2 --> C3
    C1 -->|CALLS x6| U1
    T1 -->|CALLS x2| U1
    C1 -.->|CALLS x6| GUI
```