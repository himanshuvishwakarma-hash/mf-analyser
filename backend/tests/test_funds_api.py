"""End-to-end-ish tests for the funds + categories API.

Uses the in-memory SQLite engine from `conftest.py`. Each test seeds its
own fixture data and exercises the FastAPI test client.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.fund import EtfQuote, Fund, FundMetric, FundScore, NavHistory

UTC = timezone.utc


@pytest.fixture
def seeded_db(db_session):
    db_session.add_all(
        [
            Fund(
                scheme_code=1,
                fund_name="Axis Bluechip - Regular Plan",
                amc="Axis MF",
                category="Equity",
                sub_category="Large Cap Fund",
                plan_type="Regular",
                expense_ratio=1.2,
                aum_cr=35000.0,
                is_active=True,
            ),
            Fund(
                scheme_code=2,
                fund_name="Axis Bluechip - Direct Plan",
                amc="Axis MF",
                category="Equity",
                sub_category="Large Cap Fund",
                plan_type="Direct",
                expense_ratio=0.6,
                aum_cr=35000.0,
                is_active=True,
            ),
            Fund(
                scheme_code=3,
                fund_name="SBI Liquid - Regular Plan",
                amc="SBI MF",
                category="Debt",
                sub_category="Liquid Fund",
                plan_type="Regular",
                expense_ratio=0.2,
                aum_cr=80000.0,
                is_active=True,
            ),
        ]
    )
    db_session.add(
        FundMetric(scheme_code=1, cagr_1y=0.18, cagr_3y=0.14, cagr_5y=0.12, sharpe_ratio=1.1)
    )
    db_session.add(FundScore(scheme_code=1, composite_score=78.5))
    db_session.add_all(
        [
            NavHistory(scheme_code=1, nav_date=date(2024, 4, 29), nav=100.30),
            NavHistory(scheme_code=1, nav_date=date(2024, 4, 30), nav=100.45),
        ]
    )
    db_session.commit()
    return db_session


def test_search_excludes_direct_plans(client, seeded_db) -> None:
    resp = client.get("/api/v1/funds/search", params={"q": "Axis"})
    assert resp.status_code == 200
    body = resp.json()
    codes = {f["scheme_code"] for f in body["items"]}
    assert codes == {1}, "Direct plan must be filtered out per spec §9.2"


def test_search_requires_min_length(client, seeded_db) -> None:
    resp = client.get("/api/v1/funds/search", params={"q": "a"})
    assert resp.status_code == 422


def test_list_filters_by_category_and_paginates(client, seeded_db) -> None:
    resp = client.get("/api/v1/funds/list", params={"category": "Equity", "limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["scheme_code"] == 1


def test_list_pagination_page_two_is_empty(client, seeded_db) -> None:
    resp = client.get("/api/v1/funds/list", params={"page": 2, "limit": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []


def test_fund_detail_returns_metrics_and_score(client, seeded_db) -> None:
    resp = client.get("/api/v1/funds/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["fund_name"].startswith("Axis Bluechip")
    assert body["metrics"]["cagr_3y"] == pytest.approx(0.14)
    assert body["composite_score"] == pytest.approx(78.5)
    assert body["nav_latest"] == pytest.approx(100.45)
    assert body["nav_date"] == "2024-04-30"


def test_fund_detail_404_for_unknown_scheme(client, seeded_db) -> None:
    resp = client.get("/api/v1/funds/99999")
    assert resp.status_code == 404


def test_nav_history_ordered_ascending(client, seeded_db) -> None:
    resp = client.get("/api/v1/funds/1/nav")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    dates = [point["date"] for point in body["data"]]
    assert dates == sorted(dates)


def test_compare_returns_requested_funds(client, seeded_db) -> None:
    resp = client.post("/api/v1/funds/compare", json=[1, 3])
    assert resp.status_code == 200
    body = resp.json()
    assert {f["scheme_code"] for f in body["funds"]} == {1, 3}


def test_compare_rejects_more_than_five(client, seeded_db) -> None:
    resp = client.post("/api/v1/funds/compare", json=[1, 2, 3, 4, 5, 6])
    assert resp.status_code == 400


def test_compare_404_for_unknown_scheme(client, seeded_db) -> None:
    resp = client.post("/api/v1/funds/compare", json=[1, 999])
    assert resp.status_code == 404


def test_categories_endpoint_counts_regular_only(client, seeded_db) -> None:
    resp = client.get("/api/v1/categories")
    assert resp.status_code == 200
    body = resp.json()
    counts = {c["category"]: c["fund_count"] for c in body["categories"]}
    # Direct plan (#2) excluded; Regular Equity (#1) and Regular Debt (#3) included.
    assert counts == {"Equity": 1, "Debt": 1}


def test_fund_detail_includes_live_quote_for_etf(client, seeded_db) -> None:
    """When an etf_quotes row exists for the fund, response carries live_quote + is_etf=True."""
    now = datetime.now(UTC)
    seeded_db.add(
        EtfQuote(
            scheme_code=1,
            symbol_yahoo="NIFTYBEES.NS",
            last_price=250.5,
            prev_close=245.0,
            day_change_pct=2.24,
            last_traded_at=now,
        )
    )
    seeded_db.commit()

    resp = client.get("/api/v1/funds/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_etf"] is True
    assert body["live_quote"]["symbol"] == "NIFTYBEES.NS"
    assert body["live_quote"]["last_price"] == 250.5
    assert body["live_quote"]["stale"] is False


def test_fund_detail_no_live_quote_for_mutual_fund(client, seeded_db) -> None:
    """Funds without an etf_quotes row stay is_etf=False and live_quote=None."""
    resp = client.get("/api/v1/funds/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_etf"] is False
    assert body["live_quote"] is None


def test_fund_detail_marks_stale_when_old(client, seeded_db) -> None:
    """ETF quote older than 15 min flagged as stale."""
    old = datetime.now(UTC) - timedelta(minutes=30)
    seeded_db.add(
        EtfQuote(
            scheme_code=1,
            symbol_yahoo="NIFTYBEES.NS",
            last_price=250.0,
            last_traded_at=old,
        )
    )
    seeded_db.commit()

    resp = client.get("/api/v1/funds/1")
    body = resp.json()
    assert body["live_quote"]["stale"] is True
