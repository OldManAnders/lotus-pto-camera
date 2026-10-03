# unifi_poe.py

from dataclasses import dataclass
import requests
import time
import urllib3
import logging
from utils.logging_config import get_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@dataclass
class UnifiConfig:
    host: str
    username: str
    password: str
    verify_ssl: bool = False


class UnifiPoEController:
    def __init__(self, config: UnifiConfig, rig: str = ""):
        self.config = config
        self.logger = get_logger(__name__, component="unifi", rig=rig)
        self.session = requests.Session()
        self.session.verify = config.verify_ssl
        self._login()
        self.site = self._get_site()
        

    def _login(self):
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


    def _get_site(self):
        response = self.session.get(f"{self.config.host}/api/self/sites").json()
        return response["data"][0]["name"]

    def get_switch(self, mac):
        devices = self.session.get(
            f"{self.config.host}/api/s/{self.site}/stat/device").json()["data"]
        mac = mac.lower()
        for device in devices:
            if device["mac"].lower() == mac:
                return device
            
        self.logger.error(f"Switch not found: {mac}", extra={"event": "unifi_hardware", "details": {"switch": mac}})


    def set_poe(self, switch_mac: str, port_index: int, enabled: bool, verify: bool = True, timeout: int = 60):
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