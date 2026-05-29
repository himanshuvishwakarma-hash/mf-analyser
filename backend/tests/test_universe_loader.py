"""Tests for universe_loader.apply_amfi_master."""
import pytest

from app.models.fund import Fund
from app.services import universe_loader


@pytest.fixture
def amfi_rows():
    return [
        {
            "scheme_code": 103174,
            "scheme_name": "Aditya Birla Sun Life Frontline Equity Fund - Regular Plan - Growth",
            "amc": "Aditya Birla Sun Life Mutual Fund",
            "category": "Equity",
            "sub_category": "Large Cap Fund",
            "plan_type": "Regular",
            "isin_growth": "INF209K01157",
            "isin_dividend": "INF209K01165",
            "nav": 500.12,
            "nav_date": "25-May-2026",
        },
        {
            "scheme_code": 100037,
            "scheme_name": "HDFC Liquid Fund - Regular Plan - Growth",
            "amc": "HDFC Mutual Fund",
            "category": "Debt",
            "sub_category": "Liquid Fund",
            "plan_type": "Regular",
            "isin_growth": "INF179K01CG7",
            "isin_dividend": None,
            "nav": 4789.56,
            "nav_date": "25-May-2026",
        },
    ]


def test_apply_amfi_master_inserts_new_funds(db_session, amfi_rows):
    result = universe_loader.apply_amfi_master(db_session, amfi_rows)
    assert result["inserted"] == 2
    assert result["updated"] == 0
    f = db_session.get(Fund, 103174)
    assert f.category == "Equity"
    assert f.amc == "Aditya Birla Sun Life Mutual Fund"
    assert f.plan_type == "Regular"
    assert f.source == "amfi"


def test_apply_amfi_master_updates_existing_fund(db_session, amfi_rows):
    db_session.add(Fund(
        scheme_code=103174, fund_name="Old", category=None, is_active=True
    ))
    db_session.commit()
    result = universe_loader.apply_amfi_master(db_session, amfi_rows[:1])
    assert result["updated"] == 1
    f = db_session.get(Fund, 103174)
    assert f.category == "Equity"
    assert f.amc == "Aditya Birla Sun Life Mutual Fund"


def test_apply_amfi_master_preserves_existing_amc_when_already_set(db_session, amfi_rows):
    """Don't clobber a user-set AMC."""
    db_session.add(Fund(
        scheme_code=103174, fund_name="Old", amc="Manual Override",
        category="Equity", is_active=True,
    ))
    db_session.commit()
    universe_loader.apply_amfi_master(db_session, amfi_rows[:1])
    f = db_session.get(Fund, 103174)
    assert f.amc == "Manual Override"
