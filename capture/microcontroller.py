"""ESP32-C3 HTTP control adapter for the LOTUS-PTO rig.

The microcontroller drives the three rig LEDs and the lens wiper, and reports
device status over a small HTTP API on the rig network. Every request method is
best-effort: ``requests.RequestException`` transport failures are logged and
surface as ``None`` rather than being raised.
"""
from typing import Any, Dict, Optional
import requests
from utils.logging_config import get_logger


class MicrocontrollerHandler:
    """HTTP control adapter for the ESP32-C3 rig microcontroller.

    Drives the rig LEDs and lens wiper, and reports device status over a small
    HTTP API. Request methods return ``None`` on transport failure instead of
    raising.

    Attributes:
        rig: Rig identifier used for logging context.
        ip: Controller IP address.
        port: Controller HTTP port.
        timeout: Default request timeout in seconds.
        verbose: Reserved verbosity flag (currently unused).
        logger: Logger adapter carrying component/rig context.
    """

    def __init__(self, ip: str, port: int = 80, rig: str = "",
                 timeout: float = 5, verbose: bool = False) -> None:
        """Initialize the handler and build its logger.

        Args:
            ip: Controller IP address.
            port: Controller HTTP port.
            rig: Rig identifier used for logging context.
            timeout: Default request timeout in seconds.
            verbose: Reserved verbosity flag (currently unused).
        """
        self.rig = rig
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.verbose = verbose
        self._last_ping_ok = False
        self.logger = get_logger(__name__, component="microcontroller", rig=self.rig)
        self.logger.debug(f"Initialized microcontroller: {self.rig}, IP: {self.ip}, Port: {self.port}", extra={"event": "microcontroller_initialized", "details": {"rig": self.rig, "ip": self.ip, "port": self.port}})

    @property
    def _base_url(self) -> str:
        """Return the controller base URL.

        Returns:
            Base URL such as ``http://192.0.2.10:80`` with no trailing slash.
        """
        return f"http://{self.ip}:{self.port}"

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None,
             timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Issue an HTTP GET and decode the JSON response.

        Args:
            path: Endpoint path, for example ``/status``.
            params: Optional query parameters.
            timeout: Per-request timeout in seconds; falls back to
                ``self.timeout`` when ``None``.

        Returns:
            Decoded JSON body, or ``None`` if the request failed.
        """
        try:
            res = requests.get(
                self._base_url + path,
                params=params,
                timeout=self.timeout if timeout is None else timeout
            )
            res.raise_for_status()
            detail = " ".join([f"{k}:{v}" for k, v in (params or {}).items()]) if params else path
            self.logger.debug(f"GET {path} {detail}", extra={"event": "get_request", "details": {"path": path, "params": params or {}}})
            return res.json()
        except requests.RequestException as e:
            self.logger.error(f"GET {path} failed: {e}", extra={"event": "http_get_failed", "details": {"path": path, "error": str(e)}})
            self._last_ping_ok = False
            return None

    def _post(self, path: str, json: Optional[Dict[str, Any]] = None,
              timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Issue an HTTP POST with a JSON body and decode the response.

        Args:
            path: Endpoint path, for example ``/leds``.
            json: Optional JSON-serializable request body.
            timeout: Per-request timeout in seconds; falls back to
                ``self.timeout`` when ``None``.

        Returns:
            Decoded JSON body, or ``None`` if the request failed.
        """
        try:
            res = requests.post(
                self._base_url + path,
                json=json,
                timeout=self.timeout if timeout is None else timeout
            )
            res.raise_for_status()
            return res.json()
        except requests.RequestException as e:
            self.logger.error(f"POST {path} failed: {e}", extra={"event": "http_post_failed", "details": {"path": path, "error": str(e)}})
            self._last_ping_ok = False
            return None

    def is_alive(self) -> bool:
        """Ping the controller and report whether it answered.

        Issues ``GET /ping`` and treats a ``pong`` payload as healthy.

        Returns:
            ``True`` if the controller replied with a ``pong`` payload,
            otherwise ``False``. Never raises.
        """
        data = self._get("/ping")
        if data and data.get("type") == "pong":
            self.logger.debug("Ping success", extra={"event": "ping", "details": {"result": "success"}})
            self._last_ping_ok = True
            return True
        else:
            self.logger.error("Ping failed", extra={"event": "ping", "details": {"result": "failed"}})
            self._last_ping_ok = False
            return False

    def set_leds(self, led1: Optional[int] = None,
                 led2: Optional[int] = None,
                 led3: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Set one or more LED brightness values.

        Each supplied value is clamped to the 0-255 range; omitted LEDs are left
        untouched. At least one LED must be supplied.

        Args:
            led1: Brightness for LED 1, clamped to 0-255.
            led2: Brightness for LED 2, clamped to 0-255.
            led3: Brightness for LED 3, clamped to 0-255.

        Returns:
            Decoded JSON reply from ``POST /leds``, or ``None`` when no LED was
            supplied or the request failed.
        """
        payload = {}
        if led1 is not None:
            payload["led1"] = max(0, min(255, int(led1)))
        if led2 is not None:
            payload["led2"] = max(0, min(255, int(led2)))
        if led3 is not None:
            payload["led3"] = max(0, min(255, int(led3)))

        if not payload:
            self.logger.warning("No LED values specified", extra={"event": "set_leds_error", "details": {}})
            return None

        reply = self._post("/leds", json=payload)
        if reply is None:
            self.logger.error("LED set request failed", extra={"event": "set_leds_error", "details": {"payload": payload}})
            return None
        return reply

    def get_status(self) -> Optional[Dict[str, Any]]:
        """Fetch the controller status.

        Returns:
            Decoded JSON body from ``GET /status``, or ``None`` on failure.
        """
        reply = self._get("/status")
        if reply is None:
            return None
        return reply

    def wipe(self) -> Optional[Dict[str, Any]]:
        """Trigger a lens wipe.

        Blocks for roughly four seconds while the wiper runs, using a 30-second
        request timeout.

        Returns:
            Decoded JSON reply from ``POST /wiper``, or ``None`` on failure.
        """
        reply = self._post("/wiper", timeout=30)
        if reply is None:
            self.logger.error("Wiper request failed", extra={"event": "wipe_error", "details": {}})
        return reply

    def reset_all(self) -> Optional[Dict[str, Any]]:
        """Reset the controller to its default state.

        Returns:
            Decoded JSON reply from ``POST /reset``, or ``None`` on failure.
        """
        reply = self._post("/reset")
        if reply is None:
            self.logger.error("Reset request failed", extra={"event": "reset_error", "details": {}})
            return None
        return reply
