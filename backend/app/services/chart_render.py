"""Server-side chart rendering for export reports.

matplotlib is used (NOT Recharts/frontend) because the output is embedded
into .docx and .pdf files. Output: PNG bytes that python-docx ImageRun
can consume directly.

Caching: by default we DO NOT cache to disk (keeps the service stateless).
A simple optional file-based cache hangs off (scheme_code, as_of_date)
when REPORTS_CACHE_DIR is configured. Cache invalidation is just
"delete the file" - safe because regenerating is cheap (~50ms per chart).

Style: muted, professional. No grid clutter. Z1N brand teal.
"""
from __future__ import annotations

import io
import logging
import os
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Headless backend, no display required.
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

logger = logging.getLogger(__name__)

# Z1N brand palette (kept inline to avoid frontend coupling).
COLORS = ["#0F766E", "#0EA5E9", "#F59E0B", "#DC2626", "#7C3AED"]
GRID_COLOR = "#E2E8F0"
TEXT_COLOR = "#0F172A"

_CACHE_DIR = os.environ.get("REPORTS_CACHE_DIR")


def _cache_path(key: str) -> Path | None:
    if not _CACHE_DIR:
        return None
    p = Path(_CACHE_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{key}.png"


def _style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID_COLOR)
    ax.spines["bottom"].set_color(GRID_COLOR)
    ax.tick_params(colors=TEXT_COLOR, labelsize=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.grid(axis="y", color=GRID_COLOR, linestyle="-", linewidth=0.5)


def render_nav_chart(
    nav_points: list[tuple[date, float]],
    title: str,
    *,
    cache_key: str | None = None,
    width_in: float = 6.5,
    height_in: float = 3.0,
) -> bytes:
    """Single-fund NAV chart -> PNG bytes."""
    if cache_key:
        path = _cache_path(cache_key)
        if path and path.exists():
            return path.read_bytes()

    if not nav_points:
        return _render_placeholder(title, "No NAV history available", width_in, height_in)

    dates_arr = [p[0] for p in nav_points]
    navs = [p[1] for p in nav_points]

    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=150)
    ax.plot(dates_arr, navs, color=COLORS[0], linewidth=1.6)
    ax.fill_between(dates_arr, navs, min(navs), color=COLORS[0], alpha=0.08)
    ax.set_title(title, color=TEXT_COLOR, fontsize=11, fontweight="bold", loc="left", pad=8)
    _style_axes(ax)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    data = buf.getvalue()
    if cache_key:
        p = _cache_path(cache_key)
        if p:
            p.write_bytes(data)
    return data


def render_overlay_chart(
    series: list[tuple[str, list[tuple[date, float]]]],
    title: str = "Normalised performance (rebased to 100)",
    *,
    width_in: float = 6.5,
    height_in: float = 3.2,
) -> bytes:
    """Compare chart: multiple funds normalised to base 100."""
    if not series:
        return _render_placeholder(title, "No data to compare", width_in, height_in)

    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=150)
    for i, (label, points) in enumerate(series):
        if not points:
            continue
        base = points[0][1]
        if base == 0:
            continue
        xs = [p[0] for p in points]
        ys = [p[1] / base * 100.0 for p in points]
        ax.plot(xs, ys, color=COLORS[i % len(COLORS)], linewidth=1.6, label=label)

    ax.axhline(100, color=GRID_COLOR, linewidth=0.7, linestyle="--")
    ax.set_title(title, color=TEXT_COLOR, fontsize=11, fontweight="bold", loc="left", pad=8)
    _style_axes(ax)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _render_placeholder(title: str, msg: str, w: float, h: float) -> bytes:
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    ax.text(0.5, 0.5, msg, ha="center", va="center", color="#94A3B8", fontsize=10)
    ax.set_title(title, color=TEXT_COLOR, fontsize=11, fontweight="bold", loc="left", pad=8)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
