import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Legend, ReferenceLine, CartesianGrid,
} from "recharts";
import {
  Sparkles, TrendingUp, Info, AlertCircle, Loader2,
  BarChart3, Table as TableIcon,
} from "lucide-react";
import Metric from "../components/Metric.jsx";
import { fundsApi, calculatorApi } from "../api/client.js";

function fmtRupees(v, opts = {}) {
  if (v == null || !isFinite(v)) return "-";
  const sign = v < 0 ? "-" : "";
  const abs = Math.abs(v);
  if (abs >= 1e7) return `${sign}Rs ${(abs / 1e7).toFixed(opts.digits ?? 2)} Cr`;
  if (abs >= 1e5) return `${sign}Rs ${(abs / 1e5).toFixed(opts.digits ?? 2)} L`;
  return `${sign}Rs ${Math.round(abs).toLocaleString("en-IN")}`;
}

function fmtCompactRupees(v) {
  if (v == null || !isFinite(v)) return "";
  const abs = Math.abs(v);
  if (abs >= 1e7) return `${(v / 1e7).toFixed(1)}Cr`;
  if (abs >= 1e5) return `${(v / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return `${Math.round(v)}`;
}

function impliedCAGR(corpus, invested, years) {
  if (invested <= 0 || years <= 0 || corpus <= 0) return null;
  return Math.pow(corpus / invested, 1 / years) - 1;
}

export default function Calculator() {
  const [params] = useSearchParams();
  const linkedScheme = params.get("scheme");
  const [fund, setFund] = useState(null);

  const [mode, setMode] = useState("sip");
  const [amount, setAmount] = useState(10000);
  const [years, setYears] = useState(10);
  const [overrideRate, setOverrideRate] = useState(null);
  const [view, setView] = useState("chart"); // "chart" | "table"

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!linkedScheme) return;
    fundsApi.detail(linkedScheme).then((r) => setFund(r.data)).catch(() => {});
  }, [linkedScheme]);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const body = {
        scheme_code: linkedScheme ? Number(linkedScheme) : null,
        duration_years: years,
        ...(overrideRate != null ? { expected_return_pct: overrideRate } : {}),
        ...(mode === "sip" ? { monthly_amount: amount } : { amount }),
      };
      const resp = mode === "sip"
        ? await calculatorApi.sip(body)
        : await calculatorApi.lumpsum(body);
      setResult(resp.data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Could not run projection.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(run, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, amount, years, overrideRate, linkedScheme]);

  const chartData = useMemo(() => {
    if (!result) return [];
    const y = result.yearly;
    return y.p50.map((_, i) => {
      const yr = i + 1;
      const invested = mode === "sip" ? amount * yr * 12 : amount;
      return {
        year: yr,
        invested,
        p10: y.p10[i],
        p50: y.p50[i],
        p90: y.p90[i],
        expected: y.expected[i],
        band: y.p90[i] - y.p10[i],
      };
    });
  }, [result, amount, mode]);

  const tableRows = useMemo(() => {
    if (!result) return [];
    const y = result.yearly;
    return y.p50.map((_, i) => {
      const yr = i + 1;
      const invested = mode === "sip" ? amount * yr * 12 : amount;
      return {
        year: yr,
        invested,
        p10: y.p10[i],
        p50: y.p50[i],
        p90: y.p90[i],
        expected: y.expected[i],
        cagr_p10: impliedCAGR(y.p10[i], invested, yr),
        cagr_p50: impliedCAGR(y.p50[i], invested, yr),
        cagr_p90: impliedCAGR(y.p90[i], invested, yr),
      };
    });
  }, [result, amount, mode]);

  const totalInvested = result?.total_invested ?? (mode === "sip" ? amount * years * 12 : amount);
  const final = result?.final;
  const assumedRate = result ? (result.assumptions.mu_annual * 100).toFixed(1) : "...";
  const assumedSource = result?.assumptions?.source || "default";

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="h-4 w-4 text-brand-700" />
        <h1 className="text-2xl font-bold text-slate-900">What could your money become?</h1>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Plug in a monthly SIP or lumpsum, pick how long you stay invested, and we run 10,000
        Monte Carlo simulations to show the range of likely outcomes.
      </p>

      {fund && (
        <div className="mb-4 rounded-xl bg-brand-50 border border-brand-100 p-4 text-sm">
          <div className="text-brand-700 font-medium">Projecting for: {fund.fund_name}</div>
          <div className="text-brand-700/70 text-xs mt-0.5">
            Using this fund&rsquo;s historical return and volatility.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Inputs */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6">
          <div className="flex gap-2 mb-6">
            <button
              onClick={() => setMode("sip")}
              className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition ${
                mode === "sip" ? "bg-brand-700 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              Monthly SIP
            </button>
            <button
              onClick={() => setMode("lumpsum")}
              className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition ${
                mode === "lumpsum" ? "bg-brand-700 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              One-time Lumpsum
            </button>
          </div>

          <label className="block mb-5">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium text-slate-700">
                {mode === "sip" ? "Monthly investment" : "Lumpsum amount"}
              </span>
              <span className="text-sm text-slate-500">Rs {amount.toLocaleString("en-IN")}</span>
            </div>
            <input
              type="range"
              min={mode === "sip" ? 500 : 5000}
              max={mode === "sip" ? 100000 : 5000000}
              step={mode === "sip" ? 500 : 5000}
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
              className="w-full accent-brand-700"
            />
          </label>

          <label className="block mb-5">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium text-slate-700">Investment duration</span>
              <span className="text-sm text-slate-500">{years} years</span>
            </div>
            <input
              type="range"
              min={1}
              max={30}
              step={1}
              value={years}
              onChange={(e) => setYears(Number(e.target.value))}
              className="w-full accent-brand-700"
            />
          </label>

          <label className="block">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium text-slate-700">Expected annual return</span>
              <span className="text-sm text-slate-500">
                {overrideRate != null ? `${overrideRate}%` : `${assumedRate}% (auto)`}
              </span>
            </div>
            <input
              type="range"
              min={4}
              max={20}
              step={0.5}
              value={overrideRate ?? Number(assumedRate)}
              onChange={(e) => setOverrideRate(Number(e.target.value))}
              className="w-full accent-brand-700"
            />
            <div className="text-xs text-slate-400 mt-1 flex items-start gap-1">
              <Info className="h-3 w-3 mt-0.5 shrink-0" />
              {assumedSource === "fund_5y_history" && "Auto-pulled from this fund's 5-year history."}
              {assumedSource === "fund_3y_history" && "Auto-pulled from this fund's 3-year history."}
              {(assumedSource === "default" || assumedSource === "user_override") &&
                "Equity ~10-14% historically, debt ~6-8%. Past returns don't guarantee future returns."}
            </div>
          </label>
        </div>

        {/* Results card */}
        <div className="bg-gradient-to-br from-brand-50 to-white rounded-2xl border border-brand-100 p-6">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="h-4 w-4 text-brand-700" />
            <h2 className="font-semibold text-slate-900">Projected outcome at year {years}</h2>
          </div>
          <p className="text-xs text-slate-500 mb-5">Based on 10,000 simulations.</p>

          {loading ? (
            <div className="flex items-center justify-center py-10 text-slate-500">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              Running simulations...
            </div>
          ) : error ? (
            <div className="rounded-lg bg-red-50 border border-red-100 p-3 text-sm text-red-700 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              {error}
            </div>
          ) : final ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="rounded-xl bg-white border border-slate-200 p-5">
                <div className="text-xs uppercase tracking-wide text-slate-500">Calculated return</div>
                <div className="mt-1 text-3xl font-bold text-slate-900">{fmtRupees(final.expected)}</div>
                <div className="mt-2 text-xs text-slate-500">
                  Projection at the fund's historical CAGR.
                </div>
              </div>
              <div className="rounded-xl bg-brand-700 text-white border border-brand-700 p-5">
                <div className="text-xs uppercase tracking-wide text-brand-100/90">Projected return</div>
                <div className="mt-1 text-3xl font-bold">{fmtRupees(final.p50)}</div>
                <div className="mt-2 text-xs text-brand-100/80">
                  Median across 10,000 Monte Carlo paths.
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* View toggle */}
      {chartData.length > 0 && (
        <>
          <div className="flex items-center justify-between mt-6 mb-3">
            <h2 className="font-semibold text-slate-900">Year-by-year breakdown</h2>
            <div className="inline-flex bg-white border border-slate-200 rounded-lg p-1">
              <button
                onClick={() => setView("chart")}
                className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium transition ${
                  view === "chart" ? "bg-brand-700 text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <BarChart3 className="h-3 w-3" />
                Chart
              </button>
              <button
                onClick={() => setView("table")}
                className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium transition ${
                  view === "table" ? "bg-brand-700 text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <TableIcon className="h-3 w-3" />
                Table
              </button>
            </div>
          </div>

          {view === "chart" ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-6">
              <p className="text-xs text-slate-500 mb-4">
                Shaded band = where 80% of simulations end up. P50 line is the median.
                The dashed grey line is what you put in (cumulative contributions).
              </p>
              <ResponsiveContainer width="100%" height={380}>
                <AreaChart data={chartData} margin={{ top: 8, right: 20, left: 10, bottom: 5 }}>
                  <defs>
                    <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#1f3a68" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#1f3a68" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="year"
                    tickFormatter={(y) => `${y}y`}
                    stroke="#94a3b8"
                    tick={{ fontSize: 12 }}
                  />
                  <YAxis
                    tickFormatter={fmtCompactRupees}
                    stroke="#94a3b8"
                    tick={{ fontSize: 12 }}
                    width={70}
                  />
                  <Tooltip
                    formatter={(v, key) => [fmtRupees(v), {
                      p10: "Pessimistic (P10)",
                      p50: "Median (P50)",
                      p90: "Optimistic (P90)",
                      invested: "You invested",
                      expected: "Expected",
                    }[key] || key]}
                    labelFormatter={(y) => `Year ${y}`}
                    contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0" }}
                  />
                  <Legend wrapperStyle={{ paddingTop: 8 }} />
                  {/* Shaded band: fake stack of p10 (transparent) + (p90-p10) */}
                  <Area
                    type="monotone"
                    dataKey="p10"
                    stackId="band"
                    stroke="none"
                    fill="transparent"
                    legendType="none"
                    name="P10 floor"
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="band"
                    stackId="band"
                    stroke="none"
                    fill="url(#bandGrad)"
                    legendType="none"
                    name="P10 - P90 range"
                    isAnimationActive={false}
                  />
                  {/* Visible lines */}
                  <Area
                    type="monotone"
                    dataKey="p90"
                    stroke="#16a34a"
                    strokeWidth={1.5}
                    fill="transparent"
                    name="Optimistic (P90)"
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Area
                    type="monotone"
                    dataKey="p50"
                    stroke="#1f3a68"
                    strokeWidth={2.5}
                    fill="transparent"
                    name="Median (P50)"
                    dot={false}
                    activeDot={{ r: 5 }}
                  />
                  <Area
                    type="monotone"
                    dataKey="p10"
                    stroke="#dc2626"
                    strokeWidth={1.5}
                    fill="transparent"
                    name="Pessimistic (P10)"
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Area
                    type="monotone"
                    dataKey="invested"
                    stroke="#94a3b8"
                    strokeDasharray="5 4"
                    strokeWidth={1.5}
                    fill="transparent"
                    name="You invested"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                    <tr>
                      <th className="px-4 py-3 text-left">Year</th>
                      <th className="px-4 py-3 text-right">You invested</th>
                      <th className="px-4 py-3 text-right">Pessimistic (P10)</th>
                      <th className="px-4 py-3 text-right">Median (P50)</th>
                      <th className="px-4 py-3 text-right">Optimistic (P90)</th>
                      <th className="px-4 py-3 text-right">Median CAGR</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {tableRows.map((r) => (
                      <tr key={r.year} className="hover:bg-slate-50/50">
                        <td className="px-4 py-2.5 font-medium text-slate-900">Year {r.year}</td>
                        <td className="px-4 py-2.5 text-right text-slate-600">{fmtRupees(r.invested)}</td>
                        <td className="px-4 py-2.5 text-right text-red-600">{fmtRupees(r.p10)}</td>
                        <td className="px-4 py-2.5 text-right text-brand-700 font-semibold">{fmtRupees(r.p50)}</td>
                        <td className="px-4 py-2.5 text-right text-green-700">{fmtRupees(r.p90)}</td>
                        <td className="px-4 py-2.5 text-right text-slate-700">
                          {r.cagr_p50 != null ? `${(r.cagr_p50 * 100).toFixed(1)}%` : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="px-4 py-3 border-t border-slate-100 text-xs text-slate-500">
                <span className="font-medium">Median CAGR</span> = the implied annualised return
                you would have earned if your investment grew to the P50 outcome by that year.
              </div>
            </div>
          )}

          <div className="mt-3 rounded-lg bg-amber-50 border border-amber-100 p-3 text-xs text-amber-800 flex items-start gap-2">
            <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            Monte Carlo is a model, not a prediction. Outcomes can land outside the shaded band.
          </div>
        </>
      )}
    </div>
  );
}
