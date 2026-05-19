import { HelpCircle } from "lucide-react";

export default function Metric({ label, value, hint, tone = "neutral" }) {
  const toneClass = {
    neutral: "text-slate-900",
    good: "text-green-700",
    bad: "text-red-600",
  }[tone];

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-slate-500">
        {label}
        {hint && (
          <span title={hint} className="cursor-help">
            <HelpCircle className="h-3 w-3" />
          </span>
        )}
      </div>
      <div className={`mt-1 text-xl font-bold ${toneClass}`}>{value ?? "—"}</div>
    </div>
  );
}
