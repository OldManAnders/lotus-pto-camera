'''
This script executes a series of image captures with a set of given camera parameters and a set of given lighting parameters.
The lighting and camera parameters are called by the names specified in the config.yaml.
To acquire from several rigs, this script should be executed for every camera setup
'''
import argparse
import sys

import yaml

from capture.controller import CaptureController, CaptureStep


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
