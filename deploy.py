#!/usr/bin/env python3
"""
Deploy script to copy project files to the Raspberry Pi via scp
and restart the busy-laundry systemd service via ssh.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

DEFAULT_USER = os.getenv("PI_USER", "jim")
DEFAULT_HOST = os.getenv("PI_HOST", "raspberry-jim.local")
DEFAULT_DIR = os.getenv("PI_DIR", "~/busy-laundry")
SERVICE_NAME = "busy-laundry.service"

DEFAULT_FILES = [
    "laundry_bridge.py",
    "config.py",
    "requirements.txt",
    ".env.example",
    "setup.sh",
]


def run_cmd(cmd: list[str]) -> None:
    print(f"-> {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy busy-laundry files to Raspberry Pi via scp and restart the service."
    )
    parser.add_argument(
        "--user", "-u", default=DEFAULT_USER, help=f"SSH username (default: {DEFAULT_USER})"
    )
    parser.add_argument(
        "--host", "-H", default=DEFAULT_HOST, help=f"Pi hostname or IP (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "--dir", "-d", default=DEFAULT_DIR, help=f"Remote directory on Pi (default: {DEFAULT_DIR})"
    )
    parser.add_argument(
        "--include-env",
        action="store_true",
        help="Also copy local .env file to the Raspberry Pi",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Copy files only without restarting the systemd service",
    )
    args = parser.parse_args()

    target = f"{args.user}@{args.host}"
    files_to_copy = [str(PROJECT_ROOT / f) for f in DEFAULT_FILES if (PROJECT_ROOT / f).exists()]

    if args.include_env:
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            files_to_copy.append(str(env_file))
        else:
            print("Warning: --include-env specified, but no local .env file found.")

    print(f"Copying {len(files_to_copy)} file(s) to {target}:{args.dir}...")
    run_cmd(["scp", *files_to_copy, f"{target}:{args.dir}/"])

    if not args.no_restart:
        print(f"Restarting {SERVICE_NAME} on {target}...")
        remote_cmd = (
            f"sudo systemctl restart {SERVICE_NAME} && "
            f"sudo systemctl status {SERVICE_NAME} --no-pager -l"
        )
        run_cmd(["ssh", "-t", target, remote_cmd])

    print("Deployment complete!")


if __name__ == "__main__":
    main()
