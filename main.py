'''
This script executes a series of image captures with a set of given camera parameters and a set of given lighting parameters.
The lighting and camera parameters are called by the names specified in the config.yaml.
To acquire from several rigs, this script should be executed for every camera setup
'''
import yaml, logging, traceback, sys, time, argparse, os
from camera.camera_handler import CameraHandler
from microcontroller.microcontroller_handler import MicrocontrollerHandler
from utils.logging_config import configure_logging, get_logger
from utils.unifi_poe_controller import UnifiConfig, UnifiPoEController

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
        self.name = rig
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
        self.logger = get_logger(name="main", component="main", rig=self.name)
        self.logger.debug(f"Setting log level to '{log_level}'", extra={"event": "logger_initialization", "details": {"level": log_level, "run_id": self._run_id}})

        setups = self.get_subconfig("setups")
        if self.name not in setups:
            self.logger.error(f"Unknown rig '{self.name}'", extra={"event": "config_loading", "details": {"rig": self.name, "available": list(setups.keys())}})
            raise ValueError(f"Unknown rig '{self.name}'. Available rigs: {list(setups.keys())}")
        self.rig = setups[self.name]

    def _ensure_unifi(self):
        if not self.enable_unifi:
            return None
        if self.unifi is None:
            network_conf = self.get_subconfig("network")
            host = network_conf["unifi"]["host"]
            self.logger.debug(f"Connecting to UniFi controller at {host}", extra={"event": "unifi_initialization", "details": {"host": host}})
            try:
                self.unifi = UnifiPoEController(UnifiConfig(**network_conf["unifi"]))
            except Exception as e:
                self.logger.error(f"UniFi initialization failed: {e}", extra={"event": "unifi_initialization_failure", "details": {"error": str(e)}}, exc_info=True)
                raise
        return self.unifi

    def set_log_level(self, log_level, log_file=None, run_id=""):
        ll_map={
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }
        level = ll_map.get(log_level, logging.INFO)
        configure_logging(level=level, logfile=log_file, run_id=run_id or os.environ.get("LOTUS_RUN_ID", ""), rig=getattr(self, "name", ""))

    def start_rig(self):
        # Initialize camera_handler
        try:
            self.power_on_camera()
            self.camera_handler = CameraHandler(ip=self.rig["camera"]["ip"], rig=self.name, output_folder=self.output_path) if self.enable_camera else None
            self.microcontroller_handler = MicrocontrollerHandler(ip=self.rig["microcontroller"]["ip"], port=self.rig["microcontroller"]["port"], rig=self.name) if self.enable_microcontroller else None
        except Exception as e:
                self.logger.error(f"Failed to start rig: {e}", extra={"event": "exception", "details": {"error": str(e)}}, exc_info=True)
                self.logger.error("Exiting script via sys.exit()", extra={"event": "abort", "details": {}})
                sys.exit(1)

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
            port = self.rig['camera']['switch_port']
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
            port = self.rig['camera']['switch_port']
            self.logger.info(f"Powering OFF PoE for camera at switch {switch_mac} port {port}", extra={"event": "poe_control", "details": {"switch": switch_mac, "port": port, "action": "off"}})
            result = self.unifi.set_poe(
                switch_mac=switch_mac,
                port_index=port,
                enabled=False)
            self.logger.debug(f"PoE power-off issued for {result.get('switch_mac')}", extra={"event": "poe_control_success", "details": {"switch": result.get("switch_mac"), "port": result.get("port"), "state": result.get("poe_mode")}})
        except Exception as e:
            self.logger.error(f"PoE power-off failed: {e}", extra={"event": "poe_control_failure", "details": {"error": str(e)}}, exc_info=True)

    def _set_leds(self, light_config_name):
        """Returns (requested_dict, actual_status). actual is None if disabled, {} on HTTP failure."""
        requested = self.get_named_config("lights", light_config_name)
        if not self.enable_microcontroller or self.microcontroller_handler is None:
            return requested, None
        response = self.microcontroller_handler.set_leds(**requested)
        self.logger.info(f"LEDs set for {light_config_name}", extra={"event": "lights_set", "details": {"config": light_config_name, "led1": response.get("led1") if response else None, "led2": response.get("led2") if response else None, "led3": response.get("led3") if response else None}})
        try:
            actual = self.microcontroller_handler.get_status() or {}
        except Exception:
            actual = {}
        return requested, actual

    def _capture_pair(self, cam_config_name, light_config_name):
        """Load + flush + read state + final capture. No save (caller builds metadata first).
        Returns (img_or_None, camera_meta, temp)."""
        if not self.enable_camera or self.camera_handler is None:
            return None, {"settings_actual": {}}, None
        self.camera_handler.load_config(self.get_named_config("camera", cam_config_name))
        # Keep re-sending LEDs each round: ESP32 resets non-zero LEDs after 5s (CMD_TIMEOUT_MS),
        # and this also lets Continuous auto-exposure converge.
        for _ in range(self.FLUSH_ROUNDS):
            if self.enable_microcontroller and self.microcontroller_handler is not None:
                self.microcontroller_handler.set_leds(**self.get_named_config("lights", light_config_name))
            for _ in range(self.FLUSH_GRABS):
                self.camera_handler.capture_image(cam_config_name="flush", light_config_name=light_config_name)
        if hasattr(self.camera_handler, "get_camera_meta"):
            camera_meta = self.camera_handler.get_camera_meta()
        else:
            camera_meta = {"settings_actual": {}}
        try:
            temp = self.camera_handler.camera.DeviceTemperature.Value
        except Exception:
            temp = None
        img = self.camera_handler.capture_image(cam_config_name=cam_config_name, light_config_name=light_config_name)
        if img is None:
            self.logger.error(f"No frame captured for {cam_config_name}/{light_config_name} - skipping save", extra={"event": "capture_failed", "details": {"camera_config": cam_config_name, "light_config": light_config_name}})
        return img, camera_meta, temp

    def build_capture_metadata(self, *, timestamp, cam_config_name, light_config_name,
                               requested_light, light_actual, camera_meta,
                               camera_internal_temp, capture_delay_sec) -> dict:
        """Assembles sidecar dict (schema_version 1). Camera-node reads come from camera_handler.get_camera_meta()."""
        return {
            "schema_version": 1,
            "capture": {
                "timestamp": timestamp,
                "rig": self.name,
                "camera_config": cam_config_name,
                "lighting_config": light_config_name,
                "image_file": f"{timestamp}_{self.name}_{cam_config_name}_{light_config_name}.png"
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
        """Close camera, turn off lights. Respects all disable flags."""
        if self.enable_camera and self.camera_handler is not None:
            self.camera_handler.close()
        if self.enable_microcontroller and self.microcontroller_handler is not None:
            self.microcontroller_handler.set_leds(0, 0, 0)
            self.microcontroller_handler.logger.debug("Setting lights off after capture", extra={"event": "lights", "details": {}})

    def prepare_for_capture(self):
        if self.microcontroller_handler is not None:
            self.logger.debug("Wiping lens before capturing", extra={"event": "wiper", "details": {}})
            reply = self.microcontroller_handler.wipe()  # blocks ~4s, 30s timeout inside handler
            if reply is None:
                self.logger.warning("Wiper call failed - continuing capture anyway", extra={"event": "wiper_failed", "details": {}})


# RUN AS CLI
if __name__ == "__main__":
    parser = argparse.ArgumentParser("LOTUS-PTO Camera Rig capture")
    parser.add_argument('rig', help="Choice of camera to capture from")
    parser.add_argument('--config', default="./config.yaml", type=str, help="path to main config file")
    parser.add_argument('-c', nargs=2, action='append', help="Provide the name of a camera config followed by the name of a lighting config [See available configs with --list_configs]")
    parser.add_argument('--output_path', type=str, default="/home/aau/lotus-data/")
    parser.add_argument('--disable_camera', action="store_true", default=False, help="Disable camera capture")
    parser.add_argument('--disable_microcontroller', action="store_true", default=False, help="Disable microcontroller calls")
    parser.add_argument('--disable_unifi', action="store_true", default=False, help="Disable UniFi PoE control (assume camera already powered)")
    parser.add_argument('--log_level', default="info", help="Level of verbosity of the logger")
    parser.add_argument('--log-file', dest="log_file", default=None, help="Path to daily CSV log file")
    parser.add_argument('--run-id', dest="run_id", default="", help="Run correlation id (defaults to LOTUS_RUN_ID env)")
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
        enable_unifi = not args.disable_unifi,
        log_level = args.log_level,
        log_file = args.log_file,
        run_id = args.run_id or os.environ.get("LOTUS_RUN_ID", ""),
        output_path=args.output_path
        )

    try:
        cc.logger.info(f"Routine started on {cc.name}", extra={"event": "routine_start", "details": {"rig": cc.name}})
        # Start
        cc.start_rig()

        # Prepare capture
        cc.prepare_for_capture()
        # Setup centralized logging
        if args.c is None:
            args.c = [["default", "default"]]
            cc.logger.warning("No configs provided - using default/default", extra={"event": "config_parsing", "details": {}})

        # Iterate over provided camera and lighting configurations
        for c in args.c:
            cam_config_name = c[0]
            light_config_name = c[1]
            timestamp = time.strftime("%Y%m%d-%H%M%S")  # sole ground truth (filename, folder, metadata)
            cc.logger.info(f"Capture {cam_config_name}/{light_config_name}", extra={"event": "capture", "details": {"camera_config": cam_config_name, "light_config": light_config_name}})
            requested_light, light_actual = cc._set_leds(light_config_name)
            img, camera_meta, temp = cc._capture_pair(cam_config_name, light_config_name)
            if img is None:
                continue  # save skipped, as today
            metadata = cc.build_capture_metadata(timestamp=timestamp, cam_config_name=cam_config_name, light_config_name=light_config_name, requested_light=requested_light, light_actual=light_actual, camera_meta=camera_meta, camera_internal_temp=temp, capture_delay_sec=args.capture_delay)
            _ = cc.camera_handler.save_image(img, cam_config_name=cam_config_name, light_config_name=light_config_name, timestamp=timestamp, metadata=metadata)
            if args.capture_delay>0:
                time.sleep(args.capture_delay)
        #Close out
        cc._cleanup()
        cc.logger.info(f"Routine completed on {cc.name}", extra={"event": "routine_done", "details": {"rig": cc.name}})
    except KeyboardInterrupt:
        cc.logger.warning("Capture interrupted by user (Ctrl-C)", extra={"event": "interrupted", "details": {}})
        sys.exit(130)
    finally:
        exc_info = sys.exc_info()
        if cc.enable_unifi:
            try:
                cc.power_off_camera()
            except BaseException as e:
                cc.logger.error(f"PoE power-off during shutdown failed: {e}", extra={"event": "poe_control_failure", "details": {"error": str(e)}}, exc_info=True)
                if exc_info[0] is None:
                    raise

    sys.exit(0)
