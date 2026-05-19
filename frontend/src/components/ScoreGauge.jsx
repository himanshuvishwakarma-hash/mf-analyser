// Semicircular score dial (0-100). Red -> Amber -> Green gradient.
// Self-contained SVG, no external chart lib needed.

function scoreColor(score) {
  if (score == null) return "#cbd5e1"; // slate-300
  if (score >= 75) return "#16a34a";   // green-600
  if (score >= 60) return "#84cc16";   // lime-500
  if (score >= 40) return "#f59e0b";   // amber-500
  if (score >= 20) return "#f97316";   // orange-500
  return "#dc2626";                     // red-600
}

function scoreLabel(score) {
  if (score == null) return "Not yet rated";
  if (score >= 75) return "Strong";
  if (score >= 60) return "Accumulate";
  if (score >= 40) return "Neutral";
  if (score >= 20) return "Caution";
  return "Avoid";
}

export default function ScoreGauge({ score, size = 120, showLabel = true }) {
  const r = 50;
  const cx = 60;
  const cy = 60;
  const circumference = Math.PI * r; // half circle
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score)) / 100;
  const offset = circumference * (1 - pct);
  const color = scoreColor(score);

  return (
    <div className="inline-flex flex-col items-center">
      <svg width={size} height={size * 0.72} viewBox="0 0 120 80">
        {/* track */}
        <path
          d={`M 10 60 A ${r} ${r} 0 0 1 110 60`}
          stroke="#e2e8f0"
          strokeWidth="10"
          strokeLinecap="round"
          fill="none"
        />
        {/* value */}
        <path
          d={`M 10 60 A ${r} ${r} 0 0 1 110 60`}
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          fill="none"
          strokeDasharray={`${circumference}`}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 600ms ease" }}
        />
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          fontSize="22"
          fontWeight="700"
          fill="#0f172a"
        >
          {score == null ? "—" : Math.round(score)}
        </text>
      </svg>
      {showLabel && (
        <span
          className="text-xs font-medium px-2 py-0.5 rounded-full -mt-1"
          style={{ backgroundColor: `${color}1a`, color }}
        >
          {scoreLabel(score)}
        </span>
      )}
    </div>
  );
}
