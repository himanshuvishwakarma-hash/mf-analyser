import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Trash2, AlertCircle, Loader2 } from "lucide-react";
import ScoreGauge from "../components/ScoreGauge.jsx";
import EmptyState from "../components/EmptyState.jsx";
import CompareOverlay from "../components/CompareOverlay.jsx";
import ExportButton from "../components/ExportButton.jsx";
import { fundsApi } from "../api/client.js";
import { useCompareStore } from "../store/compareStore.js";

function pct(v) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

const ROWS = [
  { key: "amc", label: "Fund house", get: (f) => f.amc || "—", numeric: false },
  { key: "category", label: "Category", get: (f) => f.category || "—", numeric: false },
  { key: "expense_ratio", label: "Annual cost", get: (f) => (f.expense_ratio != null ? `${f.expense_ratio}%` : "—"), numeric: true, lowerBetter: true },
  { key: "cagr_1y", label: "1-year return", get: (f) => pct(f.cagr_1y), numeric: true, raw: (f) => f.cagr_1y },
  { key: "cagr_3y", label: "3-year return", get: (f) => pct(f.cagr_3y), numeric: true, raw: (f) => f.cagr_3y },
  { key: "cagr_5y", label: "5-year return", get: (f) => pct(f.cagr_5y), numeric: true, raw: (f) => f.cagr_5y },
];

function highlight(row, value, allValues) {
  if (!row.numeric || !row.raw) return "";
  const nums = allValues.map(row.raw).filter((v) => v != null);
  if (nums.length < 2) return "";
  const max = Math.max(...nums);
  const min = Math.min(...nums);
  const raw = row.raw(value);
  if (raw == null) return "";
  if (row.lowerBetter) {
    if (raw === min) return "bg-green-50 text-green-800 font-semibold";
    if (raw === max) return "bg-red-50 text-red-700";
  } else {
    if (raw === max) return "bg-green-50 text-green-800 font-semibold";
    if (raw === min) return "bg-red-50 text-red-700";
  }
  return "";
}

export default function Compare() {
  const { selected, remove, clear } = useCompareStore();
  const [funds, setFunds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (selected.length === 0) {
      setFunds([]);
      return;
    }
    let cancel = false;
    setLoading(true);
    setError(null);
    fundsApi
      .compare(selected.map((f) => f.scheme_code))
      .then((r) => {
        if (!cancel) setFunds(r.data.funds || []);
      })
      .catch(() => !cancel && setError("Could not load comparison."))
      .finally(() => !cancel && setLoading(false));

    return () => {
      cancel = true;
    };
  }, [selected]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Side-by-side comparison</h1>
          <p className="text-sm text-slate-500 mt-1">
            Compare up to 5 funds. The best number in each row is highlighted green; the
            worst is highlighted red.
          </p>
        </div>
        {selected.length > 0 && (
          <div className="flex items-center gap-3">
            <ExportButton
              apiCall={(fmt) =>
                fundsApi.compareReport(selected.map((f) => f.scheme_code), fmt)
              }
              filenameBase={`comparison_${selected.map((f) => f.scheme_code).join("_")}`}
              label="Export comparison"
              disabled={selected.length === 0}
              supportsAudience={false}
            />
            <button
              onClick={clear}
              className="text-sm text-slate-500 hover:text-red-600 inline-flex items-center gap-1"
            >
              <Trash2 className="h-4 w-4" />
              Clear all
            </button>
          </div>
        )}
      </div>

      {selected.length === 0 ? (
        <EmptyState
          title="Pick some funds to compare"
          body="Open any fund and tap 'Add to compare'. Up to 5 at a time."
          cta={
            <Link to="/search" className="text-brand-700 hover:underline text-sm font-medium">
              Go to search
            </Link>
          }
        />
      ) : loading ? (
        <div className="flex items-center justify-center py-16 text-slate-500">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          Loading...
        </div>
      ) : error ? (
        <EmptyState icon={AlertCircle} title="Could not load comparison" body={error} />
      ) : (
        <div className="space-y-4">
          <CompareOverlay funds={funds} />
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          {/* Score row */}
          <div className="grid border-b border-slate-100" style={{ gridTemplateColumns: `200px repeat(${funds.length}, minmax(0, 1fr))` }}>
            <div className="p-4 text-xs uppercase tracking-wide text-slate-500 bg-slate-50">Score</div>
            {funds.map((f) => (
              <div key={f.scheme_code} className="p-4 border-l border-slate-100 text-center">
                <div className="text-xs text-slate-500 truncate mb-1">{f.amc}</div>
                <Link
                  to={`/fund/${f.scheme_code}`}
                  className="block font-semibold text-slate-900 text-sm hover:text-brand-700 truncate mb-2"
                  title={f.fund_name}
                >
                  {f.fund_name}
                </Link>
                <ScoreGauge score={f.composite_score} size={90} />
                <button
                  onClick={() => remove(f.scheme_code)}
                  className="mt-2 text-xs text-slate-400 hover:text-red-600 inline-flex items-center gap-1"
                >
                  <Trash2 className="h-3 w-3" />
                  Remove
                </button>
              </div>
            ))}
          </div>
          {/* Metric rows */}
          {ROWS.map((row) => (
            <div
              key={row.key}
              className="grid border-b border-slate-100 last:border-b-0"
              style={{ gridTemplateColumns: `200px repeat(${funds.length}, minmax(0, 1fr))` }}
            >
              <div className="p-3 text-sm text-slate-600 bg-slate-50/50 sticky left-0">{row.label}</div>
              {funds.map((f) => (
                <div
                  key={f.scheme_code}
                  className={`p-3 border-l border-slate-100 text-center text-sm ${highlight(row, f, funds)}`}
                >
                  {row.get(f)}
                </div>
              ))}
            </div>
          ))}
        </div>
        </div>
      )}
    </div>
  );
}
