import { Link } from "react-router-dom";
import { TrendingUp, Plus, Check } from "lucide-react";
import ScoreGauge from "./ScoreGauge.jsx";
import { useCompareStore } from "../store/compareStore.js";

function pct(v) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

export default function FundCard({ fund }) {
  const { selected, add, remove } = useCompareStore();
  const isSelected = !!selected.find((f) => f.scheme_code === fund.scheme_code);

  const toggle = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (isSelected) remove(fund.scheme_code);
    else add(fund);
  };

  return (
    <Link
      to={`/fund/${fund.scheme_code}`}
      className="group block bg-white rounded-xl border border-slate-200 p-5 hover:border-brand-500 hover:shadow-md transition"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wide text-slate-500 truncate">
            {fund.amc || "—"}
          </div>
          <h3 className="font-semibold text-slate-900 leading-snug line-clamp-2 mt-0.5">
            {fund.fund_name}
          </h3>
          <div className="mt-2 flex items-center gap-2 flex-wrap">
            {fund.category && (
              <span className="text-xs bg-brand-50 text-brand-700 px-2 py-0.5 rounded-full">
                {fund.category}
              </span>
            )}
            {fund.sub_category && (
              <span className="text-xs text-slate-500">{fund.sub_category}</span>
            )}
          </div>
        </div>
        <ScoreGauge score={fund.composite_score} size={92} />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3 text-center">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-slate-500">1 yr</div>
          <div className="font-semibold text-slate-900 text-sm">{pct(fund.cagr_1y)}</div>
        </div>
        <div className="border-x border-slate-100">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">3 yr</div>
          <div className="font-semibold text-slate-900 text-sm">{pct(fund.cagr_3y)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-slate-500">5 yr</div>
          <div className="font-semibold text-slate-900 text-sm">{pct(fund.cagr_5y)}</div>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <TrendingUp className="h-3 w-3" />
          Annual cost: {fund.expense_ratio != null ? `${fund.expense_ratio}%` : "—"}
        </span>
        <button
          onClick={toggle}
          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition ${
            isSelected
              ? "bg-brand-500 text-white"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          {isSelected ? <Check className="h-3 w-3" /> : <Plus className="h-3 w-3" />}
          {isSelected ? "Added" : "Compare"}
        </button>
      </div>
    </Link>
  );
}
