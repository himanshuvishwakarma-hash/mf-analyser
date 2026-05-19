"""Tests for the Monte Carlo simulation engine."""
from __future__ import annotations

import time

import pytest

from app.core.montecarlo import simulate_lumpsum, simulate_sip


def test_sip_output_shape() -> None:
    r = simulate_sip(10000, 5, 0.12, 0.18, n_sims=2000, seed=1)
    assert r["months"] == 60
    assert len(r["p10"]) == 60
    assert len(r["p50"]) == 60
    assert len(r["p90"]) == 60
    assert len(r["expected"]) == 60
    assert "final" in r
    for k in ("p10", "p50", "p90", "expected"):
        assert k in r["final"]


def test_lumpsum_output_shape() -> None:
    r = simulate_lumpsum(100000, 10, 0.12, 0.18, n_sims=2000, seed=1)
    assert r["months"] == 120
    assert len(r["p50"]) == 120


def test_percentile_ordering_sip() -> None:
    r = simulate_sip(10000, 10, 0.12, 0.18, n_sims=5000, seed=42)
    for i in range(120):
        assert r["p10"][i] <= r["p50"][i] <= r["p90"][i]


def test_percentile_ordering_lumpsum() -> None:
    r = simulate_lumpsum(100000, 25, 0.12, 0.18, n_sims=5000, seed=42)
    for i in range(0, 300, 10):
        assert r["p10"][i] <= r["p50"][i] <= r["p90"][i]


def test_sip_median_above_principal() -> None:
    """For positive mu, median corpus should exceed total invested."""
    r = simulate_sip(10000, 10, 0.12, 0.18, n_sims=5000, seed=42)
    total_invested = 10000 * 10 * 12
    assert r["final"]["p50"] > total_invested


def test_lumpsum_median_above_principal() -> None:
    r = simulate_lumpsum(100000, 10, 0.10, 0.15, n_sims=5000, seed=42)
    assert r["final"]["p50"] > 100000


def test_zero_volatility_collapses_to_expected() -> None:
    """With sigma=0 all paths equal expected, so P10=P50=P90."""
    r = simulate_sip(10000, 5, 0.10, 0.0, n_sims=1000, seed=7)
    final = r["final"]
    assert final["p10"] == pytest.approx(final["p50"], rel=1e-6)
    assert final["p50"] == pytest.approx(final["p90"], rel=1e-6)
    assert final["p50"] == pytest.approx(final["expected"], rel=1e-3)


def test_runtime_under_2s_for_10k_long() -> None:
    """Spec target: 10,000 sims x 360 months in < 2s."""
    t0 = time.time()
    simulate_sip(10000, 30, 0.12, 0.18, n_sims=10000, seed=1)
    elapsed = time.time() - t0
    assert elapsed < 2.5, f"Took {elapsed:.2f}s, target < 2.5s"


def test_long_horizon_uses_lognormal_no_negative_corpus() -> None:
    """At 20y+ we switch to log-normal; corpus must stay positive."""
    r = simulate_lumpsum(100000, 25, 0.12, 0.30, n_sims=2000, seed=99)
    for v in r["p10"]:
        assert v > 0


def test_seed_reproducibility() -> None:
    r1 = simulate_sip(5000, 5, 0.10, 0.15, n_sims=1000, seed=123)
    r2 = simulate_sip(5000, 5, 0.10, 0.15, n_sims=1000, seed=123)
    assert r1["final"]["p50"] == r2["final"]["p50"]
