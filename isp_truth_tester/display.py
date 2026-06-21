from __future__ import annotations

from datetime import datetime, timezone

from .models import PingResult, SessionData, SpeedResult
from .stats import compute_ping_stats, compute_speed_stats


def _fmt_mbps(value: float | None) -> str:
    return f"{value:.1f}" if value is not None else "—"


def _fmt_ms(value: float | None) -> str:
    return f"{value:.1f}" if value is not None else "—"


def _fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _latest_ping_by_target(pings: list[PingResult]) -> dict[str, PingResult]:
    latest: dict[str, PingResult] = {}
    for p in pings:
        latest[p.target] = p
    return latest


def _latest_speed(speeds: list[SpeedResult]) -> SpeedResult | None:
    return speeds[-1] if speeds else None


def format_status_line(
    session: SessionData,
    *,
    elapsed_sec: float,
    remaining_sec: float,
    speed_running: bool = False,
    now: datetime | None = None,
) -> str:
    """One-line summary of current and average connection stats."""
    ts = (now or datetime.now(timezone.utc)).strftime("%H:%M:%S")
    ping_stats = compute_ping_stats(session.pings)
    speed_stats = compute_speed_stats(session.speeds)
    latest = _latest_speed(session.speeds)

    # Per-target current ping
    target_bits: list[str] = []
    for target in session.meta.ping_targets:
        hit = _latest_ping_by_target(session.pings).get(target)
        if hit and hit.latency_ms is not None:
            target_bits.append(f"{target} {_fmt_ms(hit.latency_ms)}ms")
        elif hit and hit.error:
            target_bits.append(f"{target} err")
        else:
            target_bits.append(f"{target} —")

    ping_part = " · ".join(target_bits)
    if ping_stats.latency.has_data:
        ping_part += f" (avg {_fmt_ms(ping_stats.latency.average)}ms)"

    if speed_running:
        speed_part = "speed test running…"
    elif latest and not latest.error:
        speed_part = (
            f"↓ {_fmt_mbps(latest.download_mbps)} Mbps"
            f" (avg {_fmt_mbps(speed_stats.download.average)})"
            f"  ↑ {_fmt_mbps(latest.upload_mbps)} Mbps"
            f" (avg {_fmt_mbps(speed_stats.upload.average)})"
        )
        if latest.ping_ms is not None:
            speed_part += f"  st-ping {_fmt_ms(latest.ping_ms)}ms"
    elif latest and latest.error:
        speed_part = f"last speed test failed ({len(session.speeds)} runs)"
    else:
        speed_part = "speed: waiting for first test…"

    return (
        f"[{ts}] elapsed {_fmt_duration(elapsed_sec)}"
        f" · left {_fmt_duration(remaining_sec)}"
        f" | ping {ping_part}"
        f" | {speed_part}"
        f" | samples ping={len(session.pings)} speed={len(session.speeds)}"
    )


def format_speed_result(result: SpeedResult) -> str:
    if result.error:
        return f"  speed test ERROR: {result.error}"
    server = f" ({result.server})" if result.server else ""
    return (
        f"  speed test done{server}: "
        f"↓ {_fmt_mbps(result.download_mbps)} Mbps"
        f"  ↑ {_fmt_mbps(result.upload_mbps)} Mbps"
        f"  ping {_fmt_ms(result.ping_ms)} ms"
    )


def format_session_banner(session_id: str, duration_hours: float, output_dir: str) -> str:
    return (
        f"ISP Truth Tester — session {session_id}\n"
        f"  duration {duration_hours}h · output {output_dir}\n"
        f"  logging current + average stats below (Ctrl+C to stop and save)\n"
    )
