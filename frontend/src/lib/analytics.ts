/*
 * Aggregations for the analytics page. Done in the browser so days and hours are in the viewer's time zone.
 */
import type { AnalyticsPost, PlatformId } from "./types";

export type Measure = "interactions" | "views";

export interface Totals {
  posts: number;
  measured: number; // posts with numbers
  views: number;
  interactions: number;
  engagementRate: number | null; // interactions / views, over posts where views are known
}

export function totals(posts: AnalyticsPost[]): Totals {
  let views = 0,
    interactions = 0,
    measured = 0,
    rateViews = 0,
    rateInteractions = 0;
  for (const p of posts) {
    if (!p.metrics) continue;
    measured++;
    interactions += p.metrics.interactions;
    if (p.metrics.views != null) {
      views += p.metrics.views;
      rateViews += p.metrics.views;
      rateInteractions += p.metrics.interactions;
    }
  }
  return { posts: posts.length, measured, views, interactions, engagementRate: rateViews ? rateInteractions / rateViews : null };
}

/** Split a list into this period and the one before it. */
export function periods(posts: AnalyticsPost[], days: number, now = new Date()) {
  const cut = now.getTime() - days * 86_400_000;
  const prevCut = cut - days * 86_400_000;
  const current = posts.filter((p) => Date.parse(p.published_at) >= cut);
  const previous = posts.filter((p) => {
    const t = Date.parse(p.published_at);
    return t >= prevCut && t < cut;
  });
  return { current, previous };
}

export const change = (now: number, before: number) => (before > 0 ? (now - before) / before : null);

const dayKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export interface DayPoint {
  date: Date;
  key: string;
  views: number;
  interactions: number;
  posts: number;
}

/** One point per local day (empty days included), by the day each post was published. */
export function daily(posts: AnalyticsPost[], days: number, now = new Date()): DayPoint[] {
  const out: DayPoint[] = [];
  const index = new Map<string, DayPoint>();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - i);
    const point = { date: d, key: dayKey(d), views: 0, interactions: 0, posts: 0 };
    out.push(point);
    index.set(point.key, point);
  }
  for (const p of posts) {
    const point = index.get(dayKey(new Date(p.published_at)));
    if (!point) continue;
    point.posts++;
    point.views += p.metrics?.views ?? 0;
    point.interactions += p.metrics?.interactions ?? 0;
  }
  return out;
}

/** Group into n buckets (for sparklines). */
export function buckets(points: DayPoint[], n: number, measure: Measure): number[] {
  const size = Math.max(1, Math.ceil(points.length / n));
  const out: number[] = [];
  for (let i = 0; i < points.length; i += size) out.push(points.slice(i, i + size).reduce((sum, p) => sum + p[measure], 0));
  return out;
}

export interface Group {
  key: string;
  posts: number;
  measured: number;
  avgInteractions: number;
  views: number;
  interactions: number;
}

/** Average interactions per measured post, per group, best first. */
export function groupBy(posts: AnalyticsPost[], keyOf: (p: AnalyticsPost) => string | null): Group[] {
  const map = new Map<string, Group>();
  for (const p of posts) {
    const key = keyOf(p);
    if (!key) continue;
    const g = map.get(key) ?? { key, posts: 0, measured: 0, avgInteractions: 0, views: 0, interactions: 0 };
    g.posts++;
    if (p.metrics) {
      g.measured++;
      g.interactions += p.metrics.interactions;
      g.views += p.metrics.views ?? 0;
    }
    map.set(key, g);
  }
  return [...map.values()]
    .map((g) => ({ ...g, avgInteractions: g.measured ? g.interactions / g.measured : 0 }))
    .sort((a, b) => b.avgInteractions - a.avgInteractions);
}

/* ---- when to post ---------------------------------------------------------- */

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const BLOCKS = ["12–4 am", "4–8 am", "8 am–12", "12–4 pm", "4–8 pm", "8 pm–12"];
const WEEKDAY_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export interface Cell {
  weekday: number; // 0 = Monday
  block: number; // 0..5, four hours each
  posts: number;
  avgInteractions: number;
}

export function heatmap(posts: AnalyticsPost[]): Cell[] {
  const cells: Cell[] = [];
  for (let w = 0; w < 7; w++) for (let b = 0; b < 6; b++) cells.push({ weekday: w, block: b, posts: 0, avgInteractions: 0 });
  const sums = new Array(42).fill(0);
  for (const p of posts) {
    if (!p.metrics) continue;
    const d = new Date(p.published_at);
    const i = ((d.getDay() + 6) % 7) * 6 + Math.floor(d.getHours() / 4);
    cells[i].posts++;
    sums[i] += p.metrics.interactions;
  }
  cells.forEach((c, i) => (c.avgInteractions = c.posts ? sums[i] / c.posts : 0));
  return cells;
}

export interface BestTime {
  weekday: number;
  block: number;
  label: string;
  posts: number;
  basedOn: number;
}

/** The best weekday/time block, once there's enough to go on (at least 3 measured posts). */
export function bestTime(posts: AnalyticsPost[], platform?: PlatformId): BestTime | null {
  const pool = posts.filter((p) => p.metrics && (!platform || p.platform === platform));
  if (pool.length < 3) return null;
  const best = heatmap(pool)
    .filter((c) => c.posts > 0)
    .sort((a, b) => b.avgInteractions - a.avgInteractions)[0];
  if (!best) return null;
  return { ...best, label: `${WEEKDAY_LONG[best.weekday]}, ${BLOCKS[best.block]}`, basedOn: pool.length };
}

/** The next date (after now) that falls on that weekday, an hour into the block. */
export function nextOccurrence(t: Pick<BestTime, "weekday" | "block">, now = new Date()) {
  const d = new Date(now);
  d.setHours(t.block * 4 + 1, 0, 0, 0);
  const today = (d.getDay() + 6) % 7;
  let add = (t.weekday - today + 7) % 7;
  if (add === 0 && d <= now) add = 7;
  d.setDate(d.getDate() + add);
  return d;
}

/* ---- formatting ---------------------------------------------------------------- */

export const compact = (n: number) =>
  n >= 10_000 ? new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(n) : n.toLocaleString();

export const percent = (r: number | null) => (r == null ? "—" : `${(r * 100).toFixed(r < 0.1 ? 1 : 0)}%`);

/** Clean axis ticks: 0 and 3-4 round steps up to at least max. */
export function niceTicks(max: number): number[] {
  if (max <= 0) return [0, 1];
  const rough = max / 4;
  const pow = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * pow).find((s) => s >= rough) ?? 10 * pow;
  const ticks = [];
  for (let v = 0; v <= max + step * 0.001; v += step) ticks.push(Math.round(v));
  if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
  return ticks;
}
