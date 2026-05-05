from pypylon import pylon
import cv2, time, threading, os, logging, yaml

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

class CameraControl:
    def __init__(self, config=None, ip=None, interval=None, logger=None, name="noname", output_folder="./captured_images", log_level=logging.INFO) -> None:
        #Instansiate logger or accept passed logger
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)

        # store output folder path
        self.output_folder = os.path.join(output_folder, "images/")
        os.makedirs(self.output_folder, exist_ok=True)

        #Mark initiation
        self.logger.debug(f"Initialized Camera Controller {name}")
        logging.basicConfig(
            level=log_level,
            format=",[%(levelname)s],[%(name)s],%(message)s" #Leading comma as Linux Timestamps the stdout
        )

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
                self.logger.error(f"No camera found at ip: {ip}")
                self.close()

        # Open cammera
        self.camera.Open()
        self.camera_mutex = threading.Lock()
        self.name = name

        # Setup config
        if config:
            self.load_config(config)

        if interval is not None:
            self.run_in_thread(self.auto_pic_snapper, interval)

    def convert_to_bgr(self, grab_result):
        PixelFormat = grab_result.PixelType
        return self.converter.Convert(grab_result).GetArray()

    def snap_pic(self, cam_config_name="factory", light_config_name="NA") -> None:
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
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                filename = f"{timestamp}_{self.name}_{cam_config_name}_{light_config_name}.png"
                full_path = os.path.join(self.output_folder, filename)
                cv2.imwrite(full_path, img)
                self.logger.debug(f"Auto saved image as {full_path}")

            else:
                self.logger.error("Failed to grab image.")

            grabResult.Release()

        except Exception as e:
            self.logger.error(f"Error capturing image: {e}")
            self.try_reconnect()

    def stream(self) -> None:
        """
        Starts a live video stream from the Basler camera using OpenCV.

        Raises:
            TimeoutException: If the camera fails to return a frame within 5000ms.
        """

        try:
            with self.camera_mutex:
                self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

                # Converter til OpenCV format (fra Basler format til BGR/RGB) (Skal kun bruges ved bayer rg 8)
                #converter = pylon.ImageFormatConverter()
                #converter.OutputPixelFormat = pylon.PixelType_BGR8packed
                #converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

                print("Live view kører... Tryk på 'q' for at afslutte.")
                self.logger.debug("Live view started.")

                prev_time = time.time()

                while self.camera.IsGrabbing():
                    grabResult = self.camera.RetrieveResult(
                        5000, pylon.TimeoutHandling_ThrowException
                    )

                    if grabResult.GrabSucceeded():
                        # Konverter billedet til et format OpenCV kan forstå (numpy array)
                        #image = converter.Convert(grabResult)
                        #frame = image.GetArray()

                        frame = grabResult.Array

                        # Calculate FPS
                        current_time = time.time()
                        fps_actual = 1 / (current_time - prev_time)
                        prev_time = current_time

                        # Overlay FPS text on the image
                        cv2.putText(
                            frame,
                            f"FPS: {fps_actual:.1f}",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            (0, 255, 0),
                            2,
                        )

                        # Vis billedet i et vindue
                        cv2.imshow("Basler ace 2 Live View", frame)

                        # Stop hvis brugeren trykker på 'q'
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            self.logger.debug("Live view stopped by user.")
                            break
                    else:
                        self.logger.error("Failed to grab image (stream).")

                    grabResult.Release()

                # Ryd op
                self.camera.StopGrabbing()

            cv2.destroyAllWindows()
        
        except Exception as e:
            self.logger.error(f"Error during live stream: {e}")
            self.try_reconnect()

    def auto_pic_snapper(self, interval: int) -> None:
        """
        Automatically takes pictures at specified intervals.

        Args:
            interval (int): Time in seconds between each picture.

        Raises:
            TimeoutException: If the camera fails to return a frame within 5000ms.
        """

        self.logger.debug(f"Auto picture snapper started with interval {interval} seconds.")
        
        while True:
            self.snap_pic()
            self.logger.debug(f"Captured image at: {time.strftime("%Y%m%d-%H%M%S")}")
            time.sleep(interval)

    def manual_capture(self):
        try:
            with self.camera_mutex:
                self.camera.StartGrabbingMax(1)

                grabResult = self.camera.RetrieveResult(
                    5000, pylon.TimeoutHandling_ThrowException
                )

            if grabResult.GrabSucceeded():
                img = grabResult.Array
                while True:
                    user_input = input(
                        "Press s to save the image, v to view or q to quit: "
                    )

                    if user_input == "s":
                        timestamp = time.strftime("%Y%m%d-%H%M%S")
                        filename = f"{timestamp}_{self.name}_NA_NA.png"
                        full_path = os.path.join(self.output_folder, filename)
                        cv2.imwrite(full_path, img)
                        self.logger.debug(f"User saved image as {full_path}")

                    elif user_input == "v":
                        cv2.imshow("Captured Image", img)
                        cv2.waitKey(0)
                        cv2.destroyAllWindows()

                    elif user_input == "q":
                        break
            
                    else:
                        print("Invalid input. Please try again.")
            else:
                self.logger.error(f"Failed to grab image")

        except Exception as e:
            self.logger.error(f"Error capturing image: {e}")
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
            self.logger.info("Camera reconnected successfully.")

        except Exception as e:
            self.logger.error(f"Reconnection failed: {e}")

    def close(self):
        if hasattr(self, "camera") and self.camera.IsOpen():
            self.camera.Close()
        self.logger.info("Stopped")

    def load_config(self, config):
        self.last_config = config
        # Convert string to dict
        if type(config) == str:
            with open(config, "r") as file:
                self.config = yaml.safe_load(file)["DEFAULT"]["camera_config"]
        elif type(config) == dict: #Assume correct dict and continue
            self.config = config
        else:
            self.logger.error(f"Inappropriate config type ('{type(config)}')")
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
            self.logger.debug("Camera settings updated.")


        except Exception as e:
            self.logger.error(f"Error updating settings: {e}")
            #self.try_reconnect()

    @staticmethod
    def run_in_thread(func, *args) -> threading.Thread:
        """General worker function to run a function in a thread"""

        thread = threading.Thread(target=func, args=args, daemon=True)
        thread.start()
        return thread

if __name__ == "__main__":
    camera_control = CameraControl("./config.yaml")

    try:
        while True:
            user_input = input(
                "Enter 'p' to take a picture, 's' to start live view, 'u' to update settings, or 'q' to quit: "
            )
            if user_input == "p":
                camera_control.manual_capture()
            elif user_input == "s":
                camera_control.stream()
            elif user_input == "u":
                camera_control.load_config("./config.yaml")
            elif user_input == "q":
                break
            else:
                print("Invalid input. Please try again.")

    finally:
        camera_control.close()
