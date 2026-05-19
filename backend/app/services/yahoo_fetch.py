"""Yahoo Finance live-quote fetcher for ETFs.

Uses the `yfinance` library (unofficial Yahoo API wrapper).

Design:
- Fetch in chunks (default 50 symbols) to avoid request size limits.
- Per-symbol failure is non-fatal; bad rows are skipped and counted.
- Results cached in Redis for 5 minutes per symbol (read-side speedup
  for the API endpoint when Celery hasn't run yet).
- Market-hours gate (`is_market_open`) is exposed but NOT enforced here;
  caller decides whether to skip. Keeps this module pure.

Returns dataclass `Quote` with last_price, prev_close, day_change_pct,
last_traded_at, source ("yahoo"), stale flag.

Tests use `_DOWNLOAD_FN` injection seam to mock yfinance.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.fund import EtfQuote
from app.services import cache


def _is_postgres(session: Session) -> bool:
    return session.bind is not None and session.bind.dialect.name == "postgresql"

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
NSE_OPEN = time(9, 15)
NSE_CLOSE = time(15, 30)
STALE_AFTER = timedelta(minutes=15)


@dataclass
class Quote:
    symbol: str
    last_price: float | None
    prev_close: float | None
    day_change_pct: float | None
    last_traded_at: datetime | None
    source: str = "yahoo"

    @property
    def is_valid(self) -> bool:
        return self.last_price is not None and self.last_price > 0


@dataclass
class FetchResult:
    fetched: int
    succeeded: int
    failed: int
    quotes: list[Quote]


def is_market_open(now: datetime | None = None) -> bool:
    """NSE cash market hours: Mon-Fri 09:15-15:30 IST. Holidays not checked."""
    now = now or datetime.now(IST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    t = now.time()
    return NSE_OPEN <= t <= NSE_CLOSE


def is_stale(last_traded_at: datetime | None, *, now: datetime | None = None) -> bool:
    """A quote is stale if older than STALE_AFTER (15 min) during market hours."""
    if last_traded_at is None:
        return True
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if last_traded_at.tzinfo is None:
        last_traded_at = last_traded_at.replace(tzinfo=timezone.utc)
    return (now - last_traded_at) > STALE_AFTER


# ---- yfinance call seam --------------------------------------------------

def _default_download(symbols: list[str]) -> dict[str, dict]:
    """Real yfinance call. Imported lazily so tests don't need the lib.

    Returns mapping: symbol -> {last_price, prev_close, last_traded_at}.
    Symbols missing from yfinance output are simply absent from the dict.
    """
    import yfinance as yf  # local import for testability

    out: dict[str, dict] = {}
    tickers = yf.Tickers(" ".join(symbols))
    for sym in symbols:
        try:
            t = tickers.tickers.get(sym)
            if t is None:
                continue
            info = t.fast_info  # cheap, no full info() round-trip
            last = info.get("lastPrice") or info.get("last_price")
            prev = info.get("previousClose") or info.get("previous_close")
            ts = info.get("lastUpdate") or info.get("regularMarketTime")
            if isinstance(ts, int) or isinstance(ts, float):
                ts = datetime.fromtimestamp(ts, timezone.utc)
            elif isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            elif ts is None:
                ts = datetime.now(timezone.utc)
            out[sym] = {
                "last_price": float(last) if last is not None else None,
                "prev_close": float(prev) if prev is not None else None,
                "last_traded_at": ts,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("yfinance: symbol %s failed: %s", sym, exc)
    return out


_DOWNLOAD_FN: Callable[[list[str]], dict[str, dict]] = _default_download


def set_download_fn(fn: Callable[[list[str]], dict[str, dict]]) -> None:
    """Test seam - inject a fake downloader."""
    global _DOWNLOAD_FN
    _DOWNLOAD_FN = fn


def reset_download_fn() -> None:
    global _DOWNLOAD_FN
    _DOWNLOAD_FN = _default_download


# ---- core fetch ----------------------------------------------------------

def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def fetch_quotes(symbols: list[str], *, batch_size: int = 50) -> FetchResult:
    """Fetch live quotes for given Yahoo symbols. Returns FetchResult."""
    symbols = list(dict.fromkeys(s.strip() for s in symbols if s and s.strip()))
    if not symbols:
        return FetchResult(0, 0, 0, [])

    quotes: list[Quote] = []
    succeeded = 0
    for batch in _chunks(symbols, batch_size):
        try:
            raw = _DOWNLOAD_FN(batch)
        except Exception as exc:  # noqa: BLE001
            logger.error("yfinance batch failed: %s", exc)
            raw = {}
        for sym in batch:
            data = raw.get(sym)
            if not data or data.get("last_price") in (None, 0):
                quotes.append(Quote(sym, None, None, None, None))
                continue
            last = data["last_price"]
            prev = data.get("prev_close")
            change_pct = None
            if last is not None and prev not in (None, 0):
                change_pct = round((last - prev) / prev * 100.0, 4)
            quotes.append(
                Quote(
                    symbol=sym,
                    last_price=last,
                    prev_close=prev,
                    day_change_pct=change_pct,
                    last_traded_at=data.get("last_traded_at"),
                )
            )
            succeeded += 1
    failed = len(symbols) - succeeded
    return FetchResult(len(symbols), succeeded, failed, quotes)


# ---- persistence ---------------------------------------------------------

def upsert_quotes(session: Session, scheme_to_symbol: dict[int, str], result: FetchResult) -> int:
    """Persist successful quotes back to etf_quotes (keyed by scheme_code)."""
    by_symbol = {q.symbol: q for q in result.quotes}
    rows = []
    now = datetime.now(timezone.utc)
    for scheme_code, sym in scheme_to_symbol.items():
        q = by_symbol.get(sym)
        if q is None or not q.is_valid:
            continue
        rows.append(
            {
                "scheme_code": scheme_code,
                "symbol_yahoo": sym,
                "last_price": q.last_price,
                "prev_close": q.prev_close,
                "day_change_pct": q.day_change_pct,
                "last_traded_at": q.last_traded_at,
                "currency": "INR",
                "source": "yahoo",
                "updated_at": now,
            }
        )
    if not rows:
        return 0
    if _is_postgres(session):
        stmt = pg_insert(EtfQuote.__table__).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["scheme_code"],
            set_={
                "last_price": stmt.excluded.last_price,
                "prev_close": stmt.excluded.prev_close,
                "day_change_pct": stmt.excluded.day_change_pct,
                "last_traded_at": stmt.excluded.last_traded_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        session.execute(stmt)
    else:
        # Row-by-row fallback for SQLite (tests).
        for r in rows:
            existing = session.get(EtfQuote, r["scheme_code"])
            if existing is None:
                session.add(EtfQuote(**r))
            else:
                existing.last_price = r["last_price"]
                existing.prev_close = r["prev_close"]
                existing.day_change_pct = r["day_change_pct"]
                existing.last_traded_at = r["last_traded_at"]
                existing.updated_at = r["updated_at"]
    session.commit()
    # Bust cache so API picks up new values immediately.
    cache.invalidate("etf_quote:")
    return len(rows)


def load_symbol_map(session: Session) -> dict[int, str]:
    """Build {scheme_code: symbol_yahoo} from etf_quotes table."""
    rows = session.execute(
        select(EtfQuote.scheme_code, EtfQuote.symbol_yahoo)
    ).all()
    return {code: sym for (code, sym) in rows}


def run_yahoo_refresh(session: Session) -> dict[str, int]:
    """One-shot refresh: load symbol map -> fetch -> upsert. Used by Celery."""
    mapping = load_symbol_map(session)
    if not mapping:
        logger.info("no ETF symbols configured, skipping")
        return {"symbols": 0, "succeeded": 0, "failed": 0, "rows_written": 0}
    symbols = list({s for s in mapping.values()})
    result = fetch_quotes(symbols)
    written = upsert_quotes(session, mapping, result)
    return {
        "symbols": len(symbols),
        "succeeded": result.succeeded,
        "failed": result.failed,
        "rows_written": written,
    }
