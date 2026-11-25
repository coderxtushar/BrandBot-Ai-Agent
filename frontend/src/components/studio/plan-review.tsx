"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ExternalLink, PenLine, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { platform } from "@/lib/platforms";
import type { PlanDecision, RunDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

/** A run paused after research: approve or adjust the plan before anything is written. */
export function PlanReview({
  run,
  onContinue,
  onDiscard,
  busy,
}: {
  run: RunDetail;
  onContinue: (d: PlanDecision) => void;
  onDiscard: () => void;
  busy: boolean;
}) {
  const plan = run.plan!;
  const [angle, setAngle] = useState(plan.angle);
  const [pillar, setPillar] = useState(plan.pillar);
  const [keep, setKeep] = useState(() => new Set(run.sources.map((s) => s.url)));
  const [guidance, setGuidance] = useState("");

  const toggle = (url: string) =>
    setKeep((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });

  return (
    <form
      className="space-y-7"
      onSubmit={(e) => {
        e.preventDefault();
        onContinue({
          angle: angle.trim() !== plan.angle ? angle.trim() : null,
          pillar: pillar.trim() !== plan.pillar ? pillar.trim() : null,
          source_urls: keep.size === run.sources.length ? null : [...keep],
          guidance: guidance.trim(),
        });
      }}
    >
      <div>
        <h2 className="font-title text-2xl">Check the plan before Brand Bot writes</h2>
        <p className="mt-1 max-w-prose text-sm text-muted-foreground">
          Writing for {run.platforms.map((p) => platform(p).short).join(", ")} starts when you continue. This run is
          saved, so you can come back to it later from your history.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="plan-angle">Angle</Label>
        <Textarea
          id="plan-angle"
          rows={3}
          value={angle}
          maxLength={500}
          required
          onChange={(e) => setAngle(e.target.value)}
          className="min-h-0 resize-y font-title text-lg"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="plan-pillar">Topic it belongs to</Label>
        <Input id="plan-pillar" value={pillar} maxLength={200} required onChange={(e) => setPillar(e.target.value)} />
      </div>

      <fieldset>
        <legend className="text-sm font-medium">
          Sources to use <span className="font-normal text-muted-foreground">({keep.size} of {run.sources.length})</span>
        </legend>
        {run.sources.length === 0 && (
          <p className="mt-2 text-sm text-muted-foreground">No sources were found, so the writers will rely on general expertise.</p>
        )}
        <ul className="mt-3 space-y-2">
          {run.sources.map((s, i) => {
            const on = keep.has(s.url);
            return (
              <motion.li key={s.url} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                <label
                  className={cn(
                    "flex cursor-pointer gap-3 rounded-xl border p-3 transition-colors",
                    on ? "border-ink/40 bg-card" : "border-dashed border-border opacity-60",
                  )}
                >
                  <input
                    type="checkbox"
                    className="mt-1 size-4 shrink-0 accent-[var(--riso-blue)]"
                    checked={on}
                    onChange={() => toggle(s.url)}
                  />
                  <span className="min-w-0">
                    <span className="flex items-center gap-1.5 text-sm font-medium">
                      <span className={cn("truncate", !on && "line-through")}>{s.title || s.url}</span>
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noreferrer"
                        className="shrink-0 text-muted-foreground hover:text-primary"
                        aria-label={`Open ${s.title || "source"}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="size-3.5" />
                      </a>
                    </span>
                    <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">{s.snippet}</span>
                  </span>
                </label>
              </motion.li>
            );
          })}
        </ul>
      </fieldset>

      <div className="space-y-1.5">
        <Label htmlFor="plan-guidance">
          Notes for the writers <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <Textarea
          id="plan-guidance"
          rows={3}
          maxLength={1000}
          placeholder="Mention I'm speaking at PyCon next month. Avoid the word “journey”."
          value={guidance}
          onChange={(e) => setGuidance(e.target.value)}
          className="min-h-0 resize-y"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="lg" className="rounded-full" disabled={busy || !angle.trim() || !pillar.trim()}>
          <PenLine className="size-4" /> Write the posts
        </Button>
        <Button type="button" size="lg" variant="ghost" className="rounded-full" onClick={onDiscard} disabled={busy}>
          <Trash2 className="size-4" /> Discard run
        </Button>
      </div>
    </form>
  );
}
