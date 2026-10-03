"""Rig orchestration for the LOTUS-PTO capture pipeline.

``CaptureController`` owns one rig: it powers the camera over PoE, connects the
camera and microcontroller adapters, and runs a sequence of ``CaptureStep``s.
Both the CLI (``main.py``) and the GUI (``gui_capture.py``) drive it.
"""
import logging
import time
import traceback
from dataclasses import dataclass

from capture.camera import CameraHandler
from capture.microcontroller import MicrocontrollerHandler
from utils.logging_config import configure_logging, get_logger, TELEMETRY
from utils.unifi_poe_controller import UnifiConfig, UnifiPoEController


@dataclass
class CaptureStep:
    """A single capture request, normalized across the CLI and GUI.

    ``camera_config`` selects a preset from ``camera_configs``. ``light_config``
    is the name written into the saved filename. ``leds`` holds explicit
    ``set_leds`` kwargs for manual lighting; when ``None`` the LED values are
    looked up from ``light_configs`` by name.
    """
    camera_config: str
    light_config: str
    leds: dict = None


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

    def _log_camera_temperature(self, logger=None):
        """Best-effort camera temperature telemetry; never raises."""
        if not self.camera_handler:
            return
        logger = logger or self.logger
        try:
            temperature = self.camera_handler.camera.DeviceTemperature.Value
        except Exception as e:
            logger.warning("", extra={"event": "camera_temperature_failed", "details": str(e)})
            return
        logger.telemetry("", event="camera_temperature", details=temperature)

    def prepare_for_capture(self):
        if self.microcontroller_handler:
            self.logger.debug("", extra={"event": "wiper", "details": "Wiping the lense before capturing"})
            self.microcontroller_handler.wipe()
        if self.camera_handler:
            self._log_camera_temperature()

    def run_capture_sequence(self, steps, capture_delay=0):
        """Run every capture step through the shared rig pipeline.

        For each step: set the lights, load the camera preset, flush the buffer
        so the auto-exposure/white-balance algorithms converge, capture one
        frame, and save it. The lights are turned off and the camera is closed in
        a ``finally`` block, so teardown runs even if a step raises.
        """
        try:
            for step in steps:
                cam_config_name = step.camera_config
                light_config_name = step.light_config
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
                        self.camera_handler.save_image(img, cam_config_name=cam_config_name, light_config_name=light_config_name)

                if capture_delay > 0:
                    time.sleep(capture_delay)
        finally:
            self.shutdown_capture()

    def shutdown_capture(self):
        """Turn the lights off and close the camera after a capture run.

        Teardown is best-effort: a dead camera must not prevent the LEDs from
        being switched off, so failures here are logged rather than raised.
        """
        if self.camera_handler:
            self._log_camera_temperature(logger=self.camera_handler.logger)
            try:
                self.camera_handler.close()
            except Exception as e:
                self.logger.error("", extra={"event": "camera_close_failed", "details": str(e)})
        if self.microcontroller_handler:
            # Turn off lights
            self.microcontroller_handler.set_leds(0, 0, 0)
            self.microcontroller_handler.logger.debug("", extra={"event": "lights", "details": "Setting lights off after capture"})
