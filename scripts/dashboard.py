from __future__ import annotations

import argparse
import html
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    index = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
    return float(items[index])


def parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def load_records(path: Path, *, minutes: int) -> tuple[list[dict[str, Any]], datetime]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes)
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records, now
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        timestamp = parse_timestamp(record.get("ts", ""))
        if timestamp is not None and timestamp >= start:
            record["_timestamp"] = timestamp
            records.append(record)
    return records, now


def minute_buckets(now: datetime, count: int) -> list[datetime]:
    end = now.replace(second=0, microsecond=0)
    start = end - timedelta(minutes=count - 1)
    return [start + timedelta(minutes=index) for index in range(count)]


def group_by_minute(
    records: list[dict[str, Any]], buckets: list[datetime]
) -> list[list[dict[str, Any]]]:
    positions = {bucket: index for index, bucket in enumerate(buckets)}
    grouped: list[list[dict[str, Any]]] = [[] for _ in buckets]
    for record in records:
        minute = record["_timestamp"].replace(second=0, microsecond=0)
        if minute in positions:
            grouped[positions[minute]].append(record)
    return grouped


def numeric(records: list[dict[str, Any]], field: str) -> list[float]:
    return [
        float(record[field])
        for record in records
        if isinstance(record.get(field), (int, float))
    ]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def fmt(value: float, decimals: int = 1) -> str:
    if math.isclose(value, round(value)):
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"


def svg_chart(
    series: list[tuple[str, str, list[float | None]]],
    thresholds: list[tuple[str, float, str]],
    *,
    unit: str,
) -> str:
    width, height = 760, 220
    left, right, top, bottom = 58, 18, 18, 34
    plot_width = width - left - right
    plot_height = height - top - bottom
    values = [value for _, _, points in series for value in points if value is not None]
    values.extend(value for _, value, _ in thresholds)
    y_max = max(values, default=1.0)
    y_max = 1.0 if y_max <= 0 else y_max * 1.12
    point_count = max((len(points) for _, _, points in series), default=1)

    def x_pos(index: int) -> float:
        return left + (index / max(1, point_count - 1)) * plot_width

    def y_pos(value: float) -> float:
        return top + plot_height - (value / y_max) * plot_height

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img">']
    for step in range(5):
        value = y_max * step / 4
        y = y_pos(value)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" '
            'class="grid" />'
        )
        parts.append(
            f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" class="axis">'
            f"{html.escape(fmt(value))}</text>"
        )
    for label, value, color in thresholds:
        y = y_pos(value)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" '
            f'stroke="{color}" class="threshold" />'
        )
        parts.append(
            f'<text x="{width-right-4}" y="{max(12, y-5):.1f}" text-anchor="end" '
            f'fill="{color}" class="threshold-label">{html.escape(label)} {fmt(value)}</text>'
        )
    for label, color, points in series:
        segments: list[list[tuple[float, float]]] = []
        current: list[tuple[float, float]] = []
        for index, value in enumerate(points):
            if value is None:
                if current:
                    segments.append(current)
                    current = []
                continue
            current.append((x_pos(index), y_pos(value)))
        if current:
            segments.append(current)
        for segment in segments:
            coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in segment)
            parts.append(f'<polyline points="{coords}" stroke="{color}" class="series" />')
    parts.append(f'<text x="{left}" y="{height-8}" class="axis">-60 min</text>')
    parts.append(
        f'<text x="{width-right}" y="{height-8}" text-anchor="end" class="axis">now</text>'
    )
    parts.append(
        f'<text x="{left}" y="12" class="axis unit-label">{html.escape(unit)}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def panel(
    *,
    title: str,
    value: str,
    detail: str,
    chart: str,
    legends: list[tuple[str, str]],
    unit: str,
    threshold: str,
) -> str:
    legend_html = "".join(
        f'<span><i style="background:{color}"></i>{html.escape(label)}</span>'
        for label, color in legends
    )
    return f"""
    <section class="panel">
      <header><div><h2>{html.escape(title)}</h2><p>{html.escape(detail)}</p></div>
      <div class="metric">{html.escape(value)}</div></header>
      {chart}
      <footer><div class="legend">{legend_html}</div>
      <span>{html.escape(unit)} · {html.escape(threshold)}</span></footer>
    </section>"""


def build_dashboard(records: list[dict[str, Any]], now: datetime, config: dict) -> str:
    dashboard = config["dashboard"]
    minutes = int(dashboard["time_range_minutes"])
    panels = {item["id"]: item for item in dashboard["panels"]}
    buckets = minute_buckets(now, minutes)
    grouped = group_by_minute(records, buckets)
    responses = [record for record in records if record.get("event") == "response_sent"]
    requests = [record for record in records if record.get("event") == "request_received"]
    failures = [record for record in records if record.get("event") == "request_failed"]
    tool_events = [record for record in records if isinstance(record.get("tool_success"), bool)]

    latency_values = numeric(responses, "latency_ms")
    ttft_values = numeric(responses, "ttft_ms")
    latency_series: dict[str, list[float | None]] = defaultdict(list)
    for bucket in grouped:
        items = [record for record in bucket if record.get("event") == "response_sent"]
        latencies = numeric(items, "latency_ms")
        ttfts = numeric(items, "ttft_ms")
        for key, p in (("P50", 50), ("P95", 95), ("P99", 99)):
            latency_series[key].append(percentile(latencies, p) if latencies else None)
        latency_series["TTFT P95"].append(percentile(ttfts, 95) if ttfts else None)
    latency_colors = {"P50": "#38bdf8", "P95": "#f59e0b", "P99": "#ef4444", "TTFT P95": "#a78bfa"}
    latency_threshold = float(panels["latency"]["threshold"]["value"])

    traffic_series = [
        float(sum(record.get("event") == "request_received" for record in bucket))
        for bucket in grouped
    ]
    traffic_threshold = float(panels["traffic"]["threshold"]["value"])

    error_rates: list[float | None] = []
    retrieval_rates: list[float | None] = []
    for bucket in grouped:
        received = sum(record.get("event") == "request_received" for record in bucket)
        failed = sum(record.get("event") == "request_failed" for record in bucket)
        tools = [record for record in bucket if isinstance(record.get("tool_success"), bool)]
        error_rates.append((failed / received * 100) if received else None)
        retrieval_rates.append(
            (sum(record["tool_success"] for record in tools) / len(tools) * 100)
            if tools
            else None
        )
    error_rate = len(failures) / len(requests) * 100 if requests else 0.0
    retrieval_rate = (
        sum(record["tool_success"] for record in tool_events) / len(tool_events) * 100
        if tool_events
        else 0.0
    )
    error_threshold = float(panels["errors"]["threshold"]["value"])

    cost_series = [
        sum(numeric([record for record in bucket if record.get("event") == "response_sent"], "cost_usd"))
        for bucket in grouped
    ]
    total_cost = sum(numeric(responses, "cost_usd"))
    cost_threshold = float(panels["cost"]["threshold"]["value"])

    tokens_in_series: list[float] = []
    tokens_out_series: list[float] = []
    for bucket in grouped:
        items = [record for record in bucket if record.get("event") == "response_sent"]
        tokens_in_series.append(sum(numeric(items, "tokens_in")))
        tokens_out_series.append(sum(numeric(items, "tokens_out")))
    tokens_in_total = sum(numeric(responses, "tokens_in"))
    tokens_out_total = sum(numeric(responses, "tokens_out"))
    token_threshold = float(panels["tokens"]["threshold"]["value"])

    quality_series: list[float | None] = []
    for bucket in grouped:
        items = [record for record in bucket if record.get("event") == "response_sent"]
        quality = numeric(items, "quality_score")
        quality_series.append(mean(quality) if quality else None)
    quality_values = numeric(responses, "quality_score")
    quality_threshold = float(panels["quality"]["threshold"]["value"])

    cards = [
        panel(
            title=panels["latency"]["title"],
            value=f"P95 {fmt(percentile(latency_values, 95))} ms",
            detail=f"P50 {fmt(percentile(latency_values, 50))} · P99 {fmt(percentile(latency_values, 99))} · TTFT P95 {fmt(percentile(ttft_values, 95))}",
            chart=svg_chart(
                [(name, latency_colors[name], latency_series[name]) for name in latency_colors],
                [("SLO", latency_threshold, "#fb7185")],
                unit="ms",
            ),
            legends=[(name, latency_colors[name]) for name in latency_colors],
            unit="milliseconds",
            threshold=f"P95 ≤ {fmt(latency_threshold)} ms",
        ),
        panel(
            title=panels["traffic"]["title"],
            value=f"{len(requests)} requests",
            detail=f"{fmt(len(requests) / minutes, 2)} requests/min over the selected window",
            chart=svg_chart(
                [("Requests/min", "#38bdf8", traffic_series)],
                [("minimum", traffic_threshold, "#f59e0b")],
                unit="requests/min",
            ),
            legends=[("Requests/min", "#38bdf8")],
            unit="requests per minute",
            threshold=f"rate ≥ {fmt(traffic_threshold)}",
        ),
        panel(
            title=panels["errors"]["title"],
            value=f"{fmt(error_rate)}% errors",
            detail=f"Retrieval success {fmt(retrieval_rate)}% · {len(failures)} failed requests",
            chart=svg_chart(
                [
                    ("Error rate", "#ef4444", error_rates),
                    ("Retrieval success", "#22c55e", retrieval_rates),
                ],
                [("error max", error_threshold, "#fb7185"), ("retrieval min", 90, "#f59e0b")],
                unit="percent",
            ),
            legends=[("Error rate", "#ef4444"), ("Retrieval success", "#22c55e")],
            unit="percent",
            threshold=f"errors ≤ {fmt(error_threshold)}%; retrieval ≥ 90%",
        ),
        panel(
            title=panels["cost"]["title"],
            value=f"${total_cost:.4f}",
            detail="Estimated cost summed from response_sent events",
            chart=svg_chart(
                [("Cost/min", "#f59e0b", cost_series)],
                [("window max", cost_threshold, "#fb7185")],
                unit="USD",
            ),
            legends=[("Cost/min", "#f59e0b")],
            unit="USD",
            threshold=f"60-minute total ≤ ${cost_threshold:.2f}",
        ),
        panel(
            title=panels["tokens"]["title"],
            value=f"{fmt(tokens_in_total + tokens_out_total)} tokens",
            detail=f"Input {fmt(tokens_in_total)} · Output {fmt(tokens_out_total)}",
            chart=svg_chart(
                [
                    ("Input", "#38bdf8", tokens_in_series),
                    ("Output", "#a78bfa", tokens_out_series),
                ],
                [("window max", token_threshold, "#fb7185")],
                unit="tokens",
            ),
            legends=[("Input", "#38bdf8"), ("Output", "#a78bfa")],
            unit="tokens",
            threshold=f"total ≤ {fmt(token_threshold)}",
        ),
        panel(
            title=panels["quality"]["title"],
            value=f"{mean(quality_values):.2f}",
            detail=f"Mean quality proxy from {len(quality_values)} responses",
            chart=svg_chart(
                [("Quality", "#22c55e", quality_series)],
                [("minimum", quality_threshold, "#f59e0b")],
                unit="score 0–1",
            ),
            legends=[("Quality", "#22c55e")],
            unit="score 0 to 1",
            threshold=f"mean ≥ {quality_threshold:.2f}",
        ),
    ]

    generated = now.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    refresh = int(dashboard["refresh_seconds"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="{refresh}">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(dashboard['title'])}</title>
<style>
:root{{--bg:#07111f;--card:#0f1d30;--border:#223550;--text:#e6edf7;--muted:#8fa3bd}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(145deg,#07111f,#0b1627);color:var(--text);font:14px Inter,Segoe UI,sans-serif}}
main{{max-width:1560px;margin:auto;padding:28px}} .top{{display:flex;justify-content:space-between;align-items:end;margin-bottom:22px}}
h1{{font-size:28px;margin:0 0 6px}} .top p,.panel p{{color:var(--muted);margin:0}} .status{{text-align:right;line-height:1.7}}
.status b{{color:#22c55e}} .grid-layout{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}
.panel{{background:rgba(15,29,48,.94);border:1px solid var(--border);border-radius:14px;padding:18px;box-shadow:0 14px 35px #0004}}
.panel header{{display:flex;justify-content:space-between;gap:16px;align-items:start}} h2{{font-size:16px;margin:0 0 5px}} .metric{{font-size:22px;font-weight:700;white-space:nowrap}}
svg{{width:100%;height:auto;margin-top:12px}} .grid{{stroke:#263a55;stroke-width:1}} .axis{{fill:#7f93ad;font-size:10px}} .series{{fill:none;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}} .threshold{{stroke-width:1.5;stroke-dasharray:6 5}} .threshold-label{{font-size:10px;font-weight:600}}
.panel footer{{display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:12px;align-items:center}} .legend{{display:flex;gap:12px;flex-wrap:wrap}} .legend span{{display:flex;align-items:center;gap:5px}} .legend i{{width:9px;height:9px;border-radius:50%}}
@media(max-width:900px){{.grid-layout{{grid-template-columns:1fr}}.top{{align-items:start;flex-direction:column;gap:10px}}.status{{text-align:left}}}}
</style></head><body><main>
<div class="top"><div><h1>{html.escape(dashboard['title'])}</h1><p>Source: data/logs.jsonl · Time range: last {minutes} minutes · Auto-refresh: {refresh} seconds</p></div>
<div class="status"><b>● LIVE</b><br>{html.escape(generated)} · {len(records)} log events</div></div>
<div class="grid-layout">{''.join(cards)}</div>
</main></body></html>"""


def render() -> str:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    minutes = int(config["dashboard"]["time_range_minutes"])
    records, now = load_records(LOG_PATH, minutes=minutes)
    return build_dashboard(records, now, config)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        payload = render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the six-panel LLMOps dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--check", action="store_true", help="Render once and validate output")
    args = parser.parse_args()
    if args.check:
        output = render()
        expected = ["Latency", "Traffic", "Error", "Cost", "Token", "Quality"]
        missing = [name for name in expected if name.lower() not in output.lower()]
        if missing:
            print(f"Dashboard render failed; missing: {', '.join(missing)}")
            return 1
        print(f"Dashboard render OK: 6 panels, {len(output):,} HTML bytes")
        return 0
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard: http://{args.host}:{args.port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
