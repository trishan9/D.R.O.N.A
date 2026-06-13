import { cn } from "@/lib/utils";

/** Semicircular engagement gauge (0..1). Mirrors the perception node's EMA value. */
export function EngagementGauge({ value, className }: { value: number; className?: string }) {
  const v = Math.max(0, Math.min(1, value));
  const r = 52;
  const cx = 70;
  const cy = 64;
  const circumference = Math.PI * r; // half-circle arc length
  const dash = circumference * v;
  const pct = Math.round(v * 100);
  const tone = v >= 0.66 ? "hsl(var(--success))" : v >= 0.33 ? "hsl(var(--warning))" : "hsl(var(--muted-foreground))";

  return (
    <div className={cn("flex flex-col items-center", className)}>
      <svg viewBox="0 0 140 78" className="w-full max-w-[180px]">
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke="hsl(var(--muted))"
          strokeWidth="12"
          strokeLinecap="round"
        />
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke={tone}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
          className="transition-all duration-300"
        />
        <text x={cx} y={cy - 6} textAnchor="middle" className="fill-foreground text-[22px] font-bold">
          {pct}
        </text>
        <text x={cx} y={cy + 8} textAnchor="middle" className="fill-muted-foreground text-[9px] uppercase tracking-wide">
          engaged
        </text>
      </svg>
    </div>
  );
}
