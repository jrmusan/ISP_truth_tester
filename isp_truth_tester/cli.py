from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .report import generate_report
from .storage import SessionStore


DEFAULT_TARGETS = ["1.1.1.1", "8.8.8.8"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="isp-truth-tester",
        description="Monitor internet speed and latency over time (Raspberry Pi friendly).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Start a monitoring session")
    run.add_argument(
        "--duration",
        type=float,
        required=True,
        metavar="HOURS",
        help="How long to run (1–24 hours)",
    )
    run.add_argument(
        "--ping-interval",
        type=int,
        default=30,
        metavar="SEC",
        help="Seconds between ping rounds (default: 30)",
    )
    run.add_argument(
        "--speed-interval",
        type=int,
        default=600,
        metavar="SEC",
        help="Seconds between speed tests (default: 600 / 10 min)",
    )
    run.add_argument(
        "--targets",
        nargs="+",
        default=DEFAULT_TARGETS,
        metavar="HOST",
        help="Hosts to ping (default: 1.1.1.1 8.8.8.8)",
    )
    run.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for logs, JSON, and HTML report (default: ./results)",
    )
    run.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress to stderr",
    )

    report = sub.add_parser("report", help="Regenerate HTML report from saved JSON")
    report.add_argument("json_file", type=Path, help="Path to session JSON file")
    report.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output HTML path (default: alongside JSON)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        from .runner import MonitorRunner

        if not 1 <= args.duration <= 24:
            parser.error("--duration must be between 1 and 24 hours")
        if args.ping_interval < 5:
            parser.error("--ping-interval must be at least 5 seconds")
        if args.speed_interval < 60:
            parser.error("--speed-interval must be at least 60 seconds")

        try:
            runner = MonitorRunner(
                duration_hours=args.duration,
                ping_interval_sec=args.ping_interval,
                speed_interval_sec=args.speed_interval,
                ping_targets=args.targets,
                output_dir=args.output_dir,
                quiet=not args.verbose,
            )
            json_path, report_path = runner.run()
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        return 0

    if args.command == "report":
        session = SessionStore.load(args.json_file)
        out = args.output
        if out is None:
            out = args.json_file.with_name(args.json_file.stem + "_report.html")
        generate_report(session, out)
        print(out)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
