"use client";

import { useState, type ReactNode } from "react";
import { motion } from "framer-motion";

export interface BarRow {
  key: string;
  label: ReactNode;
  value: number;
  display: string;
  detail: string; // tooltip / accessible description
}

/** Ranked horizontal bars, one hue: <=24px, square at the baseline, 4px rounded at the data end, value at the tip. */
export function BarList({ rows, empty }: { rows: BarRow[]; empty: string }) {
  const [hover, setHover] = useState<string | null>(null);
  const max = Math.max(...rows.map((r) => r.value), 0);
  if (!rows.length || max === 0) return <p className="py-6 text-sm text-muted-foreground">{empty}</p>;

  return (
    <ul className="space-y-3">
      {rows.map((r, i) => (
        <li
          key={r.key}
          tabIndex={0}
          aria-label={`${typeof r.label === "string" ? r.label : r.key}: ${r.display}. ${r.detail}`}
          onPointerEnter={() => setHover(r.key)}
          onPointerLeave={() => setHover(null)}
          onFocus={() => setHover(r.key)}
          onBlur={() => setHover(null)}
          className="relative grid grid-cols-[minmax(5rem,9rem)_1fr] items-center gap-3 rounded-md py-0.5 outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="truncate text-sm">{r.label}</span>
          <span className="flex items-center gap-2">
            <motion.span
              className="h-3.5 rounded-r-[4px]"
              style={{ background: "var(--chart-mark)", opacity: hover && hover !== r.key ? 0.55 : 1 }}
              initial={{ width: 0 }}
              animate={{ width: `${Math.max((r.value / max) * 80, 1.5)}%` }}
              transition={{ duration: 0.7, delay: i * 0.05, ease: [0.22, 1, 0.36, 1] }}
            />
            <span className="shrink-0 text-sm font-medium tabular-nums">{r.display}</span>
          </span>
          {hover === r.key && (
            <span role="status" className="pointer-events-none absolute -top-9 left-[9rem] z-10 rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs whitespace-nowrap shadow-md">
              {r.detail}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
