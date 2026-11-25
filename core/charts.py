"""Matplotlib charts.

Uses ``matplotlib.figure.Figure`` directly (no pyplot), which avoids global state
and backend problems in a web server.
"""
from __future__ import annotations

import io

from matplotlib.figure import Figure

from . import logic

STATUS_COLORS = {"Overdue": "#d64545", "Due today": "#e8962e", "Due soon": "#e8cf2e", "OK": "#4c9f5a"}
GREEN = "#4c9f5a"


def _empty(message: str) -> Figure:
    fig = Figure(figsize=(5, 3.2))
    ax = fig.subplots()
    ax.text(0.5, 0.5, message, ha="center", va="center", color="#777")
    ax.axis("off")
    return fig


def fig_status(summary: dict) -> Figure:
    if not summary["total_plants"]:
        return _empty("No plants yet")
    labels = logic.STATUS_ORDER
    values = [summary["status_counts"].get(s, 0) for s in labels]
    fig = Figure(figsize=(5, 3.2))
    ax = fig.subplots()
    bars = ax.bar(labels, values, color=[STATUS_COLORS[s] for s in labels])
    ax.bar_label(bars)
    ax.set_title("Watering status")
    ax.set_ylabel("Plants")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


def fig_trend(summary: dict) -> Figure:
    trend = summary["weekly_trend"]
    if not any(count for _, count in trend):
        return _empty("No waterings logged in the last 8 weeks")
    labels = [t[0] for t in trend]
    counts = [t[1] for t in trend]
    fig = Figure(figsize=(5, 3.2))
    ax = fig.subplots()
    ax.plot(labels, counts, marker="o", color=GREEN)
    ax.fill_between(range(len(counts)), counts, alpha=0.15, color=GREEN)
    ax.set_title("Waterings per week (week starting)")
    ax.set_ylabel("Waterings")
    ax.tick_params(axis="x", labelrotation=45)
    ax.set_ylim(bottom=0)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


def fig_category(summary: dict) -> Figure:
    counts = summary["category_counts"]
    if not counts:
        return _empty("No plants yet")
    items = sorted(counts.items(), key=lambda kv: kv[1])
    fig = Figure(figsize=(5, 3.2))
    ax = fig.subplots()
    bars = ax.barh([k for k, _ in items], [v for _, v in items], color=GREEN)
    ax.bar_label(bars, padding=2)
    ax.set_title("Plants per category")
    ax.set_xlabel("Plants")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


def fig_intervals(summary: dict) -> Figure:
    intervals = summary["intervals"]
    if not intervals:
        return _empty("No plants yet")
    fig = Figure(figsize=(5, 3.2))
    ax = fig.subplots()
    top = max(intervals)
    bins = [0, 2, 4, 7, 10, 14, 21, 30, max(61, top + 1)]
    ax.hist(intervals, bins=bins, color=GREEN, edgecolor="white")
    ax.set_xscale("symlog", linthresh=7)
    ax.set_xticks([1, 3, 7, 14, 30, 60])
    ax.set_xticklabels(["1", "3", "7", "14", "30", "60"])
    ax.set_title("Distribution of watering intervals")
    ax.set_xlabel("Days between waterings")
    ax.set_ylabel("Plants")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


def fig_to_png(fig: Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    return buf.getvalue()
