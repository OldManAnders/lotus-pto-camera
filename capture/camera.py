"""pypylon-based adapter for the Basler camera on a LOTUS-PTO rig.

Wraps a pypylon ``InstantCamera`` with a small, rig-aware surface: opening and
reconnecting the device, applying named camera presets, capturing frames as BGR
arrays, and reading device state for the capture metadata sidecar.
"""
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
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
    """Adapter around a single Basler camera.

    Owns the pypylon device, applies named camera presets, captures frames as
    BGR arrays, and exposes device state for the metadata sidecar. A mutex
    serializes grabs against the shared pylon camera object.

    Attributes:
        output_folder: Root directory for saved images.
        ip: Camera IP address.
        rig: Rig identifier used for logging context.
        logger: Logger adapter carrying component/rig context.
        camera: Open pylon ``InstantCamera`` instance.
        camera_mutex: Lock serializing grab operations.
        last_config: Most recently applied preset, used on reconnect.
        config: Preset currently applied to the device.
        converter: pylon image format converter targeting BGR8 packed output.
    """

    def __init__(self, config: Optional[Any] = None, ip: Optional[str] = None,
                 rig: str = "", output_folder: str = "./captured_images") -> None:
        """Open the camera and prepare the BGR converter.

        When ``ip`` is ``None`` the first available device is opened. The output
        folder is created if missing, and ``config`` (when supplied) is applied
        via ``load_config``.

        Args:
            config: Optional preset as a dict or a YAML file path.
            ip: Camera IP address; ``None`` selects the first available device.
            rig: Rig identifier used for logging context.
            output_folder: Directory where captured images are written.

        Raises:
            Exception: If the camera cannot be opened.
        """
        # store output folder path
        self.output_folder = output_folder
        os.makedirs(self.output_folder, exist_ok=True)
        self.ip = ip
        self.rig = rig
        self.logger = get_logger(__name__, component="camera", rig=self.rig)

        try:
            if self.ip is None: #If not IP specified get first available device
                device = pylon.TlFactory.GetInstance().CreateFirstDevice()
                self.camera = pylon.InstantCamera(device)
                self.camera.Open()
                self.ip = self.camera.GetDeviceInfo().GetIpAddress()
                self.logger.info(f"No IP specified for {self.rig}, using first available camera", extra={"event": "camera_first_available", "details": {"rig": self.rig, "ip": self.ip}})
            else:
                device_info = pylon.DeviceInfo()
                device_info.SetPropertyValue("IpAddress", ip)
                device = pylon.TlFactory.GetInstance().CreateFirstDevice(device_info)
                self.camera = pylon.InstantCamera(device)
                self.camera.Open()
                self.ip = self.camera.GetDeviceInfo().GetIpAddress()
            self.logger.debug(f"Initialized camera handler {self.rig}", extra={"event": "camera_handler_initialized", "details": {"rig": self.rig, "ip": self.ip}})
        except Exception as e:
            self.logger.error(f"Failed to open camera at IP: {ip if ip is not None else f'first available - {self.ip}'} - {e}", extra={"event": "camera_not_found", "details": {"ip": ip, "error": str(e)}}, exc_info=True)
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

    def convert_to_bgr(self, grab_result: Any) -> np.ndarray:
        """Convert a pylon grab result into a BGR array.

        Args:
            grab_result: pylon grab result to convert.

        Returns:
            BGR image as a NumPy array.
        """
        PixelFormat = grab_result.PixelType
        return self.converter.Convert(grab_result).GetArray()

    def save_image(self, img: np.ndarray, cam_config_name: Optional[str] = None,
                   light_config_name: Optional[str] = None, full_path: str = "",
                   timestamp: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None
                   ) -> Tuple[Optional[str], Optional[str]]:
        """Write a captured frame and optional sidecar metadata to disk.

        When ``full_path`` is empty the image is written under
        ``<output_folder>/images/<YYYY-MM-DD>/`` derived from ``timestamp``. A
        JSON sidecar is written next to the image when ``metadata`` is given.

        Args:
            img: BGR image to save.
            cam_config_name: Camera preset name used in the filename.
            light_config_name: Lighting preset name used in the filename.
            full_path: Destination directory; derived from ``timestamp`` when
                empty.
            timestamp: Capture timestamp in ``%Y%m%d-%H%M%S`` form; defaults to
                the current time.
            metadata: Optional metadata mapping written as a ``.json`` sidecar.

        Returns:
            Tuple ``(image_path, json_path)``. ``image_path`` is ``None`` when
            the image could not be written; ``json_path`` is ``None`` when no
            metadata was supplied or the sidecar write failed.
        """
        if timestamp is None:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}_{self.rig}_{cam_config_name}_{light_config_name}.png"
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

    def capture_image(self, cam_config_name: str = "default",
                      light_config_name: str = "default") -> Optional[np.ndarray]:
        """Grab a single frame and return it as a BGR array.

        This method does not save the frame to disk and does not prompt the
        user; the caller owns persistence. It waits up to 5000 ms for a frame
        via ``RetrieveResult``. On a grab failure or any pylon error the failure
        is logged, ``try_reconnect`` is invoked, and ``None`` is returned.

        Args:
            cam_config_name: Camera preset name, accepted for call-site
                uniformity with the rest of the pipeline (unused by the grab).
            light_config_name: Lighting preset name, accepted for call-site
                uniformity with the rest of the pipeline (unused by the grab).

        Returns:
            BGR image as a NumPy array, or ``None`` if the grab failed.
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
                self.logger.error(f"Failed to grab image from camera {self.rig}", extra={"event": "grab_failed", "details": {"rig": self.rig}})

            grabResult.Release()

        except Exception as e:
            self.logger.error(f"Capture error on {self.rig}: {e}", extra={"event": "capture_error", "details": {"rig": self.rig, "error": str(e)}}, exc_info=True)
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
            self.logger.info(f"Camera reconnected: {self.rig}", extra={"event": "camera_reconnected", "details": {"rig": self.rig}})

        except Exception as e:
            self.logger.error(f"Camera reconnect failed: {e}", extra={"event": "reconnect_failed", "details": {"rig": self.rig, "error": str(e)}}, exc_info=True)

    def sleep(self) -> None:
        """Put the sensor into standby to save power between captures."""
        self.camera.BslSensorStandby.Execute()
        self.logger.debug(f"Camera put into standby mode: {self.rig}", extra={"event": "camera_sleep", "details": {"rig": self.rig}})

    def wake(self) -> None:
        """Wake the sensor from standby."""
        self.camera.BslSensorOn.Execute()
        self.logger.debug(f"Camera woken up: {self.rig}", extra={"event": "camera_wake", "details": {"rig": self.rig}})

    def close(self) -> None:
        """Close the camera connection."""
        self.camera.Close()
        self.logger.info(f"Camera stopped: {self.rig}", extra={"event": "camera_stopped", "details": {"rig": self.rig}})

    def load_config(self, config: Any) -> None:
        """Apply a camera preset to the device.

        Accepts either a preset dict or a path to a YAML file holding one under
        ``DEFAULT.camera_config``. The preset is remembered so
        ``try_reconnect`` can restore it. Errors raised while writing individual
        device nodes are logged but not propagated.

        Args:
            config: Preset mapping or path to a YAML preset file.

        Raises:
            TypeError: If ``config`` is neither a ``str`` nor a ``dict``.
        """
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
            self.logger.debug(f"Camera settings updated: {self.rig}", extra={"event": "camera_settings_updated", "details": {"rig": self.rig}})


        except Exception as e:
            self.logger.error(f"Camera settings update failed: {e}", extra={"event": "settings_update_error", "details": {"rig": self.rig, "error": str(e)}}, exc_info=True)
            #self.try_reconnect()

    def read_temperature(self) -> Optional[float]:
        """Read the camera's internal temperature."""
        try:
            return self.camera.DeviceTemperature.Value
        except Exception:
            return None

    def get_camera_meta(self) -> Dict[str, Any]:
        """Collect the current values of the tracked camera settings nodes.

        Returns:
            Mapping with a single ``settings_actual`` key whose value maps every
            node in ``SETTINGS_NODES`` to its current value, stringified when
            not JSON-serializable, or ``None`` when the node is unreadable.
        """
        meta = {"settings_actual": {}}
        def _read(node_name: str) -> Any:
            """Read a device node, stringifying non-JSON values."""
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
    def run_in_thread(func: Callable[..., Any], *args: Any) -> threading.Thread:
        """Start a callable in a daemon thread.

        Args:
            func: Callable to execute.
            *args: Positional arguments forwarded to ``func``.

        Returns:
            The started daemon thread.
        """

        thread = threading.Thread(target=func, args=args, daemon=True)
        thread.start()
        return thread
