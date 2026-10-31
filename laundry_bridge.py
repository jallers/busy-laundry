#!/usr/bin/env python3
"""
BUSY Bar + Google Home Laundry Bridge
Listens for Google Home Routine triggers (via Sinric Pro virtual switches)
and displays custom status notifications on your BUSY Bar LED matrix.
"""

import sys
import json
import signal
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

def make_device_callback(device: config.DeviceConfig):
    """Creates a Sinric Pro power-state callback for a configured device."""
    async def _on_state_change(*args, **kwargs) -> bool:
        state = args[0] if len(args) == 1 else (args[1] if len(args) > 1 else kwargs.get("state", False))
        logger.info(f"[Google Home] '{device.name}' ({device.device_id}) switched to {'ON' if state else 'OFF'}")
        if device.alert_text:
            if state:
                _active_triggers.add(device.key)
                await trigger_alert(device.alert_text)
            else:
                _active_triggers.discard(device.key)
                if not _active_triggers:
                    await clear_busy_bar()
        return True

    return _on_state_change


async def on_laundry_state_change(*args, **kwargs) -> bool:
    """Callback when 'Laundry' unified switch state changes in Google Home."""
    dev = config.DeviceConfig("laundry", "Laundry", config.LAUNDRY_DEVICE_ID, config.LAUNDRY_ALERT_TEXT)
    return await make_device_callback(dev)(*args, **kwargs)


async def on_washer_state_change(*args, **kwargs) -> bool:
    """Callback when 'Washer Alert' switch state changes in Google Home."""
    dev = config.DeviceConfig("washer", "Washer", config.WASHER_DEVICE_ID, config.WASHER_ALERT_TEXT)
    return await make_device_callback(dev)(*args, **kwargs)


async def on_dryer_state_change(*args, **kwargs) -> bool:
    """Callback when 'Dryer Alert' switch state changes in Google Home."""
    dev = config.DeviceConfig("dryer", "Dryer", config.DRYER_DEVICE_ID, config.DRYER_ALERT_TEXT)
    return await make_device_callback(dev)(*args, **kwargs)


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
    devices = config.load_devices()

    for dev in devices:
        switch = SinricProSwitch(dev.device_id)
        switch.on_power_state(make_device_callback(dev))
        sp.add(switch)
        mode_desc = f"BUSY Bar alert: '{dev.alert_text}'" if dev.alert_text else "Sinric Pro online/active only"
        logger.info(f"Registered Sinric Pro switch: {dev.name} ({dev.device_id}) [{mode_desc}]")

    if not devices:
        logger.error(
            "No valid Sinric Pro device IDs configured. "
            "Please set DEVICE_<NAME>_ID or LAUNDRY/WASHER/DRYER_DEVICE_ID in .env"
        )
        sys.exit(1)

    sinric_config = SinricProConfig(
        app_key=config.SINRIC_APP_KEY,
        app_secret=config.SINRIC_APP_SECRET
    )

    sp.on_connected(lambda: logger.info("Sinric Pro WebSocket connected."))
    sp.on_disconnected(lambda: logger.warning("Sinric Pro WebSocket disconnected."))

    logger.info("Connecting to Sinric Pro...")
    await sp.begin(sinric_config)

    if hasattr(signal, "SIGUSR1"):
        def _force_disconnect():
            logger.info("Received SIGUSR1: closing WebSocket to test reconnection...")
            if sp.websocket and sp.websocket.ws:
                asyncio.create_task(sp.websocket.ws.close())

        asyncio.get_running_loop().add_signal_handler(signal.SIGUSR1, _force_disconnect)

    logger.info("Connected to Sinric Pro!")
    logger.info(f"Target BUSY Bar IP : {config.BUSY_BAR_IP}")
    logger.info("Ready and listening for Google Home laundry routines...")

    max_reconnect_failures = 10
    consecutive_failures = 0
    base_backoff = 10

    try:
        while True:
            await asyncio.sleep(10)

            if sp.is_connected():
                consecutive_failures = 0
                continue

            # Wait if the SDK's built-in 5-second reconnect task is still in flight
            reconnect_task = getattr(sp.websocket, "_reconnect_task", None) if sp.websocket else None
            if reconnect_task is not None and not reconnect_task.done():
                continue

            consecutive_failures += 1
            if consecutive_failures > max_reconnect_failures:
                logger.error(
                    f"Failed to reconnect to Sinric Pro after {max_reconnect_failures} attempts. "
                    "Exiting so systemd can restart the service cleanly."
                )
                sys.exit(1)

            backoff = min(base_backoff * (2 ** (consecutive_failures - 1)), 60)
            logger.warning(
                f"Sinric Pro is disconnected (SDK auto-reconnect exhausted). "
                f"Retry {consecutive_failures}/{max_reconnect_failures} in {backoff}s..."
            )
            await asyncio.sleep(backoff)

            if sp.is_connected():
                consecutive_failures = 0
                continue

            if sp.websocket:
                try:
                    sp.websocket._stop_heartbeat()
                    await sp.websocket.connect()
                    logger.info("Successfully reconnected to Sinric Pro!")
                    consecutive_failures = 0
                except Exception as e:
                    logger.error(f"Reconnect attempt {consecutive_failures} failed: {e}")
            else:
                logger.error("Sinric Pro WebSocket client not initialized; exiting for restart.")
                sys.exit(1)
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
        elif arg in ("--list-devices", "--devices", "-l"):
            devices = config.load_devices()
            if not devices:
                print("No Sinric Pro devices configured.")
            else:
                print(f"Configured Sinric Pro devices ({len(devices)}):")
                for dev in devices:
                    mode = f"BUSY Bar alert: '{dev.alert_text}'" if dev.alert_text else "Online/active only (no BUSY Bar display)"
                    print(f"  - {dev.name} (key={dev.key}, id={dev.device_id}) -> {mode}")
            return
        elif arg in ("--help", "-h"):
            print("Usage:")
            print("  python laundry_bridge.py                Run 24/7 background listener")
            print("  python laundry_bridge.py --list-devices List all configured Sinric Pro devices")
            print("  python laundry_bridge.py --test         Test unified laundry notification with sound")
            print("  python laundry_bridge.py --test-washer  Test washer notification on screen")
            print("  python laundry_bridge.py --test-dryer   Test dryer notification on screen")
            print("  python laundry_bridge.py --clear        Clear current alert on screen")
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
