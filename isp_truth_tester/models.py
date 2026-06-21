from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PingResult:
    timestamp: datetime
    target: str
    latency_ms: float | None
    packet_loss_pct: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class SpeedResult:
    timestamp: datetime
    download_mbps: float | None
    upload_mbps: float | None
    ping_ms: float | None
    server: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


@dataclass
class SessionMeta:
    started_at: datetime
    duration_hours: float
    ping_interval_sec: int
    speed_interval_sec: int
    ping_targets: list[str]
    ended_at: datetime | None = None
    completed: bool = False
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["started_at"] = self.started_at.isoformat()
        d["ended_at"] = self.ended_at.isoformat() if self.ended_at else None
        return d


@dataclass
class SessionData:
    meta: SessionMeta
    pings: list[PingResult] = field(default_factory=list)
    speeds: list[SpeedResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta.to_dict(),
            "pings": [p.to_dict() for p in self.pings],
            "speeds": [s.to_dict() for s in self.speeds],
        }
