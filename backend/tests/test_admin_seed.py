"""Tests for Phase F.1 admin seed-status + first-boot endpoint."""
from __future__ import annotations

from datetime import date

from app.models.fund import Fund, FundScore, NavHistory


def test_seed_status_empty_db(client, db_session):
    resp = client.get("/api/v1/admin/seed-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "seeded": False,
        "fund_count": 0,
        "nav_count": 0,
        "score_count": 0,
        "in_progress": False,
    }


def test_seed_status_funds_only_in_progress(client, db_session):
    db_session.add(
        Fund(scheme_code=1, fund_name="X", plan_type="Regular", is_active=True)
    )
    db_session.commit()
    resp = client.get("/api/v1/admin/seed-status")
    body = resp.json()
    assert body["fund_count"] == 1
    assert body["nav_count"] == 0
    assert body["seeded"] is False
    # funds present, no scores -> in_progress
    assert body["in_progress"] is True


def test_seed_status_fully_seeded(client, db_session):
    db_session.add(
        Fund(scheme_code=1, fund_name="X", plan_type="Regular", is_active=True)
    )
    db_session.add(
        NavHistory(scheme_code=1, nav_date=date(2024, 1, 1), nav=100.0)
    )
    db_session.add(FundScore(scheme_code=1, composite_score=70.0))
    db_session.commit()
    resp = client.get("/api/v1/admin/seed-status")
    body = resp.json()
    assert body["seeded"] is True
    assert body["fund_count"] == 1
    assert body["nav_count"] == 1
    assert body["score_count"] == 1
    assert body["in_progress"] is False


def test_run_cascade_requires_token(client, db_session, monkeypatch):
    """Without ADMIN_TOKEN env, endpoint is disabled."""
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    resp = client.post("/api/v1/admin/run-cascade")
    assert resp.status_code == 503


def test_run_cascade_rejects_bad_token(client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    resp = client.post("/api/v1/admin/run-cascade", headers={"X-Admin-Token": "wrong"})
    assert resp.status_code == 401
