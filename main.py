'''
This script executes a series of image captures with a set of given camera parameters and a set of given lighting parameters.
The lighting and camera parameters are called by the names specified in the config.yaml.
To acquire from several rigs, this script should be executed for every camera setup
'''
import yaml, logging, traceback, sys, time, argparse
from camera.camera_handler import CameraHandler
from microcontroller.microcontroller_handler import MicrocontrollerHandler
from utils.logging_config import configure_logging, get_logger, TELEMETRY
from utils.unifi_poe_controller import UnifiConfig, UnifiPoEController
from dataclasses import dataclass


@dataclass
class CaptureStep:
    """A single capture request, normalized across the CLI and GUI.

    ``camera_config`` selects a preset from ``camera_configs``. ``light_config``
    is the name written into the saved filename. ``leds`` holds explicit
    ``set_leds`` kwargs for manual lighting; when ``None`` the LED values are
    looked up from ``light_configs`` by name. ``save_camera_config`` overrides
    the camera-config token in the filename (defaults to ``camera_config``).
    """
    camera_config: str
    light_config: str
    leds: dict = None
    save_camera_config: str = None


class CaptureController():
    def __init__(self,
                 rig,
                 config,
                 enable_camera = True,
                 enable_microcontroller = True,
                 output_path = "./",
                 log_level = "telemetry"
                 ):

        # Establish logger
        self.set_log_level(log_level)
        self.logger = get_logger(name="main", component=rig)
        self.logger.debug("", extra={"event": "logger_initialization", "details": f"Setting log level to '{log_level}' "})

        # Store internal variables
        self.name = rig
        self.output_path = output_path
        self.config = config
        self.enable_camera = enable_camera
        self.enable_microcontroller = enable_microcontroller
        setups = self.get_subconfig("setups")
        if self.name not in setups:
            self.logger.error("", extra={"event": "config_loading", "details": f"Unknown rig '{self.name}'. Available rigs: {list(setups.keys())}"})
            raise ValueError(f"Unknown rig '{self.name}'. Available rigs: {list(setups.keys())}")
        self.rig = setups[self.name]

        # Unifi API
        self.unifi = self.setup_unifi_api(self.get_subconfig("network"))

    def setup_unifi_api(self, network_conf):
        self.logger.debug("", extra={"event": "unifi_initialization", "details": f"Establishing connection to Unifi controller at {network_conf['unifi']['host']}"})
        try:
            return UnifiPoEController(UnifiConfig(**network_conf["unifi"]))
        except Exception as e:
            self.logger.error("", extra={"event": "unifi_initialization_failure", "details": str(e)})
            raise

    def set_log_level(self, log_level):
        ll_map={
            "debug": logging.DEBUG,
            "telemetry": TELEMETRY,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }
        configure_logging(level=ll_map[log_level])

    def start_rig(self):
        # Initialize camera_handler
        try:
            self.power_on_camera()
            self.camera_handler = CameraHandler(ip=self.rig["camera"]["ip"], name=f"{self.name},Camera", output_folder=self.output_path) if self.enable_camera else None
            self.microcontroller_handler =  MicrocontrollerHandler(ip=self.rig["microcontroller"]["ip"], port=self.rig["microcontroller"]["port"], name=f"{self.name},Microcontroller") if self.enable_microcontroller else None
        except Exception as e:
                err = traceback.format_exc().replace("\n", "|")
                self.logger.error("", extra={"event": "exception", "details": err})
                raise RuntimeError(f"Failed to start rig '{self.name}': {e}") from e

    def get_subconfig(self, subconfig):
        subconfig = subconfig.lower()
        if subconfig == "setups":
            return self.config["setups"]
        elif subconfig == "network":
            return self.config["network"]
        elif subconfig == "camera":
            return self.config["camera_configs"]
        elif subconfig == "lights":
            return self.config["light_configs"]
        else:
            self.logger.warning("", extra={"event": "config loading", "details": f"Attempted to retrieve unknown subconfig: '{subconfig}'."})
            return {}

    def get_named_config(self, kind, name):
        configs = self.get_subconfig(kind)
        if name not in configs:
            self.logger.error("", extra={"event": "config_loading", "details": f"Unknown {kind} config '{name}'. Available: {list(configs.keys())}"})
            raise ValueError(f"Unknown {kind} config '{name}'. Available: {list(configs.keys())}")
        return configs[name]

    def power_on_camera(self):
        # Power on PoE port
        try:
            self.logger.info("", extra={"event": "poe_control", "details": f"Powering ON PoE for camera at switch {self.get_subconfig("network")["camera_switch_mac"]} port {self.rig['camera']['switch_port']}"})
            result = self.unifi.set_poe(
                switch_mac=self.get_subconfig("network")["camera_switch_mac"],
                port_index=self.rig["camera"]["switch_port"],
                enabled=True)
            if not result["success"]:
                self.logger.error("", extra={"event": "poe_control_failure", "details": f"Failed to verify PoE power-on for camera on port {self.rig['camera']['switch_port']}"})
                raise RuntimeError("Camera PoE power-on not verified")
            self.logger.debug("", extra={"event": "poe_camera_warmup", "details": "Waiting 10 seconds for camera to power on and initialize"})
            time.sleep(10)
        except Exception as e:
            self.logger.error("", extra={"event": "poe_control_failure", "details": str(e)})
            raise

    def power_off_camera(self):
        try:
            self.logger.info("", extra={"event": "poe_control", "details": f"Powering OFF PoE for camera at switch {self.get_subconfig("network")["camera_switch_mac"]} port {self.rig['camera']['switch_port']}"})
            result = self.unifi.set_poe(
                switch_mac=self.get_subconfig("network")["camera_switch_mac"],
                port_index=self.rig["camera"]["switch_port"],
                enabled=False)
            self.logger.debug("", extra={"event": "poe_control_success", "details": f"{result['switch_mac']}: port:{result['port']} state:{result['poe_mode']}"})
        except Exception as e:
            self.logger.error("", extra={"event": "poe_control_failure", "details": str(e)})

    def prepare_for_capture(self):
        if self.microcontroller_handler:
            self.logger.debug("", extra={"event": "wiper", "details": "Wiping the lense before capturing"})
            self.microcontroller_handler.wipe()
        if self.camera_handler:
            self.logger.telemetry("",event="camera_temperature", details=self.camera_handler.camera.DeviceTemperature.Value)

    def run_capture_sequence(self, steps, capture_delay=0):
        """Run every capture step through the shared rig pipeline.

        For each step: set the lights, load the camera preset, flush the buffer
        so the auto-exposure/white-balance algorithms converge, capture one
        frame, and save it. When the sequence finishes the lights are turned off
        and the camera is closed.
        """
        for step in steps:
            cam_config_name = step.camera_config
            light_config_name = step.light_config
            save_cam_config_name = step.save_camera_config or cam_config_name
            led_kwargs = step.leds

            self.logger.info("", extra={"event": "capture", "details": f"{light_config_name}, {cam_config_name}"})

            if self.microcontroller_handler:
                # Initiate light (named config resolved lazily on first use)
                if led_kwargs is None:
                    led_kwargs = self.get_named_config("lights", light_config_name)
                response = self.microcontroller_handler.set_leds(**led_kwargs)
                self.logger.info("", extra={"event": "lights_set", "details": f"L1-{response.get("led1") if response else "NA"} L2-{response.get("led2") if response else "NA"} L3-{response.get("led3") if response else "NA"}"})

            if self.camera_handler:
                # Set camera settings
                self.camera_handler.load_config(self.get_named_config("camera", cam_config_name))
                # Flush buffer and let auto-settings converge
                for _ in range(3):
                    if self.microcontroller_handler:
                        _ = self.microcontroller_handler.set_leds(**led_kwargs)
                    for _ in range(5):
                        _ = self.camera_handler.capture_image(cam_config_name="flush", light_config_name=light_config_name)
                # Capture image
                img = self.camera_handler.capture_image(cam_config_name=cam_config_name, light_config_name=light_config_name)
                if img is None:
                    self.logger.error("", extra={"event": "capture_failed", "details": f"Skipping save for {cam_config_name}/{light_config_name} - no frame captured"})
                else:
                    self.camera_handler.save_image(img, cam_config_name=save_cam_config_name, light_config_name=light_config_name)

            if capture_delay > 0:
                time.sleep(capture_delay)

        self.shutdown_capture()

    def shutdown_capture(self):
        """Turn the lights off and close the camera after a capture run."""
        if self.camera_handler:
            self.camera_handler.logger.telemetry("", event="camera_temperature", details=self.camera_handler.camera.DeviceTemperature.Value)
            self.camera_handler.close()
        if self.microcontroller_handler:
            # Turn off lights
            self.microcontroller_handler.set_leds(0, 0, 0)
            self.microcontroller_handler.logger.debug("", extra={"event": "lights", "details": "Setting lights off after capture"})


# RUN AS CLI
if __name__ == "__main__":
    parser = argparse.ArgumentParser("LOTUS-PTO Camera Rig capture")
    parser.add_argument('rig', help="Choice of camera to capture from")
    parser.add_argument('--config', default="./config.yaml", type=str, help="path to main config file")
    parser.add_argument('-c', nargs=2, action='append', help="Provide the name of a camera config followed by the name of a lighting config [See available configs with --list_configs]")
    parser.add_argument('--output_path', type=str, default="/home/aau/lotus-data/")
    parser.add_argument('--disable_camera', action="store_true", default=False, help="Disable camera capture")
    parser.add_argument('--disable_microcontroller', action="store_true", default=False, help="Disable microcontroller calls")
    parser.add_argument('--log_level', default="debug", help="Level of verbosity of the logger")
    parser.add_argument('--capture_delay', default=1, type=int, help="Delay between captures")
    args = parser.parse_args()

    #Load config
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize capture object
    cc = CaptureController(
        rig = args.rig,
        config = config,
        enable_camera = not args.disable_camera,
        enable_microcontroller = not args.disable_microcontroller,
        log_level = args.log_level,
        output_path=args.output_path
        )
    
    try:
        # Start
        cc.start_rig()

        # Prepare capture
        cc.prepare_for_capture()
        # Setup centralized logging
        if args.c is None:
            args.c = [["default", "default"]]
            cc.logger.warning("", extra={"event": "config_parsing", "details":"No configs provided"})

        # Build normalized capture steps from the requested config pairs
        steps = [
            CaptureStep(camera_config=cam_config_name, light_config=light_config_name)
            for cam_config_name, light_config_name in args.c
        ]

        # Run the shared capture pipeline
        cc.run_capture_sequence(steps, capture_delay=args.capture_delay)
    except KeyboardInterrupt:
        cc.logger.warning("", extra={"event": "interrupted", "details": "Capture interrupted by user (Ctrl-C)"})
        sys.exit(130)
    except Exception as e:
        cc.logger.error("", extra={"event": "abort", "details": str(e)})
        sys.exit(1)
    finally:
        exc_info = sys.exc_info()
        try:
            cc.power_off_camera()
        except BaseException as e:
            cc.logger.error("", extra={"event": "poe_control_failure", "details": f"PoE power-off during shutdown failed: {e}"})
            if exc_info[0] is None:
                raise

    sys.exit(0)
