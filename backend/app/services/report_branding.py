"""Branding + audience-aware label maps for the fund factsheet."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from docx.shared import RGBColor

Audience = Literal["client", "advisor"]

# Brand palette (kept here so report_builder + chart_render share one source).
BRAND_TEAL = RGBColor(0x0F, 0x76, 0x6E)
BRAND_TEAL_HEX = "0F766E"
DARK = RGBColor(0x0F, 0x17, 0x2A)
GREY = RGBColor(0x64, 0x74, 0x8B)
SCORE_GREEN = RGBColor(0x0F, 0x76, 0x6E)
SCORE_AMBER = RGBColor(0xD9, 0x77, 0x06)
SCORE_ROSE = RGBColor(0xDC, 0x26, 0x26)

LOGO_PATH = Path(__file__).resolve().parents[1].parent / "data" / "branding" / "z1n_logo.png"
ARIAL_FONT = "Arial"

# Labels per metric key, keyed by audience.
AUDIENCE_LABELS: dict[str, dict[Audience, str]] = {
    "sharpe_ratio":             {"client": "Risk vs reward",      "advisor": "Sharpe ratio"},
    "std_dev":                  {"client": "Typical ups & downs", "advisor": "Volatility (std dev)"},
    "max_drawdown":             {"client": "Worst-ever fall",     "advisor": "Max drawdown"},
    "drawdown_duration_months": {"client": "Time taken to fall",  "advisor": "Drawdown duration"},
    "recovery_months":          {"client": "Recovery time",       "advisor": "Recovery (months)"},
    "cagr_1y":                  {"client": "1-year return",       "advisor": "CAGR 1y"},
    "cagr_3y":                  {"client": "3-year return",       "advisor": "CAGR 3y"},
    "cagr_5y":                  {"client": "5-year return",       "advisor": "CAGR 5y"},
    "cagr_10y":                 {"client": "10-year return",      "advisor": "CAGR 10y"},
    "expense_ratio":            {"client": "Annual cost",         "advisor": "Expense ratio"},
    "aum_cr":                   {"client": "Fund size",           "advisor": "AUM (Rs crore)"},
    "exit_load":                {"client": "Exit fee",            "advisor": "Exit load"},
}

# Plain-English one-liners (client audience only).
AUDIENCE_EXPLAINERS: dict[str, str] = {
    "sharpe_ratio": "Above 1 is good - extra return earned for the swings the fund takes.",
    "std_dev": "How much returns swing year to year. Lower = steadier ride.",
    "max_drawdown": "The biggest peak-to-bottom fall the fund has ever had.",
    "drawdown_duration_months": "How long the fund took to fall from peak to that worst bottom.",
    "recovery_months": "How long it took to recover and surpass the prior peak.",
    "expense_ratio": "What the fund charges per year. Lower is better.",
}


def audience_label(key: str, audience: Audience) -> str:
    spec = AUDIENCE_LABELS.get(key)
    if spec is None:
        return key
    return spec.get(audience, spec.get("advisor", key))


def explainer(key: str) -> str:
    """Client-side one-liner under a metric. Empty string if none."""
    return AUDIENCE_EXPLAINERS.get(key, "")


def score_band(score: float | None) -> tuple[str, RGBColor]:
    """Convert 0-100 composite score to (label, color)."""
    if score is None:
        return ("Not yet rated", GREY)
    if score >= 70:
        return ("Strong", SCORE_GREEN)
    if score >= 40:
        return ("Caution", SCORE_AMBER)
    return ("Avoid", SCORE_ROSE)
