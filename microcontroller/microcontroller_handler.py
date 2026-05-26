import requests
import threading
import time
import logging
from typing import Optional

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

        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized Microcontroller Handler '{name}' for {ip}:{port}'")
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
            self.logger.error(f"GET {path} failed: {e}")
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
            self.logger.error(f"POST {path} failed: {e}")
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
                    self.logger.debug("Ping successful")
                self._last_ping_ok = True
            else:
                if self._last_ping_ok:
                    self.logger.warning("Ping failed")
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
        """POST /set — accepts keys like 'light.1'; converts to device format."""
        # No persistent connection required; try sending regardless
        payload = {}
        for k, v in keyvals.items():
            payload[k] = v

        reply = self._post("/set", payload)
        if reply and not reply.get("success"):
            self.logger.error(f"set_values error: {reply.get('error')}")
        return reply

    def get_values(self, keys: list) -> Optional[dict]:
        """POST /get — accepts keys like 'light.1' and returns normalized data.

        Returns: {'success': True, 'data': {<requested_key>: value, ...}}
        """
        # No persistent connection required; try sending regardless

        # Map requested keys to device get-keys
        requested = list(keys)

        reply = self._post("/get", requested)
        if not reply:
            return None
        if not reply.get("success"):
            self.logger.error(f"get_values error: {reply.get('error')}")
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
                self.logger.error("send_command error: setAll requires params {'value': <0-255>}" )
                return {"success": False, "error": "missing params: value"}

        if cmd == "wipe": # Allow for the wiper to do its full sweep
            reply = self._post("/cmd", body, timeout=15)
        else:
            reply = self._post("/cmd", body)

        if reply and not reply.get("success"):
            self.logger.error(f"send_command error: {reply.get('error')}")
        return reply

    def status(self) -> Optional[dict]:
        """GET /status  — returns ip, ssid, rssi"""
        return self._get("/status")
# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    ip = input("mc IP address: ").strip()
    mc =MicrocontrollerHandler(ip, port=80, verbose=True)
    try:
        print("Starting heartbeat...")
        mc.start_heartbeat()

        print("Checking connection")
        dots=0
        while not mc.is_alive():
            dots = (dots + 1) % 6
            print(f"mc unreachable, waiting{'.' * dots}\r", end="")
            time.sleep(1)

        print("Ready. Commands:")
        print("  set <key> <value>   — e.g.  set light.1 128  (or set led0 128)")
        print("  get <key>           — e.g.  get light.1  (or get led0)")
        print("  cmd <command> [arg] — e.g.  cmd lightOn  OR  cmd setAll 200")
        print("  status")
        print("  quit")

        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break

            if not line:
                continue

            parts = line.split()
            action = parts[0].lower()

            if action in ("quit", "exit"):
                break
            elif action == "set" and len(parts) == 3:
                key, val = parts[1], parts[2]
                # Try to convert to int, fall back to string
                try:
                    val = int(val)
                except ValueError:
                    pass
                print(mc.set_values({key: val}))
            elif action == "get" and len(parts) == 2:
                print(mc.get_values([parts[1]]))
            elif action == "cmd" and len(parts) >= 2:
                cmd_name = parts[1]
                # support: cmd setAll 200
                if cmd_name == "setAll" and len(parts) >= 3:
                    try:
                        v = int(parts[2])
                    except ValueError:
                        print("Invalid value for setAll; must be integer 0-255")
                        continue
                    print(mc.send_command(cmd_name, {"value": v}))
                else:
                    print(mc.send_command(cmd_name))
            elif action == "status":
                print(mc.status())
            else:
                print("Unknown command or wrong number of arguments")

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        mc.stop_heartbeat()
