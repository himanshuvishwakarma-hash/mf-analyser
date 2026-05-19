import { useEffect, useState } from "react";
import { Database, CheckCircle2, Loader2 } from "lucide-react";
import { adminApi } from "../api/client.js";

/* Polls /admin/seed-status until seeded:true. Shows full-screen overlay until then. */
export default function FirstBootModal() {
  const [status, setStatus] = useState(null);
  const [pollMs, setPollMs] = useState(5000);

  useEffect(() => {
    let cancel = false;
    let timer;

    async function tick() {
      try {
        const r = await adminApi.seedStatus();
        if (cancel) return;
        setStatus(r.data);
        // Once seeded, slow polling to once a minute; or unmount via parent.
        if (r.data.seeded) setPollMs(60_000);
      } catch {
        // Network blip: keep polling.
      } finally {
        if (!cancel) timer = setTimeout(tick, pollMs);
      }
    }

    tick();
    return () => {
      cancel = true;
      if (timer) clearTimeout(timer);
    };
  }, [pollMs]);

  // Hide the modal entirely once seed is complete.
  if (!status || status.seeded) return null;

  const stage = status.in_progress ? "Computing scores" : "Downloading fund universe";

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-8">
        <div className="flex items-center gap-3 mb-4">
          <div className="rounded-full bg-brand-50 p-3">
            <Database className="h-5 w-5 text-brand-700" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">
            Setting up your fund universe
          </h2>
        </div>

        <p className="text-sm text-slate-600 leading-relaxed mb-6">
          On first launch we download the full list of Indian mutual funds and ~3 years
          of NAV history from the public AMFI feed, then compute risk-adjusted scores
          across the universe. This typically takes 60-90 minutes and runs in the
          background. You can keep this tab open or come back later - data will appear
          as it loads.
        </p>

        <div className="space-y-3">
          <StatusRow
            label="Fund master"
            done={status.fund_count > 0}
            value={status.fund_count > 0 ? `${status.fund_count.toLocaleString()} funds` : "Waiting..."}
          />
          <StatusRow
            label="NAV history"
            done={status.nav_count > 0}
            value={status.nav_count > 0 ? `${status.nav_count.toLocaleString()} rows` : "Waiting..."}
          />
          <StatusRow
            label="Scores computed"
            done={status.score_count > 0}
            value={status.score_count > 0 ? `${status.score_count.toLocaleString()} scored` : "Waiting..."}
          />
        </div>

        <div className="mt-6 pt-4 border-t border-slate-100 text-xs text-slate-500 flex items-center gap-1.5">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Current stage: {stage}
        </div>
      </div>
    </div>
  );
}

function StatusRow({ label, done, value }) {
  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-slate-50">
      <div className="flex items-center gap-2">
        {done ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        ) : (
          <Loader2 className="h-4 w-4 text-slate-400 animate-spin" />
        )}
        <span className={`text-sm ${done ? "text-slate-700" : "text-slate-500"}`}>{label}</span>
      </div>
      <span className={`text-sm font-medium ${done ? "text-emerald-700" : "text-slate-500"}`}>
        {value}
      </span>
    </div>
  );
}
