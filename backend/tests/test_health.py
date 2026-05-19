"""Tests for the deep health probe."""
from __future__ import annotations


def test_shallow_health_returns_ok(client) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_deep_health_returns_required_shape(client) -> None:
    resp = client.get("/api/v1/health/deep")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert body["status"] in ("ok", "warn", "down")
    assert "checks" in body
    for key in ("db", "redis", "celery", "data"):
        assert key in body["checks"], f"missing check {key}"


def test_deep_health_data_check_includes_counts(client) -> None:
    resp = client.get("/api/v1/health/deep")
    data = resp.json()["checks"]["data"]
    assert "funds_total" in data
    assert "funds_scored" in data
    assert "category_benchmarks" in data


def test_deep_health_with_empty_db_marks_data_warn(client) -> None:
    # Fresh SQLite fixture has no NAV/scores, so data check should warn.
    resp = client.get("/api/v1/health/deep")
    data = resp.json()["checks"]["data"]
    assert data["status"] == "warn"
    assert data["funds_scored"] == 0
