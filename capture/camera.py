from pypylon import pylon
import cv2, time, threading, os, yaml, logging, json
from utils.logging_config import get_logger

__PIXEL_FORMAT_MAP__ = {
    "mono8": "Mono8",
    "mono10": "Mono10",
    "mono10p": "Mono10p",
    "mono12p": "Mono12p",
    "rgb8": "RGB8",
    "brg8": "BGR8",
    "ycbcr422": "YCbCr422_8",
    "bayer_gr8": "BayerGR8",
    "bayer_rg8": "BayerRG8",
    "bayer_gb8": "BayerGB8",
    "bayer_bg8": "BayerBG8",
    "bayer_gr10": "BayerGR10",
    "bayer_rg10": "BayerRG10",
    "bayer_gb10": "BayerGB10",
    "bayer_bg10": "BayerBG10",
    "bayer_gr10p": "BayerGR10p",
    "bayer_rg10p": "BayerRG10p",
    "bayer_gb10p": "BayerGB10p",
    "bayer_bg10p": "BayerBG10p",
    "bayer_gr12": "BayerGR12",
    "bayer_rg12": "BayerRG12",
    "bayer_gb12": "BayerGB12",
    "bayer_bg12": "BayerBG12",
    "bayer_gr12p": "BayerGR12p",
    "bayer_rg12p": "BayerRG12p",
    "bayer_gb12p": "BayerGB12p",
    "bayer_bg12p": "BayerBG12p",
}

SETTINGS_NODES = [
    "Width", "Height", "OffsetX", "OffsetY",
    "PixelFormat", "BslColorSpace", "LUTEnable",
    "ExposureTime", "BslEffectiveExposureTime", "Gain",
    "AcquisitionFrameRateEnable", "AcquisitionFrameRate",
    "AutoTargetBrightness", "AutoFunctionProfile", "ExposureAuto",
    "AutoExposureTimeLowerLimit", "AutoExposureTimeUpperLimit",
    "GainAuto", "AutoGainLowerLimit", "AutoGainUpperLimit",
    "BalanceWhiteAuto",
    "AutoFunctionROIWidth", "AutoFunctionROIHeight",
    "AutoFunctionROIOffsetX", "AutoFunctionROIOffsetY",
]

class CameraHandler:
    def __init__(self, config=None, ip=None, name="NA,NA", rig=None, output_folder="./captured_images") -> None:
        # store output folder path
        self.output_folder = output_folder
        os.makedirs(self.output_folder, exist_ok=True)

        #Mark initiation (rig is first-class; name kept for backward compat)
        rig_name = rig or self._rig_from_name(name)
        self.rig_name = rig_name
        self.name = f"{rig_name},{name.split(',')[1] if ',' in name else name}"
        self.logger = get_logger(self.name, component="camera", rig=rig_name)
        self.logger.debug(f"Initialized camera handler {self.name}", extra={"event": "camera_handler_initialized", "details": {"name": self.name, "ip": ip}})

        # Get camera and open it. Discovery failures surface from
        # CreateFirstDevice (not as a None camera), so guard the whole block.
        try:
            if ip is None: #If not IP specified get first available device
                device = pylon.TlFactory.GetInstance().CreateFirstDevice()
            else:
                device_info = pylon.DeviceInfo()
                device_info.SetPropertyValue("IpAddress", ip)
                device = pylon.TlFactory.GetInstance().CreateFirstDevice(device_info)
            self.camera = pylon.InstantCamera(device)
            self.camera.Open()
        except Exception as e:
            self.logger.error(f"Failed to open camera at IP: {ip if ip is not None else 'first available'} - {e}", extra={"event": "camera_not_found", "details": {"ip": ip, "error": str(e)}}, exc_info=True)
            raise

        self.camera_mutex = threading.Lock()
        
        # Setup config
        self.last_config = None
        if config:
            self.load_config(config)
        
        # Converter to ensure output format is allways the same
        self.converter = pylon.ImageFormatConverter()
        self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

    def convert_to_bgr(self, grab_result):
        PixelFormat = grab_result.PixelType
        return self.converter.Convert(grab_result).GetArray()

    def save_image(self, img, cam_config_name=None, light_config_name=None, full_path="", timestamp=None, metadata=None):
        """Returns (image_path, json_path_or_None)."""
        if timestamp is None:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
        rig_name = self.rig_name if hasattr(self, "rig_name") else self._rig_from_name(self.name)
        filename = f"{timestamp}_{rig_name}_{cam_config_name}_{light_config_name}.png"
        if full_path == "":
            date_folder = time.strftime("%Y-%m-%d", time.strptime(timestamp, "%Y%m%d-%H%M%S"))
            full_path = os.path.join(self.output_folder, "images", date_folder)
            os.makedirs(full_path, exist_ok=True)
        image_path = os.path.join(full_path, filename)
        if not cv2.imwrite(image_path, img):
            self.logger.error(f"Failed to save image to {image_path}", extra={"event": "image_save_failed", "details": {"path": image_path}})
            return (None, None)
        self.logger.debug(f"Image saved to {image_path}", extra={"event": "image_saved", "details": {"path": image_path}})
        json_path = None
        if metadata is not None:
            json_path = os.path.splitext(image_path)[0] + ".json"
            try:
                with open(json_path, "w") as f:
                    json.dump(metadata, f, indent=2)
                self.logger.debug(f"Metadata saved to {json_path}", extra={"event": "metadata_saved", "details": {"path": json_path}})
            except OSError as e:
                self.logger.error(f"Metadata save failed for {json_path}: {e}", extra={"event": "metadata_save_failed", "details": {"path": json_path, "error": str(e)}})
                json_path = None
        return (image_path, json_path)

    def capture_image(self, cam_config_name="default", light_config_name="NA") -> None:
        """
        Captures a single frame from the Basler camera and saves it to disk.
        If called by the user, prompts for saving or viewing the image.

        Args:
            path(str): Path to where the user will save the image 

        Raises:
            TimeoutException: If the camera fails to return a frame within 5000ms.
        """

        try:
            with self.camera_mutex:
                self.camera.StartGrabbingMax(1)
                #self.camera.StartGrabbing()

                grabResult = self.camera.RetrieveResult(
                    5000, pylon.TimeoutHandling_ThrowException
                )

            if grabResult.GrabSucceeded():
                #img = grabResult.GetArray()
                img = self.convert_to_bgr(grabResult)
                grabResult.Release()
                return img

            else:
                self.logger.error(f"Failed to grab image from camera {self.name}", extra={"event": "grab_failed", "details": {"camera": self.name}})

            grabResult.Release()

        except Exception as e:
            self.logger.error(f"Capture error on {self.name}: {e}", extra={"event": "capture_error", "details": {"camera": self.name, "error": str(e)}}, exc_info=True)
            self.try_reconnect()

    def try_reconnect(self):
        """Attempts to re-open the camera if lost."""

        try:
            self.camera = pylon.InstantCamera(
            pylon.TlFactory.GetInstance().CreateFirstDevice()
        )
            self.camera.Close()
            self.camera.Open()
            if self.last_config is not None:
                self.load_config(self.last_config)
            else:
                self.logger.warning("No previous camera config to restore after reconnect", extra={"event": "reconnect_no_config", "details": {}})
            self.logger.info(f"Camera reconnected: {self.name}", extra={"event": "camera_reconnected", "details": {"camera": self.name}})

        except Exception as e:
            self.logger.error(f"Camera reconnect failed: {e}", extra={"event": "reconnect_failed", "details": {"camera": self.name, "error": str(e)}}, exc_info=True)

    def sleep(self):
        """Puts the camera into standby mode to save power. Can be used between captures."""
        self.camera.BslSensorStandby.Execute()
        self.logger.debug(f"Camera put into standby mode: {self.name}", extra={"event": "camera_sleep", "details": {"camera": self.name}})

    def wake(self):
        """Wakes the camera from standby mode."""
        self.camera.BslSensorOn.Execute()
        self.logger.debug(f"Camera woken up: {self.name}", extra={"event": "camera_wake", "details": {"camera": self.name}})

    def close(self):
        self.camera.Close()
        self.logger.info(f"Camera stopped: {self.name}", extra={"event": "camera_stopped", "details": {"camera": self.name}})

    def load_config(self, config):
        self.last_config = config
        # Convert string to dict
        if type(config) == str:
            with open(config, "r") as file:
                self.config = yaml.safe_load(file)["DEFAULT"]["camera_config"]
        elif type(config) == dict: #Assume correct dict and continue
            self.config = config
        else:
            self.logger.error(f"Invalid config type: {type(config)}", extra={"event": "bad_config_type", "details": {"type": str(type(config))}})
            raise TypeError(f"Inappropriate config type ('{type(config)}'), must be of type 'str' or 'dict'")
        
        try:    
            # Image format settings
            self.camera.Width.Value = self.config["Width"]
            self.camera.Height.Value = self.config["Height"]
            self.camera.OffsetX.Value = self.config["OffsetX"]
            self.camera.OffsetY.Value = self.config["OffsetY"]
            self.camera.PixelFormat.Value = self.config["PixelFormat"]
            self.camera.BslColorSpace.Value = self.config["BslColorSpace"]
            self.camera.LUTEnable.Value = self.config["LUTEnable"]

            # Image Capture settings
            self.camera.ExposureTime.Value = self.config["ExposureTime"]
            self.camera.Gain.Value = self.config["Gain"]
            
            # Video settings
            if bool(self.config["AcquisitionFrameRateEnable"]):
                self.camera.AcquisitionFrameRateEnable.Value = bool(self.config["AcquisitionFrameRateEnable"])
                self.camera.AcquisitionFrameRate.Value = self.config["AcquisitionFrameRate"]

            # Auto settings
            self.camera.AutoTargetBrightness.Value = self.config["AutoTargetBrightness"]
            self.camera.ExposureAuto.Value = self.config["ExposureAuto"]
            self.camera.AutoExposureTimeLowerLimit.Value = self.config["AutoExposureTimeLowerLimit"]
            self.camera.AutoExposureTimeUpperLimit.Value = self.config["AutoExposureTimeUpperLimit"]
            self.camera.AutoFunctionProfile.Value = self.config["AutoFunction"]
            self.camera.GainAuto.Value = self.config["GainAuto"]
            self.camera.AutoGainLowerLimit.Value = self.config["AutoGainLowerLimit"]
            self.camera.AutoGainUpperLimit.Value = self.config["AutoGainUpperLimit"]
            self.camera.BalanceWhiteAuto.Value = self.config["BalanceWhiteAuto"]
            self.camera.AutoFunctionROIWidth.Value = self.config["AutoROIWidth"]
            self.camera.AutoFunctionROIHeight.Value = self.config["AutoROIHeight"]
            self.camera.AutoFunctionROIOffsetX.Value = self.config["AutoROIOffsetX"]
            self.camera.AutoFunctionROIOffsetY.Value = self.config["AutoROIOffsetY"]

            # Log completion
            self.logger.debug(f"Camera settings updated: {self.name}", extra={"event": "camera_settings_updated", "details": {"camera": self.name}})


        except Exception as e:
            self.logger.error(f"Camera settings update failed: {e}", extra={"event": "settings_update_error", "details": {"camera": self.name, "error": str(e)}}, exc_info=True)
            #self.try_reconnect()

    def get_camera_meta(self) -> dict:
        meta = {"settings_actual": {}}
        def _read(node_name):
            try:
                value = getattr(self.camera, node_name).Value
                try:
                    json.dumps(value)
                    return value
                except (TypeError, ValueError):
                    return str(value)
            except Exception:
                return None
        for n in SETTINGS_NODES:
            meta["settings_actual"][n] = _read(n)
        return meta

    @staticmethod
    def _rig_from_name(name: str) -> str:
        return name.split(",")[0] if "," in name else name

    @staticmethod
    def run_in_thread(func, *args) -> threading.Thread:
        """General worker function to run a function in a thread"""

        thread = threading.Thread(target=func, args=args, daemon=True)
        thread.start()
        return thread
