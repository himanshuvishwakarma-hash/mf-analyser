from unittest.mock import AsyncMock

import pytest

from app.services.sources import nse_quote_fetcher


def test_failover_tracker_threshold():
    tracker = nse_quote_fetcher.FailoverTracker()
    assert not tracker.should_failover()
    tracker.record_failure()
    tracker.record_failure()
    assert not tracker.should_failover()
    tracker.record_failure()
    assert tracker.should_failover()


def test_failover_tracker_resets_on_success():
    tracker = nse_quote_fetcher.FailoverTracker()
    tracker.record_failure()
    tracker.record_failure()
    tracker.record_success()
    tracker.record_failure()
    assert not tracker.should_failover()


@pytest.mark.asyncio
async def test_fetch_quote_parses_priceinfo(monkeypatch):
    payload = {
        "priceInfo": {
            "lastPrice": 250.5,
            "previousClose": 245.0,
            "pChange": 2.24,
            "lastUpdateTime": "25-May-2026 15:30:00",
        }
    }
    mock = AsyncMock(return_value=payload)
    monkeypatch.setattr(nse_quote_fetcher, "_fetch_raw", mock)
    monkeypatch.setattr(
        nse_quote_fetcher.httpx,
        "AsyncClient",
        lambda **kw: _FakeAsyncCM(mock),
    )
    quote = await nse_quote_fetcher.fetch_quote("NIFTYBEES")
    assert quote.last_price == 250.5
    assert quote.prev_close == 245.0
    assert quote.day_change_pct == 2.24
    assert quote.source == "nse"


@pytest.mark.asyncio
async def test_fetch_quote_returns_none_on_missing_priceinfo(monkeypatch):
    mock = AsyncMock(return_value={})
    monkeypatch.setattr(nse_quote_fetcher, "_fetch_raw", mock)
    monkeypatch.setattr(
        nse_quote_fetcher.httpx,
        "AsyncClient",
        lambda **kw: _FakeAsyncCM(mock),
    )
    quote = await nse_quote_fetcher.fetch_quote("BOGUS")
    assert quote is None


# Minimal fake httpx.AsyncClient that satisfies the homepage-cookie GET + aclose.
class _FakeAsyncCM:
    def __init__(self, mock):
        self._mock = mock
    async def get(self, *args, **kwargs):
        # Pretend GET / succeeded (no-op)
        class R:
            def raise_for_status(self): pass
            def json(self): return {}
        return R()
    async def aclose(self):
        pass
