"""Monte Carlo simulation engine (spec section 7).

Vectorised NumPy: 10k paths times 360 months computes in ~1 second.

Public surface:
    - simulate_sip(monthly, years, mu_annual, sigma_annual, n_sims=10000) -> dict
    - simulate_lumpsum(amount, years, mu_annual, sigma_annual, n_sims=10000) -> dict

Return dict shape:
    {
        "p10": list[float]   # corpus value at the end of each month
        "p50": list[float]
        "p90": list[float]
        "expected": list[float]  # deterministic projection at mu
        "months": int
        "final": { "p10": float, "p50": float, "p90": float, "expected": float }
    }
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _annual_to_monthly(mu_a: float, sigma_a: float) -> tuple[float, float]:
    """Convert annual log-return + vol to monthly. Uses geometric-mean style."""
    mu_m = (1 + mu_a) ** (1 / 12) - 1
    sigma_m = sigma_a / np.sqrt(12)
    return mu_m, sigma_m


def _simulate_paths(
    months: int,
    mu_m: float,
    sigma_m: float,
    n_sims: int,
    seed: int | None,
) -> np.ndarray:
    """Return an array of shape (n_sims, months) of monthly multiplicative returns."""
    rng = np.random.default_rng(seed)
    # Normal returns are fine for short horizons; for 20y+ use log-normal to keep positive.
    if months >= 20 * 12:
        # Log-normal: draw log returns, exponentiate to get gross returns.
        log_mu = np.log(1 + mu_m) - 0.5 * sigma_m ** 2
        log_sigma = sigma_m
        log_returns = rng.normal(log_mu, log_sigma, size=(n_sims, months))
        return np.exp(log_returns)
    # Simple normal returns + clip to avoid negative growth factor.
    returns = rng.normal(mu_m, sigma_m, size=(n_sims, months))
    return np.maximum(1 + returns, 0.01)  # floor at -99% per month


def simulate_lumpsum(
    amount: float,
    years: int,
    mu_annual: float,
    sigma_annual: float,
    n_sims: int = 10000,
    seed: int | None = None,
) -> dict[str, Any]:
    months = int(years * 12)
    mu_m, sigma_m = _annual_to_monthly(mu_annual, sigma_annual)
    paths = _simulate_paths(months, mu_m, sigma_m, n_sims, seed)
    cum = np.cumprod(paths, axis=1)
    corpus = amount * cum  # shape (n_sims, months)
    return _summarise(corpus, mu_m, amount, months, mode="lumpsum")


def simulate_sip(
    monthly: float,
    years: int,
    mu_annual: float,
    sigma_annual: float,
    n_sims: int = 10000,
    seed: int | None = None,
) -> dict[str, Any]:
    months = int(years * 12)
    mu_m, sigma_m = _annual_to_monthly(mu_annual, sigma_annual)
    paths = _simulate_paths(months, mu_m, sigma_m, n_sims, seed)

    # Build corpus iteratively (memory-friendly, still fast for typical sizes).
    corpus = np.zeros_like(paths)
    running = np.zeros(n_sims)
    for t in range(months):
        running = (running + monthly) * paths[:, t]
        corpus[:, t] = running

    return _summarise(corpus, mu_m, monthly, months, mode="sip")


def _summarise(corpus: np.ndarray, mu_m: float, principal: float, months: int, mode: str) -> dict[str, Any]:
    p10 = np.percentile(corpus, 10, axis=0).tolist()
    p50 = np.percentile(corpus, 50, axis=0).tolist()
    p90 = np.percentile(corpus, 90, axis=0).tolist()

    # Deterministic expected path at mu_m.
    if mode == "lumpsum":
        expected = [principal * (1 + mu_m) ** (t + 1) for t in range(months)]
    else:
        expected = []
        run = 0.0
        for _ in range(months):
            run = (run + principal) * (1 + mu_m)
            expected.append(run)

    return {
        "months": months,
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "expected": expected,
        "final": {
            "p10": p10[-1] if p10 else 0,
            "p50": p50[-1] if p50 else 0,
            "p90": p90[-1] if p90 else 0,
            "expected": expected[-1] if expected else 0,
        },
    }
