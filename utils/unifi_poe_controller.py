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
    def __init__(self, config: UnifiConfig):
        self.config = config
        self.logger = get_logger(__name__, component="Unifi")
        self.session = requests.Session()
        self.session.verify = config.verify_ssl
        self._login()
        self.site = self._get_site()
        

    def _login(self):
        self.logger.debug("", extra={"event": "unifi_interface", "details": f"Logging into Unifi Api"})
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
            self.logger.error("", extra={"event": "unifi_interface", "details": f"Login failed - Unifi API inaccessible"})
        else:
            self.logger.info("", extra={"event": "unifi_interface", "details": f"Started session with unifi API"})


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
            
        self.logger.error("", extra={"event": "unifi_hardware", "details": f"Switch not found: {mac}"})


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

        self.logger.debug("", extra={"event": "poe_control", "details": f"Setting {switch_mac} P-{port_index} to {"On" if enabled else "Off"}"})
        response = self.session.put(
            f"{self.config.host}/api/s/{self.site}/rest/device/{switch['_id']}",
            json={"port_overrides": updated},).json()

        if response.get("meta", {}).get("rc") != "ok":
            self.logger.error("", extra={"event": "poe_control_failure", "details": f"Unifi Controller rejected update: {response}"})

        if verify:
            self.logger.debug("", extra={"event": "poe_control", "details": f"Verifying state change"})
            start = time.time()
            while True:
                switch = self.get_switch(switch_mac)
                port = next(p for p in switch["port_table"] if p["port_idx"] == port_index)
                if port["poe_enable"] == enabled:
                    self.logger.info("", extra={"event": "poe_control_success", "details": f"Verified: {switch_mac} P-{port_index} to {"On" if enabled else "Off"}"})
                    return {
                        "success": True,
                        "switch_mac": switch_mac,
                        "port": port_index,
                        "poe_mode": port.get("poe_mode"),
                        "poe_power": port.get("poe_power", 0),
                        "poe_good": port.get("poe_good"),
                    }
                if time.time() - start > timeout:
                    self.logger.error("", extra={"event": "poe_control_failure", "details": f"Verification timed out. ({timeout}s)"})
                    return {
                        "success": False,
                        "switch_mac": switch_mac,
                        "port": port_index,
                        "poe_mode": port.get("poe_mode"),
                        "poe_power": port.get("poe_power", 0),
                        "poe_good": port.get("poe_good"),
                    }
                time.sleep(2)