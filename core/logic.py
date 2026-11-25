"""Core business logic: schedules, statuses, summaries and warnings."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import mean

SOON_DAYS = 2             # "Due soon" window
LARGE_WATER_ML = 2000     # single watering above this is flagged
ANOMALY_WINDOW_DAYS = 30  # only recent log entries raise anomaly warnings
TREND_WEEKS = 8
STATUS_ORDER = ["Overdue", "Due today", "Due soon", "OK"]


def next_due(plant) -> date:
    return date.fromisoformat(plant.last_watered) + timedelta(days=plant.watering_interval_days)


def days_until_due(plant, today: date) -> int:
    return (next_due(plant) - today).days


def status(plant, today: date) -> str:
    d = days_until_due(plant, today)
    if d < 0:
        return "Overdue"
    if d == 0:
        return "Due today"
    if d <= SOON_DAYS:
        return "Due soon"
    return "OK"


def plant_rows(plants, today: date) -> list[dict]:
    """Table-friendly rows, most urgent first."""
    rows = [
        {
            "ID": p.id,
            "Name": p.name,
            "Species": p.species,
            "Category": p.category,
            "Location": p.location,
            "Interval (days)": p.watering_interval_days,
            "Last watered": p.last_watered,
            "Next due": next_due(p).isoformat(),
            "Days until due": days_until_due(p, today),
            "Status": status(p, today),
        }
        for p in plants
    ]
    rows.sort(key=lambda r: (r["Days until due"], r["Name"].lower()))
    return rows


def _watering_dates(logs) -> dict[str, list[date]]:
    by_plant: dict[str, list[date]] = defaultdict(list)
    for l in logs:
        if l.action == "Watered":
            by_plant[l.plant_id].append(date.fromisoformat(l.date))
    for dates in by_plant.values():
        dates.sort()
    return by_plant


def summary(plants, logs, today: date) -> dict:
    """Aggregate metrics for the summary page and reports."""
    status_counts = Counter(status(p, today) for p in plants)
    category_counts = Counter(p.category for p in plants)
    watering = _watering_dates(logs)

    gaps = [
        (b - a).days
        for dates in watering.values()
        for a, b in zip(dates, dates[1:])
    ]

    log_counts = Counter(l.plant_id for l in logs)
    per_plant = sorted(((p.name, log_counts.get(p.id, 0)) for p in plants), key=lambda t: (-t[1], t[0].lower()))
    most = per_plant[0] if per_plant else None
    least = min(per_plant, key=lambda t: (t[1], t[0].lower())) if per_plant else None

    all_watering = [d for dates in watering.values() for d in dates]
    last7 = sum(1 for d in all_watering if 0 <= (today - d).days < 7)
    last30 = sum(1 for d in all_watering if 0 <= (today - d).days < 30)

    trend = []
    for k in reversed(range(TREND_WEEKS)):
        end = today - timedelta(days=7 * k)
        start = end - timedelta(days=6)
        trend.append((start.strftime("%d %b"), sum(1 for d in all_watering if start <= d <= end)))

    volumes = [l.water_ml for l in logs if l.action == "Watered" and l.water_ml]
    return {
        "total_plants": len(plants),
        "total_logs": len(logs),
        "status_counts": {s: status_counts.get(s, 0) for s in STATUS_ORDER},
        "category_counts": dict(sorted(category_counts.items())),
        "intervals": [p.watering_interval_days for p in plants],
        "avg_interval_days": round(mean(p.watering_interval_days for p in plants), 1) if plants else None,
        "avg_gap_days": round(mean(gaps), 1) if gaps else None,
        "waterings_last_7": last7,
        "waterings_last_30": last30,
        "avg_water_ml": round(mean(volumes)) if volumes else None,
        "total_water_ml": sum(volumes),
        "most_cared": most,
        "least_cared": least,
        "weekly_trend": trend,
    }


def anomalies(plants, logs, today: date) -> list[dict]:
    """Threshold warnings: overdue plants, suspicious watering patterns, huge volumes."""
    out: list[dict] = []
    cutoff = today - timedelta(days=ANOMALY_WINDOW_DAYS)
    by_plant = defaultdict(list)
    for l in logs:
        if l.action == "Watered":
            by_plant[l.plant_id].append(l)

    for p in plants:
        until = days_until_due(p, today)
        if until < 0:
            over = -until
            severity = "critical" if over >= p.watering_interval_days else "warning"
            out.append({
                "severity": severity, "plant": p.name, "type": "Overdue",
                "message": f"{p.name} is {over} day(s) overdue for watering (was due {next_due(p).isoformat()}).",
            })
        entries = sorted(by_plant.get(p.id, []), key=lambda l: l.date)
        for prev, cur in zip(entries, entries[1:]):
            if date.fromisoformat(cur.date) < cutoff:
                continue
            gap = (date.fromisoformat(cur.date) - date.fromisoformat(prev.date)).days
            if gap == 0 or (p.watering_interval_days >= 4 and gap < 0.25 * p.watering_interval_days):
                out.append({
                    "severity": "warning", "plant": p.name, "type": "Over-watering?",
                    "message": (f"{p.name} was watered twice within {gap} day(s) "
                                f"({prev.date} and {cur.date}); its interval is {p.watering_interval_days} days."),
                })
        for l in entries:
            if l.water_ml and l.water_ml > LARGE_WATER_ML and date.fromisoformat(l.date) >= cutoff:
                out.append({
                    "severity": "warning", "plant": p.name, "type": "Large volume",
                    "message": f"{p.name} received {l.water_ml} ml on {l.date} (limit {LARGE_WATER_ML} ml).",
                })
    out.sort(key=lambda w: (w["severity"] != "critical", w["plant"].lower()))
    return out
