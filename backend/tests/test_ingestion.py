"""Unit tests for parsers and upsert helpers in `app.services.ingestion`."""
from __future__ import annotations

from datetime import date

from app.models.fund import Fund, NavHistory
from app.services.ingestion import (
    parse_main_category,
    parse_nav_date,
    parse_plan_type,
    parse_sub_category,
    upsert_funds,
    upsert_nav_history,
)

# -- Parsers ------------------------------------------------------------------

def test_parse_plan_type_direct() -> None:
    assert parse_plan_type("Axis Bluechip Fund - Direct Plan - Growth") == "Direct"


def test_parse_plan_type_regular() -> None:
    assert parse_plan_type("Axis Bluechip Fund - Regular Plan - Growth") == "Regular"


def test_parse_plan_type_ambiguous_returns_none() -> None:
    assert parse_plan_type("Axis Bluechip Fund") is None


def test_parse_main_category_equity() -> None:
    assert parse_main_category("Equity Scheme - Large Cap Fund") == "Equity"


def test_parse_main_category_debt() -> None:
    assert parse_main_category("Debt Scheme - Liquid Fund") == "Debt"


def test_parse_main_category_hybrid() -> None:
    assert parse_main_category("Hybrid Scheme - Aggressive Hybrid Fund") == "Hybrid"


def test_parse_main_category_unknown_falls_back_to_other() -> None:
    assert parse_main_category("Some New Scheme - Foo") == "Other"


def test_parse_main_category_none() -> None:
    assert parse_main_category(None) is None


def test_parse_sub_category_extracts_after_dash() -> None:
    assert parse_sub_category("Equity Scheme - Large Cap Fund") == "Large Cap Fund"


def test_parse_sub_category_no_dash() -> None:
    assert parse_sub_category("Some Scheme") == "Some Scheme"


def test_parse_nav_date_dd_mm_yyyy() -> None:
    assert parse_nav_date("30-04-2024") == date(2024, 4, 30)


# -- upsert_funds -------------------------------------------------------------

def _sample_master() -> list[dict]:
    return [
        {"schemeCode": 100027, "schemeName": "Axis Bluechip Fund - Regular Plan - Growth"},
        {"schemeCode": 100028, "schemeName": "Axis Bluechip Fund - Direct Plan - Growth"},
    ]


def _sample_details() -> dict[int, dict]:
    return {
        100027: {
            "meta": {
                "fund_house": "Axis Mutual Fund",
                "scheme_category": "Equity Scheme - Large Cap Fund",
                "scheme_code": 100027,
                "scheme_name": "Axis Bluechip Fund - Regular Plan - Growth",
            },
            "data": [],
            "status": "SUCCESS",
        }
    }


def test_upsert_funds_inserts_new_rows(db_session) -> None:
    counts = upsert_funds(db_session, _sample_master(), details=_sample_details())
    assert counts.inserted == 2
    assert counts.skipped == 0

    row = db_session.get(Fund, 100027)
    assert row is not None
    assert row.fund_name.startswith("Axis Bluechip")
    assert row.amc == "Axis Mutual Fund"
    assert row.category == "Equity"
    assert row.sub_category == "Large Cap Fund"
    assert row.plan_type == "Regular"


def test_upsert_funds_updates_existing_rows(db_session) -> None:
    upsert_funds(db_session, _sample_master(), details=_sample_details())
    # Simulate AMC rename upstream
    new_details = {
        100027: {
            "meta": {
                "fund_house": "Axis Mutual Fund Ltd",
                "scheme_category": "Equity Scheme - Large Cap Fund",
            }
        }
    }
    counts = upsert_funds(db_session, _sample_master(), details=new_details)
    assert counts.updated == 2

    row = db_session.get(Fund, 100027)
    assert row.amc == "Axis Mutual Fund Ltd"


def test_upsert_funds_skips_malformed_rows(db_session) -> None:
    bad = [
        {"schemeCode": None, "schemeName": "Nope"},
        {"schemeCode": 999, "schemeName": ""},
        {"schemeCode": 1, "schemeName": "Valid - Regular Plan"},
    ]
    counts = upsert_funds(db_session, bad)
    assert counts.skipped == 2
    assert counts.inserted == 1


# -- upsert_nav_history -------------------------------------------------------

def _seed_fund(db_session, code: int = 100027) -> None:
    db_session.add(
        Fund(scheme_code=code, fund_name="Axis Bluechip Fund - Regular Plan - Growth", is_active=True)
    )
    db_session.commit()


def test_upsert_nav_history_inserts_rows(db_session) -> None:
    _seed_fund(db_session)
    raw = [
        {"date": "30-04-2024", "nav": "100.45"},
        {"date": "29-04-2024", "nav": "100.30"},
    ]
    counts = upsert_nav_history(db_session, 100027, raw)
    assert counts.inserted == 2

    rows = db_session.query(NavHistory).all()
    assert {(r.nav_date, r.nav) for r in rows} == {
        (date(2024, 4, 30), 100.45),
        (date(2024, 4, 29), 100.30),
    }


def test_upsert_nav_history_is_idempotent(db_session) -> None:
    _seed_fund(db_session)
    raw = [{"date": "30-04-2024", "nav": "100.45"}]
    first = upsert_nav_history(db_session, 100027, raw)
    second = upsert_nav_history(db_session, 100027, raw)
    assert first.inserted == 1
    assert second.inserted == 0
    assert second.skipped == 1


def test_upsert_nav_history_skips_invalid_rows(db_session) -> None:
    _seed_fund(db_session)
    raw = [
        {"date": "30-04-2024", "nav": "0.0"},          # zero NAV
        {"date": "bad-date", "nav": "100.0"},          # unparseable date
        {"date": "30-04-2024", "nav": "garbage"},      # non-numeric NAV
        {"date": "29-04-2024", "nav": "99.5"},         # valid
    ]
    counts = upsert_nav_history(db_session, 100027, raw)
    assert counts.inserted == 1
    assert counts.skipped == 3
