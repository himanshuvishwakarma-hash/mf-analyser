import { useEffect, useState } from "react";
import { Activity, TrendingUp, TrendingDown, AlertTriangle } from "lucide-react";
import { fundsApi } from "../api/client.js";

/* Helpers */
function fmtPrice(v) {
  if (v == null) return "—";
  return `Rs ${Number(v).toFixed(2)}`;
}

function fmtRelTime(ts) {
  if (!ts) return "no data";
  const then = new Date(ts).getTime();
  const now = Date.now();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

function isMarketOpenIST() {
  // Mon-Fri 09:15-15:30 IST gate. Browser may be in any tz.
  const now = new Date();
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60_000;
  const ist = new Date(utcMs + 5.5 * 3600 * 1000);
  const dow = ist.getDay(); // 0=Sun
  if (dow === 0 || dow === 6) return false;
  const mins = ist.getHours() * 60 + ist.getMinutes();
  return mins >= 555 && mins <= 930; // 09:15 -> 15:30
}

export default function LivePriceBadge({ initialQuote, schemeCode, pollSec = 60 }) {
  const [quote, setQuote] = useState(initialQuote);

  // Poll while page is open + market is open. Polls quietly; no spinner UI.
  useEffect(() => {
    if (!schemeCode) return;
    let cancel = false;
    const tick = () => {
      if (!isMarketOpenIST()) return;
      fundsApi
        .detail(schemeCode)
        .then((r) => {
          if (!cancel && r?.data?.live_quote) setQuote(r.data.live_quote);
        })
        .catch(() => {
          /* keep last good quote */
        });
    };
    const id = setInterval(tick, pollSec * 1000);
    return () => {
      cancel = true;
      clearInterval(id);
    };
  }, [schemeCode, pollSec]);

  if (!quote) return null;

  const change = quote.day_change_pct;
  const up = change != null && change > 0;
  const down = change != null && change < 0;
  const Arrow = up ? TrendingUp : down ? TrendingDown : Activity;
  const tone = up
    ? "text-emerald-700 bg-emerald-50 border-emerald-200"
    : down
    ? "text-rose-700 bg-rose-50 border-rose-200"
    : "text-slate-600 bg-slate-50 border-slate-200";

  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="rounded-full bg-brand-50 p-2">
            <Activity className="h-4 w-4 text-brand-700" />
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-500">
              Live price (ETF)
            </div>
            <div className="text-2xl font-bold text-slate-900">{fmtPrice(quote.last_price)}</div>
            <div className="text-xs text-slate-500">
              Symbol {quote.symbol} • Updated {fmtRelTime(quote.last_traded_at)}
            </div>
          </div>
        </div>

        {change != null && (
          <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-medium ${tone}`}>
            <Arrow className="h-4 w-4" />
            {change > 0 ? "+" : ""}
            {change.toFixed(2)}% today
          </div>
        )}
      </div>

      {quote.stale && (
        <div className="mt-3 flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5" />
          Live data is stale. Showing the most recent value we received.
        </div>
      )}
    </div>
  );
}
