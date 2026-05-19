"""Tests for app.services.yahoo_fetch.

Mocks the yfinance call seam so tests run without network.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.fund import EtfQuote, Fund
from app.services import yahoo_fetch
from app.services.yahoo_fetch import (
    IST,
    Quote,
    fetch_quotes,
    is_market_open,
    is_stale,
    run_yahoo_refresh,
    upsert_quotes,
)

UTC = timezone.utc


def _seed_fund(session, code=120716, name="NIFTYBEES ETF"):
    f = Fund(scheme_code=code, fund_name=name, plan_type="Regular", is_active=True)
    session.add(f)
    session.commit()
    return f


def _seed_etf_quote(session, code=120716, symbol="NIFTYBEES.NS"):
    eq = EtfQuote(scheme_code=code, symbol_yahoo=symbol)
    session.add(eq)
    session.commit()
    return eq


def test_market_open_during_session():
    dt = datetime(2026, 5, 18, 10, 30, tzinfo=IST)
    assert is_market_open(dt) is True


def test_market_closed_after_hours():
    dt = datetime(2026, 5, 18, 16, 0, tzinfo=IST)
    assert is_market_open(dt) is False


def test_market_closed_weekend():
    dt = datetime(2026, 5, 16, 11, 0, tzinfo=IST)
    assert is_market_open(dt) is False


def test_market_open_at_open_edge():
    dt = datetime(2026, 5, 18, 9, 15, tzinfo=IST)
    assert is_market_open(dt) is True


def test_market_open_at_close_edge():
    dt = datetime(2026, 5, 18, 15, 30, tzinfo=IST)
    assert is_market_open(dt) is True


def test_is_stale_none_returns_true():
    assert is_stale(None) is True


def test_is_stale_recent_returns_false():
    now = datetime.now(UTC)
    assert is_stale(now - timedelta(minutes=5), now=now) is False


def test_is_stale_old_returns_true():
    now = datetime.now(UTC)
    assert is_stale(now - timedelta(minutes=30), now=now) is True


def test_fetch_quotes_success():
    def fake_download(syms):
        ts = datetime.now(UTC)
        return {
            "NIFTYBEES.NS": {"last_price": 250.50, "prev_close": 245.00, "last_traded_at": ts},
            "GOLDBEES.NS": {"last_price": 75.10, "prev_close": 74.20, "last_traded_at": ts},
        }

    yahoo_fetch.set_download_fn(fake_download)
    try:
        result = fetch_quotes(["NIFTYBEES.NS", "GOLDBEES.NS"])
    finally:
        yahoo_fetch.reset_download_fn()

    assert result.fetched == 2
    assert result.succeeded == 2
    assert result.failed == 0
    nifty = next(q for q in result.quotes if q.symbol == "NIFTYBEES.NS")
    assert nifty.last_price == 250.50
    assert nifty.day_change_pct == pytest.approx(2.2449, abs=1e-3)


def test_fetch_quotes_partial_failure():
    def fake_download(syms):
        ts = datetime.now(UTC)
        return {"NIFTYBEES.NS": {"last_price": 250.0, "prev_close": 245.0, "last_traded_at": ts}}

    yahoo_fetch.set_download_fn(fake_download)
    try:
        result = fetch_quotes(["NIFTYBEES.NS", "MISSING.NS"])
    finally:
        yahoo_fetch.reset_download_fn()

    assert result.fetched == 2
    assert result.succeeded == 1
    assert result.failed == 1
    missing = next(q for q in result.quotes if q.symbol == "MISSING.NS")
    assert missing.is_valid is False


def test_fetch_quotes_full_failure():
    def fake_download(syms):
        raise RuntimeError("yahoo down")

    yahoo_fetch.set_download_fn(fake_download)
    try:
        result = fetch_quotes(["NIFTYBEES.NS"])
    finally:
        yahoo_fetch.reset_download_fn()

    assert result.succeeded == 0
    assert result.failed == 1


def test_fetch_quotes_empty_input():
    result = fetch_quotes([])
    assert result.fetched == 0
    assert result.quotes == []


def test_fetch_quotes_dedupe_symbols():
    seen = []

    def fake_download(syms):
        seen.append(list(syms))
        return {
            s: {"last_price": 100.0, "prev_close": 99.0, "last_traded_at": datetime.now(UTC)}
            for s in syms
        }

    yahoo_fetch.set_download_fn(fake_download)
    try:
        result = fetch_quotes(["NIFTYBEES.NS", "NIFTYBEES.NS", " NIFTYBEES.NS "])
    finally:
        yahoo_fetch.reset_download_fn()

    assert result.fetched == 1
    assert seen[0] == ["NIFTYBEES.NS"]


def test_upsert_quotes_writes_new_rows(db_session):
    _seed_fund(db_session)
    _seed_etf_quote(db_session)

    ts = datetime.now(UTC)
    result = yahoo_fetch.FetchResult(
        fetched=1,
        succeeded=1,
        failed=0,
        quotes=[Quote("NIFTYBEES.NS", 250.0, 245.0, 2.04, ts)],
    )
    written = upsert_quotes(db_session, {120716: "NIFTYBEES.NS"}, result)
    assert written == 1
    row = db_session.get(EtfQuote, 120716)
    assert row.last_price == 250.0
    assert row.day_change_pct == 2.04


def test_upsert_quotes_idempotent(db_session):
    _seed_fund(db_session)
    _seed_etf_quote(db_session)

    ts = datetime.now(UTC)
    fr = yahoo_fetch.FetchResult(
        1, 1, 0, [Quote("NIFTYBEES.NS", 250.0, 245.0, 2.04, ts)]
    )
    upsert_quotes(db_session, {120716: "NIFTYBEES.NS"}, fr)
    upsert_quotes(db_session, {120716: "NIFTYBEES.NS"}, fr)
    rows = db_session.query(EtfQuote).all()
    assert len(rows) == 1
    assert rows[0].last_price == 250.0


def test_upsert_quotes_skips_invalid(db_session):
    _seed_fund(db_session)
    _seed_etf_quote(db_session)

    fr = yahoo_fetch.FetchResult(
        1, 0, 1, [Quote("NIFTYBEES.NS", None, None, None, None)]
    )
    written = upsert_quotes(db_session, {120716: "NIFTYBEES.NS"}, fr)
    assert written == 0


def test_run_yahoo_refresh_full_flow(db_session):
    _seed_fund(db_session)
    _seed_etf_quote(db_session)

    def fake_download(syms):
        return {
            "NIFTYBEES.NS": {
                "last_price": 260.0,
                "prev_close": 255.0,
                "last_traded_at": datetime.now(UTC),
            }
        }

    yahoo_fetch.set_download_fn(fake_download)
    try:
        result = run_yahoo_refresh(db_session)
    finally:
        yahoo_fetch.reset_download_fn()

    assert result["symbols"] == 1
    assert result["succeeded"] == 1
    assert result["rows_written"] == 1
    row = db_session.get(EtfQuote, 120716)
    assert row.last_price == 260.0


def test_run_yahoo_refresh_empty_map(db_session):
    result = run_yahoo_refresh(db_session)
    expected = {"symbols": 0, "succeeded": 0, "failed": 0, "rows_written": 0}
    assert result == expected
