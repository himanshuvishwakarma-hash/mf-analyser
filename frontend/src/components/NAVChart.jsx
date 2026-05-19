import { useEffect, useMemo, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Loader2 } from "lucide-react";
import { fundsApi } from "../api/client.js";

const RANGES = [
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 },
  { label: "3Y", days: 365 * 3 },
  { label: "5Y", days: 365 * 5 },
  { label: "Max", days: null },
];

function isoDaysAgo(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function NAVChart({ schemeCode }) {
  const [range, setRange] = useState("1Y");
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancel = false;
    setLoading(true);
    const params = {};
    const r = RANGES.find((x) => x.label === range);
    if (r?.days) params.from = isoDaysAgo(r.days);
    fundsApi.nav(schemeCode, params).then((resp) => {
      if (!cancel) setData(resp.data.data || []);
    }).catch(() => !cancel && setData([])).finally(() => !cancel && setLoading(false));
    return () => {
      cancel = true;
    };
  }, [schemeCode, range]);

  // Down-sample to ~250 points so the chart renders smoothly even on Max range.
  const points = useMemo(() => {
    if (!data.length) return [];
    const step = Math.max(1, Math.floor(data.length / 250));
    return data.filter((_, i) => i % step === 0);
  }, [data]);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-slate-900">NAV history</h2>
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
        <div className="flex items-center justify-center h-48 text-slate-500">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          Loading...
        </div>
      ) : points.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-slate-400 text-sm">
          No NAV data available.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={points} margin={{ top: 5, right: 5, left: 10, bottom: 5 }}>
            <XAxis
              dataKey="date"
              tickFormatter={(d) => d.slice(0, 7)}
              stroke="#94a3b8"
              tick={{ fontSize: 11 }}
              minTickGap={40}
            />
            <YAxis
              domain={["auto", "auto"]}
              stroke="#94a3b8"
              tick={{ fontSize: 11 }}
              width={60}
            />
            <Tooltip
              formatter={(v) => v.toFixed(4)}
              contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0" }}
            />
            <Line
              type="monotone"
              dataKey="nav"
              stroke="#1f3a68"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
