"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ExternalLink, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { StudioHeader } from "@/components/studio/studio-header";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useBrands } from "@/hooks/use-studio-data";
import {
  BLOCKS,
  bestTime,
  buckets,
  change,
  compact,
  daily,
  groupBy,
  heatmap,
  percent,
  periods,
  totals,
  type Measure,
} from "@/lib/analytics";
import { api } from "@/lib/api";
import { PLATFORMS, platform as platformMeta } from "@/lib/platforms";
import type { PlatformId } from "@/lib/types";
import { cn } from "@/lib/utils";
import { BarList } from "./bar-list";
import { Heatmap } from "./heatmap";
import { StatTile } from "./stat-tile";
import { TrendChart } from "./trend-chart";

const RANGES = [7, 30, 90] as const;
const ALL = "all";

function Card({
  title,
  subtitle,
  action,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    // min-w-0: let wide content (heatmap, table) scroll inside the card instead of stretching the grid
    <section className={cn("min-w-0 rounded-3xl border border-border bg-card p-5 sm:p-6", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-title text-lg">{title}</h2>
          {subtitle && <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Segmented<T extends string | number>({ value, options, onChange, label }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-full border border-border bg-card p-1">
      {options.map((o) => (
        <button
          key={String(o.value)}
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn("relative rounded-full px-3.5 py-1 text-sm transition-colors", o.value === value ? "text-paper" : "text-muted-foreground hover:text-foreground")}
        >
          {o.value === value && <motion.span layoutId={`seg-${label}`} className="absolute inset-0 rounded-full bg-ink" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
          <span className="relative">{o.label}</span>
        </button>
      ))}
    </div>
  );
}

export function AnalyticsView() {
  const qc = useQueryClient();
  const [days, setDays] = useState<number>(30);
  const [brandId, setBrandId] = useState<string>(ALL);
  const [platform, setPlatform] = useState<string>(ALL);
  const [measure, setMeasure] = useState<Measure>("interactions");
  const [refreshing, setRefreshing] = useState(false);
  const brands = useBrands();

  // Two periods' worth, so every number can be compared with the period before.
  const q = useQuery({
    queryKey: ["analytics", days, brandId, platform],
    queryFn: () => api.analyticsPosts(days * 2, { brandId: brandId === ALL ? undefined : brandId, platform: platform === ALL ? undefined : platform }),
    placeholderData: keepPreviousData,
  });

  const view = useMemo(() => {
    const all = q.data ?? [];
    const { current, previous } = periods(all, days);
    const now = totals(current);
    const before = totals(previous);
    const series = daily(current, days);
    return {
      current,
      now,
      before,
      series,
      platforms: groupBy(current, (p) => p.platform),
      topics: groupBy(current, (p) => p.pillar),
      cells: heatmap(current),
      best: bestTime(current),
      bestBy: PLATFORMS.map((p) => ({ p, t: bestTime(current, p.id) })).filter((x) => x.t),
      top: [...current].filter((p) => p.metrics).sort((a, b) => (b.metrics!.interactions - a.metrics!.interactions)).slice(0, 8),
      unmeasured: current.filter((p) => !p.metrics).length,
    };
  }, [q.data, days]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      const r = await api.refreshStats();
      await qc.invalidateQueries({ queryKey: ["analytics"] });
      toast.success(r.updated ? `Updated stats for ${r.updated} post${r.updated === 1 ? "" : "s"}.` : "Everything is already up to date.");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setRefreshing(false);
    }
  };

  const { now, before } = view;
  const empty = q.isSuccess && view.current.length === 0;

  return (
    <div className="flex min-h-dvh flex-col">
      <StudioHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
        <h1 className="font-display text-5xl sm:text-6xl">Analytics</h1>
        <p className="mt-3 max-w-xl text-muted-foreground">How your published posts are doing, and what to write more of. Stats refresh every few hours.</p>

        {/* filters: one row, scoping everything below */}
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Segmented label="Date range" value={days} onChange={setDays} options={RANGES.map((d) => ({ value: d, label: `${d} days` }))} />
          <Select value={brandId} onValueChange={setBrandId}>
            <SelectTrigger className="w-44 rounded-full" aria-label="Brand"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All brands</SelectItem>
              {brands.data?.map((b) => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={platform} onValueChange={setPlatform}>
            <SelectTrigger className="w-44 rounded-full" aria-label="Platform"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All platforms</SelectItem>
              {PLATFORMS.map((p) => <SelectItem key={p.id} value={p.id}>{p.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button variant="outline" className="rounded-full sm:ml-auto" onClick={refresh} disabled={refreshing}>
            <RefreshCw className={cn("size-4", refreshing && "animate-spin")} /> {refreshing ? "Refreshing…" : "Refresh stats"}
          </Button>
        </div>

        {q.isLoading && <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-32 rounded-2xl" />)}</div>}
        {q.isError && <p className="mt-8 text-destructive">{(q.error as Error).message}</p>}

        {empty && (
          <div className="mt-10 rounded-3xl border border-dashed border-border p-10 text-center">
            <p className="font-display text-4xl">No published posts in this range.</p>
            <p className="mx-auto mt-3 max-w-md text-muted-foreground">
              Publish a draft, or mark one you posted yourself, and its results show up here.
            </p>
            <Button asChild className="mt-6 rounded-full"><Link href="/studio">Go to your drafts</Link></Button>
          </div>
        )}

        {q.data && !empty && (
          <div className={cn("mt-8 space-y-4 transition-opacity", q.isFetching && "opacity-60")}>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile label="Posts published" value={now.posts.toLocaleString()} delta={change(now.posts, before.posts)} hint={`vs the ${days} days before`} />
              <StatTile label="Views" value={compact(now.views)} delta={change(now.views, before.views)} trend={buckets(view.series, 12, "views")} hint={`vs the ${days} days before`} />
              <StatTile label="Interactions" value={compact(now.interactions)} delta={change(now.interactions, before.interactions)} trend={buckets(view.series, 12, "interactions")} hint="likes, comments, shares, saves" />
              <StatTile
                label="Engagement rate"
                value={percent(now.engagementRate)}
                delta={now.engagementRate != null && before.engagementRate ? change(now.engagementRate, before.engagementRate) : null}
                hint="interactions per view"
              />
            </div>

            {view.unmeasured > 0 && (
              <p className="rounded-2xl bg-riso-sun/25 px-4 py-3 text-sm">
                {view.unmeasured} post{view.unmeasured === 1 ? " has" : "s have"} no numbers yet (LinkedIn and posts you made yourself don&apos;t report them).{" "}
                <Link href="/studio/scheduled" className="font-medium underline underline-offset-2">Add their results</Link> so they count.
              </p>
            )}

            <div className="grid gap-4 lg:grid-cols-3">
              <Card
                title={measure === "interactions" ? "Interactions per day" : "Views per day"}
                subtitle="By the day each post was published"
                className="lg:col-span-2"
                action={<Segmented label="Measure" value={measure} onChange={setMeasure} options={[{ value: "interactions", label: "Interactions" }, { value: "views", label: "Views" }]} />}
              >
                <TrendChart points={view.series} measure={measure} label={measure === "interactions" ? "Interactions" : "Views"} />
              </Card>

              <Card title="When to post" subtitle="Average interactions per post, by when it went out">
                {view.best ? (
                  <>
                    <p className="font-display text-4xl leading-none">{view.best.label}</p>
                    <p className="mt-2 text-sm text-muted-foreground">Your strongest slot, based on {view.best.basedOn} posts.</p>
                    {view.bestBy.length > 0 && (
                      <ul className="mt-5 space-y-2 text-sm">
                        {view.bestBy.map(({ p, t }) => (
                          <li key={p.id} className="flex items-center justify-between gap-3 border-t border-border pt-2">
                            <span className="flex items-center gap-2"><p.icon className="size-4" aria-hidden /> {p.short}</span>
                            <span className="text-muted-foreground">{t!.label}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">After three or more posts with results, your best day and time shows here, and in the Publish dialog.</p>
                )}
              </Card>
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              <Card title="Day and time" subtitle={`Each cell is a four-hour block in your time zone (${BLOCKS[0]} … ${BLOCKS[5]})`} className="lg:col-span-2">
                <Heatmap cells={view.cells} />
              </Card>
              <Card title="Platforms" subtitle="Average interactions per post">
                <BarList
                  empty="No results yet."
                  rows={view.platforms.filter((g) => g.measured).map((g) => {
                    const meta = platformMeta(g.key as PlatformId);
                    return {
                      key: g.key,
                      label: meta.short,
                      value: g.avgInteractions,
                      display: Math.round(g.avgInteractions).toLocaleString(),
                      detail: `${meta.label}: ${g.measured} post${g.measured === 1 ? "" : "s"} with results, ${compact(g.interactions)} interactions${g.views ? `, ${compact(g.views)} views` : ""}`,
                    };
                  })}
                />
              </Card>
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              <Card title="Topics" subtitle="Average interactions per post. Future runs lean toward what works.">
                <BarList
                  empty="Results by topic show up once posts from different topics have numbers."
                  rows={view.topics.filter((g) => g.measured).map((g) => ({
                    key: g.key,
                    label: g.key,
                    value: g.avgInteractions,
                    display: Math.round(g.avgInteractions).toLocaleString(),
                    detail: `${g.measured} post${g.measured === 1 ? "" : "s"} with results`,
                  }))}
                />
              </Card>
              <Card title="Top posts" subtitle="By interactions" className="lg:col-span-2">
                {/* relative: keeps the sr-only header inside the scroll box (absolute elements escape it otherwise) */}
                <div className="relative -mx-2 overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-sm">
                    <thead className="text-xs text-muted-foreground">
                      <tr>
                        <th className="w-[55%] px-2 pb-2 font-medium">Post</th>
                        <th className="px-2 pb-2 text-right font-medium">Views</th>
                        <th className="px-2 pb-2 text-right font-medium">Interactions</th>
                        <th className="px-2 pb-2 text-right font-medium">Rate</th>
                        <th className="px-2 pb-2"><span className="sr-only">Link</span></th>
                      </tr>
                    </thead>
                    <tbody className="tabular-nums">
                      {view.top.map((p) => {
                        const meta = platformMeta(p.platform);
                        return (
                          <tr key={p.publication_id} className="border-t border-border align-top">
                            <td className="max-w-0 px-2 py-2.5">
                              <Link href={`/studio?run=${p.run_id}`} className="block truncate hover:underline">{p.preview}</Link>
                              <span className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                                <meta.icon className="size-3" aria-hidden /> {meta.short}, {new Date(p.published_at).toLocaleDateString([], { month: "short", day: "numeric" })}
                              </span>
                            </td>
                            <td className="px-2 py-2.5 text-right">{p.metrics!.views != null ? compact(p.metrics!.views) : "—"}</td>
                            <td className="px-2 py-2.5 text-right font-medium">{p.metrics!.interactions.toLocaleString()}</td>
                            <td className="px-2 py-2.5 text-right">{percent(p.metrics!.engagement_rate)}</td>
                            <td className="px-2 py-2.5 text-right">
                              {p.external_url && (
                                <a href={p.external_url} target="_blank" rel="noreferrer" aria-label="Open post" className="text-muted-foreground hover:text-foreground">
                                  <ExternalLink className="inline size-3.5" />
                                </a>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
