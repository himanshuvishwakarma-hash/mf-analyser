"""Nightly data refresh tasks.

refresh_fund_master  - populates / updates the funds master list.
refresh_nav_history  - backfills NAV history (Regular plans only by default).
compute_metrics      - computes per-fund metrics (CAGR/Sharpe/etc.).
compute_scores       - computes composite score with peer-percentile model.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.data_fetch import MFApiClient, MFApiError
from app.core.metrics_engine import recompute_all_fund_metrics
from app.core.scoring_engine import recompute_all_scores, recompute_category_benchmarks
from app.db import SessionLocal
from app.models.fund import Fund
from app.services import cache
from app.services.amfi_scraper import run_amfi_scrape
from app.services.ingestion import upsert_funds, upsert_nav_history
from app.services.yahoo_fetch import is_market_open, run_yahoo_refresh
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# Async helpers ---------------------------------------------------------------

async def _fetch_all_funds_with_meta(
    client: MFApiClient, scheme_codes: list[int]
) -> dict[int, dict]:
    details: dict[int, dict] = {}
    for code in scheme_codes:
        try:
            details[code] = await client.get_fund(code)
        except MFApiError as e:
            logger.warning("fund detail fetch failed for %s: %s", code, e)
    return details


async def _refresh_fund_master_async(populate_meta: bool) -> dict[str, int]:
    async with MFApiClient() as client:
        raw_list = await client.list_all_funds()
        details_map: dict[int, dict] = {}
        if populate_meta:
            codes = [int(item["schemeCode"]) for item in raw_list if "schemeCode" in item]
            details_map = await _fetch_all_funds_with_meta(client, codes)

    session: Session = SessionLocal()
    try:
        counts = upsert_funds(session, raw_list, details=details_map)
    finally:
        session.close()

    cache.invalidate("funds:")
    cache.invalidate("categories:")
    return {
        "inserted": counts.inserted,
        "updated": counts.updated,
        "skipped": counts.skipped,
        "details_fetched": len(details_map),
    }


async def _refresh_nav_history_async(
    scheme_code: int | None,
    regular_only: bool = True,
    limit: int | None = None,
) -> dict[str, int]:
    """Fetch NAV history.

    regular_only: only Regular plans (matches spec section 9.2 universe).
    limit: cap number of schemes processed; useful for quick smoke runs.
    """
    session: Session = SessionLocal()
    try:
        if scheme_code is not None:
            target_codes = [scheme_code]
        else:
            stmt = select(Fund.scheme_code).where(Fund.is_active.is_(True))
            if regular_only:
                stmt = stmt.where(Fund.plan_type == "Regular")
            target_codes = [c for (c,) in session.execute(stmt).all()]
            if limit:
                target_codes = target_codes[:limit]
    finally:
        session.close()

    total_inserted = 0
    total_skipped = 0
    total_failed = 0

    async with MFApiClient() as client:
        for idx, code in enumerate(target_codes, 1):
            try:
                payload = await client.get_fund(code)
            except MFApiError as e:
                logger.warning("nav fetch failed for %s: %s", code, e)
                total_failed += 1
                continue

            # Also opportunistically backfill missing meta fields from /mf/{code}
            meta = payload.get("meta") or {}
            data = payload.get("data") or []
            local = SessionLocal()
            try:
                fund_row = local.get(Fund, code)
                if fund_row is not None:
                    if not fund_row.amc and meta.get("fund_house"):
                        fund_row.amc = meta["fund_house"]
                    if not fund_row.category and meta.get("scheme_category"):
                        from app.services.ingestion import parse_main_category, parse_sub_category
                        fund_row.category = parse_main_category(meta["scheme_category"])
                        fund_row.sub_category = parse_sub_category(meta["scheme_category"])
                    local.commit()

                counts = upsert_nav_history(local, code, data)
                total_inserted += counts.inserted
                total_skipped += counts.skipped
            finally:
                local.close()

            if idx % 100 == 0:
                logger.info("nav fetch progress: %d/%d schemes done", idx, len(target_codes))

    cache.invalidate(f"nav:{scheme_code}:" if scheme_code else "nav:")
    return {
        "schemes": len(target_codes),
        "rows_inserted": total_inserted,
        "rows_skipped": total_skipped,
        "failed_schemes": total_failed,
    }


# Celery tasks ----------------------------------------------------------------

@celery_app.task(name="app.tasks.refresh.refresh_fund_master", bind=True, max_retries=3)
def refresh_fund_master(self, populate_meta: bool = False) -> dict[str, int]:
    try:
        result = asyncio.run(_refresh_fund_master_async(populate_meta=populate_meta))
        logger.info("refresh_fund_master OK: %s", result)
        return result
    except Exception as exc:
        logger.exception("refresh_fund_master failed")
        raise self.retry(exc=exc, countdown=60 * 5) from exc


@celery_app.task(name="app.tasks.refresh.refresh_nav_history", bind=True, max_retries=3)
def refresh_nav_history(
    self, scheme_code: int | None = None, regular_only: bool = True, limit: int | None = None
) -> dict[str, int]:
    try:
        result = asyncio.run(
            _refresh_nav_history_async(scheme_code, regular_only=regular_only, limit=limit)
        )
        logger.info("refresh_nav_history OK: %s", result)
        return result
    except Exception as exc:
        logger.exception("refresh_nav_history failed")
        raise self.retry(exc=exc, countdown=60 * 5) from exc


@celery_app.task(name="app.tasks.refresh.compute_metrics")
def compute_metrics(limit: int | None = None) -> dict[str, int]:
    """Recompute fund_metrics for every fund with enough NAV history."""
    session = SessionLocal()
    try:
        result = recompute_all_fund_metrics(session, limit=limit)
    finally:
        session.close()
    cache.invalidate("funds:")
    return result


@celery_app.task(name="app.tasks.refresh.compute_benchmarks")
def compute_benchmarks() -> dict[str, int]:
    """Recompute category_benchmarks (p25/p50/p75 per metric per category)."""
    session = SessionLocal()
    try:
        result = recompute_category_benchmarks(session)
    finally:
        session.close()
    cache.invalidate("categories:")
    return result


@celery_app.task(name="app.tasks.refresh.compute_scores")
def compute_scores() -> dict[str, int]:
    """Recompute composite scores per spec section 3."""
    session = SessionLocal()
    try:
        result = recompute_all_scores(session)
    finally:
        session.close()
    cache.invalidate("funds:")
    cache.invalidate("categories:")
    return result


@celery_app.task(name="app.tasks.refresh.refresh_etf_quotes", bind=True, max_retries=2)
def refresh_etf_quotes(self, force: bool = False) -> dict[str, int | bool]:
    """Pull live ETF quotes - NSE primary, Yahoo fallback after 3 fails (v3.3A)."""
    if not force and not is_market_open():
        logger.info("refresh_etf_quotes: market closed, skip")
        return {"skipped": True, "reason": "market_closed"}

    from app.services.sources import nse_quote_fetcher

    session = SessionLocal()
    try:
        result = asyncio.run(_run_etf_refresh(session, nse_quote_fetcher))
    except Exception as exc:
        logger.exception("refresh_etf_quotes failed")
        raise self.retry(exc=exc, countdown=60 * 2) from exc
    finally:
        session.close()
    logger.info("refresh_etf_quotes OK: %s", result)
    return {**result, "skipped": False}


async def _run_etf_refresh(session, nse) -> dict[str, int | str]:
    """NSE first; on 3 consecutive failures, cascade to Yahoo for the rest."""
    from sqlalchemy import select

    from app.models.fund import EtfQuote

    rows = session.execute(
        select(EtfQuote.scheme_code, EtfQuote.symbol_yahoo)
    ).all()
    tracker = nse.FailoverTracker()
    written = 0
    succeeded = 0
    failed = 0
    used_yahoo = False

    for scheme_code, yahoo_symbol in rows:
        if tracker.should_failover():
            used_yahoo = True
            break
        nse_symbol = (yahoo_symbol or "").replace(".NS", "")
        if not nse_symbol:
            continue
        quote = await nse.fetch_quote(nse_symbol)
        if quote is None:
            tracker.record_failure()
            failed += 1
            continue
        tracker.record_success()
        succeeded += 1
        existing = session.get(EtfQuote, scheme_code)
        if existing is not None:
            existing.last_price = quote.last_price
            existing.prev_close = quote.prev_close
            existing.day_change_pct = quote.day_change_pct
            existing.last_traded_at = quote.last_traded_at
            existing.source = "nse"
            written += 1
    session.commit()

    if used_yahoo:
        logger.warning("NSE failed %d consecutive times - cascading to Yahoo", tracker.THRESHOLD)
        yahoo_result = run_yahoo_refresh(session)
        return {
            "primary": "nse+yahoo",
            "nse_succeeded": succeeded,
            "nse_failed": failed,
            "rows_written": written + yahoo_result.get("rows_written", 0),
        }
    return {
        "primary": "nse",
        "nse_succeeded": succeeded,
        "nse_failed": failed,
        "rows_written": written,
    }


@celery_app.task(name="app.tasks.refresh.refresh_expense_ratios", bind=True, max_retries=2)
def refresh_expense_ratios(self) -> dict[str, object]:
    """Weekly AMFI TER scrape - updates funds.expense_ratio + as_of date."""
    session = SessionLocal()
    try:
        result = run_amfi_scrape(session)
    finally:
        session.close()
    cache.invalidate("funds:")
    return {
        "status": result.status,
        "rows_in_file": result.rows_in_file,
        "rows_matched": result.rows_matched,
        "rows_updated": result.rows_updated,
        "as_of": result.as_of.isoformat() if result.as_of else None,
        "error": result.error,
    }


@celery_app.task(name="app.tasks.refresh.refresh_etf_nav_history", bind=True, max_retries=2)
def refresh_etf_nav_history(self) -> dict[str, int]:
    """Backfill NAV history for every fund present in etf_quotes.

    ETFs typically have plan_type=NULL and would be skipped by the default
    refresh_nav_history (regular_only=True). This task explicitly fetches
    NAV for the ETF universe so the metrics + scoring pipeline can rate them.

    Runs nightly via Celery beat at 23:25 IST, right after the main NAV
    refresh kicks off.
    """
    from app.models.fund import EtfQuote  # local import keeps cold-start cheap
    session = SessionLocal()
    try:
        codes = [c for (c,) in session.execute(select(EtfQuote.scheme_code)).all()]
    finally:
        session.close()

    if not codes:
        logger.info("refresh_etf_nav_history: no ETFs configured, skip")
        return {"etfs": 0, "rows_inserted": 0, "rows_skipped": 0, "failed_schemes": 0}

    total_inserted = 0
    total_skipped = 0
    total_failed = 0
    for code in codes:
        try:
            res = asyncio.run(
                _refresh_nav_history_async(code, regular_only=False, limit=None)
            )
            total_inserted += res.get("rows_inserted", 0)
            total_skipped += res.get("rows_skipped", 0)
            total_failed += res.get("failed_schemes", 0)
        except Exception:
            logger.exception("refresh_etf_nav_history failed for %s", code)
            total_failed += 1
    out = {
        "etfs": len(codes),
        "rows_inserted": total_inserted,
        "rows_skipped": total_skipped,
        "failed_schemes": total_failed,
    }
    logger.info("refresh_etf_nav_history OK: %s", out)
    return out


@celery_app.task(name="app.tasks.refresh.deactivate_stale_funds")
def deactivate_stale_funds(threshold_days: int = 60) -> dict[str, int]:
    """Flip is_active=False on funds whose NAV history is stale or missing.

    A fund counts as stale if either:
      * It has no rows in nav_history at all, OR
      * Its latest nav_date is more than `threshold_days` days old.

    This silently hides closed-ended schemes, matured FMPs, and any
    discontinued fund whose AMC stopped publishing NAVs. The row stays
    in the table - we only flip the flag - so historical analysis is
    preserved.
    """
    from datetime import date, timedelta

    from sqlalchemy import func, update

    from app.models.fund import NavHistory  # local import

    cutoff = date.today() - timedelta(days=threshold_days)
    session = SessionLocal()
    try:
        # Subquery: latest NAV date per scheme.
        latest_subq = (
            select(NavHistory.scheme_code, func.max(NavHistory.nav_date).label("last_nav"))
            .group_by(NavHistory.scheme_code)
            .subquery()
        )

        # Active funds whose latest NAV is older than cutoff -> deactivate.
        # Funds with NO NAV rows at all are NOT deactivated - they may just
        # be waiting for the next NAV backfill cycle.
        stale_codes = [
            c
            for (c,) in session.execute(
                select(Fund.scheme_code)
                .join(latest_subq, latest_subq.c.scheme_code == Fund.scheme_code)
                .where(Fund.is_active.is_(True))
                .where(latest_subq.c.last_nav < cutoff)
            ).all()
        ]

        # Inactive funds whose latest NAV is recent again -> reactivate.
        # Self-healing: once full NAV backfill catches up, previously-stale
        # schemes flip back on automatically.
        revived_codes = [
            c
            for (c,) in session.execute(
                select(Fund.scheme_code)
                .join(latest_subq, latest_subq.c.scheme_code == Fund.scheme_code)
                .where(Fund.is_active.is_(False))
                .where(latest_subq.c.last_nav >= cutoff)
            ).all()
        ]

        if stale_codes:
            session.execute(
                update(Fund).where(Fund.scheme_code.in_(stale_codes)).values(is_active=False)
            )
        if revived_codes:
            session.execute(
                update(Fund).where(Fund.scheme_code.in_(revived_codes)).values(is_active=True)
            )
        if stale_codes or revived_codes:
            session.commit()
        cache.invalidate("funds:")
        cache.invalidate("categories:")
    finally:
        session.close()

    out = {
        "deactivated": len(stale_codes),
        "reactivated": len(revived_codes),
        "threshold_days": threshold_days,
    }
    logger.info("deactivate_stale_funds OK: %s", out)
    return out


@celery_app.task(name="app.tasks.refresh.refresh_universe", bind=True, max_retries=3)
def refresh_universe(self) -> dict[str, int]:
    """v3.3A: Pull AMFI NAVAll, upsert funds with authoritative category + plan_type."""
    from app.services.sources import amfi_master
    from app.services.universe_loader import apply_amfi_master

    try:
        rows = asyncio.run(amfi_master.fetch_navall())
    except Exception as exc:
        logger.exception("refresh_universe: AMFI fetch failed")
        raise self.retry(exc=exc, countdown=60 * 10) from exc

    session = SessionLocal()
    try:
        result = apply_amfi_master(session, rows)
    finally:
        session.close()
    logger.info("refresh_universe OK: %s", result)
    return result
