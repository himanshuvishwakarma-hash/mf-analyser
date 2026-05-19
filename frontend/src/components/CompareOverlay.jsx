import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid,
} from "recharts";
import { Loader2 } from "lucide-react";
import { fundsApi } from "../api/client.js";

const PALETTE = ["#1f3a68", "#16a34a", "#dc2626", "#f59e0b", "#7c3aed"];

function isoDaysAgo(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

const RANGES = [
  { label: "1Y", days: 365 },
  { label: "3Y", days: 365 * 3 },
  { label: "5Y", days: 365 * 5 },
  { label: "Max", days: null },
];

export default function CompareOverlay({ funds }) {
  const [range, setRange] = useState("3Y");
  const [series, setSeries] = useState({}); // scheme_code -> [{date, nav}]
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancel = false;
    setLoading(true);
    const params = {};
    const r = RANGES.find((x) => x.label === range);
    if (r?.days) params.from = isoDaysAgo(r.days);

    Promise.all(
      funds.map((f) =>
        fundsApi.nav(f.scheme_code, params).then((resp) => ({
          code: f.scheme_code,
          data: resp.data.data || [],
        })).catch(() => ({ code: f.scheme_code, data: [] }))
      )
    ).then((results) => {
      if (cancel) return;
      const map = {};
      for (const { code, data } of results) map[code] = data;
      setSeries(map);
    }).finally(() => !cancel && setLoading(false));

    return () => { cancel = true; };
  }, [funds, range]);

  // Build a single merged time-indexed array, rebased to 100 at the first
  // date where every fund has data.
  const chartData = useMemo(() => {
    if (Object.keys(series).length === 0) return [];

    // Find common start = max of first dates across all funds.
    const firstDates = funds
      .map((f) => series[f.scheme_code]?.[0]?.date)
      .filter(Boolean);
    if (firstDates.length === 0) return [];
    const commonStart = firstDates.sort()[firstDates.length - 1];

    // For each fund: find NAV at commonStart (or first NAV after), use as base.
    const bases = {};
    funds.forEach((f) => {
      const s = series[f.scheme_code] || [];
      const baseRow = s.find((p) => p.date >= commonStart);
      bases[f.scheme_code] = baseRow?.nav;
    });

    // Build union of all dates >= commonStart, then per-fund interpolated value.
    const allDatesSet = new Set();
    funds.forEach((f) => {
      (series[f.scheme_code] || []).forEach((p) => {
        if (p.date >= commonStart) allDatesSet.add(p.date);
      });
    });
    const allDates = [...allDatesSet].sort();

    // Down-sample to ~200 points for snappy rendering.
    const step = Math.max(1, Math.floor(allDates.length / 200));
    const sampled = allDates.filter((_, i) => i % step === 0);

    // Build last-seen lookup per fund for fast access.
    const lookup = {};
    funds.forEach((f) => {
      const arr = series[f.scheme_code] || [];
      let i = 0;
      lookup[f.scheme_code] = (date) => {
        while (i + 1 < arr.length && arr[i + 1].date <= date) i++;
        return arr[i]?.nav;
      };
    });

    return sampled.map((d) => {
      const row = { date: d };
      funds.forEach((f) => {
        const v = lookup[f.scheme_code](d);
        const base = bases[f.scheme_code];
        if (v != null && base) row[f.scheme_code] = (v / base) * 100;
      });
      return row;
    });
  }, [funds, series]);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="font-semibold text-slate-900">Performance overlay</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Each fund rebased to 100 at the earliest common date. Higher = more growth.
          </p>
        </div>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r.label}
              onClick={() => setRange(r.label)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
                range === r.label
                  ? "bg-brand-700 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>
      {loading ? (
        <div className="flex items-center justify-center h-72 text-slate-500">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          Loading NAV...
        </div>
      ) : chartData.length === 0 ? (
        <div className="h-72 flex items-center justify-center text-slate-400 text-sm">
          Not enough NAV data to overlay. Try a shorter date range.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="date"
              tickFormatter={(d) => d?.slice(0, 7)}
              stroke="#94a3b8"
              tick={{ fontSize: 11 }}
              minTickGap={40}
            />
            <YAxis
              stroke="#94a3b8"
              tick={{ fontSize: 11 }}
              width={50}
              tickFormatter={(v) => v.toFixed(0)}
            />
            <Tooltip
              formatter={(v) => (v != null ? v.toFixed(2) : "-")}
              contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0" }}
            />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
            {funds.map((f, i) => (
              <Line
                key={f.scheme_code}
                type="monotone"
                dataKey={f.scheme_code}
                name={f.fund_name}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
