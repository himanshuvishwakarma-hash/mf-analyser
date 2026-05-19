import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Plus, Check, Calculator, TrendingUp, ShieldCheck, Coins, AlertCircle, Loader2 } from "lucide-react";
import ScoreGauge from "../components/ScoreGauge.jsx";
import Metric from "../components/Metric.jsx";
import EmptyState from "../components/EmptyState.jsx";
import NAVChart from "../components/NAVChart.jsx";
import LivePriceBadge from "../components/LivePriceBadge.jsx";
import ExportButton from "../components/ExportButton.jsx";
import { fundsApi } from "../api/client.js";
import { useCompareStore } from "../store/compareStore.js";

function pct(v, digits = 2) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export default function FundDetail() {
  const { schemeCode } = useParams();
  const [fund, setFund] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { selected, add, remove } = useCompareStore();

  useEffect(() => {
    let cancel = false;
    setLoading(true);
    setError(null);

    fundsApi
      .detail(schemeCode)
      .then((r) => {
        if (!cancel) setFund(r.data);
      })
      .catch((e) => {
        if (!cancel) {
          setError(
            e?.response?.status === 404
              ? "We couldn't find that fund."
              : "Could not load fund details."
          );
        }
      })
      .finally(() => !cancel && setLoading(false));

    return () => {
      cancel = true;
    };
  }, [schemeCode]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        Loading fund...
      </div>
    );
  }

  if (error || !fund) {
    return (
      <EmptyState
        icon={AlertCircle}
        title={error || "Fund not available"}
        cta={
          <Link to="/search" className="text-brand-700 hover:underline text-sm font-medium">
            Back to search
          </Link>
        }
      />
    );
  }

  const isSelected = !!selected.find((f) => f.scheme_code === fund.scheme_code);
  const m = fund.metrics || {};

  return (
    <div>
      <Link
        to="/search"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-700 mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to search
      </Link>

      {/* Header */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-wide text-slate-500">
              {fund.amc || "Asset management company"}
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 mt-1 leading-tight">
              {fund.fund_name}
            </h1>
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              {fund.category && (
                <span className="text-xs bg-brand-50 text-brand-700 px-2.5 py-1 rounded-full">
                  {fund.category}
                </span>
              )}
              {fund.sub_category && (
                <span className="text-xs text-slate-500">{fund.sub_category}</span>
              )}
              {fund.aum_cr != null && (
                <span className="text-xs text-slate-500">
                  • Fund size: Rs {fund.aum_cr.toLocaleString()} Cr
                </span>
              )}
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                onClick={() => (isSelected ? remove(fund.scheme_code) : add(fund))}
                className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  isSelected
                    ? "bg-brand-500 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {isSelected ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                {isSelected ? "Added to compare" : "Add to compare"}
              </button>
              <Link
                to={`/calculator?scheme=${fund.scheme_code}`}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-brand-700 text-white hover:bg-brand-900 transition"
              >
                <Calculator className="h-4 w-4" />
                Run a SIP / Lumpsum projection
              </Link>
              <ExportButton
                apiCall={(fmt) => fundsApi.report(fund.scheme_code, fmt)}
                filenameBase={`factsheet_${fund.scheme_code}`}
                label="Export factsheet"
              />
            </div>
          </div>

          <div className="text-center shrink-0">
            <ScoreGauge score={fund.composite_score} size={160} />
            <div className="text-xs text-slate-500 mt-2 max-w-[180px]">
              Our 0&ndash;100 score combines returns, risk, cost, and momentum vs other funds in
              the same category.
            </div>
          </div>
        </div>

        {fund.is_etf && fund.live_quote && (
          <LivePriceBadge
            initialQuote={fund.live_quote}
            schemeCode={fund.scheme_code}
          />
        )}
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
        <Metric
          label="Latest NAV"
          value={fund.nav_latest != null ? `Rs ${fund.nav_latest.toFixed(4)}` : "—"}
          hint="The unit price as of the most recent trading day"
        />
        <Metric
          label="Annual cost"
          value={fund.expense_ratio != null ? `${fund.expense_ratio}%` : "—"}
          hint="What the fund charges you per year. Lower is better"
        />
        <Metric
          label="Exit fee"
          value={fund.exit_load || "None"}
          hint="Fee deducted if you withdraw early"
        />
        <Metric
          label="As of"
          value={fund.nav_date || "—"}
          hint="Date of the latest NAV"
        />
      </div>

      {/* Performance */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 mt-4">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="h-4 w-4 text-brand-700" />
          <h2 className="font-semibold text-slate-900">Returns</h2>
          <span className="text-xs text-slate-500">annualised, after fund costs</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Metric label="1 year" value={pct(m.cagr_1y)} />
          <Metric label="3 years" value={pct(m.cagr_3y)} />
          <Metric label="5 years" value={pct(m.cagr_5y)} />
          <Metric label="10 years" value={pct(m.cagr_10y)} />
        </div>
      </div>

      {/* Risk + cost */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck className="h-4 w-4 text-brand-700" />
            <h2 className="font-semibold text-slate-900">Risk profile</h2>
          </div>
          <div className="space-y-3">
            <Metric
              label="Return vs risk (Sharpe)"
              value={m.sharpe_ratio != null ? m.sharpe_ratio.toFixed(2) : "—"}
              hint="How much extra return the fund earns for the volatility it takes. Above 1 is good"
            />
            <Metric
              label="Worst-ever fall (drawdown)"
              value={pct(m.max_drawdown, 1)}
              hint="The biggest peak-to-bottom drop in NAV the fund has ever had"
            />
            <Metric
              label="Time taken to fall"
              value={m.drawdown_duration_months != null ? `${m.drawdown_duration_months} months` : "—"}
              hint="How long the fund took to fall from its peak to that worst-ever bottom"
            />
            <Metric
              label="Recovery time"
              value={m.recovery_months != null ? `${m.recovery_months} months` : "Not yet recovered"}
              hint="How long it took to climb back above the previous peak after the worst drawdown"
            />
          </div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Coins className="h-4 w-4 text-brand-700" />
            <h2 className="font-semibold text-slate-900">Recent momentum</h2>
          </div>
          <div className="space-y-3">
            <Metric
              label="Last 3 months"
              value={pct(m.momentum_3m, 1)}
              hint="Point-to-point return over the last 90 days"
            />
            <Metric
              label="Last 6 months"
              value={pct(m.momentum_6m, 1)}
              hint="Point-to-point return over the last 180 days"
            />
            <p className="text-xs text-slate-500 pt-1">
              Momentum signals near-term direction, but doesn&rsquo;t guarantee future returns.
            </p>
          </div>
        </div>
      </div>

      {/* NAV history */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 mt-4">
        <NAVChart schemeCode={fund.scheme_code} />
      </div>
    </div>
  );
}
