from __future__ import annotations

import signal
import sys
import threading
import time
from pathlib import Path

from .display import format_session_banner, format_speed_result, format_status_line
from .models import SessionData, SessionMeta, utc_now
from .ping_test import run_pings
from .report import generate_report, report_path_for_session
from .speed_test import run_speed_test
from .storage import SessionStore

_STATUS_HEARTBEAT_SEC = 10


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
        self._signal_received: int | None = None
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
        if not self.quiet:
            print(
                format_session_banner(
                    self._store.session_id,
                    duration_hours,
                    str(self._store.output_dir),
                ),
                file=sys.stderr,
                end="",
            )

    def _log(self, msg: str) -> None:
        if not self.quiet:
            print(msg, file=sys.stderr, flush=True)

    def _print_status(
        self,
        *,
        elapsed_sec: float,
        remaining_sec: float,
        speed_running: bool = False,
    ) -> None:
        if self.quiet:
            return
        line = format_status_line(
            self.session,
            elapsed_sec=elapsed_sec,
            remaining_sec=remaining_sec,
            speed_running=speed_running,
        )
        print(line, file=sys.stderr, flush=True)

    def _handle_signal(self, signum: int, _frame: object) -> None:
        self._stop_requested = True
        self._signal_received = signum

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
        next_status = start
        speed_lock = threading.Lock()
        speed_running = False

        def run_speed_async() -> None:
            nonlocal speed_running
            result = run_speed_test()
            with speed_lock:
                self.session.speeds.append(result)
                self._store.log_speed(result)
                self._store.save(self.session)
                elapsed = time.monotonic() - start
                self._log(format_speed_result(result))
                self._print_status(
                    elapsed_sec=elapsed,
                    remaining_sec=self.duration_sec - elapsed,
                )
            speed_running = False

        while not self._stop_requested:
            elapsed = time.monotonic() - start
            if elapsed >= self.duration_sec:
                break
            remaining = self.duration_sec - elapsed

            now = time.monotonic()

            if now >= next_ping:
                for result in run_pings(self.ping_targets):
                    self.session.pings.append(result)
                    self._store.log_ping(result)
                self._store.save(self.session)
                next_ping = now + self.ping_interval_sec
                self._print_status(
                    elapsed_sec=elapsed,
                    remaining_sec=remaining,
                    speed_running=speed_running,
                )
                next_status = now + _STATUS_HEARTBEAT_SEC

            if now >= next_speed and not speed_running:
                speed_running = True
                next_speed = now + self.speed_interval_sec
                self._log("  starting speed test…")
                self._print_status(
                    elapsed_sec=elapsed,
                    remaining_sec=remaining,
                    speed_running=True,
                )
                threading.Thread(target=run_speed_async, daemon=True).start()

            if not self.quiet and now >= next_status:
                self._print_status(
                    elapsed_sec=elapsed,
                    remaining_sec=remaining,
                    speed_running=speed_running,
                )
                next_status = now + _STATUS_HEARTBEAT_SEC

            sleep_until = min(next_ping, next_speed, start + self.duration_sec)
            if not self.quiet:
                sleep_until = min(sleep_until, next_status)
            delay = max(0.0, sleep_until - time.monotonic())
            if delay > 0:
                end_sleep = time.monotonic() + delay
                while time.monotonic() < end_sleep and not self._stop_requested:
                    time.sleep(min(0.5, end_sleep - time.monotonic()))

        # Wait for an in-flight speed test so its result is captured
        while speed_running:
            time.sleep(0.2)

        if self._signal_received is not None:
            self._log(f"\nReceived signal {self._signal_received}, finishing up…")

        completed = not self._stop_requested
        json_path, report_path = self._finalize(completed=completed)
        if not self.quiet:
            status = "completed" if completed else "stopped early"
            self._log(f"\nSession {status}.")
            self._log(f"  data:   {json_path}")
            self._log(f"  report: {report_path}")
        return json_path, report_path
