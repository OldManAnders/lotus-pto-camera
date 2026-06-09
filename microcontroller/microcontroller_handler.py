import requests
import threading
import time
import logging
from typing import Optional
from utils.logging_config import get_logger

class MicrocontrollerHandler:
    def __init__(self, ip, port=80, timeout=5, reconnect_interval=5, heartbeat_interval=10, name="NA, NA", verbose=False) -> None:
        self.name = name
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.reconnect_interval = reconnect_interval
        self.heartbeat_interval = heartbeat_interval
        self.verbose = verbose
        # _connected/explicit connect/disconnect are no longer required;
        # we use HTTP requests on demand and run a lightweight ping loop.
        self._last_ping_ok = False
        self._stop_event = threading.Event()
        self._heartbeat_thread = None

        self.logger = get_logger(__name__, component=self.name.split(",")[0])
        self.logger.debug("", extra={"event": "microcontroller_initialized", "details": f"Initialized microcontroller: {self.name}, IP: {self.ip}, Port: {self.port}"})
    # -------------------------------------------------------------------------
    # Helpers (PRIVATE)
    # -------------------------------------------------------------------------
    @property
    def _base_url(self) -> str:
        return f"http://{self.ip}:{self.port}"

    def _get(self, path: str) -> Optional[dict]:
        try:
            res = requests.get(self._base_url + path, timeout=self.timeout)
            res.raise_for_status()
            return res.json()
        except requests.RequestException as e:
            self.logger.error("", extra={"event": "http_get_failed", "details": f"{str(e)}"})
            # mark last ping as failed; heartbeat loop will report
            self._last_ping_ok = False
            return {"success": False, "error": str(e)}

    def _post(self, path: str, payload: dict, timeout=None) -> Optional[dict]:
        try:
            res = requests.post(
                self._base_url + path,
                json=payload,
                timeout=self.timeout if timeout is None else timeout
            )
            res.raise_for_status()
            return res.json()
        except requests.RequestException as e:
            self.logger.error("", extra={"event": "http_post_failed", "details": f"{str(e)}"})
            # mark last ping as failed; heartbeat loop will report
            self._last_ping_ok = False
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------------------
    # Heartbeat functionality (PRIVATE)
    # -------------------------------------------------------------------------
    def _heartbeat_loop(self) -> None:
        while not self._stop_event.is_set():
            data = self._get("/ping")
            if data and data.get("type") == "pong":
                if not self._last_ping_ok:
                    self.logger.debug("", extra={"event": "ping", "details": "success"})
                self._last_ping_ok = True
            else:
                if self._last_ping_ok:
                    self.logger.warning("", extra={"event": "ping", "details": "failed"})
                self._last_ping_ok = False
            time.sleep(self.heartbeat_interval)

    # -------------------------------------------------------------------------
    # API (Public)
    # -------------------------------------------------------------------------
    def start_heartbeat(self) -> None:
        """
        Start a background thread that periodically polls connectivity to the device with a "ping -> pong" request
        """
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._stop_event.clear()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        self._stop_event.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1)
        self._last_ping_ok = False

    def is_alive(self) -> bool:
        return self._last_ping_ok

    def set_values(self, keyvals: dict) -> Optional[dict]:
        """POST /set — accepts keys like 'light1'; converts to device format."""
        # No persistent connection required; try sending regardless
        payload = {}
        for k, v in keyvals.items():
            payload[k] = v

        reply = self._post("/set", payload)
        if reply and not reply.get("success"):
            self.logger.error("", extra={"event": "set_values_error", "details": f"{reply.get('error')}"})
        return reply

    def get_values(self, keys: list) -> Optional[dict]:
        """POST /get — accepts keys like 'light1' and returns normalized data.

        Returns: {'success': True, 'data': {<requested_key>: value, ...}}
        """
        # No persistent connection required; try sending regardless

        # Map requested keys to device get-keys
        requested = list(keys)

        reply = self._post("/get", requested)
        if not reply:
            return None
        if not reply.get("success"):
            self.logger.error("", extra={"event": "get_values_error", "details": f"{reply.get('error')}"})
            return reply

        data = reply.get("data", {})
        # Map device-returned keys back to the caller's requested keys
        mapped = {}
        for orig, dk in zip(requested, requested):
            if dk in data:
                mapped[orig] = data[dk]
            else:
                mapped[orig] = None

        return {"success": True, "data": mapped}

    def send_command(self, cmd: str, params: dict = None) -> Optional[dict]:
        """POST /cmd  — e.g. send_command('lightOn')"""
        # No persistent connection required; try sending regardless
        body = {"cmd": cmd}
        if params:
            body["params"] = params

        # Basic validation for known commands
        if cmd == "setAll":
            if not params or "value" not in params:
                self.logger.error("", extra={"event": "send_command_error", "details": "missing params or value"})
                return {"success": False, "error": "missing params: value"}

        if cmd == "wipe": # Allow for the wiper to do its full sweep
            reply = self._post("/cmd", body, timeout=15)
        else:
            reply = self._post("/cmd", body)

        if reply and not reply.get("success"):
            self.logger.error("", extra={"event": "send_command_error", "details": f"{reply.get('error')}"})
        return reply

    def status(self) -> Optional[dict]:
        """GET /status  — returns ip, ssid, rssi"""
        return self._get("/status")