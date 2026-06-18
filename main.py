'''
This script executes a series of image captures with a set of given camera parameters and a set of given lighting parameters.
The lighting and camera parameters are called by the names specified in the config.yaml.
To acquire from several rigs, this script should be executed for every camera setup
'''
import yaml, logging, traceback, sys, datetime, os, time
from camera.camera_handler import CameraHandler
from microcontroller.microcontroller_handler import MicrocontrollerHandler
from utils.logging_config import configure_logging, get_logger, TELEMETRY
from utils.unifi_poe_controller import UnifiConfig, UnifiPoEController

__log_level_map__={
    "debug": logging.DEBUG,
    "telemetry": TELEMETRY,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

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
        self.rig = self.get_subconfig("setups")[self.name]

        # Unifi API
        self.unifi = self.setup_unifi_api(self.get_subconfig("network"))

    def setup_unifi_api(self, network_conf):
        self.logger.debug("", extra={"event": "unifi_initialization", "details": f"Establishing connection to Unifi controller at {network_conf['unifi']['host']}"})
        try:
            return UnifiPoEController(UnifiConfig(**network_conf["unifi"]))
        except Exception as e:
            self.logger.error("", extra={"event": "unifi_initialization_failure", "details": str(e)})

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
                self.logger.error("", extra={"event": "abort", "details": "Exiting script via sys.exit()"})
                sys.exit()

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

    def power_on_camera(self):
        # Power on PoE port
        try:
            self.logger.info("", extra={"event": "poe_control", "details": f"Powering ON PoE for camera at switch {self.get_subconfig("network")["camera_switch_mac"]} port {self.rig['camera']['switch_port']}"})
            result = self.unifi.set_poe(
                switch_mac=self.get_subconfig("network")["camera_switch_mac"],
                port_index=self.rig["camera"]["switch_port"],
                enabled=True)
            if result["success"]:
                self.logger.debug("", extra={"event": "poe_camera_warmup", "details": "Waiting 20 seconds for camera to power on and initialize"})
                time.sleep(20)
            else:
                self.logger.error
        except Exception as e:
            self.logger.error("", extra={"event": "poe_control_failure", "details": str(e)})
        
    def power_off_camera(self):
        try:
            self.logger.info("", extra={"event": "poe_control", "details": f"Powering off PoE for camera at switch {self.get_subconfig("network")["camera_switch_mac"]} port {self.rig['camera']['switch_port']}"})
            result = self.unifi.set_poe(
                switch_mac=self.get_subconfig("network")["camera_switch_mac"],
                port_index=self.rig["camera"]["switch_port"],
                enabled=False)
            self.logger.debug("", extra={"event": "poe_control_success", "details": f"{result['switch_mac']}: port:{result['port']} state:{result['poe_mode']}"})
        except Exception as e:
            self.logger.error("", extra={"event": "poe_control_failure", "details": str(e)})

    def prepare_for_capture(self):
        if self.microcontroller_handler:
            self.logger.debug("", extra={"event": "wiper", "details": "Wiping the lense before image capture"})
            self.microcontroller_handler.wipe()
        if self.camera_handler:
            self.logger.telemetry("",event="camera_temperature", details=self.camera_handler.camera.DeviceTemperature.Value)
            # Flush buffer
            self.logger.debug("", event="camera_operations", details="Flushing camera framebuffer")
            for _ in range(1,6):
                _ = self.camera_handler.capture_image()
        
def run_cli():
    import argparse
    parser = argparse.ArgumentParser("LOTUS-PTO Camera Rig capture")
    parser.add_argument('rig', help="Choice of camera to capture from")
    parser.add_argument('--config', default="./config.yaml", type=str, help="path to main config file")
    parser.add_argument('-c', nargs=2, action='append', help="Provide the name of a camera config followed by the name of a lighting config [See available configs with --list_configs]")
    parser.add_argument('--output_path', type=str, default="./captured_data/")
    parser.add_argument('--disable_camera', action="store_true", default=False, help="Disable camera capture")
    parser.add_argument('--disable_microcontroller', action="store_true", default=False, help="Disable microcontroller calls")
    parser.add_argument('--log_level', default="telemetry", help="Level of verbosity of the logger")
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
        cc.start_rig()

        cc.prepare_for_capture()
        if cc.camera_handler:
            cc.camera_handler.logger.telemetry("", event="camera_temperature", details=cc.camera_handler.camera.DeviceTemperature.Value)

        # Setup centralized logging
        if args.c is None:
            args.c = [["default", "default"]]
            cc.logger.warning("", extra={"event": "config_parsing", "details":"No configs provided"})

        # Iterate over provided camera and lighting configurations
        for c in args.c:
            cam_config_name = c[0]
            light_config_name = c[1]
            cc.logger.info("", extra={"event": "capture", "details": f"{light_config_name}, {cam_config_name}"})
            if cc.microcontroller_handler:
                #Initiate light
                response = cc.microcontroller_handler.set_leds(**cc.get_subconfig("lights")[light_config_name])
            if cc.camera_handler:
                #Set camera settings
                cc.camera_handler.load_config(cc.get_subconfig("camera")[cam_config_name])
                #Capture image
                img = cc.camera_handler.capture_image(cam_config_name=cam_config_name, light_config_name=light_config_name)
                cc.camera_handler.save_image(img, cam_config_name=cam_config_name, light_config_name=light_config_name)

        #Close out
        if cc.camera_handler:
            cc.camera_handler.logger.telemetry("", event="camera_temperature", details=cc.camera_handler.camera.DeviceTemperature.Value)
            cc.camera_handler.close()
        if cc.microcontroller_handler:
            #Turn off lights
            cc.microcontroller_handler.set_leds(0,0,0)
            cc.microcontroller_handler.logger.debug("", extra={"event": "lights", "details": "Setting lights off after capture"})
    finally:
        cc.power_off_camera()

if __name__ == "__main__":
    run_cli()