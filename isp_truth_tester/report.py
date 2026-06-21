from __future__ import annotations

import html
from pathlib import Path

from .models import SessionData
from .stats import (
    PingStats,
    SpeedStats,
    compute_ping_stats,
    compute_speed_stats,
    fmt_stat,
)


def _esc(value: object) -> str:
    return html.escape(str(value))


def _stat_card(label: str, stat_text: str, accent: str) -> str:
    return f"""
    <div class="stat-card" style="--accent: {accent}">
      <div class="stat-label">{_esc(label)}</div>
      <div class="stat-value">{stat_text}</div>
    </div>"""


def _chart_svg(
    points: list[tuple[str, float]],
    label: str,
    color: str,
    height: int = 140,
    width: int = 800,
) -> str:
    if len(points) < 2:
        return f'<p class="muted">Not enough data for {label} chart.</p>'

    values = [v for _, v in points]
    vmin, vmax = min(values), max(values)
    pad = (vmax - vmin) * 0.1 or 1
    ymin, ymax = vmin - pad, vmax + pad
    inner_w = width - 48
    inner_h = height - 32

    def x_at(i: int) -> float:
        return 40 + (i / (len(points) - 1)) * inner_w

    def y_at(v: float) -> float:
        ratio = (v - ymin) / (ymax - ymin)
        return 16 + inner_h * (1 - ratio)

    poly = " ".join(f"{x_at(i):.1f},{y_at(v):.1f}" for i, (_, v) in enumerate(points))

    y_labels = ""
    for i in range(4):
        val = ymin + (ymax - ymin) * i / 3
        y = y_at(val)
        y_labels += (
            f'<text x="36" y="{y + 4:.1f}" class="axis" text-anchor="end">'
            f"{val:.0f}</text>"
        )

    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{_esc(label)} over time">
      <line x1="40" y1="{16 + inner_h}" x2="{40 + inner_w}" y2="{16 + inner_h}" class="axis-line"/>
      {y_labels}
      <polyline points="{poly}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>
    </svg>"""


def generate_report(session: SessionData, output_path: Path) -> Path:
    ping_stats: PingStats = compute_ping_stats(session.pings)
    speed_stats: SpeedStats = compute_speed_stats(session.speeds)

    status = "Completed"
    status_class = "badge-ok"
    if session.meta.cancelled:
        status = "Stopped early"
        status_class = "badge-warn"
    elif not session.meta.completed:
        status = "In progress"
        status_class = "badge-neutral"

    ping_points = [
        (p.timestamp.isoformat(), p.latency_ms)
        for p in session.pings
        if p.latency_ms is not None
    ]
    dl_points = [
        (s.timestamp.isoformat(), s.download_mbps)
        for s in session.speeds
        if s.download_mbps is not None
    ]
    ul_points = [
        (s.timestamp.isoformat(), s.upload_mbps)
        for s in session.speeds
        if s.upload_mbps is not None
    ]

    ping_chart = _chart_svg(ping_points, "Latency", "#38bdf8")
    dl_chart = _chart_svg(dl_points, "Download", "#34d399")
    ul_chart = _chart_svg(ul_points, "Upload", "#a78bfa")

    started = session.meta.started_at.strftime("%b %d, %Y %H:%M UTC")
    ended = (
        session.meta.ended_at.strftime("%b %d, %Y %H:%M UTC")
        if session.meta.ended_at
        else "—"
    )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>ISP Truth Tester Report</title>
  <style>
    :root {{
      --bg: #0b1120;
      --surface: #111827;
      --border: #1f2937;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --ok: #34d399;
      --warn: #fbbf24;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
      background: radial-gradient(ellipse at top, #111827 0%, var(--bg) 55%);
      color: var(--text);
      line-height: 1.5;
      padding: 2rem 1rem 3rem;
    }}
    .wrap {{ max-width: 960px; margin: 0 auto; }}
    h1 {{ font-size: 1.75rem; margin: 0 0 .25rem; letter-spacing: -0.02em; }}
    .subtitle {{ color: var(--muted); margin-bottom: 1.5rem; }}
    .badge {{
      display: inline-block;
      padding: .2rem .6rem;
      border-radius: 999px;
      font-size: .75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .04em;
    }}
    .badge-ok {{ background: rgba(52,211,153,.15); color: var(--ok); }}
    .badge-warn {{ background: rgba(251,191,36,.15); color: var(--warn); }}
    .badge-neutral {{ background: rgba(156,163,175,.15); color: var(--muted); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: .75rem;
      margin: 1rem 0 1.5rem;
    }}
    .stat-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      border-top: 3px solid var(--accent, #38bdf8);
    }}
    .stat-label {{
      font-size: .75rem;
      text-transform: uppercase;
      letter-spacing: .06em;
      color: var(--muted);
      margin-bottom: .35rem;
    }}
    .stat-value {{ font-size: .95rem; font-weight: 500; }}
    section {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 1.25rem;
      margin-bottom: 1rem;
    }}
    section h2 {{
      margin: 0 0 1rem;
      font-size: 1.1rem;
    }}
    .chart {{ width: 100%; height: auto; display: block; }}
    .axis {{ fill: var(--muted); font-size: 10px; }}
    .axis-line {{ stroke: var(--border); }}
    .muted {{ color: var(--muted); font-size: .9rem; }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 1rem 2rem;
      font-size: .875rem;
      color: var(--muted);
      margin-top: .5rem;
    }}
    footer {{
      margin-top: 2rem;
      text-align: center;
      color: var(--muted);
      font-size: .8rem;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <span class="badge {status_class}">{_esc(status)}</span>
    <h1>ISP Truth Tester</h1>
    <p class="subtitle">Internet speed &amp; latency monitoring report</p>

    <div class="meta">
      <span>Started: {_esc(started)}</span>
      <span>Ended: {_esc(ended)}</span>
      <span>Duration target: {_esc(session.meta.duration_hours)} h</span>
      <span>Ping samples: {len(session.pings)}</span>
      <span>Speed samples: {len(session.speeds)}</span>
    </div>

    <section>
      <h2>Latency (ping)</h2>
      <div class="grid">
        {_stat_card("Latency", fmt_stat(ping_stats.latency, " ms"), "#38bdf8")}
        {_stat_card("Packet loss", fmt_stat(ping_stats.packet_loss, "%", 0), "#f472b6")}
        {_stat_card("Failed pings", str(ping_stats.errors), "#fb7185")}
      </div>
      {ping_chart}
    </section>

    <section>
      <h2>Speed</h2>
      <div class="grid">
        {_stat_card("Download", fmt_stat(speed_stats.download, " Mbps"), "#34d399")}
        {_stat_card("Upload", fmt_stat(speed_stats.upload, " Mbps"), "#a78bfa")}
        {_stat_card("Speedtest ping", fmt_stat(speed_stats.ping, " ms"), "#38bdf8")}
        {_stat_card("Failed tests", str(speed_stats.errors), "#fb7185")}
      </div>
      {dl_chart}
      <div style="height:.75rem"></div>
      {ul_chart}
    </section>

    <footer>Generated by ISP Truth Tester</footer>
  </div>
</body>
</html>"""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(doc, encoding="utf-8")
    return output_path


def report_path_for_session(json_path: Path) -> Path:
    return json_path.with_name(json_path.stem + "_report.html")
