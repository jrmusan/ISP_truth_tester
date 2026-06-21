from __future__ import annotations

import signal
import sys
import threading
import time
from pathlib import Path

from .models import SessionData, SessionMeta, utc_now
from .ping_test import run_pings
from .report import generate_report, report_path_for_session
from .speed_test import run_speed_test
from .storage import SessionStore


class MonitorRunner:
    """Runs ping and speed tests for a configured duration."""

    def __init__(
        self,
        duration_hours: float,
        ping_interval_sec: int,
        speed_interval_sec: int,
        ping_targets: list[str],
        output_dir: Path,
        quiet: bool = True,
    ) -> None:
        if not 1 <= duration_hours <= 24:
            raise ValueError("duration must be between 1 and 24 hours")

        self.duration_sec = duration_hours * 3600
        self.ping_interval_sec = ping_interval_sec
        self.speed_interval_sec = speed_interval_sec
        self.ping_targets = ping_targets
        self.quiet = quiet

        self._stop_requested = False
        self._store = SessionStore(output_dir)
        self.session = SessionData(
            meta=SessionMeta(
                started_at=utc_now(),
                duration_hours=duration_hours,
                ping_interval_sec=ping_interval_sec,
                speed_interval_sec=speed_interval_sec,
                ping_targets=ping_targets,
            )
        )

        self._store.save(self.session)
        self._log(f"Session {self._store.session_id} started")

    def _log(self, msg: str) -> None:
        if not self.quiet:
            print(msg, file=sys.stderr)

    def _handle_signal(self, signum: int, _frame: object) -> None:
        self._stop_requested = True
        self._log(f"\nReceived signal {signum}, finishing up…")

    def _finalize(self, *, completed: bool) -> tuple[Path, Path]:
        self.session.meta.ended_at = utc_now()
        self.session.meta.completed = completed
        self.session.meta.cancelled = not completed
        self._store.save(self.session)

        report_path = report_path_for_session(self._store.json_path)
        generate_report(self.session, report_path)
        return self._store.json_path, report_path

    def run(self) -> tuple[Path, Path]:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        start = time.monotonic()
        next_ping = start
        next_speed = start
        speed_lock = threading.Lock()
        speed_running = False

        def run_speed_async() -> None:
            nonlocal speed_running
            result = run_speed_test()
            with speed_lock:
                self.session.speeds.append(result)
                self._store.log_speed(result)
                self._store.save(self.session)
            speed_running = False

        while not self._stop_requested:
            elapsed = time.monotonic() - start
            if elapsed >= self.duration_sec:
                break

            now = time.monotonic()

            if now >= next_ping:
                for result in run_pings(self.ping_targets):
                    self.session.pings.append(result)
                    self._store.log_ping(result)
                self._store.save(self.session)
                next_ping = now + self.ping_interval_sec

            if now >= next_speed and not speed_running:
                speed_running = True
                next_speed = now + self.speed_interval_sec
                threading.Thread(target=run_speed_async, daemon=True).start()

            sleep_until = min(next_ping, next_speed, start + self.duration_sec)
            delay = max(0.0, sleep_until - time.monotonic())
            if delay > 0:
                end_sleep = time.monotonic() + delay
                while time.monotonic() < end_sleep and not self._stop_requested:
                    time.sleep(min(0.5, end_sleep - time.monotonic()))

        # Wait for an in-flight speed test so its result is captured
        while speed_running:
            time.sleep(0.2)

        completed = not self._stop_requested
        return self._finalize(completed=completed)
