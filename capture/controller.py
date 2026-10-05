"""Rig orchestration for the LOTUS-PTO capture pipeline.

CaptureController owns one rig: it powers the camera over PoE, connects the
camera and microcontroller adapters, and runs a sequence of CaptureStep
objects. Both the CLI (main.py) and the GUI (gui_capture.py) drive it.
"""
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from capture.camera import CameraHandler
from capture.microcontroller import MicrocontrollerHandler
from utils.logging_config import configure_logging, get_logger
from utils.unifi_poe_controller import UnifiConfig, UnifiPoEController


@dataclass
class CaptureStep:
    """A single capture request, normalized across the CLI and GUI.

    Attributes:
        camera_config: Name of a preset in ``camera_configs``.
        light_config: Lighting name written into the saved filename.
        leds: Explicit ``set_leds`` kwargs for manual lighting; when ``None``
            the LED values are looked up from ``light_configs`` by name.
    """
    camera_config: str
    light_config: str
    leds: Optional[Dict[str, int]] = None


class CaptureController():
    """Own and operate a single LOTUS-PTO camera rig.

    Powers the camera over PoE (unless UniFi control is disabled), connects the
    camera and microcontroller adapters, and runs capture sequences built from
    ``CaptureStep`` objects.

    Attributes:
        rig: Rig identifier selecting an entry under ``setups``.
        config: Full parsed configuration mapping.
        rig_config: Configuration mapping for this rig.
        output_path: Root output directory for captured images.
        enable_camera: Whether the camera adapter is used.
        enable_microcontroller: Whether the microcontroller adapter is used.
        enable_unifi: Whether PoE power control is performed.
        unifi: Lazily created UniFi PoE controller, or ``None``.
        camera_handler: Connected camera adapter, or ``None``.
        microcontroller_handler: Connected microcontroller adapter, or ``None``.
        logger: Logger adapter carrying component/rig context.
    """
    POE_WARMUP_SEC = 10
    FLUSH_ROUNDS = 3
    FLUSH_GRABS = 5

    def __init__(self,
                 rig: str,
                 config: Dict[str, Any],
                 enable_camera: bool = True,
                 enable_microcontroller: bool = True,
                 enable_unifi: bool = True,
                 output_path: str = "./",
                 log_level: str = "info",
                 log_file: Optional[str] = None,
                 run_id: str = ""
                 ) -> None:
        """Initialize the controller for one rig.

        Args:
            rig: Rig identifier; must exist under the ``setups`` config.
            config: Full parsed configuration mapping.
            enable_camera: Enable the camera adapter.
            enable_microcontroller: Enable the microcontroller adapter.
            enable_unifi: Enable UniFi PoE power control.
            output_path: Root output directory for captured images.
            log_level: Logging level name or numeric level.
            log_file: Optional path to the CSV log file.
            run_id: Run correlation id; falls back to the ``LOTUS_RUN_ID``
                environment variable.

        Raises:
            ValueError: If ``rig`` is not present under ``setups``.
        """

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

    def _ensure_unifi(self) -> Optional[UnifiPoEController]:
        """Lazily create the UniFi PoE controller.

        Returns:
            The controller, or ``None`` when UniFi control is disabled.

        Raises:
            Exception: Re-raised if controller initialization fails.
        """
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

    def set_log_level(self, log_level: str, log_file: Optional[str] = None,
                      run_id: str = "") -> None:
        """Configure the process-wide logging setup.

        Args:
            log_level: Logging level name or numeric level.
            log_file: Optional path to the CSV log file.
            run_id: Run correlation id; falls back to the ``LOTUS_RUN_ID``
                environment variable.
        """
        configure_logging(
            level=log_level,
            logfile=log_file,
            run_id=run_id or os.environ.get("LOTUS_RUN_ID", ""),
            rig=getattr(self, "rig", ""),
        )

    def start_rig(self) -> None:
        """Power the camera and connect the rig adapters.

        Raises:
            RuntimeError: If any adapter fails to initialize.
        """
        # Initialize camera_handler
        try:
            self.power_on_camera()
            self.camera_handler = CameraHandler(ip=self.rig_config["camera"]["ip"], rig=self.rig, output_folder=self.output_path) if self.enable_camera else None
            self.microcontroller_handler = MicrocontrollerHandler(ip=self.rig_config["microcontroller"]["ip"], port=self.rig_config["microcontroller"]["port"], rig=self.rig) if self.enable_microcontroller else None
        except Exception as e:
            self.logger.error(f"Failed to start rig: {e}", extra={"event": "exception", "details": {"error": str(e)}}, exc_info=True)
            raise RuntimeError(f"Failed to start rig '{self.rig}': {e}") from e

    def get_subconfig(self, subconfig: str) -> Dict[str, Any]:
        """Return a named configuration section.

        Args:
            subconfig: Section name: ``setups``, ``network``, ``camera``, or
                ``lights`` (case-insensitive).

        Returns:
            The requested section, or an empty dict for unknown names.
        """
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

    def get_named_config(self, kind: str, name: str) -> Dict[str, Any]:
        """Look up a named camera or lighting preset.

        Args:
            kind: Preset kind: ``camera`` or ``lights``.
            name: Preset name within that kind.

        Returns:
            The preset mapping.

        Raises:
            ValueError: If the named preset does not exist.
        """
        configs = self.get_subconfig(kind)
        if name not in configs:
            self.logger.error(f"Unknown {kind} config '{name}'", extra={"event": "config_loading", "details": {"kind": kind, "name": name, "available": list(configs.keys())}})
            raise ValueError(f"Unknown {kind} config '{name}'. Available: {list(configs.keys())}")
        return configs[name]

    def power_on_camera(self) -> None:
        """Power the camera's PoE port on and wait for warm-up.

        No-op when UniFi control is disabled.

        Raises:
            RuntimeError: If the PoE power-on cannot be verified.
            Exception: Re-raised if the UniFi call itself fails.
        """
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

    def power_off_camera(self) -> None:
        """Power the camera's PoE port off.

        No-op when UniFi control is disabled. Failures are logged and not
        raised.
        """
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

    def _log_camera_temperature(self, logger: Optional[logging.LoggerAdapter] = None) -> None:
        """Log the camera's internal temperature.

        Never raises.

        Args:
            logger: Logger to use; defaults to ``self.logger``.
        """
        if self.camera_handler is None:
            return
        logger = logger or self.logger
        temperature = self.camera_handler.read_temperature()
        if temperature is None:
            logger.warning("Camera temperature unavailable", extra={"event": "camera_temperature_failed", "details": {}})
            return
        logger.debug(f"Camera temperature {temperature}", extra={"event": "camera_temperature", "details": {"celsius": temperature}})

    def _set_leds(self, light_config_name: str,
                  led_kwargs: Optional[Dict[str, int]] = None
                  ) -> Tuple[Dict[str, int], Optional[Dict[str, Any]]]:
        """Resolve and apply the lighting for a capture step.

        Args:
            light_config_name: Lighting preset name used when ``led_kwargs`` is
                ``None``.
            led_kwargs: Explicit ``set_leds`` kwargs for manual lighting; when
                ``None`` the values are looked up from ``light_configs`` by
                name.

        Returns:
            Tuple ``(requested, actual_status)``. ``requested`` is the resolved
            LED mapping; ``actual_status`` is ``None`` when the microcontroller
            is disabled, otherwise the reported LED state (``{}`` if the status
            request failed).
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

    def _capture_pair(self, cam_config_name: str, light_config_name: str,
                      led_kwargs: Optional[Dict[str, int]] = None
                      ) -> Tuple[Optional[np.ndarray], Dict[str, Any], Optional[float]]:
        """Load a preset, flush the buffer, and capture one final frame.

        The caller is responsible for saving; this method only acquires.

        Args:
            cam_config_name: Camera preset to load before capturing.
            light_config_name: Lighting preset used to resolve ``led_kwargs``.
            led_kwargs: Explicit ``set_leds`` kwargs; resolved from the lighting
                preset when ``None``.

        Returns:
            Tuple ``(img_or_None, camera_meta, camera_internal_temp)``. ``img``
            is ``None`` when the camera is disabled or the final grab failed.
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

    def build_capture_metadata(self, *, timestamp: str, cam_config_name: str,
                               light_config_name: str,
                               requested_light: Dict[str, int],
                               light_actual: Optional[Dict[str, Any]],
                               camera_meta: Dict[str, Any],
                               camera_internal_temp: Optional[float],
                               capture_delay_sec: int) -> Dict[str, Any]:
        """Assemble the sidecar metadata mapping.

        Args:
            timestamp: Capture timestamp shared by filename and folder.
            cam_config_name: Camera preset name.
            light_config_name: Lighting preset name.
            requested_light: LED values requested for the capture.
            light_actual: LED values reported by the microcontroller.
            camera_meta: Camera settings metadata from the adapter.
            camera_internal_temp: Camera internal temperature in Celsius.
            capture_delay_sec: Inter-capture delay in seconds.

        Returns:
            Metadata mapping with ``schema_version`` 1.
        """
        return {
            "schema_version": 1,
            "capture": {
                "timestamp": timestamp,
                "rig": self.rig,
                "ip": self.camera_handler.ip if self.camera_handler else None,
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
                "buffer_flushed_grabs": int(self.FLUSH_ROUNDS * self.FLUSH_GRABS),
                "capture_delay_sec": capture_delay_sec
            }
        }

    def _cleanup(self) -> None:
        """Close the camera and switch the lights off.

        Respects all enable flags; teardown failures are logged, not raised.
        """
        if self.enable_camera and self.camera_handler is not None:
            self._log_camera_temperature(logger=self.camera_handler.logger)
            try:
                self.camera_handler.close()
            except Exception as e:
                self.logger.error(f"Camera close failed: {e}", extra={"event": "camera_close_failed", "details": {"error": str(e)}})
        if self.enable_microcontroller and self.microcontroller_handler is not None:
            self.microcontroller_handler.set_leds(0, 0, 0)
            self.microcontroller_handler.logger.debug("Setting lights off after capture", extra={"event": "lights", "details": {}})

    def prepare_for_capture(self) -> None:
        """Wipe the lens and log the camera temperature before capturing.

        Wiper failures are logged and capture continues.
        """
        if self.microcontroller_handler is not None:
            self.logger.debug("Wiping lens before capturing", extra={"event": "wiper", "details": {}})
            reply = self.microcontroller_handler.wipe()  # blocks ~4s, 30s timeout inside handler
            if reply is None:
                self.logger.warning("Wiper call failed - continuing capture anyway", extra={"event": "wiper_failed", "details": {}})
        if self.camera_handler is not None:
            self._log_camera_temperature()

    def run_capture_sequence(self, steps: List[CaptureStep],
                             capture_delay: int = 0) -> None:
        """Run every capture step through the shared rig pipeline.

        For each step: set the lights, load the camera preset, flush the buffer
        so the auto-exposure/white-balance algorithms converge, capture one
        frame, and save it with a sidecar metadata file. Lights are switched off
        and the camera is closed in a ``finally`` block, so teardown runs even
        if a step raises.

        Args:
            steps: Capture steps to execute in order.
            capture_delay: Delay in seconds after each capture; ``0`` disables
                the delay.
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
