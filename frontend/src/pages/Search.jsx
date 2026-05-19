import { useEffect, useMemo, useState } from "react";
import { Search as SearchIcon, Sparkles, Filter, Loader2, AlertCircle } from "lucide-react";
import FundCard from "../components/FundCard.jsx";
import EmptyState from "../components/EmptyState.jsx";
import { fundsApi } from "../api/client.js";

const CATEGORIES = ["All", "Equity", "Debt", "Hybrid", "Index/ETF", "Solution", "Other"];

function useDebounced(value, delay = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return v;
}

export default function Search() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("All");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const debouncedQ = useDebounced(q, 350);

  useEffect(() => {
    let cancel = false;
    setLoading(true);
    setError(null);

    const fetchData = async () => {
      try {
        let resp;
        if (debouncedQ && debouncedQ.length >= 2) {
          resp = await fundsApi.search(debouncedQ, 30);
        } else {
          resp = await fundsApi.list({
            page: 1,
            limit: 30,
            ...(category !== "All" ? { category } : {}),
          });
        }
        if (!cancel) setItems(resp.data.items || []);
      } catch (e) {
        if (!cancel) {
          setItems([]);
          setError(
            e?.response?.status === 501
              ? "We're still wiring up live data. Check back shortly."
              : "Could not reach the fund database. Is the backend running?"
          );
        }
      } finally {
        if (!cancel) setLoading(false);
      }
    };

    fetchData();
    return () => {
      cancel = true;
    };
  }, [debouncedQ, category]);

  const filtered = useMemo(() => items, [items]);
  const hasResults = filtered.length > 0;

  return (
    <div>
      {/* Hero */}
      <section className="rounded-2xl bg-gradient-to-br from-brand-700 via-brand-500 to-brand-700 text-white px-8 py-10 shadow-sm">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 text-xs uppercase tracking-wide bg-white/10 rounded-full px-3 py-1 mb-4">
            <Sparkles className="h-3 w-3" />
            Z1N Capital research desk
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold leading-tight">
            Find the right mutual fund in seconds.
          </h1>
          <p className="mt-2 text-brand-100/90 text-sm sm:text-base">
            Search across every active scheme in India. Each fund is scored on a 0&ndash;100
            scale that blends past performance, risk, cost, and recent momentum &mdash; so
            you don&rsquo;t have to read fact sheets to know what&rsquo;s good.
          </p>

          <div className="mt-6 relative">
            <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Try &ldquo;Axis Bluechip&rdquo;, &ldquo;SBI Liquid&rdquo;, or a fund house..."
              className="w-full pl-12 pr-4 py-3.5 rounded-xl text-slate-900 bg-white shadow-md focus:outline-none focus:ring-4 focus:ring-white/30"
            />
          </div>
        </div>
      </section>

      {/* Category chips */}
      <section className="mt-6 flex items-center gap-2 flex-wrap">
        <span className="text-xs uppercase tracking-wide text-slate-500 flex items-center gap-1 mr-1">
          <Filter className="h-3 w-3" />
          Category
        </span>
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition ${
              category === c
                ? "bg-brand-700 text-white"
                : "bg-white text-slate-700 border border-slate-200 hover:border-brand-500"
            }`}
          >
            {c}
          </button>
        ))}
      </section>

      {/* Results */}
      <section className="mt-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-slate-900">
            {debouncedQ && debouncedQ.length >= 2
              ? `Results for "${debouncedQ}"`
              : category === "All"
              ? "Browse top funds"
              : `Top ${category} funds`}
          </h2>
          {!loading && hasResults && (
            <span className="text-xs text-slate-500">{filtered.length} funds</span>
          )}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16 text-slate-500">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            Loading funds...
          </div>
        ) : error ? (
          <EmptyState
            icon={AlertCircle}
            title="Couldn't load funds"
            body={error}
          />
        ) : !hasResults ? (
          <EmptyState
            title={debouncedQ ? "No funds matched that search" : "No funds in the database yet"}
            body={
              debouncedQ
                ? "Try a shorter name or a different fund house."
                : "Run the initial data sync from the backend to populate the universe. See the README for the one-liner."
            }
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((f) => (
              <FundCard key={f.scheme_code} fund={f} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
