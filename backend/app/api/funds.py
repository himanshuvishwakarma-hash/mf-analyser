"""Fund search, list, detail, NAV history, comparison, report endpoints."""
from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fund import EtfQuote, Fund, FundMetric, FundScore, NavHistory
from app.schemas.fund import FundDetail, FundListResponse, FundMetrics, FundSummary, LiveQuote
from app.services import cache
from app.services.pdf_convert import PdfConvertError, docx_to_pdf
from app.services.report_builder import build_comparison_report, build_fund_factsheet
from app.services.yahoo_fetch import is_stale

router = APIRouter()


def _exclude_direct_plans(stmt):
    """Restrict the universe shown to advisors.

    Filters:
      * is_active=True (hides closed / discontinued funds)
      * plan_type='Regular' OR (plan_type IS NULL AND name has no Direct marker)
      * category IS NOT NULL (hides stub records with no AMFI category mapping)
      * Drops common closed-ended patterns: FMP, Fixed Maturity, Series N,
        Interval Plan, Capital Protection schemes
    """
    name = func.lower(Fund.fund_name)
    closed_patterns = [
        "%fmp%",
        "%fixed maturity%",
        "%series%",
        "%interval plan%",
        "%capital protect%",
    ]
    stmt = (
        stmt.where(Fund.is_active.is_(True))
        .where(Fund.category.is_not(None))
        .where(
            (Fund.plan_type == "Regular")
            | (
                (Fund.plan_type.is_(None))
                & ~name.like("%direct%")
                & ~name.like("%(d)%")
                & ~name.like("%-direct-%")
            )
        )
    )
    for pat in closed_patterns:
        stmt = stmt.where(~name.like(pat))
    return stmt


# Frontend button labels -> DB filters. AMFI taxonomy splits ETFs and Index
# funds into category="Other" with various sub_category strings. The mapping
# below lets the discover page work with friendly labels.
CATEGORY_ALIASES: dict[str, dict[str, list[str]]] = {
    "Equity":    {"categories": ["Equity"]},
    "Debt":      {"categories": ["Debt"]},
    "Hybrid":    {"categories": ["Hybrid"]},
    "Index/ETF": {"sub_patterns": ["%index%", "%etf%"]},
    "Solution":  {"sub_patterns": ["%solution%", "%retirement%", "%children%"]},
    "Other": {
        "categories": ["Other"],
        # Exclude sub_categories already covered by Index/ETF + Solution buttons
        # so each fund shows under exactly one tab.
        "exclude_sub_patterns": [
            "%index%", "%etf%", "%solution%", "%retirement%", "%children%",
        ],
    },
}


def _apply_category_filter(stmt, category: str | None):
    if not category:
        return stmt
    spec = CATEGORY_ALIASES.get(category)
    if spec is None:
        # Unknown label - treat as exact-match for backward compat.
        return stmt.where(Fund.category == category)
    if cats := spec.get("categories"):
        stmt = stmt.where(Fund.category.in_(cats))
    if subs := spec.get("sub_patterns"):
        from sqlalchemy import or_
        sub_lower = func.lower(Fund.sub_category)
        stmt = stmt.where(or_(*[sub_lower.like(p) for p in subs]))
    if excl := spec.get("exclude_sub_patterns"):
        sub_lower = func.lower(Fund.sub_category)
        for p in excl:
            stmt = stmt.where(~sub_lower.like(p))
    return stmt


def _serialise_summary(
    fund: Fund, metric: FundMetric | None, score: FundScore | None
) -> dict[str, Any]:
    return {
        "scheme_code": fund.scheme_code,
        "fund_name": fund.fund_name,
        "amc": fund.amc,
        "category": fund.category,
        "sub_category": fund.sub_category,
        "expense_ratio": fund.expense_ratio,
        "aum_cr": fund.aum_cr,
        "cagr_1y": metric.cagr_1y if metric else None,
        "cagr_3y": metric.cagr_3y if metric else None,
        "cagr_5y": metric.cagr_5y if metric else None,
        "composite_score": score.composite_score if score else None,
    }


@router.get("/search", response_model=FundListResponse)
def search_funds(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> FundListResponse:
    pattern = f"%{q.strip()}%"
    base = (
        select(Fund, FundMetric, FundScore)
        .outerjoin(FundMetric, FundMetric.scheme_code == Fund.scheme_code)
        .outerjoin(FundScore, FundScore.scheme_code == Fund.scheme_code)
        .where((Fund.fund_name.ilike(pattern)) | (Fund.amc.ilike(pattern)))
    )
    base = _exclude_direct_plans(base).limit(limit)
    rows = db.execute(base).all()
    items = [
        FundSummary(**_serialise_summary(fund, metric, score))
        for (fund, metric, score) in rows
    ]
    return FundListResponse(items=items, total=len(items), page=1, limit=limit)


@router.get("/list", response_model=FundListResponse)
def list_funds(
    category: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> FundListResponse:
    base = (
        select(Fund, FundMetric, FundScore)
        .outerjoin(FundMetric, FundMetric.scheme_code == Fund.scheme_code)
        .outerjoin(FundScore, FundScore.scheme_code == Fund.scheme_code)
        .where(Fund.is_active.is_(True))
    )
    base = _apply_category_filter(base, category)
    base = _exclude_direct_plans(base)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = db.scalar(count_stmt) or 0
    offset = (page - 1) * limit
    rows = db.execute(base.order_by(Fund.fund_name).offset(offset).limit(limit)).all()
    items = [FundSummary(**_serialise_summary(f, m, s)) for (f, m, s) in rows]
    return FundListResponse(items=items, total=int(total), page=page, limit=limit)


@router.get("/{scheme_code}", response_model=FundDetail)
def get_fund(scheme_code: int, db: Session = Depends(get_db)) -> FundDetail:
    fund = db.get(Fund, scheme_code)
    if fund is None or not fund.is_active:
        raise HTTPException(status_code=404, detail=f"Fund {scheme_code} not found")

    latest_nav = db.execute(
        select(NavHistory.nav, NavHistory.nav_date)
        .where(NavHistory.scheme_code == scheme_code)
        .order_by(desc(NavHistory.nav_date))
        .limit(1)
    ).first()

    metric = db.get(FundMetric, scheme_code)
    score = db.execute(
        select(FundScore)
        .where(FundScore.scheme_code == scheme_code)
        .order_by(desc(FundScore.computed_at))
        .limit(1)
    ).scalar_one_or_none()

    metrics_obj = (
        FundMetrics(
            cagr_1y=metric.cagr_1y,
            cagr_3y=metric.cagr_3y,
            cagr_5y=metric.cagr_5y,
            cagr_10y=metric.cagr_10y,
            sharpe_ratio=metric.sharpe_ratio,
            std_dev=metric.std_dev,
            max_drawdown=metric.max_drawdown,
            drawdown_duration_months=metric.drawdown_duration_months,
            recovery_months=metric.recovery_months,
            momentum_3m=metric.momentum_3m,
            momentum_6m=metric.momentum_6m,
        )
        if metric
        else FundMetrics()
    )

    etf_row = db.get(EtfQuote, scheme_code)
    is_etf = etf_row is not None
    live_quote: LiveQuote | None = None
    if etf_row is not None:
        live_quote = LiveQuote(
            symbol=etf_row.symbol_yahoo,
            last_price=etf_row.last_price,
            prev_close=etf_row.prev_close,
            day_change_pct=etf_row.day_change_pct,
            last_traded_at=etf_row.last_traded_at,
            source=etf_row.source or "yahoo",
            stale=is_stale(etf_row.last_traded_at),
        )

    return FundDetail(
        scheme_code=fund.scheme_code,
        fund_name=fund.fund_name,
        amc=fund.amc,
        category=fund.category,
        sub_category=fund.sub_category,
        expense_ratio=fund.expense_ratio,
        exit_load=fund.exit_load,
        aum_cr=fund.aum_cr,
        nav_latest=latest_nav.nav if latest_nav else None,
        nav_date=latest_nav.nav_date if latest_nav else None,
        metrics=metrics_obj,
        composite_score=score.composite_score if score else None,
        is_etf=is_etf,
        live_quote=live_quote,
    )


@router.get("/{scheme_code}/nav")
def get_nav_history(
    scheme_code: int,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from datetime import date as _date

    if not db.get(Fund, scheme_code):
        raise HTTPException(status_code=404, detail=f"Fund {scheme_code} not found")

    # Parse ISO dates up-front so the SQL filter compares Date to Date
    # (not Date to str, which Postgres+SQLAlchemy can silently misfire on).
    def _parse(s: str | None) -> _date | None:
        if not s:
            return None
        try:
            return _date.fromisoformat(s)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid date '{s}', expected YYYY-MM-DD"
            ) from exc

    from_d = _parse(from_date)
    to_d = _parse(to_date)

    cache_key = f"nav:{scheme_code}:{from_d or ''}:{to_d or ''}"

    def loader() -> dict[str, Any]:
        stmt = (
            select(NavHistory.nav_date, NavHistory.nav)
            .where(NavHistory.scheme_code == scheme_code)
            .order_by(NavHistory.nav_date)
        )
        if from_d:
            stmt = stmt.where(NavHistory.nav_date >= from_d)
        if to_d:
            stmt = stmt.where(NavHistory.nav_date <= to_d)
        rows = db.execute(stmt).all()
        return {
            "scheme_code": scheme_code,
            "count": len(rows),
            "data": [{"date": d.isoformat(), "nav": float(n)} for (d, n) in rows],
        }

    return cache.get_or_set(cache_key, loader, ttl=60 * 60)


@router.post("/compare")
def compare_funds(scheme_codes: list[int], db: Session = Depends(get_db)) -> dict[str, Any]:
    if not scheme_codes:
        raise HTTPException(status_code=400, detail="Provide at least one scheme_code")
    if len(scheme_codes) > 5:
        raise HTTPException(status_code=400, detail="At most 5 funds may be compared")

    funds = (
        db.execute(
            select(Fund)
            .where(Fund.scheme_code.in_(scheme_codes))
            .where(Fund.is_active.is_(True))
        )
        .scalars()
        .all()
    )
    if len(funds) != len(scheme_codes):
        missing = sorted(set(scheme_codes) - {f.scheme_code for f in funds})
        raise HTTPException(status_code=404, detail=f"Schemes not found: {missing}")

    metrics_by_code = {
        m.scheme_code: m
        for m in db.execute(
            select(FundMetric).where(FundMetric.scheme_code.in_(scheme_codes))
        ).scalars().all()
    }
    latest_score_rows = (
        db.execute(
            select(FundScore)
            .where(FundScore.scheme_code.in_(scheme_codes))
            .order_by(FundScore.scheme_code, desc(FundScore.computed_at))
        )
        .scalars()
        .all()
    )
    score_by_code: dict[int, FundScore] = {}
    for s in latest_score_rows:
        score_by_code.setdefault(s.scheme_code, s)

    return {
        "funds": [
            _serialise_summary(
                f, metrics_by_code.get(f.scheme_code), score_by_code.get(f.scheme_code)
            )
            for f in funds
        ]
    }


# ---------- Report endpoints (Phase D) -----------------------------------

def _stream_docx(data: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _stream_pdf(data: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{scheme_code}/report")
def fund_report(
    scheme_code: int,
    format: str = Query("docx", pattern="^(docx|pdf)$"),
    audience: str = Query("client", pattern="^(client|advisor)$"),
    db: Session = Depends(get_db),
):
    """Generate a per-fund factsheet as .docx or .pdf. audience=client|advisor."""
    try:
        docx_bytes = build_fund_factsheet(db, scheme_code, audience=audience)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    safe_name = "".join(c if c.isalnum() else "_" for c in str(scheme_code))
    if format == "docx":
        return _stream_docx(docx_bytes, f"factsheet_{safe_name}.docx")

    try:
        pdf_bytes = docx_to_pdf(docx_bytes)
    except PdfConvertError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _stream_pdf(pdf_bytes, f"factsheet_{safe_name}.pdf")


@router.post("/compare/report")
def compare_report(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    """Generate a comparison report. Body: {scheme_codes:[...], format:"docx"|"pdf"}."""
    codes = payload.get("scheme_codes") or []
    fmt = payload.get("format", "docx")
    if fmt not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="format must be docx or pdf")
    if not codes or len(codes) > 5:
        raise HTTPException(status_code=400, detail="Provide 1-5 scheme_codes")

    try:
        docx_bytes = build_comparison_report(db, codes)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    fname = "comparison_" + "_".join(str(c) for c in codes[:5])
    if fmt == "docx":
        return _stream_docx(docx_bytes, f"{fname}.docx")

    try:
        pdf_bytes = docx_to_pdf(docx_bytes)
    except PdfConvertError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _stream_pdf(pdf_bytes, f"{fname}.pdf")
