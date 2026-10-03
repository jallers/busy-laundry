#!/usr/bin/env python3
"""
BUSY Bar + Google Home Laundry Bridge
Listens for Google Home Routine triggers (via Sinric Pro virtual switches)
and displays custom status notifications on your BUSY Bar LED matrix.
"""

import sys
import json
import logging
import asyncio
import urllib.request
import urllib.error
from typing import Optional

import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("busy-laundry")

# Active auto-clear task reference and tracking of active notifications
_auto_clear_task: Optional[asyncio.Task] = None
_active_triggers: set[str] = set()


async def send_to_busy_bar(text: str, is_clear: bool = False) -> bool:
    # 1. Try busylib if installed
    try:
        from busylib import AsyncBusyBar
        from busylib.features import notify
        token_arg = config.BUSY_BAR_TOKEN if config.BUSY_BAR_TOKEN else None
        bb = AsyncBusyBar(config.BUSY_BAR_IP, token=token_arg)
        await bb.version()
        if not is_clear:
            sound_arg = config.ALERT_SOUND if config.ALERT_SOUND else None
            await notify(bb, text, icon="check", sound=sound_arg, application_name="laundry")
            logger.info(f"Notification sent to BUSY Bar via busylib: '{text}' (sound={sound_arg})")
            return True
        else:
            await bb.display_clear(application_name="laundry")
            logger.info("Cleared display on BUSY Bar via busylib.")
            return True
    except ImportError:
        logger.debug("busylib not installed or importable, falling back to direct HTTP.")
    except Exception as e:
        logger.warning(f"busylib call failed ({e}), falling back to direct HTTP API...")

    # 2. Resilient Direct HTTP Fallback
    """
    Sends a draw command to the BUSY Bar.
    Uses busylib if available, with a resilient direct HTTP fallback.
    """
    elements = []
    if not is_clear and text:
        elements.append({
            "id": "laundry_status",
            "type": "text",
            "x": 2,
            "y": 4,
            "text": text,
            "font": "small",
            "display": "front"
        })

    payload = {
        "application_name": "laundry",
        "elements": elements
    }
    url = f"http://{config.BUSY_BAR_IP}/api/display/draw"
    req_data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if config.BUSY_BAR_TOKEN:
        headers["X-API-Token"] = config.BUSY_BAR_TOKEN
        headers["Authorization"] = f"Bearer {config.BUSY_BAR_TOKEN}"

    req = urllib.request.Request(
        url,
        data=req_data,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status in (200, 204):
                logger.info("Successfully updated BUSY Bar via direct HTTP API.")
                return True
            else:
                logger.warning(f"BUSY Bar returned HTTP status {response.status}")
                return False
    except urllib.error.URLError as e:
        logger.error(f"Failed to connect to BUSY Bar at {config.BUSY_BAR_IP}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error communicating with BUSY Bar: {e}")
        return False


async def clear_busy_bar() -> bool:
    """Clears the laundry alert from the screen."""
    logger.info("Clearing laundry alert from BUSY Bar display.")
    _active_triggers.clear()
    return await send_to_busy_bar("", is_clear=True)


def schedule_auto_clear(seconds: int):
    """Schedules clearing the display after a specified timeout."""
    global _auto_clear_task
    if _auto_clear_task and not _auto_clear_task.done():
        _auto_clear_task.cancel()

    if seconds <= 0:
        return

    async def _clear_worker():
        try:
            await asyncio.sleep(seconds)
            await clear_busy_bar()
        except asyncio.CancelledError:
            pass

    _auto_clear_task = asyncio.create_task(_clear_worker())


async def trigger_alert(message: str):
    """Triggers an alert on the BUSY Bar and schedules auto-clear."""
    logger.info(f"===> LAUNDRY ALERT: {message} <===")
    success = await send_to_busy_bar(message)
    if success and config.ALERT_TIMEOUT_SECONDS > 0:
        schedule_auto_clear(config.ALERT_TIMEOUT_SECONDS)


# --- Sinric Pro Callbacks ---

async def on_laundry_state_change(*args, **kwargs) -> bool:
    """Callback when 'Laundry' unified switch state changes in Google Home."""
    state = args[0] if len(args) == 1 else (args[1] if len(args) > 1 else kwargs.get("state", False))
    logger.info(f"[Google Home] 'Laundry' switch changed to {'ON' if state else 'OFF'}")
    if state:
        _active_triggers.add("laundry")
        await trigger_alert(config.LAUNDRY_ALERT_TEXT)
    else:
        _active_triggers.discard("laundry")
        if not _active_triggers:
            await clear_busy_bar()
    return True


async def on_washer_state_change(*args, **kwargs) -> bool:
    """Callback when 'Washer Alert' switch state changes in Google Home."""
    state = args[0] if len(args) == 1 else (args[1] if len(args) > 1 else kwargs.get("state", False))
    logger.info(f"[Google Home] 'Washer Alert' switched to {'ON' if state else 'OFF'}")
    if state:
        _active_triggers.add("washer")
        await trigger_alert(config.WASHER_ALERT_TEXT)
    else:
        _active_triggers.discard("washer")
        if not _active_triggers:
            await clear_busy_bar()
    return True


async def on_dryer_state_change(*args, **kwargs) -> bool:
    """Callback when 'Dryer Alert' switch state changes in Google Home."""
    state = args[0] if len(args) == 1 else (args[1] if len(args) > 1 else kwargs.get("state", False))
    logger.info(f"[Google Home] 'Dryer Alert' switched to {'ON' if state else 'OFF'}")
    if state:
        _active_triggers.add("dryer")
        await trigger_alert(config.DRYER_ALERT_TEXT)
    else:
        _active_triggers.discard("dryer")
        if not _active_triggers:
            await clear_busy_bar()
    return True


async def run_daemon():
    """Runs the Sinric Pro listener daemon."""
    errors = config.validate_config(require_sinric=True)
    if errors:
        logger.error("Configuration validation failed:")
        for err in errors:
            logger.error(f"  - {err}")
        logger.error("Please configure your .env file before starting the service.")
        sys.exit(1)

    try:
        from sinricpro import SinricPro, SinricProSwitch, SinricProConfig
    except ImportError:
        logger.error("The 'sinricpro' package is not installed. Run: pip install -r requirements.txt")
        sys.exit(1)

    sp = SinricPro.get_instance()
    devices_registered = 0

    if config.LAUNDRY_DEVICE_ID and "your_laundry" not in config.LAUNDRY_DEVICE_ID:
        laundry_switch = SinricProSwitch(config.LAUNDRY_DEVICE_ID)
        laundry_switch.on_power_state(on_laundry_state_change)
        sp.add(laundry_switch)
        logger.info(f"Registered Sinric Pro switch: Laundry ({config.LAUNDRY_DEVICE_ID})")
        devices_registered += 1

    if config.WASHER_DEVICE_ID and "your_washer" not in config.WASHER_DEVICE_ID:
        washer_switch = SinricProSwitch(config.WASHER_DEVICE_ID)
        washer_switch.on_power_state(on_washer_state_change)
        sp.add(washer_switch)
        logger.info(f"Registered Sinric Pro switch: Washer ({config.WASHER_DEVICE_ID})")
        devices_registered += 1

    if config.DRYER_DEVICE_ID and "your_dryer" not in config.DRYER_DEVICE_ID:
        dryer_switch = SinricProSwitch(config.DRYER_DEVICE_ID)
        dryer_switch.on_power_state(on_dryer_state_change)
        sp.add(dryer_switch)
        logger.info(f"Registered Sinric Pro switch: Dryer ({config.DRYER_DEVICE_ID})")
        devices_registered += 1

    if devices_registered == 0:
        logger.error("No valid Sinric Pro device IDs configured. Please set LAUNDRY_DEVICE_ID or WASHER/DRYER_DEVICE_ID in .env")
        sys.exit(1)

    sinric_config = SinricProConfig(
        app_key=config.SINRIC_APP_KEY,
        app_secret=config.SINRIC_APP_SECRET
    )

    logger.info("Connecting to Sinric Pro...")
    await sp.begin(sinric_config)

    logger.info("Connected to Sinric Pro!")
    logger.info(f"Target BUSY Bar IP : {config.BUSY_BAR_IP}")
    logger.info("Ready and listening for Google Home laundry routines...")

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await sp.stop()


def main():
    """CLI handler for testing and starting the service."""
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--test", "-t", "--test-laundry"):
            print(f"Testing laundry notification: '{config.LAUNDRY_ALERT_TEXT}' (sound: '{config.ALERT_SOUND}') -> {config.BUSY_BAR_IP}")
            asyncio.run(send_to_busy_bar(config.LAUNDRY_ALERT_TEXT))
            return
        elif arg in ("--test-washer", "--washer", "-w"):
            print(f"Testing washer alert: '{config.WASHER_ALERT_TEXT}' -> {config.BUSY_BAR_IP}")
            asyncio.run(send_to_busy_bar(config.WASHER_ALERT_TEXT))
            return
        elif arg in ("--test-dryer", "--dryer", "-d"):
            print(f"Testing dryer alert: '{config.DRYER_ALERT_TEXT}' -> {config.BUSY_BAR_IP}")
            asyncio.run(send_to_busy_bar(config.DRYER_ALERT_TEXT))
            return
        elif arg in ("--clear", "-c"):
            print(f"Clearing alert display on {config.BUSY_BAR_IP}")
            asyncio.run(clear_busy_bar())
            return
        elif arg in ("--help", "-h"):
            print("Usage:")
            print("  python laundry_bridge.py               Run 24/7 background listener")
            print("  python laundry_bridge.py --test        Test unified laundry notification with sound")
            print("  python laundry_bridge.py --test-washer Test washer notification on screen")
            print("  python laundry_bridge.py --test-dryer  Test dryer notification on screen")
            print("  python laundry_bridge.py --clear       Clear current alert on screen")
            return
        else:
            print(f"Unknown argument: {arg}")
            print("Run with --help for options.")
            sys.exit(1)

    # Start main daemon
    try:
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        logger.info("Bridge stopped by user.")
        try:
            asyncio.run(clear_busy_bar())
        except Exception:
            pass


if __name__ == "__main__":
    main()
