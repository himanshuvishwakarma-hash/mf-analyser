# Fund Factsheet Redesign - Design Spec

**Author:** Z1N engineering
**Date:** 2026-05-21
**Status:** Approved

## Goal

Replace the current plain text-only factsheet with a branded, audience-aware
report. One Word/PDF export with a toggle between two tones:

1. **Client** (default) - plain English, friendly labels, hides advanced sub-scores.
2. **Advisor** - keeps technical terms (Sharpe, std dev, drawdown), adds the
   sub-score breakdown grid and ops metadata (AMFI code, plan type, expense
   ratio as-of date).

Same underlying data, different framing.

## Architecture

- **Single Python builder** with `audience` parameter:
  `build_fund_factsheet(session, scheme_code, audience: Literal["client", "advisor"] = "client") -> bytes`
- New module `app/services/report_branding.py` owns:
  - Brand constants (`BRAND_TEAL`, `LOGO_PATH`, `ARIAL_FONT`)
  - `AUDIENCE_LABELS: dict[str, dict[str, str]]` keyed by metric name
  - `AUDIENCE_EXPLAINERS: dict[str, dict[str, str]]` short prose (client only)
  - `score_band(score: float) -> tuple[str, str]` returns ("Strong", "green") etc.
- Existing `report_builder.py` stays the single source of truth for layout.
  Helpers gain an `audience` arg; section-level gating lives in
  `build_fund_factsheet`.
- API: `GET /api/v1/funds/{code}/report?format=docx|pdf&audience=client|advisor`
  - `audience` query param defaults to `"client"`
  - Pydantic-validated regex `^(client|advisor)$`
- Frontend `ExportButton.jsx` adds a 3-state choice: Word, PDF, plus a small
  audience switch (For client / For advisor). Defaults to "For client".

## Document layout

The same six sections appear in both audiences, but content differs:

| Section | Client version | Advisor version |
|---------|----------------|------------------|
| **Cover header** | Z1N logo + "Fund Factsheet" + fund name (big) + AMC (small) | Identical |
| **Snapshot card** | NAV, As of, Fund size, Annual cost, Exit fee | + plan type, AMFI code, expense ratio as-of date |
| **Score panel** | Big score gauge (0-100) + plain-English band ("Strong", "Caution", "Avoid") | + sub-scores grid (Sharpe / CAGR / Drawdown / Expense / Momentum) |
| **Returns** | "What you would have earned" with 1-line explainer | "Annualised CAGR" technical labels |
| **Risk profile** | 3 friendly tiles: "Typical ups and downs", "Worst-ever fall", "Recovery time" | Sharpe ratio, std dev, max drawdown + duration, recovery months - with one-line technical definitions |
| **NAV chart** | Same chart, captioned "Price journey over time" | Same chart, captioned "NAV history" |
| **Footer** | Friendly disclaimer + Z1N tagline | Standard SEBI disclaimer + UTC generation timestamp |

## Audience toggle mechanics

- `AUDIENCE_LABELS` maps metric key to per-audience label.
  Example: `{"sharpe_ratio": {"client": "Risk vs reward", "advisor": "Sharpe ratio"}}`
- `AUDIENCE_EXPLAINERS` is populated for the `client` audience only -
  one short sentence under each metric tile, e.g.
  `{"sharpe_ratio": "Above 1 is good; the fund earns extra return for the swings it takes."}`
- Advisor-only sections gated by `if audience == "advisor":` blocks.
- Score band thresholds (matches existing `ScoreGauge.jsx`):
  - `>= 70` -> `("Strong", brand-teal)`
  - `40-69` -> `("Caution", amber)`
  - `< 40`  -> `("Avoid", rose)`

## Branding

- Logo file path: `backend/data/branding/z1n_logo.png`
- Loader: `_add_logo_header(doc)` tries `LOGO_PATH`; if missing, falls back to
  centered text `"Z1N CAPITAL"` in teal at 10pt bold. Logging warning, not error.
- Recommended logo: PNG, transparent background, at least 300x100 px.
  Square or landscape both work; aspect preserved.
- Font: Arial (already standard). All headings stay in `BRAND_TEAL`.

## Error handling

- Unknown audience value in API -> HTTP 422 (Pydantic regex rejection).
- Logo missing -> warning logged, text fallback used. No 500.
- All existing error paths preserved (404 for missing fund, 503 for PDF service
  down, etc).

## Testing

Four new pytest cases in `tests/test_reports.py`:

1. `test_factsheet_client_hides_sub_scores` - generate client factsheet, parse
   XML, assert sub-score labels (`Sharpe`, `Momentum score` etc.) are NOT
   present.
2. `test_factsheet_advisor_shows_sub_scores` - same but with `audience="advisor"`,
   assert labels ARE present.
3. `test_logo_fallback_when_missing` - point `LOGO_PATH` at non-existent file;
   factsheet still builds, contains the text "Z1N CAPITAL".
4. `test_audience_label_mapping` - verify `AUDIENCE_LABELS["sharpe_ratio"]`
   returns distinct strings for client vs advisor.

Plus two API tests:

5. `test_report_endpoint_accepts_audience_param` - `GET ?audience=advisor` returns 200.
6. `test_report_endpoint_rejects_bad_audience` - `?audience=manager` returns 422.

## What stays the same

- Bytes-returning interface, StreamingResponse plumbing, PDF conversion path,
  cache headers, factsheet filename format, NAV chart PNG, footer disclaimer
  layout (text differs but position identical).

## Out of scope (parked for later)

- Logo CDN / asset versioning - file lives in repo for now.
- Per-client white-label branding - single Z1N look only.
- Translations - English only.
- Comparison report redesign - factsheet only this round; comparison stays
  current layout (will mirror the changes in a follow-up).
- Cover page on its own sheet - single-flow document for now.

## Acceptance criteria

- Hitting the report endpoint without `audience` returns a client factsheet.
- Hitting with `audience=advisor` returns the same data with technical labels
  and the sub-score grid added.
- Logo file present -> rendered top-left of header. Logo missing -> Z1N text
  shown, no error in output.
- All existing report tests still pass.
- New audience tests pass.
- Frontend "For client" / "For advisor" toggle works and produces correctly
  differentiated downloads.

---

*Z1N Capital - Internal - Draft v0.1*
