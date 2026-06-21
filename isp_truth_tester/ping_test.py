from __future__ import annotations

import platform
import re
import subprocess
from typing import Sequence

from .models import PingResult, utc_now

_PING_RE = re.compile(r"min/avg/max/(?:mdev|stddev)\s*=\s*[\d.]+/([\d.]+)/")


def run_ping(target: str, count: int = 3, timeout_sec: int = 10) -> PingResult:
    """Ping a host and return latency stats."""
    ts = utc_now()
    system = platform.system().lower()

    if system == "windows":
        cmd = ["ping", "-n", str(count), "-w", str(timeout_sec * 1000), target]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout_sec), target]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec + 5,
        )
        output = proc.stdout + proc.stderr

        if proc.returncode != 0 and "0% packet loss" not in output:
            return PingResult(
                timestamp=ts,
                target=target,
                latency_ms=None,
                packet_loss_pct=100.0,
                error=output.strip() or f"ping exited {proc.returncode}",
            )

        loss_match = re.search(r"(\d+(?:\.\d+)?)%\s+packet loss", output)
        packet_loss = float(loss_match.group(1)) if loss_match else 0.0

        latency_ms: float | None = None
        avg_match = _PING_RE.search(output)
        if avg_match:
            latency_ms = float(avg_match.group(1))
        else:
            # Windows format: Average = 12ms
            win_match = re.search(r"Average\s*=\s*(\d+)ms", output, re.I)
            if win_match:
                latency_ms = float(win_match.group(1))

        return PingResult(
            timestamp=ts,
            target=target,
            latency_ms=latency_ms,
            packet_loss_pct=packet_loss,
        )
    except subprocess.TimeoutExpired:
        return PingResult(
            timestamp=ts,
            target=target,
            latency_ms=None,
            packet_loss_pct=100.0,
            error="ping timed out",
        )
    except FileNotFoundError:
        return PingResult(
            timestamp=ts,
            target=target,
            latency_ms=None,
            packet_loss_pct=100.0,
            error="ping command not found",
        )


def run_pings(targets: Sequence[str]) -> list[PingResult]:
    return [run_ping(t) for t in targets]
