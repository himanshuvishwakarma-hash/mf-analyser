"""H.5 - NSE NMF II enrichment script."""
from __future__ import annotations

import pandas as pd

from app.models.fund import Fund
from app.scripts.load_nse_master import enrich_funds, map_category


def test_map_category_known_types():
    assert map_category("EQUITY FUND") == "Equity"
    assert map_category("Debt Fund") == "Debt"
    assert map_category("LIQUID FUND") == "Debt"
    assert map_category("HYBRID FUND") == "Hybrid"


def test_map_category_unknown_falls_back_to_other():
    assert map_category("WEIRD TYPE") == "Other"
    assert map_category(None) == "Other"
    assert map_category("") == "Other"


def test_enrich_fills_null_category(db_session):
    db_session.add(Fund(scheme_code=100, fund_name="X", category=None, is_active=True))
    db_session.commit()
    df = pd.DataFrame(
        [
            {
                "Amfi": 100,
                "Fund Description": "X Fund",
                "Fund Type": "EQUITY FUND",
                "Status": "Active",
                "Fund Nature": "OPEN",
            }
        ]
    )
    result = enrich_funds(db_session, df)
    assert result["matched_in_db"] == 1
    assert result["updated_category"] == 1
    db_session.expire_all()
    assert db_session.get(Fund, 100).category == "Equity"


def test_enrich_does_not_overwrite_existing_category(db_session):
    db_session.add(Fund(scheme_code=101, fund_name="Y", category="Hybrid", is_active=True))
    db_session.commit()
    df = pd.DataFrame(
        [
            {
                "Amfi": 101,
                "Fund Description": "Y Fund",
                "Fund Type": "EQUITY FUND",  # would map to Equity but we keep existing
                "Status": "Active",
                "Fund Nature": "OPEN",
            }
        ]
    )
    result = enrich_funds(db_session, df)
    assert result["updated_category"] == 0
    assert db_session.get(Fund, 101).category == "Hybrid"


def test_enrich_deactivates_close_ended(db_session):
    db_session.add(Fund(scheme_code=102, fund_name="FMP", category="Debt", is_active=True))
    db_session.commit()
    df = pd.DataFrame(
        [
            {
                "Amfi": 102,
                "Fund Description": "FMP",
                "Fund Type": "DEBT FUND",
                "Status": "Active",
                "Fund Nature": "CLOSE",
            }
        ]
    )
    result = enrich_funds(db_session, df)
    assert result["deactivated_close_ended"] == 1
    db_session.expire_all()
    assert db_session.get(Fund, 102).is_active is False


def test_enrich_deactivates_status_deactive(db_session):
    db_session.add(Fund(scheme_code=103, fund_name="Dead", category="Equity", is_active=True))
    db_session.commit()
    df = pd.DataFrame(
        [
            {
                "Amfi": 103,
                "Fund Description": "Dead",
                "Fund Type": "EQUITY FUND",
                "Status": "Deactive",
                "Fund Nature": "OPEN",
            }
        ]
    )
    result = enrich_funds(db_session, df)
    assert result["deactivated_status"] == 1
    assert db_session.get(Fund, 103).is_active is False


def test_enrich_skips_unmatched_amfi_codes(db_session):
    df = pd.DataFrame(
        [
            {
                "Amfi": 99999,
                "Fund Description": "Ghost",
                "Fund Type": "EQUITY FUND",
                "Status": "Active",
                "Fund Nature": "OPEN",
            }
        ]
    )
    result = enrich_funds(db_session, df)
    assert result["matched_in_db"] == 0
    assert result["unmatched_amfi_codes"] == 1


def test_enrich_dry_run_does_not_commit(db_session):
    db_session.add(Fund(scheme_code=104, fund_name="Test", category=None, is_active=True))
    db_session.commit()
    df = pd.DataFrame(
        [
            {
                "Amfi": 104,
                "Fund Description": "Test",
                "Fund Type": "EQUITY FUND",
                "Status": "Active",
                "Fund Nature": "OPEN",
            }
        ]
    )
    result = enrich_funds(db_session, df, dry_run=True)
    assert result["updated_category"] == 1
    assert result.get("dry_run") is True
    db_session.expire_all()
    assert db_session.get(Fund, 104).category is None  # rolled back


def test_enrich_skips_amfi_null_rows(db_session):
    db_session.add(Fund(scheme_code=105, fund_name="Has Code", category=None, is_active=True))
    db_session.commit()
    df = pd.DataFrame(
        [
            {  # null Amfi -> dropped
                "Amfi": None,
                "Fund Description": "No Code",
                "Fund Type": "EQUITY FUND",
                "Status": "Active",
                "Fund Nature": "OPEN",
            },
            {
                "Amfi": 105,
                "Fund Description": "Has Code",
                "Fund Type": "DEBT FUND",
                "Status": "Active",
                "Fund Nature": "OPEN",
            },
        ]
    )
    result = enrich_funds(db_session, df)
    assert result["rows_in_file"] == 1  # null Amfi dropped
    assert result["matched_in_db"] == 1
