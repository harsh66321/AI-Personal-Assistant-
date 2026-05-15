from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

try:
    import requests
except ImportError:
    requests = None


@dataclass
class SmartDevice:
    id: str
    name: str
    device_type: str
    address: str
    enabled: bool = True
    state: str = "unknown"


class SmartHomeController:
    def __init__(self, config_file: Optional[str] = None):
        self.devices: dict[str, SmartDevice] = {}
        self.hubs: dict[str, dict] = {}
        if config_file:
            self._load_config(config_file)

    def _load_config(self, config_file: str) -> None:
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
                for device in config.get("devices", []):
                    d = SmartDevice(**device)
                    self.devices[d.id] = d
                self.hubs = config.get("hubs", {})
        except (OSError, json.JSONDecodeError):
            pass

    def add_device(self, device_id: str, name: str, device_type: str, address: str) -> str:
        device = SmartDevice(id=device_id, name=name, device_type=device_type, address=address)
        self.devices[device_id] = device
        return f"Device '{name}' added to smart home."

    def add_home_assistant_hub(self, hub_id: str, url: str, token: str) -> str:
        self.hubs[hub_id] = {"url": url, "token": token}
        return f"Home Assistant hub '{hub_id}' configured."

    def control_device(self, device_name: str, action: str) -> str:
        device = next((d for d in self.devices.values() if d.name.lower() == device_name.lower()), None)
        if not device:
            return f"Device '{device_name}' not found."

        if not device.enabled:
            return f"Device '{device_name}' is disabled."

        return self._send_command(device, action)

    def _send_command(self, device: SmartDevice, action: str) -> str:
        if not requests:
            return "HTTP requests not available. Install requests library."

        try:
            if device.device_type in {"light", "switch"}:
                state = "on" if action.lower() in {"on", "turn on", "enable"} else "off"
                device.state = state
                return f"Turning {state} {device.name}."
            elif device.device_type == "temperature":
                try:
                    target_temp = float(action)
                    device.state = str(target_temp)
                    return f"Setting {device.name} to {target_temp} degrees."
                except ValueError:
                    return f"Invalid temperature value: {action}"
            else:
                return f"Unknown action for {device.device_type}."
        except Exception as exc:
            return f"Failed to control device: {exc}"

    def send_to_home_assistant(self, hub_id: str, entity_id: str, action: str, value: Optional[str] = None) -> str:
        if hub_id not in self.hubs:
            return f"Hub '{hub_id}' not configured."

        if not requests:
            return "HTTP requests not available."

        hub = self.hubs[hub_id]
        headers = {"Authorization": f"Bearer {hub['token']}", "Content-Type": "application/json"}

        try:
            payload = {"action": action}
            if value:
                payload["value"] = value

            response = requests.post(
                f"{hub['url']}/api/services/homeassistant/{action}",
                headers=headers,
                json={"entity_id": entity_id},
                timeout=10,
            )
            if response.status_code in {200, 201}:
                return f"Home Assistant command sent: {action} for {entity_id}."
            return f"Home Assistant error: {response.status_code}."
        except Exception as exc:
            return f"Failed to contact Home Assistant: {exc}"

    def list_devices(self) -> str:
        if not self.devices:
            return "No smart devices configured."

        lines = [f"• {d.name} ({d.device_type}) - {d.state}" for d in self.devices.values()]
        return "Smart devices:\n" + "\n".join(lines)

    def get_device_status(self, device_name: str) -> str:
        device = next((d for d in self.devices.values() if d.name.lower() == device_name.lower()), None)
        if not device:
            return f"Device '{device_name}' not found."

        return f"{device.name} ({device.device_type}): {device.state}"

    def automate_routine(self, routine_name: str, devices_actions: dict[str, str]) -> str:
        results = []
        for device_name, action in devices_actions.items():
            result = self.control_device(device_name, action)
            results.append(result)

        return f"Routine '{routine_name}' executed:\n" + "\n".join(results)
