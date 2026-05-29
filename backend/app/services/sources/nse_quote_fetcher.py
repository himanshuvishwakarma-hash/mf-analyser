"""NSE quote API client for live ETF prices (v3.3A).

Endpoint: https://www.nseindia.com/api/quote-equity?symbol=<SYMBOL>
Notes:
  - NSE requires a session cookie set via a prior GET to / and a real-looking
    User-Agent header.
  - Symbols are NSE tickers WITHOUT the .NS suffix (Yahoo's suffix).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://www.nseindia.com"
QUOTE_PATH = "/api/quote-equity"
TIMEOUT_SEC = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class NseQuote:
    symbol: str
    last_price: float
    prev_close: float | None
    day_change_pct: float | None
    last_traded_at: datetime
    source: str = "nse"


class FailoverTracker:
    """Tracks consecutive failures to decide when to cascade to Yahoo."""

    THRESHOLD = 3

    def __init__(self) -> None:
        self._fails = 0

    def record_failure(self) -> None:
        self._fails += 1

    def record_success(self) -> None:
        self._fails = 0

    def should_failover(self) -> bool:
        return self._fails >= self.THRESHOLD


async def _fetch_raw(symbol: str, client: httpx.AsyncClient) -> dict:
    resp = await client.get(QUOTE_PATH, params={"symbol": symbol})
    resp.raise_for_status()
    return resp.json()


async def fetch_quote(symbol: str, client: httpx.AsyncClient | None = None) -> NseQuote | None:
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept": "application/json",
            },
            trust_env=False,
            timeout=TIMEOUT_SEC,
        )
        await client.get("/")
    try:
        data = await _fetch_raw(symbol, client)
    except Exception as exc:
        logger.warning("nse_quote_fetcher: %s failed: %s", symbol, exc)
        return None
    finally:
        if own_client:
            await client.aclose()

    pi = data.get("priceInfo")
    if not pi or pi.get("lastPrice") is None:
        return None
    return NseQuote(
        symbol=symbol,
        last_price=float(pi["lastPrice"]),
        prev_close=float(pi["previousClose"]) if pi.get("previousClose") else None,
        day_change_pct=float(pi["pChange"]) if pi.get("pChange") else None,
        last_traded_at=datetime.now(timezone.utc),
    )
