"""Phase H.2 - refresh_etf_nav_history task tests."""
from __future__ import annotations

from app.models.fund import EtfQuote, Fund
from app.tasks.refresh import refresh_etf_nav_history


def test_refresh_etf_nav_history_no_etfs(db_session, monkeypatch):
    """Empty etf_quotes table returns zeros without dispatching anything."""
    # Point the task at our in-memory session.
    from app import db as db_module
    monkeypatch.setattr(db_module, "SessionLocal", lambda: db_session)
    import app.tasks.refresh as r
    monkeypatch.setattr(r, "SessionLocal", lambda: db_session)

    result = refresh_etf_nav_history.run()  # bypass Celery dispatch
    assert result == {
        "etfs": 0,
        "rows_inserted": 0,
        "rows_skipped": 0,
        "failed_schemes": 0,
    }


def test_refresh_etf_nav_history_iterates_etf_codes(db_session, monkeypatch):
    """For each ETF row, the task calls _refresh_nav_history_async once."""
    db_session.add(Fund(scheme_code=1, fund_name="N50", plan_type=None, is_active=True))
    db_session.add(Fund(scheme_code=2, fund_name="GOLD", plan_type=None, is_active=True))
    db_session.add(EtfQuote(scheme_code=1, symbol_yahoo="NIFTYBEES.NS"))
    db_session.add(EtfQuote(scheme_code=2, symbol_yahoo="GOLDBEES.NS"))
    db_session.commit()

    import app.tasks.refresh as r
    monkeypatch.setattr(r, "SessionLocal", lambda: db_session)

    seen_codes = []

    async def fake_async(scheme_code, regular_only=True, limit=None):
        seen_codes.append((scheme_code, regular_only, limit))
        return {"schemes": 1, "rows_inserted": 5, "rows_skipped": 0, "failed_schemes": 0}

    monkeypatch.setattr(r, "_refresh_nav_history_async", fake_async)

    result = refresh_etf_nav_history.run()
    assert result["etfs"] == 2
    assert result["rows_inserted"] == 10
    assert set(c[0] for c in seen_codes) == {1, 2}
    # regular_only must be False for ETFs (otherwise they get filtered out)
    assert all(c[1] is False for c in seen_codes)
