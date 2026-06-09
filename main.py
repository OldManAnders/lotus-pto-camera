'''
This script executes a series of image captures with a set of given camera parameters and a set of given lighting parameters.
The lighting and camera parameters are called by the names specified in the config.yaml.
To acquire from several rigs, this script should be executed for every camera setup
'''
import argparse, yaml, logging, traceback, sys, datetime, os
from camera.camera_handler import CameraHandler
from microcontroller.microcontroller_handler import MicrocontrollerHandler
from utils.logging_config import configure_logging, get_logger, TELEMETRY

__CONFIG__ = "./config.yaml"
with open(__CONFIG__, 'r') as f:
    __CONFIG__ = yaml.safe_load(f)


__log_level_map__={
    "debug": logging.DEBUG,
    "telemetry": TELEMETRY,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

parser = argparse.ArgumentParser("LOTUS-PTO Camera Rig capture")
parser.add_argument(dest='rig', help="Choice of camera to capture from", choices=__CONFIG__["setups"].keys())
parser.add_argument('-c', nargs=2, action='append', help="Provide the name of a camera config followed by the name of a lighting config [See available configs with --list_configs]")
parser.add_argument('--list_configs', action='store_true', help="List all camera and lighting configs by name")
parser.add_argument('--output_path', type=str, default="./captured_data/")
parser.add_argument('--disable_camera', action="store_true", default=False, help="Disable camera capture")
parser.add_argument('--disable_microcontroller', action="store_true", default=False, help="Disable microcontroller calls")
parser.add_argument('--log_level', default="telemetry", choices=__log_level_map__.keys(), help="Level of verbosity of the logger")
args = parser.parse_args()

# Setup centralized logging
configure_logging(level=__log_level_map__[args.log_level])
logger = get_logger("server.main", component=args.rig)
logger.debug("", extra={"event": "logging", "details": "logging configured with level " + args.log_level})

if args.list_configs:
    print("List of available camera configs:")
    for cam_config in list(__CONFIG__["camera_configs"].keys()):
        print(cam_config)
    print("List of available lighting configs:")
    for lit_config in list(__CONFIG__["light_configs"].keys()):
        print(lit_config)

# Get setup specific config
rig = __CONFIG__["setups"][args.rig]
logger.debug("", extra={"event": "initialization", "details": f"Loaded config for rig {args.rig}"})

# Creating daily folder
today = datetime.date.today().strftime("%Y-%m-%d")
image_output_path = os.path.join(args.output_path, "images", today)
os.makedirs(image_output_path, exist_ok=True)
logger.debug("", extra={"event": "output", "details": f"Images will be saved to {image_output_path}"})

#Initiate camera controller
try:
    if args.disable_camera:
        camera_handler = None
        logger.warning("", extra={"event": "module_disabled", "details": "Camera module disabled via CLI argument"})
    else:
        camera_handler = CameraHandler(ip=rig["camera"]["ip"], name=f"{args.rig},Camera", output_folder=image_output_path)
        camera_handler.wake() #Ensure camera is awake and ready for capture
except:
    #Format stacktraces into a single line with | markers to indicate linebreaks
    err = traceback.format_exc().replace("\n", "|")
    logger.error("", extra={"event": "exception", "details": {"trace": err}})
    logger.error("", extra={"event": "abort", "details": {}})
    sys.exit()

#Initiate microcontroller controller
try: 
    if args.disable_microcontroller:
        micro_controller = None   
        logger.warning("", extra={"event": "module_disabled", "details": "Micro controller module disabled via CLI argument"})
    else:
        micro_controller = MicrocontrollerHandler(ip=rig["microcontroller"]["ip"], port=rig["microcontroller"]["port"], name=f"{args.rig},Microcontroller")
except:
    #Format stacktraces into a single line with | markers to indicate linebreaks
    err = traceback.format_exc().replace("\n", "|")
    logger.error("", extra={"event": "exception", "details": {"trace": err}})
    logger.error("", extra={"event": "abort", "details": {}})
    sys.exit()

if args.c is None:
    args.c = [["default", "default"]]
    logger.warning("", extra={"event": "config_parsing", "details":"No configs provided"})

# Pre capture telemetry
if micro_controller:
    #Temperature sensor
    resp = micro_controller.get_values(["sensor.temperature"])
    if resp["success"]:
        for key, val in resp["data"].items():
            logger.telemetry(event=key, details=val)
    
    #Pressure sensor
    resp = micro_controller.get_values(["sensor.pressure"])
    if resp["success"]:
        for key, val in resp["data"].items():
            logger.telemetry(event=key, details=val)

if camera_handler:
    logger.telemetry(event="camera_temperature", details=camera_handler.camera.DeviceTemperature.Value)

try:
    # Log the amount of configs 
    logger.debug("", extra={"event": "configs_count", "details": f"Number of configs: {len(args.c)}"})
    
    #Wipe the lense
    if micro_controller:
        logger.debug("", extra={"event": "wiper", "details": "Wiping the lense before image capture"})
        micro_controller.send_command("wipe")

    # Iterate over provided camera and lighting configurations
    for c in args.c:
        cam_config_name = c[0]
        light_config_name = c[1]
        logger.info("", extra={"event": "capture_config", "details": f"{light_config_name}, {cam_config_name}"})

        if micro_controller:
            #Initiate light
            micro_controller.set_values(__CONFIG__["light_configs"][light_config_name])
        
        if camera_handler:
            #Set camera settings
            camera_handler.load_config(__CONFIG__["camera_configs"][cam_config_name])
            #Capture image
            img = camera_handler.capture_image(cam_config_name=cam_config_name, light_config_name=light_config_name)
            camera_handler.save_image(img, cam_config_name=cam_config_name, light_config_name=light_config_name)

    # Post capture telemetry
    if micro_controller:
        #Temperature sensor
        resp = micro_controller.get_values(["sensor.temperature"])
        if resp["success"]:
            for key, val in resp["data"].items():
                logger.telemetry(event=key, details=val)
        
        #Pressure sensor
        resp = micro_controller.get_values(["sensor.pressure"])
        if resp["success"]:
            for key, val in resp["data"].items():
                logger.telemetry(event=key, details=val)

    if camera_handler:
        logger.telemetry(event="camera_temperature", details=camera_handler.camera.DeviceTemperature.Value)

    #Close out
    if micro_controller:
        #Turn off lights
        micro_controller.send_command("lightOff")
        logger.debug("", extra={"event": "lights", "details": "Setting lights off after capture"})

    if camera_handler:
        camera_handler.sleep() #Put camera to sleep to save power between captures
        camera_handler.close()

except:
    #Format stacktraces into a single line with | markers to indicate linebreaks
    err = traceback.format_exc().replace("\n", "|")
    logger.error("", extra={"event": "exception", "details": {"trace": err}})
