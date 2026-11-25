"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CircleAlert, CircleCheck, ExternalLink, Lightbulb } from "lucide-react";
import { platform as platformMeta } from "@/lib/platforms";
import type { PlatformResult, RunDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { DraftCard } from "./draft-card";

function Verdict({ result }: { result: PlatformResult }) {
  if (result.error)
    return (
      <div role="alert" className="flex gap-2 rounded-2xl bg-destructive/10 p-4 text-sm text-destructive">
        <CircleAlert className="mt-0.5 size-4 shrink-0" />
        <p>This platform couldn&apos;t be written: {result.error}</p>
      </div>
    );
  const r = result.review;
  if (!r) return null;
  return (
    <div className={cn("flex gap-3 rounded-2xl p-4 text-sm", r.approved ? "bg-riso-green/10" : "bg-riso-sun/25")}>
      {r.approved ? <CircleCheck className="mt-0.5 size-4 shrink-0 text-riso-green" /> : <CircleAlert className="mt-0.5 size-4 shrink-0" />}
      <div>
        <p className="font-medium">
          {r.approved ? "The editor approved this" : "The editor wants a human look"}, {r.score}/10
          {result.attempts > 1 && <span className="font-normal text-muted-foreground"> after {result.attempts} drafts</span>}
        </p>
        {r.issues.length > 0 && <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[13px]">{r.issues.map((i, n) => <li key={n}>{i}</li>)}</ul>}
      </div>
    </div>
  );
}

function Strategy({ run }: { run: RunDetail }) {
  const p = run.brand_profile;
  return (
    <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
      <div className="space-y-6">
        {run.plan && (
          <section className="rounded-3xl bg-ink p-6 text-paper">
            <p className="flex items-center gap-2 text-sm text-paper/70">
              <Lightbulb className="size-4" /> The angle, from your topic “{run.plan.pillar}”
            </p>
            <p className="mt-3 font-display text-3xl sm:text-4xl">{run.plan.angle}</p>
          </section>
        )}
        <section>
          <h3 className="font-title text-lg">Sources ({run.sources.length})</h3>
          {run.sources.length === 0 && <p className="mt-2 text-sm text-muted-foreground">No web sources were used for this run.</p>}
          <ul className="mt-3 divide-y divide-border border-y border-border">
            {run.sources.map((s) => (
              <li key={s.url} className="py-3">
                <a href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 font-medium text-primary hover:underline">
                  {s.title || s.url} <ExternalLink className="size-3.5" />
                </a>
                <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{s.snippet}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
      {p && (
        <section className="space-y-4 rounded-3xl border border-border bg-card p-6 text-sm">
          <h3 className="font-title text-lg">Brand profile used</h3>
          <p>{p.positioning}</p>
          <p className="text-muted-foreground">{p.audience_persona}</p>
          <div className="flex flex-wrap gap-1.5">
            {p.voice.traits.map((t) => <span key={t} className="rounded-full bg-riso-sun/30 px-2.5 py-1 text-xs">{t}</span>)}
          </div>
          {p.visual_style && <p><span className="font-medium">Visual style:</span> {p.visual_style}</p>}
          <p className="text-primary">{p.hashtags.map((h) => `#${h}`).join(" ")}</p>
        </section>
      )}
    </div>
  );
}

export function ResultsView({ run }: { run: RunDetail }) {
  const tabs = [
    ...run.results.map((r) => ({ id: r.platform as string, result: r })),
    { id: "strategy", result: null as PlatformResult | null },
  ];
  const [active, setActive] = useState(tabs[0].id);
  const current = tabs.find((t) => t.id === active) ?? tabs[0];

  return (
    <div>
      <div role="tablist" aria-label="Platforms" className="-mx-4 flex gap-1 overflow-x-auto border-b border-border px-4 sm:mx-0 sm:px-0">
        {tabs.map((t) => {
          const meta = t.result ? platformMeta(t.result.platform) : null;
          const needsLook = t.result && (t.result.error || !t.result.review?.approved);
          const selected = t.id === current.id;
          return (
            <button
              key={t.id}
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={selected}
              aria-controls={`panel-${t.id}`}
              onClick={() => setActive(t.id)}
              className={cn(
                "relative flex shrink-0 items-center gap-2 px-3 py-3 text-sm transition-colors",
                selected ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {meta && <meta.icon className="size-4" aria-hidden />}
              {meta ? meta.short : "Strategy & sources"}
              {needsLook && <span className="size-1.5 rounded-full bg-riso-sun ring-2 ring-riso-sun/30" aria-label="needs a look" />}
              {selected && (
                <motion.span layoutId="tab-ink" className="absolute inset-x-1 -bottom-px h-[3px] rounded-full bg-ink" transition={{ type: "spring", stiffness: 500, damping: 38 }} />
              )}
            </button>
          );
        })}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={current.id}
          role="tabpanel"
          id={`panel-${current.id}`}
          aria-labelledby={`tab-${current.id}`}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="space-y-5 pt-6"
        >
          {current.result ? (
            <>
              <Verdict result={current.result} />
              {current.result.items.map((item, i) => (
                <DraftCard
                  key={current.result!.drafts[i]?.id ?? i}
                  runId={run.id}
                  platform={current.result!.platform}
                  index={i}
                  title={current.result!.items.length > 1 ? `Version ${i + 1}` : platformMeta(current.result!.platform).format}
                  item={item}
                  text={current.result!.text[i]}
                  draft={current.result!.drafts[i]}
                />
              ))}
            </>
          ) : (
            <Strategy run={run} />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
