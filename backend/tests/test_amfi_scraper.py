"""Tests for the AMFI TER scraper.

We never hit the network here: the parse + upsert paths are tested with
synthetic Excel bytes and the manual CSV path is tested directly.
"""
from __future__ import annotations

import io
from datetime import date

import pandas as pd

from app.models.fund import Fund
from app.services.amfi_scraper import (
    _date_from_filename,
    apply_manual_csv,
    parse_excel,
    upsert_expense_ratios,
)


def _make_excel(rows: list[dict]) -> bytes:
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def test_date_from_filename_picks_month_and_year() -> None:
    assert _date_from_filename("TER_Oct2025.xlsx") == date(2025, 10, 1)
    assert _date_from_filename("/downloads/Total Expense Ratio April 2024.xlsx") == date(2024, 4, 1)


def test_date_from_filename_returns_none_when_no_match() -> None:
    assert _date_from_filename("random.xlsx") is None


def test_parse_excel_finds_columns_case_insensitively() -> None:
    content = _make_excel([
        {"Scheme Code": 100027, "Scheme Name": "X", "Total Expense Ratio": 1.25},
        {"Scheme Code": 100028, "Scheme Name": "Y", "Total Expense Ratio": 0.75},
    ])
    parsed = parse_excel(content)
    assert len(parsed) == 2
    assert parsed["scheme_code"].tolist() == [100027, 100028]
    assert parsed["expense_ratio"].tolist() == [1.25, 0.75]


def test_parse_excel_drops_rows_with_missing_data() -> None:
    content = _make_excel([
        {"Scheme Code": 100027, "Expense Ratio": 1.25},
        {"Scheme Code": None, "Expense Ratio": 0.5},
        {"Scheme Code": 100028, "Expense Ratio": None},
    ])
    parsed = parse_excel(content)
    assert len(parsed) == 1
    assert int(parsed["scheme_code"].iloc[0]) == 100027


def test_upsert_expense_ratios_updates_matching_funds(db_session) -> None:
    db_session.add_all([
        Fund(scheme_code=100027, fund_name="A", expense_ratio=2.0, is_active=True),
        Fund(scheme_code=100028, fund_name="B", expense_ratio=1.0, is_active=True),
    ])
    db_session.commit()

    parsed = pd.DataFrame({"scheme_code": [100027, 100028, 999999], "expense_ratio": [1.25, 1.0, 0.5]})
    matched, updated = upsert_expense_ratios(db_session, parsed, date(2025, 10, 1))
    assert matched == 2
    assert updated == 1  # only 100027 actually changed

    row = db_session.get(Fund, 100027)
    assert row.expense_ratio == 1.25
    assert row.expense_ratio_as_of == date(2025, 10, 1)


def test_apply_manual_csv_happy_path(db_session) -> None:
    db_session.add(Fund(scheme_code=100027, fund_name="A", is_active=True))
    db_session.commit()

    csv_text = "scheme_code,expense_ratio\n100027,1.5\n"
    res = apply_manual_csv(db_session, csv_text)
    assert res.status == "ok"
    assert res.rows_matched == 1
    assert res.rows_updated == 1
    row = db_session.get(Fund, 100027)
    assert row.expense_ratio == 1.5


def test_apply_manual_csv_rejects_missing_columns(db_session) -> None:
    res = apply_manual_csv(db_session, "foo,bar\n1,2\n")
    assert res.status == "error"
    assert "scheme_code" in res.error
