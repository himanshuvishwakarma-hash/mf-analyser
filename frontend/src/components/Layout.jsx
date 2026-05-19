import { Outlet, NavLink, Link } from "react-router-dom";
import { Search, GitCompare, Calculator, TrendingUp } from "lucide-react";
import { useCompareStore } from "../store/compareStore.js";
import HealthDot from "./HealthDot.jsx";

const tabs = [
  { to: "/search", label: "Discover", icon: Search },
  { to: "/compare", label: "Compare", icon: GitCompare },
  { to: "/calculator", label: "Calculator", icon: Calculator },
];

export default function Layout() {
  const selected = useCompareStore((s) => s.selected);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="mx-auto max-w-7xl px-6 py-3 flex items-center justify-between">
          <Link to="/search" className="flex items-center gap-2 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-700 to-brand-500 flex items-center justify-center text-white shadow-sm">
              <TrendingUp className="h-4 w-4" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-bold text-slate-900 group-hover:text-brand-700 transition">
                Z1N Capital
              </div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500">
                Mutual Fund Analyser
              </div>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            <HealthDot />
            <nav className="flex gap-1">
            {tabs.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                className={({ isActive }) =>
                  `inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition ${
                    isActive
                      ? "bg-brand-50 text-brand-700"
                      : "text-slate-600 hover:text-brand-700 hover:bg-slate-50"
                  }`
                }
              >
                <t.icon className="h-4 w-4" />
                <span className="hidden sm:inline">{t.label}</span>
              </NavLink>
            ))}
            </nav>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <Outlet />
        </div>
      </main>

      {selected.length > 0 && (
        <footer className="sticky bottom-0 bg-white border-t border-slate-200 shadow-lg">
          <div className="mx-auto max-w-7xl px-6 py-3 flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 flex-wrap min-w-0">
              <span className="text-xs uppercase tracking-wide text-slate-500 shrink-0">
                Compare list:
              </span>
              {selected.map((f) => (
                <span
                  key={f.scheme_code}
                  className="inline-flex items-center gap-1 bg-brand-50 text-brand-700 px-2.5 py-1 rounded-full text-xs truncate max-w-[200px]"
                  title={f.fund_name}
                >
                  {f.fund_name}
                </span>
              ))}
            </div>
            <Link
              to="/compare"
              className="bg-brand-700 hover:bg-brand-900 text-white text-sm font-medium px-4 py-2 rounded-lg whitespace-nowrap shadow-sm"
            >
              Compare {selected.length} {selected.length === 1 ? "fund" : "funds"}
            </Link>
          </div>
        </footer>
      )}
    </div>
  );
}
