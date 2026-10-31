import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

BUSY_BAR_IP = os.getenv("BUSY_BAR_IP", "192.168.1.100").strip()
BUSY_BAR_TOKEN = os.getenv("BUSY_BAR_TOKEN", "").strip()
SINRIC_APP_KEY = os.getenv("SINRIC_APP_KEY", "").strip()
SINRIC_APP_SECRET = os.getenv("SINRIC_APP_SECRET", "").strip()
# Legacy / built-in laundry device IDs
LAUNDRY_DEVICE_ID = os.getenv("LAUNDRY_DEVICE_ID", "").strip()
WASHER_DEVICE_ID = os.getenv("WASHER_DEVICE_ID", "").strip()
DRYER_DEVICE_ID = os.getenv("DRYER_DEVICE_ID", "").strip()

ALERT_TIMEOUT_SECONDS = int(os.getenv("ALERT_TIMEOUT_SECONDS", "1800"))
LAUNDRY_ALERT_TEXT = os.getenv("LAUNDRY_ALERT_TEXT", "Laundry done").strip()
ALERT_SOUND = os.getenv("ALERT_SOUND", "event").strip()

# Compatibility if washer/dryer alert text are customized
WASHER_ALERT_TEXT = os.getenv("WASHER_ALERT_TEXT", LAUNDRY_ALERT_TEXT).strip()
DRYER_ALERT_TEXT = os.getenv("DRYER_ALERT_TEXT", LAUNDRY_ALERT_TEXT).strip()


@dataclass(frozen=True)
class DeviceConfig:
    """Configuration for a single Sinric Pro virtual switch device."""
    key: str
    name: str
    device_id: str
    alert_text: Optional[str] = None


def _is_valid_device_id_value(value: str) -> bool:
    """Returns True if the device ID string is non-empty and not a template placeholder."""
    if not value:
        return False
    lower = value.lower()
    return not (lower.startswith("your_") or "device_id_here" in lower)


def load_devices() -> list[DeviceConfig]:
    """
    Loads all configured Sinric Pro devices from environment variables.

    Supports:
    1. Built-in laundry devices (LAUNDRY_DEVICE_ID, WASHER_DEVICE_ID, DRYER_DEVICE_ID),
       which display their respective alert text on the BUSY Bar by default.
    2. Arbitrary named devices via DEVICE_<NAME>_ID=<id> (and optional DEVICE_<NAME>_TEXT=<text>).
       If DEVICE_<NAME>_TEXT is omitted or empty, the device is connected and activated in
       Sinric Pro without displaying an alert on the BUSY Bar.
    """
    devices: list[DeviceConfig] = []
    seen_ids: set[str] = set()

    def _add_device(key: str, name: str, device_id: str, alert_text: Optional[str]) -> None:
        if not _is_valid_device_id_value(device_id) or device_id in seen_ids:
            return
        seen_ids.add(device_id)
        cleaned_text = alert_text.strip() if alert_text and alert_text.strip() else None
        devices.append(
            DeviceConfig(
                key=key,
                name=name,
                device_id=device_id,
                alert_text=cleaned_text,
            )
        )

    # 1. Built-in laundry switches (backward compatible)
    if _is_valid_device_id_value(LAUNDRY_DEVICE_ID):
        text_override = os.getenv("DEVICE_LAUNDRY_TEXT")
        _add_device(
            "laundry",
            "Laundry",
            LAUNDRY_DEVICE_ID,
            text_override if text_override is not None else LAUNDRY_ALERT_TEXT,
        )

    if _is_valid_device_id_value(WASHER_DEVICE_ID):
        text_override = os.getenv("DEVICE_WASHER_TEXT")
        _add_device(
            "washer",
            "Washer",
            WASHER_DEVICE_ID,
            text_override if text_override is not None else WASHER_ALERT_TEXT,
        )

    if _is_valid_device_id_value(DRYER_DEVICE_ID):
        text_override = os.getenv("DEVICE_DRYER_TEXT")
        _add_device(
            "dryer",
            "Dryer",
            DRYER_DEVICE_ID,
            text_override if text_override is not None else DRYER_ALERT_TEXT,
        )

    # 2. Arbitrary named devices: DEVICE_<NAME>_ID (with optional DEVICE_<NAME>_TEXT)
    pattern = re.compile(r"^DEVICE_([A-Za-z0-9_]+)_ID$")
    for env_key, raw_val in sorted(os.environ.items()):
        match = pattern.match(env_key)
        if not match:
            continue
        raw_name = match.group(1)
        device_id = raw_val.strip()
        if not _is_valid_device_id_value(device_id):
            continue

        norm_key = raw_name.lower()
        display_name = raw_name.replace("_", " ").title()
        alert_text = os.getenv(f"DEVICE_{raw_name}_TEXT", "").strip() or None
        _add_device(norm_key, display_name, device_id, alert_text)

    return devices


DEVICES: list[DeviceConfig] = load_devices()


def validate_config(require_sinric: bool = True) -> list[str]:
    """Validates configuration and returns a list of missing setting warnings/errors."""
    errors = []
    devices = load_devices()
    needs_busy_bar = (not require_sinric) or any(d.alert_text for d in devices)

    if needs_busy_bar and (not BUSY_BAR_IP or BUSY_BAR_IP == "192.168.1.100"):
        errors.append("BUSY_BAR_IP is not set or still default (192.168.1.100)")

    if require_sinric:
        if not SINRIC_APP_KEY or "your_sinric" in SINRIC_APP_KEY:
            errors.append("SINRIC_APP_KEY is missing")
        if not SINRIC_APP_SECRET or "your_sinric" in SINRIC_APP_SECRET:
            errors.append("SINRIC_APP_SECRET is missing")

        if not devices:
            errors.append(
                "At least one device ID must be set (e.g. DEVICE_<NAME>_ID, LAUNDRY_DEVICE_ID, WASHER_DEVICE_ID, or DRYER_DEVICE_ID)"
            )

    return errors
