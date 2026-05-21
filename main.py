'''
This script executes a series of image captures with a set of given camera parameters and a set of given lighting parameters.
The lighting and camera parameters are called by the names specified in the config.yaml.
To acquire from several rigs, this script should be executed for every camera setup
'''
import argparse, yaml, logging, traceback, sys
from camera.camera_handler import CameraHandler
from microcontroller.microcontroller_handler import MicrocontrollerHandler

__CONFIG__ = "./config.yaml"
with open(__CONFIG__, 'r') as f:
    __CONFIG__ = yaml.safe_load(f)


# Prepare custom logging
TELEMETRY_LEVEL = 15
logging.addLevelName(TELEMETRY_LEVEL, "TELEMETRY")
logging.TELEMETRY = TELEMETRY_LEVEL

#Telemetry logging function
def telemetry(self, message, *args, name=None, **kwargs):
    if self.isEnabledFor(logging.TELEMETRY):
        record = self.makeRecord(
            name=name or self.name,
            level=TELEMETRY_LEVEL,
            fn="", lno=0, msg=message,
            args=args, exc_info=None
        )
        self.handle(record)
#Add telemetry function to logging
logging.Logger.telemetry = telemetry

__log_level_map__={
    "debug": logging.DEBUG,
    "telemetry": logging.TELEMETRY,
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
parser.add_argument('--disable_telemetry', action="store_true", default=False, help="Disable telemetry calls to the microcontroller and camera (e.g. temperature readings)")
parser.add_argument('--log_level', default="debug", choices=__log_level_map__.keys(), help="Level of verbosity of the logger")
args = parser.parse_args()

#Setup logger
logging.basicConfig(
    level=__log_level_map__[args.log_level],
    format="%(asctime)s,%(levelname)s,%(name)s,%(message)s",
    datefmt='%Y-%m-%d%H:%M:%S'
    )
logger = logging.getLogger("server,main")
logger.debug(f"Initialized Main Logger '{logger.name}'")

if args.list_configs:
    logger.debug("#### CAMERA CONFIGS ####")
    for cam_config in list(__CONFIG__["camera_configs"].keys()):
        logger.debug(cam_config)
    logger.debug("### LIGHTING CONFIGS ###")
    for lit_config in list(__CONFIG__["light_configs"].keys()):
        logger.debug(lit_config)

# Get setup specific config
rig = __CONFIG__["setups"][args.rig]
logger.debug(f"Initializing setup: {args.rig}")

#Initiate camera controller
try:
    if args.disable_camera:
        camera_handler = None
        logger.warning(f"'--disable_camera' set ({args.disable_camera}): Camera control is disabled")
    else:
        camera_handler = CameraHandler(ip=rig["camera"]["ip"], name=f"{args.rig},Camera", output_folder=args.output_path)
except:
    #Format stacktraces into a single line with | markers to indicate linebreaks
    err = traceback.format_exc().replace("\n", "|")
    logger.error(err)
    logger.error("Aborting...")
    sys.exit()

#Initiate microcontroller controller
try: 
    if args.disable_microcontroller:
        micro_controller = None   
        logger.warning(f"'--disable_microcontroller' set ({args.disable_microcontroller}): Microcontroller communication is disabled")
    else:
        micro_controller = MicrocontrollerHandler(ip=rig["microcontroller"]["ip"], port=rig["microcontroller"]["port"], name=f"{args.rig}, Microcontroller")
except:
    #Format stacktraces into a single line with | markers to indicate linebreaks
    err = traceback.format_exc().replace("\n", "|")
    logger.error(err)
    logger.error("Aborting...")
    sys.exit()

if args.c is None:
    args.c = [["default", "default"]]
    logger.warning(f"No configs provided. A single image will be captured with default settings")

# Pre capture telemetry
if micro_controller:
    #Temperature sensor
    resp = micro_controller.get_values(["sensor.temperature"])
    if resp["success"]:
        for key, val in resp["data"].items():
            logger.telemetry(val, name=f"{args.rig},{key}")
    
    #Pressure sensor
    resp = micro_controller.get_values(["sensor.pressure"])
    if resp["success"]:
        for key, val in resp["data"].items():
            logger.telemetry(val, name=f"{args.rig},{key}")
if camera_handler:
    logger.telemetry(camera_handler.camera.DeviceTemperature.Value, name=f"{args.rig},Camera_Temperature")

try:
    # Log the amount of configs 
    logger.debug(f"{len(args.c)} configs")
    
    #Wipe the lense
    if micro_controller:
        logger.debug(f"Sending command to wipe lense")
        micro_controller.send_command("wipe")

    # Iterate over provided camera and lighting configurations
    for c in args.c:
        cam_config_name = c[0]
        light_config_name = c[1]
        logger.info(f"Capturing an image with [{cam_config_name}] [{light_config_name}]")

        if micro_controller:
            #Initiate light
            micro_controller.set_values(__CONFIG__["light_configs"][light_config_name])
        
        if camera_handler:
            #Set camera settings
            camera_handler.load_config(__CONFIG__["camera_configs"][cam_config_name])
            #Capture image
            camera_handler.snap_pic(cam_config_name=cam_config_name, light_config_name=light_config_name)
    
    # Post capture telemetry
    if micro_controller:
        #Temperature sensor
        resp = micro_controller.get_values(["sensor.temperature"])
        if resp["success"]:
            for key, val in resp["data"].items():
                logger.telemetry(val, name=f"{args.rig},{key}")
        
        #Pressure sensor
        resp = micro_controller.get_values(["sensor.pressure"])
        if resp["success"]:
            for key, val in resp["data"].items():
                logger.telemetry(val, name=f"{args.rig},{key}")

    if camera_handler:
        logger.telemetry(camera_handler.camera.DeviceTemperature.Value, name=f"{args.rig},Camera_Temperature")

    #Close out
    if micro_controller:
        #Turn off lights
        micro_controller.send_command("lightOff")

    if camera_handler:
        camera_handler.close()

except:
    #Format stacktraces into a single line with | markers to indicate linebreaks
    err = traceback.format_exc().replace("\n", "|")
    logger.error(err)
