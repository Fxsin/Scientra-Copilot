#!/usr/bin/env python3
"""
Scientra Copilot — GROBID First-Run Setup

Handles the complete GROBID setup flow for first-time users:
  1. Check Docker installation
  2. Pull GROBID image (if needed)
  3. Create and start the scientra_grobid container
  4. Wait for GROBID health check

Usage:
  python Scripts/setup_grobid.py              # Interactive setup
  python Scripts/setup_grobid.py --quiet      # Non-interactive (for CI/scripts)
  python Scripts/setup_grobid.py --reset      # Remove old container and recreate
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ── Defaults ──
GROBID_IMAGE = "lfoppiano/grobid:0.8.1"
CONTAINER_NAME = "scientra_grobid"
HOST_PORT = 18070
CONTAINER_PORT = 8070
HEALTH_URL = f"http://localhost:{HOST_PORT}/api/isalive"
STARTUP_TIMEOUT = 90  # seconds — GROBID needs time to load models


def print_step(step: int, total: int, msg: str) -> None:
    print(f"\n  [{step}/{total}] {msg}")


def docker_installed() -> bool:
    """Check if Docker CLI is available."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False


def container_exists(name: str) -> bool:
    """Check if a Docker container exists (running or stopped)."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
        return name in result.stdout.splitlines()
    except Exception:
        return False


def container_running(name: str) -> bool:
    """Check if a Docker container is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
        return name in result.stdout.splitlines()
    except Exception:
        return False


def grobid_healthy(url: str = HEALTH_URL, timeout: float = 5.0) -> bool:
    """Check if GROBID is responding."""
    try:
        with urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace").strip().lower()
            return resp.status == 200 and "true" in body
    except Exception:
        return False


def run_docker(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a docker command and return the result."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def setup_grobid(quiet: bool = False, reset: bool = False) -> dict[str, Any]:
    """Main setup flow. Returns a result dict with status and details."""
    total_steps = 5
    step = 0

    # ── Step 1: Check Docker ──
    step += 1
    if not quiet:
        print_step(step, total_steps, "Checking Docker installation...")

    if not docker_installed():
        msg = (
            "Docker is not installed or not accessible.\n"
            "Please install Docker Desktop:\n"
            "  • Windows: https://docs.docker.com/desktop/install/windows-install/\n"
            "  • macOS:   https://docs.docker.com/desktop/install/mac-install/\n"
            "  • Linux:   https://docs.docker.com/engine/install/\n"
            "\nAfter installation, restart your terminal and run this script again."
        )
        return {"status": "failed", "step": "check_docker", "error": msg}

    if not quiet:
        print("     Docker: OK")

    # ── Step 2: Handle existing container ──
    step += 1
    if not quiet:
        print_step(step, total_steps, "Checking existing GROBID container...")

    if container_exists(CONTAINER_NAME):
        if reset:
            if not quiet:
                print(f"     Resetting container '{CONTAINER_NAME}'...")
            run_docker(["docker", "rm", "-f", CONTAINER_NAME])
        elif container_running(CONTAINER_NAME) and grobid_healthy():
            if not quiet:
                print(f"     Container '{CONTAINER_NAME}' is already running and healthy.")
            return {
                "status": "available",
                "step": "already_running",
                "health_url": HEALTH_URL,
                "container": CONTAINER_NAME,
            }
        elif container_running(CONTAINER_NAME):
            if not quiet:
                print(f"     Container is running but not healthy. Restarting...")
            run_docker(["docker", "restart", CONTAINER_NAME])
        else:
            if not quiet:
                print(f"     Starting existing container...")
            run_docker(["docker", "start", CONTAINER_NAME])
    else:
        if not quiet:
            print(f"     No existing container found. Will create new one.")

    # ── Step 3: Pull/update GROBID image ──
    step += 1
    if not quiet:
        print_step(step, total_steps, f"Pulling GROBID image ({GROBID_IMAGE})...")
        print(f"     This may take a few minutes on first run...")

    pull_result = run_docker(["docker", "pull", GROBID_IMAGE], timeout=300)
    if pull_result.returncode != 0:
        msg = f"Failed to pull GROBID image:\n{pull_result.stderr}"
        return {"status": "failed", "step": "pull_image", "error": msg}

    if not quiet:
        print("     Image ready.")

    # ── Step 4: Create container (if not exists) ──
    step += 1
    if not container_exists(CONTAINER_NAME):
        if not quiet:
            print_step(step, total_steps, f"Creating container '{CONTAINER_NAME}'...")
        create_result = run_docker([
            "docker", "run", "-d",
            "--name", CONTAINER_NAME,
            "-p", f"{HOST_PORT}:{CONTAINER_PORT}",
            "--restart", "unless-stopped",
            GROBID_IMAGE,
        ], timeout=30)
        if create_result.returncode != 0:
            msg = f"Failed to create container:\n{create_result.stderr}"
            return {"status": "failed", "step": "create_container", "error": msg}
        if not quiet:
            print(f"     Container created.")
    else:
        if not quiet:
            print(f"     Container already exists.")

    # ── Step 5: Wait for GROBID to be healthy ──
    step += 1
    if not quiet:
        print_step(step, total_steps, f"Waiting for GROBID to be ready...")

    deadline = time.time() + STARTUP_TIMEOUT
    last_status = ""
    while time.time() < deadline:
        if grobid_healthy():
            if not quiet:
                print(f"     GROBID is ready! ({HEALTH_URL})")
            return {
                "status": "available",
                "step": "healthy",
                "health_url": HEALTH_URL,
                "container": CONTAINER_NAME,
            }
        # Show startup progress
        if not quiet:
            elapsed = int(STARTUP_TIMEOUT - (deadline - time.time()))
            status = f"waiting... ({elapsed}s elapsed)"
            if status != last_status and elapsed % 10 == 0:
                print(f"     {status}")
            last_status = status
        time.sleep(2)

    # Timeout — check container logs for diagnostics
    logs = run_docker(["docker", "logs", "--tail", "20", CONTAINER_NAME])
    msg = (
        f"GROBID did not become ready within {STARTUP_TIMEOUT}s.\n"
        f"\nContainer logs (last 20 lines):\n{logs.stdout[-2000:]}"
    )
    return {"status": "timeout", "step": "health_check", "error": msg, "container_logs": logs.stdout}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scientra Copilot — GROBID First-Run Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Scripts/setup_grobid.py              # Interactive setup
  python Scripts/setup_grobid.py --quiet      # For scripts / CI
  python Scripts/setup_grobid.py --reset      # Recreate from scratch
        """,
    )
    parser.add_argument("--quiet", action="store_true", help="Minimal output for scripting")
    parser.add_argument("--reset", action="store_true", help="Remove and recreate container")
    args = parser.parse_args()

    if not args.quiet:
        print("=" * 55)
        print("  Scientra Copilot — GROBID Setup")
        print("=" * 55)
        print(f"  Container: {CONTAINER_NAME}")
        print(f"  Image:     {GROBID_IMAGE}")
        print(f"  Port:      {HOST_PORT} → {CONTAINER_PORT}")
        print(f"  Health:    {HEALTH_URL}")

    result = setup_grobid(quiet=args.quiet, reset=args.reset)

    if not args.quiet:
        print(f"\n  Result: {result['status']}")

    if result["status"] == "failed":
        print(f"\n  ❌ SETUP FAILED\n")
        print(f"  {result.get('error', 'Unknown error')}")
        print(f"\n  Manual setup:")
        print(f"    docker run -d --name {CONTAINER_NAME} -p {HOST_PORT}:{CONTAINER_PORT} {GROBID_IMAGE}")
        return 1
    elif result["status"] == "timeout":
        print(f"\n  ⚠ TIMEOUT — GROBID is taking too long to start.")
        print(f"  Check: docker logs {CONTAINER_NAME}")
        print(f"\n  You can also try restarting: docker restart {CONTAINER_NAME}")
        return 1
    else:
        if not args.quiet:
            print(f"  ✅ GROBID is ready at {HEALTH_URL}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
