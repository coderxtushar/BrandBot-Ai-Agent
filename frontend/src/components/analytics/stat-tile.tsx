import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const w = 96,
    h = 28,
    max = Math.max(...values, 1);
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, h - 2 - (v / max) * (h - 4)]);
  const [lx, ly] = pts[pts.length - 1];
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden className="overflow-visible">
      <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" className="text-muted-foreground/50" />
      <circle cx={lx} cy={ly} r={3} fill="var(--chart-mark)" stroke="var(--card)" strokeWidth={2} />
    </svg>
  );
}

/** label · value · change vs the previous period · optional sparkline */
export function StatTile({
  label,
  value,
  delta,
  trend,
  hint,
}: {
  label: string;
  value: string;
  delta?: number | null;
  trend?: number[];
  hint?: string;
}) {
  const up = (delta ?? 0) >= 0;
  return (
    <div className="flex flex-col justify-between gap-3 rounded-2xl border border-border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <div className="flex items-end justify-between gap-2">
        <p className="text-3xl font-semibold tracking-tight">{value}</p>
        {trend && <Sparkline values={trend} />}
      </div>
      <p className="text-xs text-muted-foreground">
        {delta != null ? (
          <span className={cn("inline-flex items-center gap-0.5 font-medium", up ? "text-riso-green" : "text-destructive")}>
            {up ? <ArrowUpRight className="size-3.5" aria-hidden /> : <ArrowDownRight className="size-3.5" aria-hidden />}
            {up ? "+" : "−"}
            {Math.abs(delta * 100).toFixed(0)}%
            <span className="sr-only">{up ? " up" : " down"}</span>
          </span>
        ) : null}{" "}
        {hint}
      </p>
    </div>
  );
}
