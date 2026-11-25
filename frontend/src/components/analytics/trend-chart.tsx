"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useWidth } from "@/hooks/use-width";
import { compact, niceTicks, type DayPoint, type Measure } from "@/lib/analytics";

const H = 220;
const PAD = { top: 12, right: 12, bottom: 26, left: 44 };

const dateLabel = (d: Date) => d.toLocaleDateString([], { month: "short", day: "numeric" });

/** One series over time: 2px line, 10% area wash, crosshair + tooltip, table view. */
export function TrendChart({ points, measure, label }: { points: DayPoint[]; measure: Measure; label: string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const values = points.map((p) => p[measure]);
  const ticks = niceTicks(Math.max(...values, 0));
  const top = ticks[ticks.length - 1] || 1;
  const innerW = Math.max(0, width - PAD.left - PAD.right);
  const innerH = H - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (points.length > 1 ? (i / (points.length - 1)) * innerW : innerW / 2);
  const y = (v: number) => PAD.top + innerH - (v / top) * innerH;
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[measure]).toFixed(1)}`).join("");
  const area = `${line}L${x(points.length - 1)},${y(0)}L${x(0)},${y(0)}Z`;
  const labelEvery = Math.ceil(points.length / Math.max(2, Math.floor(innerW / 70)));
  const shown = active ?? null;

  const pick = (clientX: number, rect: DOMRect) => {
    const rel = clientX - rect.left - PAD.left;
    setActive(Math.max(0, Math.min(points.length - 1, Math.round((rel / Math.max(innerW, 1)) * (points.length - 1)))));
  };

  return (
    <div>
      <div ref={ref} className="relative">
        {width > 0 && (
          <svg
            width={width}
            height={H}
            role="img"
            aria-label={`${label} per day. Use the arrow keys to read each day.`}
            tabIndex={0}
            className="block rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onPointerMove={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
            onPointerLeave={() => setActive(null)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") setActive((a) => Math.min(points.length - 1, (a ?? -1) + 1));
              if (e.key === "ArrowLeft") setActive((a) => Math.max(0, (a ?? points.length) - 1));
              if (e.key === "Escape") setActive(null);
            }}
            onBlur={() => setActive(null)}
          >
            {ticks.map((t) => (
              <g key={t}>
                <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeWidth={1} />
                <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-muted-foreground text-[11px] tabular-nums">
                  {compact(t)}
                </text>
              </g>
            ))}
            {points.map((p, i) => {
              const last = points.length - 1;
              // regular labels every few days, plus the last day (skipping a regular one that would collide with it)
              const show = i === last || (i % labelEvery === 0 && last - i >= labelEvery * 0.6);
              return show ? (
                <text key={p.key} x={x(i)} y={H - 6} textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"} className="fill-muted-foreground text-[11px]">
                  {dateLabel(p.date)}
                </text>
              ) : null;
            })}
            {/* A fade, not a draw-on: pathLength goes stale when the chart resizes, and Chrome doesn't always
                repaint an animated clip-path on SVG groups. Opacity always repaints. */}
            <motion.g key={`series-${measure}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}>
              <path d={area} fill="var(--chart-mark)" fillOpacity={0.1} />
              <path d={line} fill="none" stroke="var(--chart-mark)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            </motion.g>
            {/* end value, labelled once */}
            <circle cx={x(points.length - 1)} cy={y(values[values.length - 1])} r={4} fill="var(--chart-mark)" stroke="var(--card)" strokeWidth={2} />
            {shown != null && (
              <g pointerEvents="none">
                <line x1={x(shown)} x2={x(shown)} y1={PAD.top} y2={y(0)} stroke="var(--muted-foreground)" strokeOpacity={0.5} strokeWidth={1} />
                <circle cx={x(shown)} cy={y(values[shown])} r={5} fill="var(--chart-mark)" stroke="var(--card)" strokeWidth={2} />
              </g>
            )}
          </svg>
        )}
        {shown != null && width > 0 && (
          <div
            role="status"
            className="pointer-events-none absolute top-1 rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md"
            style={{ left: Math.min(Math.max(x(shown) - 70, 0), width - 150), width: 140 }}
          >
            <p className="text-base font-semibold">{values[shown].toLocaleString()}</p>
            <p className="text-muted-foreground">
              {label}, {points[shown].date.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}
            </p>
            <p className="text-muted-foreground">{points[shown].posts} post{points[shown].posts === 1 ? "" : "s"} published</p>
          </div>
        )}
      </div>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-muted-foreground">Show as table</summary>
        <div className="mt-2 max-h-56 overflow-auto rounded-lg border border-border">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-card text-muted-foreground">
              <tr><th className="px-3 py-2 font-medium">Day</th><th className="px-3 py-2 text-right font-medium">Posts</th><th className="px-3 py-2 text-right font-medium">{label}</th></tr>
            </thead>
            <tbody className="tabular-nums">
              {points.filter((p) => p.posts || p[measure]).map((p) => (
                <tr key={p.key} className="border-t border-border">
                  <td className="px-3 py-1.5">{dateLabel(p.date)}</td>
                  <td className="px-3 py-1.5 text-right">{p.posts}</td>
                  <td className="px-3 py-1.5 text-right">{p[measure].toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
