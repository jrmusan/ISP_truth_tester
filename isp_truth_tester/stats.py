from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import PingResult, SpeedResult


@dataclass
class StatSummary:
    count: int
    minimum: float | None
    maximum: float | None
    average: float | None

    @property
    def has_data(self) -> bool:
        return self.count > 0 and self.average is not None


def _summarize(values: Sequence[float]) -> StatSummary:
    if not values:
        return StatSummary(count=0, minimum=None, maximum=None, average=None)
    return StatSummary(
        count=len(values),
        minimum=min(values),
        maximum=max(values),
        average=sum(values) / len(values),
    )


@dataclass
class PingStats:
    latency: StatSummary
    packet_loss: StatSummary
    errors: int


@dataclass
class SpeedStats:
    download: StatSummary
    upload: StatSummary
    ping: StatSummary
    errors: int


def compute_ping_stats(pings: Sequence[PingResult]) -> PingStats:
    latencies = [p.latency_ms for p in pings if p.latency_ms is not None]
    losses = [p.packet_loss_pct for p in pings]
    errors = sum(1 for p in pings if p.error or p.latency_ms is None)
    return PingStats(
        latency=_summarize(latencies),
        packet_loss=_summarize(losses),
        errors=errors,
    )


def compute_speed_stats(speeds: Sequence[SpeedResult]) -> SpeedStats:
    downloads = [s.download_mbps for s in speeds if s.download_mbps is not None]
    uploads = [s.upload_mbps for s in speeds if s.upload_mbps is not None]
    pings = [s.ping_ms for s in speeds if s.ping_ms is not None]
    errors = sum(1 for s in speeds if s.error)
    return SpeedStats(
        download=_summarize(downloads),
        upload=_summarize(uploads),
        ping=_summarize(pings),
        errors=errors,
    )


def fmt_stat(stat: StatSummary, unit: str = "", decimals: int = 1) -> str:
    if not stat.has_data:
        return "—"
    fmt = f"{{:.{decimals}f}}"
    return (
        f"min {fmt.format(stat.minimum)}{unit} · "
        f"avg {fmt.format(stat.average)}{unit} · "
        f"max {fmt.format(stat.maximum)}{unit}"
    )
