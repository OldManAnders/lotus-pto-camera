from typing import Optional
import requests
from utils.logging_config import get_logger

class MicrocontrollerHandler:
    def __init__(self, ip, port=80, timeout=5, heartbeat_interval=10, name="NA,NA", verbose=False) -> None:
        self.name = name
        self.ip = ip
        self.port = port
        self.timeout = timeout
        
        self.heartbeat_interval = heartbeat_interval
        self.verbose = verbose
        self._last_ping_ok = False
        self.logger = get_logger(__name__, component=self.name.split(",")[0])
        self.logger.debug("", extra={"event": "microcontroller_initialized", "details": f"Initialized microcontroller: {self.name}, IP: {self.ip}, Port: {self.port}"})

    # -------------------------------------------------------------------------
    # Helpers (PRIVATE)
    # -------------------------------------------------------------------------
    @property
    def _base_url(self) -> str:
        return f"http://{self.ip}:{self.port}"

    def _get(self, path: str, params: dict = None, timeout=None) -> Optional[dict]:
        try:
            res = requests.get(
                self._base_url + path,
                params=params,
                timeout=self.timeout if timeout is None else timeout
            )
            res.raise_for_status()
            self.logger.debug("", extra={"event": "get_request", "details": f"Called get with {" ".join([f"{k}:{v}" for k,v in params.items()])}"})            
            return res.json()
        except requests.RequestException as e:
            self.logger.error("", extra={"event": "http_get_failed", "details": f"{str(e)}"})
            self._last_ping_ok = False
            return None

    def _post(self, path: str, json: dict = None, timeout=None) -> Optional[dict]:
        try:
            res = requests.post(
                self._base_url + path,
                json=json,
                timeout=self.timeout if timeout is None else timeout
            )
            res.raise_for_status()
            return res.json()
        except requests.RequestException as e:
            self.logger.error("", extra={"event": "http_post_failed", "details": f"{str(e)}"})
            self._last_ping_ok = False
            return None

    # -------------------------------------------------------------------------
    # Device control (PUBLIC)
    # -------------------------------------------------------------------------
    def is_alive(self) -> bool:
        data = self._get("/ping")
        if data and data.get("type") == "pong":
            self.logger.debug("", extra={"event": "ping", "details": "success"})
            self._last_ping_ok = True
            return True
        else:
            self.logger.error("", extra={"event": "ping", "details": "Failed"})
            self._last_ping_ok = False
            return False

    def set_leds(self, led1: int = None, led2: int = None, led3: int = None) -> Optional[dict]:
        payload = {}
        if led1 is not None:
            payload["led1"] = max(0, min(255, int(led1)))
        if led2 is not None:
            payload["led2"] = max(0, min(255, int(led2)))
        if led3 is not None:
            payload["led3"] = max(0, min(255, int(led3)))

        if not payload:
            self.logger.warning("", extra={"event": "set_leds_error", "details": "no LED values specified"})
            return None

        reply = self._post("/leds", json=payload)
        if reply is None:
            self.logger.error("", extra={"event": "set_leds_error", "details": "request failed"})
            return None
        return reply

    def get_status(self) -> Optional[dict]:
        reply = self._get("/status")
        if reply is None:
            return None
        return reply

    def wipe(self) -> Optional[dict]:
        reply = self._post("/wiper", timeout=30)
        if reply is None:
            self.logger.error("", extra={"event": "wipe_error", "details": "request failed"})
        return reply

    def reset_all(self) -> Optional[dict]:
        reply = self._post("/reset")
        if reply is None:
            self.logger.error("", extra={"event": "reset_error", "details": "request failed"})
            return None
        return reply