"""Export builders: Markdown summary, plain-text audit log, CSV files."""
from __future__ import annotations

import csv
import io
from datetime import date

from . import logic


def _safe_cell(value):
    """Neutralise spreadsheet formula injection in exported text cells."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def _md(text) -> str:
    return str(text).replace("|", "\\|")


def build_markdown(summary: dict, rows: list[dict], warnings: list[dict], today: date) -> str:
    s = summary
    lines = [
        "# Plant Care Log - Summary Report",
        "",
        f"_Generated {today.isoformat()}_",
        "",
        "## Key metrics",
        "",
        f"- Total plants: **{s['total_plants']}**",
        f"- Care entries logged: **{s['total_logs']}**",
        f"- Average watering interval: **{s['avg_interval_days'] if s['avg_interval_days'] is not None else 'n/a'}** days",
        f"- Average gap between logged waterings: **{s['avg_gap_days'] if s['avg_gap_days'] is not None else 'n/a'}** days",
        f"- Waterings in the last 7 / 30 days: **{s['waterings_last_7']} / {s['waterings_last_30']}**",
        f"- Total water logged: **{s['total_water_ml']} ml**",
    ]
    if s["most_cared"]:
        lines.append(f"- Most cared-for plant: **{s['most_cared'][0]}** ({s['most_cared'][1]} entries)")
    if s["least_cared"]:
        lines.append(f"- Least cared-for plant: **{s['least_cared'][0]}** ({s['least_cared'][1]} entries)")

    lines += ["", "## Status", "", "| Status | Plants |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in s["status_counts"].items()]

    lines += ["", "## Plants per category", "", "| Category | Plants |", "|---|---|"]
    lines += [f"| {_md(k)} | {v} |" for k, v in s["category_counts"].items()] or ["| - | 0 |"]

    lines += ["", "## Warnings", ""]
    if warnings:
        lines += [f"- **{w['severity'].upper()}** - {w['message']}" for w in warnings]
    else:
        lines.append("No warnings. All plants are on schedule.")

    lines += ["", "## Plants", "",
              "| Name | Category | Location | Interval | Last watered | Next due | Status |",
              "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {_md(r['Name'])} | {_md(r['Category'])} | {_md(r['Location'])} | {r['Interval (days)']} d | "
            f"{r['Last watered']} | {r['Next due']} | {r['Status']} |"
        )
    return "\n".join(lines) + "\n"


def build_text_audit(plants, logs, warnings: list[dict], today: date) -> str:
    names = {p.id: p.name for p in plants}
    out = [
        "PLANT CARE LOG - AUDIT",
        f"Generated: {today.isoformat()}",
        f"Plants: {len(plants)}   Entries: {len(logs)}",
        "=" * 72,
        "WARNINGS",
    ]
    out += [f"  [{w['severity'].upper():8}] {w['message']}" for w in warnings] or ["  none"]
    out += ["=" * 72, "CARE HISTORY (oldest first)",
            f"{'Date':<11}{'Plant':<24}{'Action':<12}{'Water':>8}  Notes"]
    for l in sorted(logs, key=lambda l: (l.date, l.id)):
        water = f"{l.water_ml} ml" if l.water_ml is not None else "-"
        out.append(f"{l.date:<11}{names.get(l.plant_id, '?')[:23]:<24}{l.action:<12}{water:>8}  {l.notes}")
    return "\n".join(out) + "\n"


def plants_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    fields = ["Name", "Species", "Category", "Location", "Interval (days)",
              "Last watered", "Next due", "Days until due", "Status"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: _safe_cell(r[k]) for k in fields})
    return buf.getvalue()


def logs_csv(plants, logs) -> str:
    names = {p.id: p.name for p in plants}
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Plant", "Action", "Water (ml)", "Notes"])
    for l in sorted(logs, key=lambda l: (l.date, l.id)):
        writer.writerow([l.date, _safe_cell(names.get(l.plant_id, "")), l.action,
                         "" if l.water_ml is None else l.water_ml, _safe_cell(l.notes)])
    return buf.getvalue()
