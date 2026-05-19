import { useEffect, useState } from "react";
import { ShieldAlert, Play, RefreshCw, CheckCircle2, AlertTriangle, Database } from "lucide-react";
import { adminApi, healthApi } from "../api/client.js";

const TOKEN_KEY = "z1n_admin_token";

export default function Admin() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) || "");
  const [health, setHealth] = useState(null);
  const [seed, setSeed] = useState(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Fetch open status (no auth needed).
  useEffect(() => {
    let cancel = false;
    async function fetchAll() {
      try {
        const [h, s] = await Promise.all([healthApi.deep(), adminApi.seedStatus()]);
        if (!cancel) {
          setHealth(h.data);
          setSeed(s.data);
        }
      } catch {
        if (!cancel) setError("Could not reach backend.");
      }
    }
    fetchAll();
    const t = setInterval(fetchAll, 15000);
    return () => { cancel = true; clearInterval(t); };
  }, []);

  const onRunCascade = async () => {
    if (!token) { setError("Enter the admin token first."); return; }
    sessionStorage.setItem(TOKEN_KEY, token);
    setRunning(true); setError(null); setResult(null);
    try {
      const r = await adminApi.runCascade(token);
      setResult(r.data);
    } catch (e) {
      const code = e?.response?.status;
      setError(code === 401 ? "Invalid admin token." :
               code === 503 ? "Admin endpoints disabled (ADMIN_TOKEN unset on server)." :
               "Cascade trigger failed.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <ShieldAlert className="h-5 w-5 text-amber-600" />
        <h1 className="text-2xl font-bold text-slate-900">Admin</h1>
        <span className="text-xs text-slate-500 ml-2">v2 - simple shared-secret auth</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* System health */}
        <section className="bg-white rounded-2xl border border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Database className="h-4 w-4 text-brand-700" />
            System health
          </h2>
          {!health ? (
            <p className="text-sm text-slate-500">Loading...</p>
          ) : (
            <div className="space-y-2 text-sm">
              {Object.entries(health.checks || {}).map(([k, v]) => (
                <CheckRow key={k} name={k} value={v} />
              ))}
              <div className="pt-3 mt-3 border-t border-slate-100 text-xs text-slate-500">
                Rollup status: <strong className="text-slate-700">{health.status}</strong>
              </div>
            </div>
          )}
        </section>

        {/* Seed status */}
        <section className="bg-white rounded-2xl border border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            Data seed
          </h2>
          {!seed ? (
            <p className="text-sm text-slate-500">Loading...</p>
          ) : (
            <ul className="text-sm space-y-2">
              <li className="flex justify-between"><span>Funds in master</span><strong>{seed.fund_count.toLocaleString()}</strong></li>
              <li className="flex justify-between"><span>NAV rows</span><strong>{seed.nav_count.toLocaleString()}</strong></li>
              <li className="flex justify-between"><span>Scores computed</span><strong>{seed.score_count.toLocaleString()}</strong></li>
              <li className="flex justify-between pt-2 border-t border-slate-100">
                <span>Seeded?</span>
                <strong className={seed.seeded ? "text-emerald-700" : "text-amber-700"}>
                  {seed.seeded ? "Yes" : "Not yet"}
                </strong>
              </li>
            </ul>
          )}
        </section>
      </div>

      {/* Manual cascade trigger */}
      <section className="bg-white rounded-2xl border border-slate-200 p-6 mt-4">
        <h2 className="font-semibold text-slate-900 mb-2 flex items-center gap-2">
          <RefreshCw className="h-4 w-4 text-brand-700" />
          Manual refresh
        </h2>
        <p className="text-sm text-slate-500 mb-4">
          Trigger the full nightly cascade now (fund master -> NAV history -> metrics
          -> benchmarks -> scores). Useful after an outage or on first boot.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="password"
            placeholder="Admin token"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="px-3 py-2 border border-slate-200 rounded-lg text-sm w-64"
          />
          <button
            onClick={onRunCascade}
            disabled={running || !token}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-brand-700 text-white hover:bg-brand-900 disabled:opacity-50 transition"
          >
            <Play className="h-4 w-4" />
            {running ? "Dispatching..." : "Run cascade now"}
          </button>
        </div>
        {error && (
          <div className="mt-3 flex items-center gap-1.5 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
            <AlertTriangle className="h-3.5 w-3.5" />
            {error}
          </div>
        )}
        {result && (
          <div className="mt-3 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
            Cascade dispatched. Task IDs: {Object.entries(result.tasks).map(([k, v]) => `${k}=${v.slice(0, 8)}`).join(", ")}
          </div>
        )}
      </section>
    </div>
  );
}

const STATUS_COLORS = {
  ok: "text-emerald-700 bg-emerald-50",
  warn: "text-amber-700 bg-amber-50",
  down: "text-rose-700 bg-rose-50",
  unknown: "text-slate-600 bg-slate-50",
};

function CheckRow({ name, value }) {
  const cls = STATUS_COLORS[value.status] || STATUS_COLORS.unknown;
  return (
    <div className="flex items-center justify-between">
      <span className="capitalize text-slate-700">{name}</span>
      <span className={`text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded ${cls}`}>
        {value.status}
      </span>
    </div>
  );
}
