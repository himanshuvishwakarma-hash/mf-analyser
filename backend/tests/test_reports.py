"""Tests for chart_render, report_builder, pdf_convert, and report endpoints."""
from __future__ import annotations

import io
import shutil
import zipfile
from datetime import date

import pytest

from app.models.fund import Fund, FundMetric, FundScore, NavHistory
from app.services import pdf_convert
from app.services.chart_render import render_nav_chart, render_overlay_chart
from app.services.report_builder import (
    build_comparison_report,
    build_fund_factsheet,
)


def _seed_fund(session, code=1, name="Test Equity Fund", category="Equity"):
    session.add(
        Fund(
            scheme_code=code,
            fund_name=name,
            amc="Test AMC",
            category=category,
            sub_category="Large Cap Fund",
            plan_type="Regular",
            expense_ratio=1.05,
            exit_load="1% if redeemed within 1 year",
            aum_cr=12345.67,
            is_active=True,
        )
    )
    session.add(
        FundMetric(
            scheme_code=code,
            cagr_1y=0.18,
            cagr_3y=0.14,
            cagr_5y=0.12,
            cagr_10y=0.11,
            sharpe_ratio=1.2,
            std_dev=0.16,
            max_drawdown=-0.28,
            recovery_months=14,
            momentum_3m=0.04,
            momentum_6m=0.09,
        )
    )
    session.add(
        FundScore(
            scheme_code=code,
            composite_score=78.5,
            sharpe_score=82.0,
            cagr_1y_score=75.0,
            cagr_3y_score=80.0,
            cagr_5y_score=78.0,
            drawdown_score=70.0,
            expense_score=65.0,
            momentum_score=85.0,
        )
    )
    session.add_all(
        [
            NavHistory(scheme_code=code, nav_date=date(2024, 1, 1), nav=100.0),
            NavHistory(scheme_code=code, nav_date=date(2024, 6, 1), nav=105.0),
            NavHistory(scheme_code=code, nav_date=date(2024, 12, 1), nav=118.5),
        ]
    )
    session.commit()


# ---- chart_render -------------------------------------------------------

def test_render_nav_chart_returns_png_bytes():
    points = [(date(2024, 1, 1), 100.0), (date(2024, 6, 1), 110.0), (date(2024, 12, 1), 120.0)]
    png = render_nav_chart(points, "Test Fund")
    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 500  # non-trivial size


def test_render_nav_chart_empty_history_returns_placeholder():
    png = render_nav_chart([], "Empty")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_overlay_chart_multi_series():
    s1 = [(date(2024, 1, 1), 100.0), (date(2024, 6, 1), 110.0)]
    s2 = [(date(2024, 1, 1), 50.0), (date(2024, 6, 1), 58.0)]
    png = render_overlay_chart([("Fund A", s1), ("Fund B", s2)])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


# ---- report_builder: factsheet -----------------------------------------

def test_factsheet_builds_valid_docx(db_session):
    _seed_fund(db_session)
    docx_bytes = build_fund_factsheet(db_session, 1)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 5000

    # .docx is a ZIP - confirm it opens.
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
        names = zf.namelist()
        assert "word/document.xml" in names
        xml = zf.read("word/document.xml").decode("utf-8")
        # Key content present.
        assert "Test Equity Fund" in xml
        assert "Test AMC" in xml
        assert "Z1N CAPITAL" in xml
        # A return value (18.00% from cagr_1y=0.18)
        assert "18.00%" in xml


def test_factsheet_missing_fund_raises(db_session):
    with pytest.raises(ValueError):
        build_fund_factsheet(db_session, 99999)


def test_factsheet_handles_missing_metrics(db_session):
    """Fund without metrics/score still produces a valid factsheet."""
    session = db_session
    session.add(
        Fund(scheme_code=2, fund_name="Bare Fund", plan_type="Regular", is_active=True)
    )
    session.commit()
    docx_bytes = build_fund_factsheet(session, 2)
    assert docx_bytes[:2] == b"PK"  # zip magic


# ---- report_builder: comparison ----------------------------------------

def test_comparison_report_two_funds(db_session):
    _seed_fund(db_session, code=1, name="Alpha Fund")
    _seed_fund(db_session, code=2, name="Beta Fund")
    docx_bytes = build_comparison_report(db_session, [1, 2])
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
        assert "Alpha Fund" in xml
        assert "Beta Fund" in xml
        assert "Fund Comparison Report" in xml


def test_comparison_report_rejects_empty_list(db_session):
    with pytest.raises(ValueError):
        build_comparison_report(db_session, [])


def test_comparison_report_rejects_too_many(db_session):
    with pytest.raises(ValueError):
        build_comparison_report(db_session, list(range(1, 7)))


def test_comparison_report_missing_fund_raises(db_session):
    _seed_fund(db_session, code=1)
    with pytest.raises(ValueError, match="Schemes not found"):
        build_comparison_report(db_session, [1, 99999])


# ---- pdf_convert -------------------------------------------------------

def test_pdf_convert_raises_when_soffice_missing(monkeypatch):
    monkeypatch.setattr(pdf_convert, "_soffice_path", lambda: None)
    with pytest.raises(pdf_convert.PdfConvertError, match="LibreOffice"):
        pdf_convert.docx_to_pdf(b"fake-bytes")


@pytest.mark.skipif(not shutil.which("soffice") and not shutil.which("libreoffice"),
                    reason="LibreOffice not installed in this environment")
def test_pdf_convert_end_to_end(db_session):
    _seed_fund(db_session)
    docx_bytes = build_fund_factsheet(db_session, 1)
    pdf_bytes = pdf_convert.docx_to_pdf(docx_bytes)
    assert pdf_bytes[:4] == b"%PDF"


# ---- report API endpoints ----------------------------------------------

def test_fund_report_docx_endpoint(client, db_session):
    _seed_fund(db_session)
    resp = client.get("/api/v1/funds/1/report?format=docx")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "factsheet_1.docx" in resp.headers["content-disposition"]
    assert resp.content[:2] == b"PK"


def test_fund_report_unknown_scheme_404(client, db_session):
    resp = client.get("/api/v1/funds/99999/report?format=docx")
    assert resp.status_code == 404


def test_fund_report_invalid_format_422(client, db_session):
    _seed_fund(db_session)
    resp = client.get("/api/v1/funds/1/report?format=xls")
    assert resp.status_code == 422


def test_compare_report_endpoint(client, db_session):
    _seed_fund(db_session, code=1, name="Alpha Fund")
    _seed_fund(db_session, code=2, name="Beta Fund")
    resp = client.post(
        "/api/v1/funds/compare/report",
        json={"scheme_codes": [1, 2], "format": "docx"},
    )
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"


def test_compare_report_rejects_bad_format(client, db_session):
    _seed_fund(db_session, code=1)
    resp = client.post(
        "/api/v1/funds/compare/report",
        json={"scheme_codes": [1], "format": "rtf"},
    )
    assert resp.status_code == 400
