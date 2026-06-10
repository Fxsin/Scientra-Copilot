from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "Config" / "grobid.yaml"

DEFAULT_IMAGE = "lfoppiano/grobid:0.8.1"
DEFAULT_CONTAINER = "scientra_grobid"
DEFAULT_PORT = 18070
DEFAULT_HEALTH = "/api/isalive"


def ensure_grobid_available(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    startup_timeout_seconds: int = 90,
    auto_setup: bool = True,
) -> dict[str, Any]:
    """Make sure GROBID is running. Auto-creates container if needed."""

    config = load_grobid_config(Path(config_path))
    base_url = str(config.get("grobid_base_url") or f"http://localhost:{DEFAULT_PORT}").rstrip("/")
    health_endpoint = str(config.get("health_endpoint") or DEFAULT_HEALTH)
    container = str(config.get("docker_container") or DEFAULT_CONTAINER)
    health_url = f"{base_url}{health_endpoint}"

    # Already running?
    if grobid_health_ok(health_url):
        return {
            "status": "available",
            "health_url": health_url,
            "auto_setup_triggered": False,
            "message": "GROBID is already running and healthy.",
        }

    # Try docker start on existing container
    docker_ok = _docker_available()
    if not docker_ok:
        return {
            "status": "unavailable",
            "health_url": health_url,
            "auto_setup_triggered": False,
            "message": (
                "Docker is not installed. GROBID requires Docker.\n"
                "Install Docker Desktop: https://docs.docker.com/desktop/\n"
                "Then run: python Scripts/setup_grobid.py"
            ),
        }

    if _container_exists(container):
        # Try restarting existing container
        subprocess.run(["docker", "start", container], capture_output=True, timeout=30)
        if _wait_for_grobid(health_url, startup_timeout_seconds):
            return {
                "status": "available_after_docker_start",
                "health_url": health_url,
                "auto_setup_triggered": False,
                "message": "GROBID started from existing container.",
            }

    # Container doesn't exist or won't start → auto-setup
    if auto_setup:
        result = _auto_setup_container(container, health_url, startup_timeout_seconds)
        if result["status"] == "available":
            result["auto_setup_triggered"] = True
        return result

    return {
        "status": "unavailable",
        "health_url": health_url,
        "auto_setup_triggered": False,
        "message": (
            f"GROBID container '{container}' not found and auto_setup is disabled.\n"
            f"Run the setup: python Scripts/setup_grobid.py\n"
            f"Or manually: docker run -d --name {container} -p {DEFAULT_PORT}:8070 {DEFAULT_IMAGE}"
        ),
    }


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "--version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _container_exists(name: str) -> bool:
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
        return name in result.stdout.splitlines()
    except Exception:
        return False


def _wait_for_grobid(health_url: str, timeout: int) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if grobid_health_ok(health_url):
            return True
        time.sleep(2)
    return False


def _auto_setup_container(container: str, health_url: str, timeout: int) -> dict[str, Any]:
    """Create and start the GROBID container from scratch."""
    # Pull image
    subprocess.run(["docker", "pull", DEFAULT_IMAGE], capture_output=True, timeout=300)
    # Remove stale container if exists
    if _container_exists(container):
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=10)
    # Create
    result = subprocess.run([
        "docker", "run", "-d",
        "--name", container,
        "-p", f"{DEFAULT_PORT}:8070",
        "--restart", "unless-stopped",
        DEFAULT_IMAGE,
    ], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return {
            "status": "unavailable",
            "health_url": health_url,
            "auto_setup_triggered": True,
            "message": f"Failed to create GROBID container:\n{result.stderr}",
        }
    if _wait_for_grobid(health_url, timeout):
        return {
            "status": "available",
            "health_url": health_url,
            "auto_setup_triggered": True,
            "message": "GROBID container created and healthy.",
        }
    return {
        "status": "unavailable",
        "health_url": health_url,
        "auto_setup_triggered": True,
        "message": f"GROBID container created but not responding. Check: docker logs {container}",
    }


def grobid_health_ok(url: str, timeout_seconds: float = 5.0) -> bool:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace").strip().lower()
            return response.status == 200 and "true" in body
    except Exception:
        return False


def load_grobid_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ensure GROBID is running (auto-setup if needed).")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--no-auto-setup", action="store_true", help="Don't auto-create container")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = ensure_grobid_available(
        args.config,
        startup_timeout_seconds=args.timeout,
        auto_setup=not args.no_auto_setup,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status:  {result['status']}")
        print(f"health:  {result['health_url']}")
        print(f"message: {result['message']}")
    return 0 if result["status"].startswith("available") else 1


if __name__ == "__main__":
    raise SystemExit(main())
