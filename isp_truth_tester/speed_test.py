from __future__ import annotations

import json
import subprocess
import sys

from .models import SpeedResult, utc_now


def run_speed_test(timeout_sec: int = 120) -> SpeedResult:
    """Run a speed test via speedtest-cli and return results."""
    ts = utc_now()

    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "speedtest",
                "--json",
                "--secure",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_sec + 30,
        )
    except subprocess.TimeoutExpired:
        return SpeedResult(
            timestamp=ts,
            download_mbps=None,
            upload_mbps=None,
            ping_ms=None,
            error="speed test timed out",
        )
    except FileNotFoundError:
        return SpeedResult(
            timestamp=ts,
            download_mbps=None,
            upload_mbps=None,
            ping_ms=None,
            error="python not found for speedtest",
        )

    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        return SpeedResult(
            timestamp=ts,
            download_mbps=None,
            upload_mbps=None,
            ping_ms=None,
            error=err,
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return SpeedResult(
            timestamp=ts,
            download_mbps=None,
            upload_mbps=None,
            ping_ms=None,
            error=f"invalid speedtest JSON: {exc}",
        )

    # speedtest-cli reports bits/sec; convert to Mbps
    download = data.get("download")
    upload = data.get("upload")
    ping = data.get("ping")
    server = data.get("server", {})

    server_label = None
    if isinstance(server, dict):
        name = server.get("name", "")
        country = server.get("country", "")
        server_label = f"{name}, {country}".strip(", ")

    return SpeedResult(
        timestamp=ts,
        download_mbps=round(download / 1_000_000, 2) if download else None,
        upload_mbps=round(upload / 1_000_000, 2) if upload else None,
        ping_ms=round(float(ping), 2) if ping is not None else None,
        server=server_label or None,
    )
