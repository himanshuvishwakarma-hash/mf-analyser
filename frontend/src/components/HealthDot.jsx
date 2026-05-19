import { useEffect, useState } from "react";
import { healthApi } from "../api/client.js";

const COLORS = {
  ok: "#16a34a",
  warn: "#f59e0b",
  down: "#dc2626",
  unknown: "#94a3b8",
};

const LABELS = {
  ok: "All systems healthy",
  warn: "Data may be stale",
  down: "Service issue",
  unknown: "Checking...",
};

function ageLabel(hours) {
  if (hours == null) return "never";
  if (hours < 1) return `${Math.round(hours * 60)}m ago`;
  if (hours < 24) return `${Math.round(hours)}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function HealthDot() {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let cancel = false;
    const fetchIt = async () => {
      try {
        const r = await healthApi.deep();
        if (!cancel) setData(r.data);
      } catch {
        if (!cancel) setData({ status: "down", checks: {} });
      }
    };
    fetchIt();
    const t = setInterval(fetchIt, 30000);
    return () => { cancel = true; clearInterval(t); };
  }, []);

  const status = data?.status || "unknown";
  const color = COLORS[status];
  const label = LABELS[status];
  const dataCheck = data?.checks?.data;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs font-medium text-slate-600 hover:bg-slate-50 transition"
        title={label}
      >
        <span
          className="w-2 h-2 rounded-full"
          style={{ backgroundColor: color, boxShadow: `0 0 0 3px ${color}22` }}
        />
        <span className="hidden md:inline">
          {dataCheck ? `Synced ${ageLabel(dataCheck.score_age_hours)}` : "Status"}
        </span>
      </button>

      {open && data && (
        <div className="absolute right-0 mt-2 w-72 bg-white rounded-lg border border-slate-200 shadow-lg p-4 z-20 text-sm">
          <div className="flex items-center justify-between mb-2">
            <div className="font-semibold text-slate-900">{label}</div>
            <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-700">x</button>
          </div>
          <div className="space-y-1.5 text-xs">
            {Object.entries(data.checks || {}).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <span className="capitalize text-slate-500">{k}</span>
                <span
                  className="px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide font-semibold"
                  style={{ backgroundColor: `${COLORS[v.status] || COLORS.unknown}22`, color: COLORS[v.status] || COLORS.unknown }}
                >
                  {v.status}
                </span>
              </div>
            ))}
          </div>
          {dataCheck && (
            <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500 space-y-0.5">
              <div>Funds: {dataCheck.funds_total?.toLocaleString()}</div>
              <div>Scored: {dataCheck.funds_scored?.toLocaleString()}</div>
              <div>Last NAV: {dataCheck.latest_nav_date || "-"}</div>
              <div>Last score: {ageLabel(dataCheck.score_age_hours)}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
