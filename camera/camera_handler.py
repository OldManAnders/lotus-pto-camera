from pypylon import pylon
import cv2, time, threading, os, yaml, logging
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

class CameraHandler:
    def __init__(self, config=None, ip=None, name="NA, NA", output_folder="./captured_images") -> None:
        # store output folder path
        self.output_folder = output_folder
        os.makedirs(self.output_folder, exist_ok=True)

        #Mark initiation
        self.name = name
        self.logger = get_logger(name, component=self.name.split(",")[0])
        self.logger.debug("", extra={"event": "camera_handler_initialized", "details": f"{name}"})

        # Get camera
        if ip is None: #If not IP specified get first available device
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        else:
            device_info = pylon.DeviceInfo()
            device_info.SetPropertyValue("IpAddress", ip)
            tl_factory = pylon.TlFactory.GetInstance()
            device = tl_factory.CreateFirstDevice(device_info)
            self.camera = pylon.InstantCamera(device)
            if self.camera is None:
                self.logger.error("", extra={"event": "camera_not_found", "details": f"Camera not found at IP: {ip}"})
                self.close()

        # Open cammera
        self.camera.Open()
        self.camera_mutex = threading.Lock()
        
        # Setup config
        if config:
            self.load_config(config)
        
        # Converter to ensure output format is allways the same
        self.converter = pylon.ImageFormatConverter()
        self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

    def convert_to_bgr(self, grab_result):
        PixelFormat = grab_result.PixelType
        return self.converter.Convert(grab_result).GetArray()

    def save_image(self, img, cam_config_name=None,light_config_name=None):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        rig_name = self.name.split(",")[0]
        filename = f"{timestamp}_{rig_name}_{cam_config_name}_{light_config_name}.png"
        full_path = os.path.join(self.output_folder, filename)
        cv2.imwrite(full_path, img)
        self.logger.debug("", extra={"event": "image_saved", "details": f"Image saved to {full_path}"})

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

                grabResult = self.camera.RetrieveResult(
                    5000, pylon.TimeoutHandling_ThrowException
                )

            if grabResult.GrabSucceeded():
                img = self.convert_to_bgr(grabResult)
                grabResult.Release()
                return img

            else:
                self.logger.error("", extra={"event": "grab_failed", "details": f"Failed to grab image from camera {self.name}"})

            grabResult.Release()

        except Exception as e:
            self.logger.error("", extra={"event": "capture_error", "details": f"{str(e)}"})
            self.try_reconnect()

    def try_reconnect(self):
        """Attempts to re-open the camera if lost."""

        try:
            self.camera = pylon.InstantCamera(
            pylon.TlFactory.GetInstance().CreateFirstDevice()
        )
            self.camera.Close()
            self.camera.Open()
            self.load_config(self.last_config)
            self.logger.info("", extra={"event": "camera_reconnected", "details": f"Camera reconnected: {self.name}"})

        except Exception as e:
            self.logger.error("", extra={"event": "reconnect_failed", "details": f"{str(e)}"})

    def sleep(self):
        """Puts the camera into standby mode to save power. Can be used between captures."""
        self.camera.BslSensorStandby.Execute()
        self.logger.debug("", extra={"event": "camera_sleep", "details": f"Camera put into standby mode: {self.name}"})

    def wake(self):
        """Wakes the camera from standby mode."""
        self.camera.BslSensorOn.Execute()
        self.logger.debug("", extra={"event": "camera_wake", "details": f"Camera woken up: {self.name}"})

    def close(self):
        self.camera.Close()
        self.logger.info("", extra={"event": "camera_stopped", "details": f"Camera stopped: {self.name}"})

    def load_config(self, config):
        self.last_config = config
        # Convert string to dict
        if type(config) == str:
            with open(config, "r") as file:
                self.config = yaml.safe_load(file)["DEFAULT"]["camera_config"]
        elif type(config) == dict: #Assume correct dict and continue
            self.config = config
        else:
            self.logger.error("", extra={"event": "bad_config_type", "details": f"Invalid config type: {type(config)}"})
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

            # Log completion
            self.logger.debug("", extra={"event": "camera_settings_updated", "details": f"Camera settings updated: {self.name}"})


        except Exception as e:
            self.logger.error("", extra={"event": "settings_update_error", "details": f"{str(e)}"})
            #self.try_reconnect()

    @staticmethod
    def run_in_thread(func, *args) -> threading.Thread:
        """General worker function to run a function in a thread"""

        thread = threading.Thread(target=func, args=args, daemon=True)
        thread.start()
        return thread
