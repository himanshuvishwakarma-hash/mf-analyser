"""Phase F.3 - etf_quotes appears in /health/deep checks."""
from __future__ import annotations

from datetime import datetime, timezone

from app.models.fund import EtfQuote, Fund


def test_health_deep_etf_quotes_unknown_when_no_etfs(client, db_session):
    resp = client.get("/api/v1/health/deep")
    body = resp.json()
    assert "etf_quotes" in body["checks"]
    assert body["checks"]["etf_quotes"]["status"] == "unknown"
    assert body["checks"]["etf_quotes"]["tracked"] == 0


def test_health_deep_etf_quotes_ok_when_recent(client, db_session):
    db_session.add(Fund(scheme_code=1, fund_name="NIFTYBEES", plan_type="Regular", is_active=True))
    db_session.add(
        EtfQuote(
            scheme_code=1,
            symbol_yahoo="NIFTYBEES.NS",
            last_price=250.0,
            last_traded_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    resp = client.get("/api/v1/health/deep")
    body = resp.json()
    assert body["checks"]["etf_quotes"]["tracked"] == 1
    assert body["checks"]["etf_quotes"]["status"] == "ok"
