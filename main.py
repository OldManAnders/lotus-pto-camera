'''
Docstring for capture.py
This script executes a series of image captures with a set of given camera parameters and a set of given lighting parameters.
The lighting and camera parameters are called by the names specified in the capture_config.yaml.
To acquire from several rigs, this script should be executed for every camera setup
'''

import argparse, yaml, logging, traceback, sys
#Local imports
from camera.camera_handler import CameraHandler
from microcontroller.microcontroller_handler import MicrocontrollerHandler

__CONFIG__ = "./config.yaml"
with open(__CONFIG__, 'r') as f:
    __CONFIG__ = yaml.safe_load(f)


__log_level_map__={
    "debug": logging.DEBUG,
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
parser.add_argument('--log_level', default="debug", choices=__log_level_map__.keys(), help="Level of verbosity of the logger")
args = parser.parse_args()

#Setup logger
capture_logger = logging.getLogger(__name__)
logging.basicConfig(
    level=__log_level_map__[args.log_level],
    format=",%(levelname)s,%(name)s,%(message)s" #Leading comma as Linux Timestamps the stdout
    )

if args.list_configs:
    capture_logger.debug("#### CAMERA CONFIGS ####")
    for cam_config in list(__CONFIG__["camera_configs"].keys()):
        capture_logger.debug(cam_config)
    capture_logger.debug("### LIGHTING CONFIGS ###")
    for lit_config in list(__CONFIG__["light_configs"].keys()):
        capture_logger.debug(lit_config)

# Get setup specific config
rig = __CONFIG__["setups"][args.rig]
capture_logger.debug(f"Initializing setup: {args.rig}")

#Initiate camera controller
try:
    if args.disable_camera:
        camera_controller = None
        capture_logger.warning(f"'--disable_camera' set ({args.disable_camera}): Camera control is disabled")
    else:
        camera_controller = CameraHandler(ip=rig["camera"]["ip"], name=args.rig, output_folder=args.output_path, log_level=__log_level_map__[args.log_level])
except:
    #Format stacktraces into a single line with | markers to indicate linebreaks
    err = traceback.format_exc().replace("\n", "|")
    capture_logger.error(err)
    capture_logger.error("Aborting...")
    sys.exit()

try:
    #Initiate microcontroller controller 
    if args.disable_microcontroller:
        micro_controller = None   
    else:
        micro_controller = MicrocontrollerHandler(ip=rig["microcontroller"]["ip"], port=rig["microcontroller"]["port"])
        capture_logger.warning(f"'--disable_microcontroller' set ({args.disable_microcontroller}): Microcontroller communication is disabled")
except:
    #Format stacktraces into a single line with | markers to indicate linebreaks
    err = traceback.format_exc().replace("\n", "|")
    capture_logger.error(err)
    capture_logger.error("Aborting...")
    sys.exit()

#Check and report of 
if args.c is not None:
    try:
        capture_logger.debug(f"{len(args.c)} configs provided")
        #Wipe the lense
        if micro_controller:
            capture_logger.debug(f"Sending command to wipe lense")
            micro_controller.send_command("wipe")

        for c in args.c:
            cam_config_name = c[0]
            light_config_name = c[1]
            capture_logger.debug(f"Capturing an image with [{cam_config_name}] [{light_config_name}]")
            if micro_controller:
                capture_logger.info(f"Current Camera temperature {camera_controller.camera.DeviceTemperature.Value}")
                #Initiate light
                micro_controller.set_values(__CONFIG__["light_configs"][light_config_name])
            
            if camera_controller:
                #Set camera settings
                camera_controller.load_config(__CONFIG__["camera_configs"][cam_config_name])
                #Capture image
                camera_controller.snap_pic(cam_config_name=cam_config_name, light_config_name=light_config_name)
        
        #Close out
        if micro_controller:
            #Turn off lights
            micro_controller.send_command("lightOff")

        if camera_controller:
            camera_controller.close()

    except:
        #Format stacktraces into a single line with | markers to indicate linebreaks
        err = traceback.format_exc().replace("\n", "|")
        capture_logger.error(err)
else: 
    try:
        capture_logger.warning(f"No configs provided. A single image will be captured with default settings")
        
        if micro_controller:
            #Initiate light
            micro_controller.set_values(rig["light"])

        if camera_controller:
            #Set camera settings
            camera_controller.load_config(rig["camera"]["settings"])
            camera_controller.snap_pic(cam_config_name="default", light_config_name="default")
            camera_controller.close()

        if micro_controller:
            micro_controller.send_command("lightOff")
        
    except Exception:
        #Format stacktraces into a single line with | markers to indicate linebreaks
        err = traceback.format_exc().replace("\n", "|")
        capture_logger.error(err)
