import os
from pathlib import Path
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

BUSY_BAR_IP = os.getenv("BUSY_BAR_IP", "192.168.1.100").strip()
BUSY_BAR_TOKEN = os.getenv("BUSY_BAR_TOKEN", "").strip()
SINRIC_APP_KEY = os.getenv("SINRIC_APP_KEY", "").strip()
SINRIC_APP_SECRET = os.getenv("SINRIC_APP_SECRET", "").strip()
# Devices: either a unified LAUNDRY_DEVICE_ID or separate WASHER/DRYER_DEVICE_IDs
LAUNDRY_DEVICE_ID = os.getenv("LAUNDRY_DEVICE_ID", "").strip()
WASHER_DEVICE_ID = os.getenv("WASHER_DEVICE_ID", "").strip()
DRYER_DEVICE_ID = os.getenv("DRYER_DEVICE_ID", "").strip()

ALERT_TIMEOUT_SECONDS = int(os.getenv("ALERT_TIMEOUT_SECONDS", "1800"))
LAUNDRY_ALERT_TEXT = os.getenv("LAUNDRY_ALERT_TEXT", "Laundry done").strip()
ALERT_SOUND = os.getenv("ALERT_SOUND", "event").strip()

# Compatibility if washer/dryer alert text are customized
WASHER_ALERT_TEXT = os.getenv("WASHER_ALERT_TEXT", LAUNDRY_ALERT_TEXT).strip()
DRYER_ALERT_TEXT = os.getenv("DRYER_ALERT_TEXT", LAUNDRY_ALERT_TEXT).strip()


def validate_config(require_sinric: bool = True) -> list[str]:
    """Validates configuration and returns a list of missing setting warnings/errors."""
    errors = []
    if not BUSY_BAR_IP or BUSY_BAR_IP == "192.168.1.100":
        errors.append("BUSY_BAR_IP is not set or still default (192.168.1.100)")
    
    if require_sinric:
        if not SINRIC_APP_KEY or "your_sinric" in SINRIC_APP_KEY:
            errors.append("SINRIC_APP_KEY is missing")
        if not SINRIC_APP_SECRET or "your_sinric" in SINRIC_APP_SECRET:
            errors.append("SINRIC_APP_SECRET is missing")

        has_unified = bool(LAUNDRY_DEVICE_ID and "your_laundry" not in LAUNDRY_DEVICE_ID)
        has_separate = bool(
            (WASHER_DEVICE_ID and "your_washer" not in WASHER_DEVICE_ID) or
            (DRYER_DEVICE_ID and "your_dryer" not in DRYER_DEVICE_ID)
        )
        if not (has_unified or has_separate):
            errors.append("At least one device ID must be set: LAUNDRY_DEVICE_ID or WASHER_DEVICE_ID / DRYER_DEVICE_ID")
            
    return errors
