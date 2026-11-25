"use client";

import { useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { CalendarClock, ExternalLink, RotateCcw, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { usePublications } from "@/hooks/use-studio-data";
import { api } from "@/lib/api";
import { platform as platformMeta } from "@/lib/platforms";
import { dayLabel, formatTime, formatWhen, nextHour, toLocalInput } from "@/lib/time";
import type { PublicationItem, PublicationStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { compact, percent } from "@/lib/analytics";
import { ResultsDialog } from "./results-dialogs";
import { StudioHeader } from "./studio-header";

const TABS: { id: string; label: string; statuses: PublicationStatus[]; empty: string }[] = [
  { id: "upcoming", label: "Upcoming", statuses: ["scheduled", "publishing"], empty: "Nothing scheduled. Open a draft and choose Publish to plan a post." },
  { id: "published", label: "Published", statuses: ["published"], empty: "Posts you publish show up here with a link to them." },
  { id: "attention", label: "Needs attention", statuses: ["failed", "cancelled"], empty: "No failed or cancelled posts." },
];

function Reschedule({ item, onDone }: { item: PublicationItem; onDone: () => void }) {
  const [value, setValue] = useState(() => toLocalInput(new Date(Math.max(Date.parse(item.scheduled_at), nextHour().getTime()))));
  const [open, setOpen] = useState(false);
  const save = async () => {
    try {
      await api.reschedule(item.id, new Date(value).toISOString());
      toast.success(`Rescheduled for ${formatWhen(new Date(value).toISOString())}.`);
      setOpen(false);
      onDone();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="rounded-full">
          <CalendarClock className="size-3.5" /> Reschedule
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 space-y-3">
        <label className="block text-sm font-medium" htmlFor={`when-${item.id}`}>New time</label>
        <Input id={`when-${item.id}`} type="datetime-local" value={value} min={toLocalInput(new Date())} onChange={(e) => setValue(e.target.value)} />
        <Button size="sm" className="w-full" onClick={save} disabled={!value}>Save time</Button>
      </PopoverContent>
    </Popover>
  );
}

function Results({ item, refresh }: { item: PublicationItem; refresh: () => void }) {
  const [open, setOpen] = useState(false);
  const m = item.metrics;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl bg-muted/70 px-3 py-2 text-sm">
      {m ? (
        <>
          {m.views != null && <span><span className="font-semibold">{compact(m.views)}</span> views</span>}
          <span><span className="font-semibold">{m.interactions.toLocaleString()}</span> interactions</span>
          {m.engagement_rate != null && <span className="text-muted-foreground">{percent(m.engagement_rate)} engagement</span>}
        </>
      ) : (
        <span className="text-muted-foreground">{item.metrics_error ?? "No numbers yet."}</span>
      )}
      <button type="button" onClick={() => setOpen(true)} className="ml-auto text-sm font-medium text-primary hover:underline">
        {m ? "Update results" : "Add results"}
      </button>
      <ResultsDialog pub={item} open={open} onOpenChange={setOpen} onSaved={refresh} />
    </div>
  );
}

function Row({ item, refresh }: { item: PublicationItem; refresh: () => void }) {
  const meta = platformMeta(item.platform);
  const act = async (fn: () => Promise<PublicationItem>, done: (p: PublicationItem) => string) => {
    try {
      const p = await fn();
      if (p.status === "failed") toast.error(p.error ?? "Publishing failed.");
      else toast.success(done(p));
      refresh();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };
  return (
    <motion.li layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: -20 }} className="rounded-2xl border border-border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-start gap-x-5 gap-y-3">
        <div className="w-20 shrink-0">
          <p className="font-display text-3xl tabular-nums">{formatTime(item.published_at ?? item.scheduled_at)}</p>
          {item.status === "publishing" && (
            <p className="mt-1 flex items-center gap-1.5 text-xs text-riso-pink">
              <span className="size-1.5 animate-pulse rounded-full bg-riso-pink" /> Publishing
            </p>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <meta.icon className="size-4" aria-hidden />
            <span className="font-medium">{meta.label}</span>
            <span className="text-muted-foreground">{item.account_name ?? "disconnected account"}</span>
            <span className="text-muted-foreground">for {item.brand_name}</span>
          </p>
          <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{item.preview}</p>
          {item.error && <p className={cn("mt-2 text-sm", item.status === "failed" ? "text-destructive" : "text-muted-foreground")}>{item.error}</p>}
          {item.status === "published" && <Results item={item} refresh={refresh} />}
        </div>
        <div className="flex w-full flex-wrap justify-end gap-2 sm:w-auto">
          {item.external_url && (
            <Button asChild variant="outline" size="sm" className="rounded-full">
              <a href={item.external_url} target="_blank" rel="noreferrer">
                <ExternalLink className="size-3.5" /> View post
              </a>
            </Button>
          )}
          <Button asChild variant="ghost" size="sm" className="rounded-full">
            <Link href={`/studio?run=${item.run_id}`}>Open draft</Link>
          </Button>
          {item.status === "scheduled" && (
            <>
              <Reschedule item={item} onDone={refresh} />
              <Button variant="ghost" size="sm" className="rounded-full text-muted-foreground hover:text-destructive" onClick={() => act(() => api.cancelPublication(item.id), () => "Cancelled.")}>
                <X className="size-3.5" /> Cancel
              </Button>
            </>
          )}
          {item.status === "failed" && (
            <Button size="sm" className="rounded-full" onClick={() => act(() => api.retryPublication(item.id), (p) => (p.status === "published" ? `Published to ${meta.label}.` : "Queued to retry."))}>
              <RotateCcw className="size-3.5" /> Try again
            </Button>
          )}
          {item.status === "cancelled" && item.account_id && <Reschedule item={item} onDone={refresh} />}
        </div>
      </div>
    </motion.li>
  );
}

export function ScheduledView() {
  const [tab, setTab] = useState(TABS[0]);
  const qc = useQueryClient();
  const { data, isLoading, error } = usePublications(tab.statuses);
  const refresh = () => qc.invalidateQueries({ queryKey: ["publications"] });

  // Upcoming reads soonest-first, grouped by day; the others newest-first.
  const items = [...(data ?? [])].sort((a, b) =>
    tab.id === "upcoming" ? Date.parse(a.scheduled_at) - Date.parse(b.scheduled_at) : Date.parse(b.published_at ?? b.scheduled_at) - Date.parse(a.published_at ?? a.scheduled_at),
  );
  const groups = items.reduce<{ day: string; items: PublicationItem[] }[]>((acc, item) => {
    const day = dayLabel(item.published_at ?? item.scheduled_at);
    const last = acc[acc.length - 1];
    if (last?.day === day) last.items.push(item);
    else acc.push({ day, items: [item] });
    return acc;
  }, []);

  return (
    <div className="flex min-h-dvh flex-col">
      <StudioHeader />
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10 sm:px-6">
        <h1 className="font-display text-5xl sm:text-6xl">Scheduled</h1>
        <p className="mt-3 text-muted-foreground">Everything you&apos;ve published or planned, across brands. Times are in your time zone.</p>

        <div role="tablist" aria-label="Post status" className="mt-8 inline-flex rounded-full border border-border bg-card p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={t.id === tab.id}
              onClick={() => setTab(t)}
              className={cn("relative rounded-full px-4 py-1.5 text-sm transition-colors", t.id === tab.id ? "text-paper" : "text-muted-foreground hover:text-foreground")}
            >
              {t.id === tab.id && <motion.span layoutId="scheduled-tab" className="absolute inset-0 rounded-full bg-ink" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
              <span className="relative">{t.label}</span>
            </button>
          ))}
        </div>

        <div className="mt-8">
          {isLoading && <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}</div>}
          {error && <p className="text-destructive">{(error as Error).message}</p>}
          {data && items.length === 0 && (
            <div className="rounded-3xl border border-dashed border-border p-10 text-center text-muted-foreground">{tab.empty}</div>
          )}
          <div className="space-y-10">
            {groups.map((g) => (
              <section key={g.day}>
                <h2 className="mb-3 font-title text-lg">{g.day}</h2>
                <ol className="relative space-y-3 border-l-2 border-dotted border-border pl-4 sm:pl-6">
                  <AnimatePresence initial={false}>
                    {g.items.map((item) => <Row key={item.id} item={item} refresh={refresh} />)}
                  </AnimatePresence>
                </ol>
              </section>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
