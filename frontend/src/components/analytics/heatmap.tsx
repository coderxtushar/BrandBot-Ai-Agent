"use client";

import { useState } from "react";
import { BLOCKS, WEEKDAYS, type Cell } from "@/lib/analytics";

const HEAT = ["var(--heat-1)", "var(--heat-2)", "var(--heat-3)", "var(--heat-4)", "var(--heat-5)"];

/** Weekday × time of day, sequential blue (more interactions = darker on paper, lighter on the dark sheet). */
export function Heatmap({ cells }: { cells: Cell[] }) {
  const [active, setActive] = useState<Cell | null>(null);
  const max = Math.max(...cells.map((c) => c.avgInteractions), 0);
  const bin = (v: number) => Math.min(4, Math.floor((v / max) * 5));

  return (
    <div>
      <div className="relative overflow-x-auto">
        <div className="grid min-w-[420px] grid-cols-[2.5rem_repeat(6,minmax(0,1fr))] gap-[2px]" aria-label="Average interactions by day and time">
          <span />
          {BLOCKS.map((b) => (
            <span key={b} className="pb-1 text-center text-[11px] text-muted-foreground">{b}</span>
          ))}
          {WEEKDAYS.map((day, w) => (
            <div key={day} className="contents">
              <span className="self-center text-xs text-muted-foreground">{day}</span>
              {cells.filter((c) => c.weekday === w).map((c) => {
                const label = `${day} ${BLOCKS[c.block]}: ${c.posts ? `${Math.round(c.avgInteractions)} avg interactions over ${c.posts} post${c.posts === 1 ? "" : "s"}` : "no posts yet"}`;
                return (
                  <button
                    key={c.block}
                    type="button"
                    aria-label={label}
                    onPointerEnter={() => setActive(c)}
                    onPointerLeave={() => setActive(null)}
                    onFocus={() => setActive(c)}
                    onBlur={() => setActive(null)}
                    className="h-8 rounded-[4px] outline-none transition hover:brightness-110 focus-visible:ring-2 focus-visible:ring-ring"
                    style={{ background: c.posts && max > 0 ? HEAT[bin(c.avgInteractions)] : "var(--muted)" }}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <p aria-live="polite" className="min-h-4">
          {active ? (active.posts ? `${WEEKDAYS[active.weekday]} ${BLOCKS[active.block]}: ${Math.round(active.avgInteractions)} avg interactions, ${active.posts} post${active.posts === 1 ? "" : "s"}` : `${WEEKDAYS[active.weekday]} ${BLOCKS[active.block]}: no posts yet`) : "Hover a cell for details."}
        </p>
        <span className="flex items-center gap-1.5" aria-hidden>
          Fewer
          {HEAT.map((c) => <span key={c} className="size-3 rounded-[3px]" style={{ background: c }} />)}
          More interactions
        </span>
      </div>
    </div>
  );
}
