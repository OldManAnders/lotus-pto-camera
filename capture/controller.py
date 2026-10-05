"""Rig orchestration for the LOTUS-PTO capture pipeline.

``CaptureController`` owns one rig: it powers the camera over PoE, connects the
camera and microcontroller adapters, and runs a sequence of ``CaptureStep``s.
Both the CLI (``main.py``) and the GUI (``gui_capture.py``) drive it.
"""
import logging
import os
import time
from dataclasses import dataclass

from capture.camera import CameraHandler
from capture.microcontroller import MicrocontrollerHandler
from utils.logging_config import configure_logging, get_logger
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
    POE_WARMUP_SEC = 10
    FLUSH_ROUNDS = 3
    FLUSH_GRABS = 5

    def __init__(self,
                 rig,
                 config,
                 enable_camera = True,
                 enable_microcontroller = True,
                 enable_unifi = True,
                 output_path = "./",
                 log_level = "info",
                 log_file = None,
                 run_id = ""
                 ):

        # Store identity first so logging can carry rig/run context
        self.rig = rig
        self.output_path = output_path
        self.config = config
        self.enable_camera = enable_camera
        self.enable_microcontroller = enable_microcontroller
        self.enable_unifi = enable_unifi
        self.unifi = None
        self.camera_handler = None
        self.microcontroller_handler = None
        self._log_file = log_file
        self._run_id = run_id or os.environ.get("LOTUS_RUN_ID", "")

        # Establish logger
        self.set_log_level(log_level, log_file=log_file, run_id=self._run_id)
        self.logger = get_logger(__name__, component="main", rig=self.rig)
        self.logger.debug(f"Setting log level to '{log_level}'", extra={"event": "logger_initialization", "details": {"level": log_level, "run_id": self._run_id}})

        setups = self.get_subconfig("setups")
        if self.rig not in setups:
            self.logger.error(f"Unknown rig '{self.rig}'", extra={"event": "config_loading", "details": {"rig": self.rig, "available": list(setups.keys())}})
            raise ValueError(f"Unknown rig '{self.rig}'. Available rigs: {list(setups.keys())}")
        self.rig_config = setups[self.rig]

    def _ensure_unifi(self):
        """Lazily create the UniFi PoE controller. Returns None when disabled."""
        if not self.enable_unifi:
            return None
        if self.unifi is None:
            network_conf = self.get_subconfig("network")
            host = network_conf["unifi"]["host"]
            self.logger.debug(f"Connecting to UniFi controller at {host}", extra={"event": "unifi_initialization", "details": {"host": host}})
            try:
                self.unifi = UnifiPoEController(UnifiConfig(**network_conf["unifi"]), rig=self.rig)
            except Exception as e:
                self.logger.error(f"UniFi initialization failed: {e}", extra={"event": "unifi_initialization_failure", "details": {"error": str(e)}}, exc_info=True)
                raise
        return self.unifi

    def set_log_level(self, log_level, log_file=None, run_id=""):
        configure_logging(
            level=log_level,
            logfile=log_file,
            run_id=run_id or os.environ.get("LOTUS_RUN_ID", ""),
            rig=getattr(self, "rig", ""),
        )

    def start_rig(self):
        # Initialize camera_handler
        try:
            self.power_on_camera()
            self.camera_handler = CameraHandler(ip=self.rig_config["camera"]["ip"], rig=self.rig, output_folder=self.output_path) if self.enable_camera else None
            self.microcontroller_handler = MicrocontrollerHandler(ip=self.rig_config["microcontroller"]["ip"], port=self.rig_config["microcontroller"]["port"], rig=self.rig) if self.enable_microcontroller else None
        except Exception as e:
            self.logger.error(f"Failed to start rig: {e}", extra={"event": "exception", "details": {"error": str(e)}}, exc_info=True)
            raise RuntimeError(f"Failed to start rig '{self.rig}': {e}") from e

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
            self.logger.warning(f"Attempted to retrieve unknown subconfig: '{subconfig}'", extra={"event": "config_loading", "details": {"subconfig": subconfig}})
            return {}

    def get_named_config(self, kind, name):
        configs = self.get_subconfig(kind)
        if name not in configs:
            self.logger.error(f"Unknown {kind} config '{name}'", extra={"event": "config_loading", "details": {"kind": kind, "name": name, "available": list(configs.keys())}})
            raise ValueError(f"Unknown {kind} config '{name}'. Available: {list(configs.keys())}")
        return configs[name]

    def power_on_camera(self):
        if not self.enable_unifi:
            self.logger.info("UniFi disabled - skipping PoE power-on (assume camera pre-powered)", extra={"event": "poe_control", "details": {"action": "skipped", "reason": "unifi_disabled"}})
            return
        # Power on PoE port
        try:
            switch_mac = self.get_subconfig("network")["camera_switch_mac"]
            port = self.rig_config['camera']['switch_port']
            self.logger.info(f"Powering ON PoE for camera at switch {switch_mac} port {port}", extra={"event": "poe_control", "details": {"switch": switch_mac, "port": port, "action": "on"}})
            self._ensure_unifi()
            result = self.unifi.set_poe(
                switch_mac=switch_mac,
                port_index=port,
                enabled=True)
            if not result["success"]:
                self.logger.error(f"Failed to verify PoE power-on for camera on port {port}", extra={"event": "poe_control_failure", "details": {"port": port}})
                raise RuntimeError("Camera PoE power-on not verified")
            self.logger.debug(f"Waiting {self.POE_WARMUP_SEC} seconds for camera to power on and initialize", extra={"event": "poe_camera_warmup", "details": {"warmup_sec": self.POE_WARMUP_SEC}})
            time.sleep(self.POE_WARMUP_SEC)
        except Exception as e:
            self.logger.error(f"PoE power-on failed: {e}", extra={"event": "poe_control_failure", "details": {"error": str(e)}}, exc_info=True)
            raise

    def power_off_camera(self):
        if not self.enable_unifi:
            self.logger.info("UniFi disabled - skipping PoE power-off", extra={"event": "poe_control", "details": {"action": "skipped", "reason": "unifi_disabled"}})
            return
        try:
            switch_mac = self.get_subconfig("network")["camera_switch_mac"]
            port = self.rig_config['camera']['switch_port']
            self.logger.info(f"Powering OFF PoE for camera at switch {switch_mac} port {port}", extra={"event": "poe_control", "details": {"switch": switch_mac, "port": port, "action": "off"}})
            result = self.unifi.set_poe(
                switch_mac=switch_mac,
                port_index=port,
                enabled=False)
            self.logger.debug(f"PoE power-off issued for {result.get('switch_mac')}", extra={"event": "poe_control_success", "details": {"switch": result.get("switch_mac"), "port": result.get("port"), "state": result.get("poe_mode")}})
        except Exception as e:
            self.logger.error(f"PoE power-off failed: {e}", extra={"event": "poe_control_failure", "details": {"error": str(e)}}, exc_info=True)

    def _log_camera_temperature(self, logger=None):
        """Log the camera's internal temperature. Never raises."""
        if self.camera_handler is None:
            return
        logger = logger or self.logger
        temperature = self.camera_handler.read_temperature()
        if temperature is None:
            logger.warning("Camera temperature unavailable", extra={"event": "camera_temperature_failed", "details": {}})
            return
        logger.debug(f"Camera temperature {temperature}", extra={"event": "camera_temperature", "details": {"celsius": temperature}})

    def _set_leds(self, light_config_name, led_kwargs=None):
        """Resolve and apply the lighting for a step.

        ``led_kwargs`` holds explicit ``set_leds`` kwargs for manual lighting;
        when ``None`` the values are looked up from ``light_configs`` by name.
        Returns ``(requested_dict, actual_status)``; ``actual_status`` is ``None``
        when the microcontroller is disabled, otherwise the reported LED state
        (``{}`` if the status request failed).
        """
        if led_kwargs is None:
            requested = dict(self.get_named_config("lights", light_config_name))
        else:
            requested = dict(led_kwargs)
        if not self.enable_microcontroller or self.microcontroller_handler is None:
            return requested, None
        response = self.microcontroller_handler.set_leds(**requested)
        self.logger.info(f"LEDs set for {light_config_name}", extra={"event": "lights_set", "details": {"config": light_config_name, "led1": response.get("led1") if response else None, "led2": response.get("led2") if response else None, "led3": response.get("led3") if response else None}})
        try:
            actual = self.microcontroller_handler.get_status() or {}
        except Exception:
            actual = {}
        return requested, actual

    def _capture_pair(self, cam_config_name, light_config_name, led_kwargs=None):
        """Load + flush + read state + final capture. No save (caller builds metadata first).

        Returns ``(img_or_None, camera_meta, camera_internal_temp)``.
        """
        if not self.enable_camera or self.camera_handler is None:
            return None, {"settings_actual": {}}, None
        self.camera_handler.load_config(self.get_named_config("camera", cam_config_name))
        if led_kwargs is None:
            led_kwargs = self.get_named_config("lights", light_config_name)
        # Keep re-sending LEDs each round: the ESP32 resets non-zero LEDs after
        # ~5s (CMD_TIMEOUT_MS), and this also lets Continuous auto-exposure converge.
        for _ in range(self.FLUSH_ROUNDS):
            if self.enable_microcontroller and self.microcontroller_handler is not None:
                self.microcontroller_handler.set_leds(**led_kwargs)
            for _ in range(self.FLUSH_GRABS):
                self.camera_handler.capture_image(cam_config_name="flush", light_config_name=light_config_name)
        if hasattr(self.camera_handler, "get_camera_meta"):
            camera_meta = self.camera_handler.get_camera_meta()
        else:
            camera_meta = {"settings_actual": {}}
        temp = self.camera_handler.read_temperature()
        img = self.camera_handler.capture_image(cam_config_name=cam_config_name, light_config_name=light_config_name)
        if img is None:
            self.logger.error(f"No frame captured for {cam_config_name}/{light_config_name} - skipping save", extra={"event": "capture_failed", "details": {"camera_config": cam_config_name, "light_config": light_config_name}})
        return img, camera_meta, temp

    def build_capture_metadata(self, *, timestamp, cam_config_name, light_config_name,
                               requested_light, light_actual, camera_meta,
                               camera_internal_temp, capture_delay_sec) -> dict:
        """Assemble the sidecar metadata dict (schema_version 1).

        Camera-node reads come from ``camera_handler.get_camera_meta()``.
        """
        return {
            "schema_version": 1,
            "capture": {
                "timestamp": timestamp,
                "rig": self.rig,
                "camera_config": cam_config_name,
                "lighting_config": light_config_name,
                "image_file": f"{timestamp}_{self.rig}_{cam_config_name}_{light_config_name}.png"
            },
            "camera": {
                "settings_actual": camera_meta.get("settings_actual", {})
            },
            "lighting": {
                "requested_config": light_config_name,
                "requested": requested_light,
                "actual": light_actual
            },
            "sensors": {
                "camera_internal_temp": camera_internal_temp
            },
            "pipeline": {
                "poe_warmup_sec": self.POE_WARMUP_SEC,
                "buffer_flush_iterations": self.FLUSH_ROUNDS,
                "buffer_flush_grabs_per_iteration": self.FLUSH_GRABS,
                "capture_delay_sec": capture_delay_sec
            }
        }

    def _cleanup(self):
        """Close the camera and turn off the lights. Respects all disable flags."""
        if self.enable_camera and self.camera_handler is not None:
            self._log_camera_temperature(logger=self.camera_handler.logger)
            try:
                self.camera_handler.close()
            except Exception as e:
                self.logger.error(f"Camera close failed: {e}", extra={"event": "camera_close_failed", "details": {"error": str(e)}})
        if self.enable_microcontroller and self.microcontroller_handler is not None:
            self.microcontroller_handler.set_leds(0, 0, 0)
            self.microcontroller_handler.logger.debug("Setting lights off after capture", extra={"event": "lights", "details": {}})

    def prepare_for_capture(self):
        if self.microcontroller_handler is not None:
            self.logger.debug("Wiping lens before capturing", extra={"event": "wiper", "details": {}})
            reply = self.microcontroller_handler.wipe()  # blocks ~4s, 30s timeout inside handler
            if reply is None:
                self.logger.warning("Wiper call failed - continuing capture anyway", extra={"event": "wiper_failed", "details": {}})
        if self.camera_handler is not None:
            self._log_camera_temperature()

    def run_capture_sequence(self, steps, capture_delay=0):
        """Run every capture step through the shared rig pipeline.

        For each step: set the lights, load the camera preset, flush the buffer
        so the auto-exposure/white-balance algorithms converge, capture one
        frame, and save it with a sidecar metadata file. Lights are switched off
        and the camera is closed in a ``finally`` block, so teardown runs even if
        a step raises.
        """
        try:
            for step in steps:
                cam_config_name = step.camera_config
                light_config_name = step.light_config
                timestamp = time.strftime("%Y%m%d-%H%M%S")  # sole ground truth (filename, folder, metadata)

                self.logger.info(f"Capture {cam_config_name}/{light_config_name}", extra={"event": "capture", "details": {"camera_config": cam_config_name, "light_config": light_config_name}})

                requested_light, light_actual = self._set_leds(light_config_name, led_kwargs=step.leds)
                img, camera_meta, temp = self._capture_pair(cam_config_name, light_config_name, led_kwargs=step.leds)
                if img is None:
                    continue
                metadata = self.build_capture_metadata(
                    timestamp=timestamp, cam_config_name=cam_config_name,
                    light_config_name=light_config_name, requested_light=requested_light,
                    light_actual=light_actual, camera_meta=camera_meta,
                    camera_internal_temp=temp, capture_delay_sec=capture_delay)
                self.camera_handler.save_image(
                    img, cam_config_name=cam_config_name, light_config_name=light_config_name,
                    timestamp=timestamp, metadata=metadata)

                if capture_delay > 0:
                    time.sleep(capture_delay)
        finally:
            self._cleanup()
