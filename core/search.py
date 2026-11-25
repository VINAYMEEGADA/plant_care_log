"""Keyword and category based retrieval."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from . import logic


def _tokens(keyword: str) -> list[str]:
    return [t for t in (keyword or "").lower().split() if t]


def filter_plants(plants, logs=(), keyword: str = "", categories=None, statuses=None, today: date | None = None):
    """All keyword tokens must appear somewhere in the plant's text or its log notes."""
    today = today or date.today()
    tokens = _tokens(keyword)
    log_text = defaultdict(list)
    for l in logs:
        log_text[l.plant_id].append(f"{l.action} {l.notes}")

    result = []
    for p in plants:
        if categories and p.category not in categories:
            continue
        if statuses and logic.status(p, today) not in statuses:
            continue
        if tokens:
            hay = " ".join([p.name, p.species, p.category, p.location, p.notes, *log_text.get(p.id, [])]).lower()
            if not all(t in hay for t in tokens):
                continue
        result.append(p)
    return result


def search_logs(logs, plants, keyword: str = "", actions=None, start: date | None = None, end: date | None = None):
    """Return care-log rows (newest first) matching the filters."""
    names = {p.id: p.name for p in plants}
    tokens = _tokens(keyword)
    rows = []
    for l in logs:
        d = date.fromisoformat(l.date)
        if actions and l.action not in actions:
            continue
        if start and d < start:
            continue
        if end and d > end:
            continue
        name = names.get(l.plant_id, "(deleted plant)")
        if tokens:
            hay = f"{name} {l.action} {l.notes}".lower()
            if not all(t in hay for t in tokens):
                continue
        rows.append({"Date": l.date, "Plant": name, "Action": l.action,
                     "Water (ml)": l.water_ml, "Notes": l.notes})
    rows.sort(key=lambda r: (r["Date"], r["Plant"]), reverse=True)
    return rows
