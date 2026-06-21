from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import PingResult, SessionData, SessionMeta, SpeedResult, utc_now


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SessionStore:
    """Persists session data to JSON and a human-readable log."""

    def __init__(self, output_dir: Path, session_id: str | None = None) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if session_id is None:
            session_id = utc_now().strftime("%Y%m%d_%H%M%S")
        self.session_id = session_id
        self.json_path = self.output_dir / f"session_{session_id}.json"
        self.log_path = self.output_dir / f"session_{session_id}.log"

    def append_log(self, line: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")

    def save(self, session: SessionData) -> None:
        with self.json_path.open("w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2)

        self._rewrite_log(session)

    def log_ping(self, result: PingResult) -> None:
        if result.error:
            self.append_log(
                f"[{result.timestamp.isoformat()}] PING {result.target}: ERROR — {result.error}"
            )
        elif result.latency_ms is not None:
            self.append_log(
                f"[{result.timestamp.isoformat()}] PING {result.target}: "
                f"{result.latency_ms:.1f} ms (loss {result.packet_loss_pct:.0f}%)"
            )
        else:
            self.append_log(
                f"[{result.timestamp.isoformat()}] PING {result.target}: no response"
            )

    def log_speed(self, result: SpeedResult) -> None:
        if result.error:
            self.append_log(
                f"[{result.timestamp.isoformat()}] SPEED: ERROR — {result.error}"
            )
        else:
            dl = f"{result.download_mbps:.1f}" if result.download_mbps is not None else "—"
            ul = f"{result.upload_mbps:.1f}" if result.upload_mbps is not None else "—"
            ping = f"{result.ping_ms:.1f}" if result.ping_ms is not None else "—"
            server = f" via {result.server}" if result.server else ""
            self.append_log(
                f"[{result.timestamp.isoformat()}] SPEED: "
                f"↓{dl} Mbps  ↑{ul} Mbps  ping {ping} ms{server}"
            )

    def _rewrite_log(self, session: SessionData) -> None:
        lines = [
            "ISP Truth Tester — Session Log",
            f"Session ID: {self.session_id}",
            f"Started: {session.meta.started_at.isoformat()}",
            f"Duration target: {session.meta.duration_hours} h",
            f"Ping interval: {session.meta.ping_interval_sec} s",
            f"Speed interval: {session.meta.speed_interval_sec} s",
            f"Targets: {', '.join(session.meta.ping_targets)}",
            "",
        ]
        for p in session.pings:
            if p.error:
                lines.append(
                    f"[{p.timestamp.isoformat()}] PING {p.target}: ERROR — {p.error}"
                )
            elif p.latency_ms is not None:
                lines.append(
                    f"[{p.timestamp.isoformat()}] PING {p.target}: "
                    f"{p.latency_ms:.1f} ms (loss {p.packet_loss_pct:.0f}%)"
                )
        for s in session.speeds:
            if s.error:
                lines.append(f"[{s.timestamp.isoformat()}] SPEED: ERROR — {s.error}")
            else:
                dl = f"{s.download_mbps:.1f}" if s.download_mbps is not None else "—"
                ul = f"{s.upload_mbps:.1f}" if s.upload_mbps is not None else "—"
                ping = f"{s.ping_ms:.1f}" if s.ping_ms is not None else "—"
                lines.append(
                    f"[{s.timestamp.isoformat()}] SPEED: ↓{dl} ↑{ul} Mbps, ping {ping} ms"
                )

        if session.meta.ended_at:
            status = "completed" if session.meta.completed else "cancelled"
            lines.extend(
                [
                    "",
                    f"Ended: {session.meta.ended_at.isoformat()} ({status})",
                    f"Ping samples: {len(session.pings)}",
                    f"Speed samples: {len(session.speeds)}",
                ]
            )

        with self.log_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    @classmethod
    def load(cls, json_path: Path) -> SessionData:
        with json_path.open(encoding="utf-8") as f:
            raw: dict[str, Any] = json.load(f)

        meta_raw = raw["meta"]
        meta = SessionMeta(
            started_at=_parse_ts(meta_raw["started_at"]),
            duration_hours=meta_raw["duration_hours"],
            ping_interval_sec=meta_raw["ping_interval_sec"],
            speed_interval_sec=meta_raw["speed_interval_sec"],
            ping_targets=meta_raw["ping_targets"],
            ended_at=_parse_ts(meta_raw["ended_at"]) if meta_raw.get("ended_at") else None,
            completed=meta_raw.get("completed", False),
            cancelled=meta_raw.get("cancelled", False),
        )

        pings = [
            PingResult(
                timestamp=_parse_ts(p["timestamp"]),
                target=p["target"],
                latency_ms=p.get("latency_ms"),
                packet_loss_pct=p.get("packet_loss_pct", 0),
                error=p.get("error"),
            )
            for p in raw.get("pings", [])
        ]

        speeds = [
            SpeedResult(
                timestamp=_parse_ts(s["timestamp"]),
                download_mbps=s.get("download_mbps"),
                upload_mbps=s.get("upload_mbps"),
                ping_ms=s.get("ping_ms"),
                server=s.get("server"),
                error=s.get("error"),
            )
            for s in raw.get("speeds", [])
        ]

        return SessionData(meta=meta, pings=pings, speeds=speeds)
