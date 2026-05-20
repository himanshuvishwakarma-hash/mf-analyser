"""H.4 - inactive funds + stricter Direct exclusion are filtered out everywhere."""
from __future__ import annotations

from datetime import date, timedelta

from app.models.fund import Fund, NavHistory
from app.tasks.refresh import deactivate_stale_funds


def test_inactive_fund_hidden_from_list(client, db_session):
    db_session.add_all(
        [
            Fund(scheme_code=1, fund_name="Alive Equity Fund - Regular",
                 plan_type="Regular", category="Equity", is_active=True),
            Fund(scheme_code=2, fund_name="Dead Fund - Regular",
                 plan_type="Regular", category="Equity", is_active=False),
        ]
    )
    db_session.commit()
    resp = client.get("/api/v1/funds/list?limit=10")
    body = resp.json()
    codes = {f["scheme_code"] for f in body["items"]}
    assert codes == {1}


def test_inactive_fund_returns_404_from_detail(client, db_session):
    db_session.add(
        Fund(scheme_code=99, fund_name="Closed Fund", plan_type="Regular", category="Equity", is_active=False)
    )
    db_session.commit()
    resp = client.get("/api/v1/funds/99")
    assert resp.status_code == 404


def test_inactive_fund_excluded_from_compare(client, db_session):
    db_session.add(Fund(scheme_code=1, fund_name="Live", plan_type="Regular", category="Equity", is_active=True))
    db_session.add(Fund(scheme_code=2, fund_name="Dead", plan_type="Regular", category="Equity", is_active=False))
    db_session.commit()
    resp = client.post("/api/v1/funds/compare", json=[1, 2])
    assert resp.status_code == 404  # scheme 2 missing from filtered set


def test_direct_plan_excluded_by_name_pattern(client, db_session):
    db_session.add_all(
        [
            Fund(scheme_code=1, fund_name="Foo Fund - Regular Plan",
                 plan_type=None, category="Equity", is_active=True),
            Fund(scheme_code=2, fund_name="Foo Fund - Direct Plan",
                 plan_type=None, category="Equity", is_active=True),
            Fund(scheme_code=3, fund_name="Foo Fund (D) Growth",
                 plan_type=None, is_active=True),
        ]
    )
    db_session.commit()
    resp = client.get("/api/v1/funds/list?limit=10")
    codes = {f["scheme_code"] for f in resp.json()["items"]}
    assert codes == {1}


def test_deactivate_stale_funds_flips_old_funds(db_session, monkeypatch):
    today = date.today()
    db_session.add(
        Fund(scheme_code=1, fund_name="Stale", plan_type="Regular", category="Equity", is_active=True)
    )
    db_session.add(
        Fund(scheme_code=2, fund_name="Fresh", plan_type="Regular", category="Equity", is_active=True)
    )
    db_session.add(
        Fund(scheme_code=3, fund_name="NoNAV", plan_type="Regular", category="Equity", is_active=True)
    )
    # Stale: last NAV 90 days ago
    db_session.add(NavHistory(scheme_code=1, nav_date=today - timedelta(days=90), nav=10.0))
    # Fresh: last NAV today
    db_session.add(NavHistory(scheme_code=2, nav_date=today, nav=20.0))
    # NoNAV: no rows at all
    db_session.commit()

    import app.tasks.refresh as r
    monkeypatch.setattr(r, "SessionLocal", lambda: db_session)

    result = deactivate_stale_funds.run(threshold_days=60)
    # H.4 v2: no-NAV funds (scheme 3) stay ACTIVE - they may just be
    # waiting for the next NAV backfill. Only schemes with an existing
    # NAV that has gone stale (scheme 1) get deactivated.
    assert result["deactivated"] == 1

    db_session.expire_all()
    assert db_session.get(Fund, 1).is_active is False  # stale NAV -> off
    assert db_session.get(Fund, 2).is_active is True   # fresh NAV -> on
    assert db_session.get(Fund, 3).is_active is True   # no NAV yet -> stays on



def test_deactivate_stale_funds_reactivates_when_nav_fresh(db_session, monkeypatch):
    """Self-healing: an inactive fund that got a fresh NAV flips back on."""
    from datetime import date

    db_session.add(
        Fund(scheme_code=10, fund_name="Was Stale", plan_type="Regular", category="Equity", is_active=False)
    )
    db_session.add(NavHistory(scheme_code=10, nav_date=date.today(), nav=42.0))
    db_session.commit()

    import app.tasks.refresh as r
    monkeypatch.setattr(r, "SessionLocal", lambda: db_session)

    result = deactivate_stale_funds.run(threshold_days=60)
    assert result["reactivated"] == 1
    db_session.expire_all()
    assert db_session.get(Fund, 10).is_active is True
