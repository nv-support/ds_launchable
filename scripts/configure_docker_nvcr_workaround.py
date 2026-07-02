#!/usr/bin/env python3
"""Disable Docker 29.5.x containerd image store for NVCR pulls."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def main() -> int:
    try:
        docker_version = subprocess.check_output(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            text=True,
        ).strip()
    except Exception as exc:
        print(f"Docker is not available yet; skipping NVCR workaround: {exc}")
        return 0

    if not docker_version.startswith("29.5."):
        print(f"Docker {docker_version}: NVCR workaround not needed.")
        return 0

    daemon_path = Path("/etc/docker/daemon.json")
    try:
        current = subprocess.check_output(["sudo", "cat", str(daemon_path)], text=True)
        daemon = json.loads(current or "{}")
    except subprocess.CalledProcessError:
        daemon = {}

    features = daemon.setdefault("features", {})
    if features.get("containerd-snapshotter") is False:
        print(f"Docker {docker_version}: NVCR workaround already configured.")
        return 0

    features["containerd-snapshotter"] = False
    tmp = Path("/tmp/docker-daemon-nvcr-workaround.json")
    tmp.write_text(json.dumps(daemon, indent=2) + "\n")
    subprocess.run(["sudo", "cp", str(tmp), str(daemon_path)], check=True)
    subprocess.run(["sudo", "systemctl", "restart", "docker"], check=True)
    print(f"Docker {docker_version}: disabled containerd-snapshotter and restarted Docker.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
