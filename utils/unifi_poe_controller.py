"""Control Power over Ethernet ports on a UniFi switch.

``UnifiPoEController`` logs into the UniFi controller API, resolves the default
site and switch, and toggles per-port PoE mode. ``set_poe`` optionally polls
the switch until the requested state is confirmed or a timeout elapses.
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass
import requests
import time
import urllib3
import logging
from utils.logging_config import get_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@dataclass
class UnifiConfig:
    """Connection settings for a UniFi controller.

    Attributes:
        host: Base URL of the controller, including scheme.
        username: Controller account username.
        password: Controller account password.
        verify_ssl: Whether to verify the controller's TLS certificate.
    """

    host: str
    username: str
    password: str
    verify_ssl: bool = False


class UnifiPoEController:
    """Manage PoE state on ports of a UniFi switch.

    Attributes:
        config: Connection settings used for the controller session.
        logger: Logger adapter tagged with the ``unifi`` component.
        session: Authenticated ``requests.Session`` for controller calls.
        site: Name of the default controller site.
    """

    def __init__(self, config: UnifiConfig, rig: str = "") -> None:
        """Initialize the controller and log into the UniFi API.

        Args:
            config: Connection settings for the controller.
            rig: Camera rig label used to tag log records.

        Returns:
            None.

        Raises:
            requests.HTTPError: If the login request fails.
        """
        self.config = config
        self.logger = get_logger(__name__, component="unifi", rig=rig)
        self.session = requests.Session()
        self.session.verify = config.verify_ssl
        self._login()
        self.site = self._get_site()
        

    def _login(self) -> None:
        """Authenticate against the UniFi API and validate site access.

        Returns:
            None.

        Raises:
            requests.HTTPError: If the login endpoint responds with an error
                status.
        """
        self.logger.debug(f"Logging into UniFi API at {self.config.host}", extra={"event": "unifi_interface", "details": {"host": self.config.host}})
        r = self.session.post(
            f"{self.config.host}/api/login",
            json={
                "username": self.config.username,
                "password": self.config.password,
                },
            )
        r.raise_for_status()

        site_check = self.session.get(f"{self.config.host}/api/self/sites").json()
        if site_check["meta"]["rc"] != "ok":
            self.logger.error("UniFi login failed - API inaccessible", extra={"event": "unifi_interface", "details": {"host": self.config.host}})
        else:
            self.logger.info("Started session with UniFi API", extra={"event": "unifi_interface", "details": {"host": self.config.host}})


    def _get_site(self) -> str:
        """Return the name of the first site exposed by the controller."""
        response = self.session.get(f"{self.config.host}/api/self/sites").json()
        return response["data"][0]["name"]

    def get_switch(self, mac: str) -> Optional[Dict[str, Any]]:
        """Look up a switch device by MAC address.

        Args:
            mac: Switch MAC address, compared case-insensitively.

        Returns:
            The device dictionary for the switch, or ``None`` when no device matches.
        """
        devices = self.session.get(
            f"{self.config.host}/api/s/{self.site}/stat/device").json()["data"]
        mac = mac.lower()
        for device in devices:
            if device["mac"].lower() == mac:
                return device
            
        self.logger.error(f"Switch not found: {mac}", extra={"event": "unifi_hardware", "details": {"switch": mac}})


    def set_poe(self, switch_mac: str, port_index: int, enabled: bool, verify: bool = True, timeout: int = 60) -> Optional[Dict[str, Any]]:
        """Enable or disable PoE on a switch port.

        When ``verify`` is ``True``, the switch is polled every 2 seconds until
        the port's PoE state matches the request or ``timeout`` seconds elapse.

        Args:
            switch_mac: MAC address of the target switch.
            port_index: Port index on the switch.
            enabled: ``True`` to enable PoE (mode ``"auto"``); ``False`` to
                disable it (mode ``"off"``).
            verify: When ``True``, poll until the new state is confirmed.
            timeout: Maximum seconds to wait for verification.

        Returns:
            When ``verify`` is ``True``, a dict with keys ``success`` (bool),
            ``switch_mac`` (str), ``port`` (int), ``poe_mode``, ``poe_power``,
            and ``poe_good`` describing the outcome. When ``verify`` is
            ``False``, ``None``.
        """
        poe_mode = "auto" if enabled else "off"
        switch = self.get_switch(switch_mac)
        overrides = switch.get("port_overrides", [])
        updated = []
        found = False

        for override in overrides:
            if override.get("port_idx") == port_index:
                override["poe_mode"] = poe_mode
                found = True
            updated.append(override)

        if not found:
            updated.append({
                "port_idx": port_index,
                "poe_mode": poe_mode,
            })

        self.logger.debug(f"Setting {switch_mac} P-{port_index} to {'On' if enabled else 'Off'}", extra={"event": "poe_control", "details": {"switch": switch_mac, "port": port_index, "action": "on" if enabled else "off"}})
        response = self.session.put(
            f"{self.config.host}/api/s/{self.site}/rest/device/{switch['_id']}",
            json={"port_overrides": updated},).json()

        if response.get("meta", {}).get("rc") != "ok":
            self.logger.error("UniFi controller rejected update", extra={"event": "poe_control_failure", "details": {"switch": switch_mac, "port": port_index}})

        if verify:
            self.logger.debug("Verifying PoE state change", extra={"event": "poe_control", "details": {"switch": switch_mac, "port": port_index, "action": "verify"}})
            start = time.time()
            while True:
                switch = self.get_switch(switch_mac)
                port = next(p for p in switch["port_table"] if p["port_idx"] == port_index)
                if port["poe_enable"] == enabled:
                    self.logger.info(f"Verified: {switch_mac} P-{port_index} to {'On' if enabled else 'Off'}", extra={"event": "poe_control_success", "details": {"switch": switch_mac, "port": port_index, "state": port.get("poe_mode")}})
                    return {
                        "success": True,
                        "switch_mac": switch_mac,
                        "port": port_index,
                        "poe_mode": port.get("poe_mode"),
                        "poe_power": port.get("poe_power", 0),
                        "poe_good": port.get("poe_good"),
                    }
                if time.time() - start > timeout:
                    self.logger.error(f"PoE verification timed out ({timeout}s)", extra={"event": "poe_control_failure", "details": {"switch": switch_mac, "port": port_index, "timeout": timeout}})
                    return {
                        "success": False,
                        "switch_mac": switch_mac,
                        "port": port_index,
                        "poe_mode": port.get("poe_mode"),
                        "poe_power": port.get("poe_power", 0),
                        "poe_good": port.get("poe_good"),
                    }
                time.sleep(2)