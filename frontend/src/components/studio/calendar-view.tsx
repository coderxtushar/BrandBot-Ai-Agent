"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  pointerWithin,
  rectIntersection,
  type CollisionDetection,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { CircleAlert, CircleCheck, ChevronLeft, ChevronRight, Clock } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { api } from "@/lib/api";
import { platform as platformMeta } from "@/lib/platforms";
import { formatTime } from "@/lib/time";
import type { PublicationItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import { StudioHeader } from "./studio-header";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const keyOf = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
const startOfMonth = (d: Date) => new Date(d.getFullYear(), d.getMonth(), 1);

/** 6 weeks, Monday first, covering the month. */
function gridDays(month: Date) {
  const first = startOfMonth(month);
  const start = new Date(first);
  start.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
}

/** The day under the pointer wins (what people expect on a calendar); keyboard drags fall back to overlap. */
const dayUnderPointer: CollisionDetection = (args) => {
  const hits = pointerWithin(args);
  return hits.length ? hits : rectIntersection(args);
};

const movable = (p: PublicationItem) => p.status === "scheduled" || (p.status === "failed" && !!p.account_id);
const when = (p: PublicationItem) => p.published_at ?? p.scheduled_at;

function StatusIcon({ p }: { p: PublicationItem }) {
  if (p.status === "published") return <CircleCheck className="size-3 shrink-0" aria-label="Published" />;
  if (p.status === "failed") return <CircleAlert className="size-3 shrink-0" aria-label="Failed" />;
  return <Clock className="size-3 shrink-0" aria-label="Scheduled" />;
}

function Chip({ p, lifted = false }: { p: PublicationItem; lifted?: boolean }) {
  const meta = platformMeta(p.platform);
  return (
    <span
      className={cn(
        "flex w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-[11px] leading-tight",
        p.status === "published" && "bg-ink text-paper",
        p.status === "scheduled" && "border border-riso-blue/40 bg-riso-blue/10 text-foreground",
        p.status === "publishing" && "bg-riso-pink/15 text-foreground",
        p.status === "failed" && "border border-destructive/40 bg-destructive/10 text-destructive",
        lifted && "rotate-2 shadow-lg ring-2 ring-riso-pink",
      )}
    >
      <StatusIcon p={p} />
      <meta.icon className="size-3 shrink-0" aria-hidden />
      <span className="shrink-0 tabular-nums">{formatTime(when(p))}</span>
      <span className="truncate opacity-80">{p.preview}</span>
    </span>
  );
}

function DraggableChip({ p }: { p: PublicationItem }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: p.id, data: p });
  return (
    <button
      ref={setNodeRef}
      type="button"
      {...listeners}
      {...attributes}
      aria-label={`${platformMeta(p.platform).label} post at ${formatTime(when(p))}. Drag to another day to reschedule.`}
      className={cn("block w-full cursor-grab touch-none rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring active:cursor-grabbing", isDragging && "opacity-30")}
      onClick={(e) => e.stopPropagation()}
    >
      <Chip p={p} />
    </button>
  );
}

function Day({
  date,
  inMonth,
  posts,
  onOpen,
}: {
  date: Date;
  inMonth: boolean;
  posts: PublicationItem[];
  onOpen: () => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: keyOf(date), data: date });
  const today = keyOf(date) === keyOf(new Date());
  const past = date < new Date(new Date().setHours(0, 0, 0, 0));
  return (
    <div
      ref={setNodeRef}
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onOpen()}
      aria-label={`${date.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}, ${posts.length} post${posts.length === 1 ? "" : "s"}`}
      className={cn(
        "relative flex min-h-16 flex-col gap-1 bg-card p-1.5 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring sm:min-h-28",
        !inMonth && "bg-background text-muted-foreground",
        isOver && !past && "bg-riso-sun/25",
        isOver && past && "bg-destructive/10",
      )}
    >
      <span className={cn("grid size-6 place-items-center rounded-full text-xs tabular-nums", today && "bg-ink font-semibold text-paper")}>{date.getDate()}</span>
      {/* phones: dots; larger screens: chips */}
      <span className="flex flex-wrap gap-1 sm:hidden">
        {posts.slice(0, 4).map((p) => (
          <span key={p.id} className={cn("size-1.5 rounded-full", p.status === "published" ? "bg-ink" : p.status === "failed" ? "bg-destructive" : "bg-riso-blue")} />
        ))}
      </span>
      <span className="hidden flex-col gap-1 sm:flex">
        {posts.slice(0, 3).map((p) => (movable(p) ? <DraggableChip key={p.id} p={p} /> : <Chip key={p.id} p={p} />))}
        {posts.length > 3 && <span className="px-1 text-[11px] text-muted-foreground">+{posts.length - 3} more</span>}
      </span>
    </div>
  );
}

export function CalendarView() {
  const qc = useQueryClient();
  const [month, setMonth] = useState(() => startOfMonth(new Date()));
  const [dragging, setDragging] = useState<PublicationItem | null>(null);
  const [openDay, setOpenDay] = useState<Date | null>(null);
  const days = useMemo(() => gridDays(month), [month]);
  const range = useMemo(() => {
    const end = new Date(days[41]);
    end.setDate(end.getDate() + 1);
    return { start: days[0].toISOString(), end: end.toISOString() };
  }, [days]);
  const queryKey = ["publications", "calendar", range.start];
  const { data, isFetching } = useQuery({ queryKey, queryFn: () => api.publications(undefined, range), placeholderData: keepPreviousData });

  const byDay = useMemo(() => {
    const map = new Map<string, PublicationItem[]>();
    for (const p of data ?? []) {
      if (p.status === "cancelled") continue;
      const k = keyOf(new Date(when(p)));
      map.set(k, [...(map.get(k) ?? []), p]);
    }
    map.forEach((list) => list.sort((a, b) => Date.parse(when(a)) - Date.parse(when(b))));
    return map;
  }, [data]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor));

  const onDragStart = (e: DragStartEvent) => setDragging(e.active.data.current as PublicationItem);
  const onDragEnd = async (e: DragEndEvent) => {
    setDragging(null);
    const p = e.active.data.current as PublicationItem;
    const day = e.over?.data.current as Date | undefined;
    if (!p || !day || keyOf(day) === keyOf(new Date(p.scheduled_at))) return;
    const old = new Date(p.scheduled_at);
    const next = new Date(day);
    next.setHours(old.getHours(), old.getMinutes(), 0, 0);
    if (next < new Date()) {
      toast.error("That time has already passed. Drop it on a later day.");
      return;
    }
    // move it right away; the server confirms
    qc.setQueryData<PublicationItem[]>(queryKey, (list) => list?.map((x) => (x.id === p.id ? { ...x, scheduled_at: next.toISOString(), status: "scheduled" } : x)));
    try {
      await api.reschedule(p.id, next.toISOString());
      toast.success(`Moved to ${next.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })} at ${formatTime(next.toISOString())}.`);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      qc.invalidateQueries({ queryKey: ["publications"] });
    }
  };

  const shift = (n: number) => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + n, 1));
  const dayPosts = openDay ? byDay.get(keyOf(openDay)) ?? [] : [];

  return (
    <div className="flex min-h-dvh flex-col">
      <StudioHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-5xl sm:text-6xl">Calendar</h1>
            <p className="mt-3 text-muted-foreground">Drag a scheduled post to another day to move it. It keeps its time of day.</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" className="rounded-full" aria-label="Previous month" onClick={() => shift(-1)}><ChevronLeft className="size-4" /></Button>
            <Button variant="outline" className="rounded-full" onClick={() => setMonth(startOfMonth(new Date()))}>Today</Button>
            <Button variant="outline" size="icon" className="rounded-full" aria-label="Next month" onClick={() => shift(1)}><ChevronRight className="size-4" /></Button>
          </div>
        </div>

        <AnimatePresence mode="wait" initial={false}>
          <motion.h2
            key={month.toISOString()}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="mt-8 font-title text-2xl"
          >
            {month.toLocaleDateString([], { month: "long", year: "numeric" })}
          </motion.h2>
        </AnimatePresence>

        <DndContext sensors={sensors} collisionDetection={dayUnderPointer} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)}>
          <div className={cn("mt-4 overflow-hidden rounded-2xl border border-border bg-border transition-opacity", isFetching && "opacity-70")}>
            <div className="grid grid-cols-7 gap-px">
              {WEEKDAYS.map((d) => (
                <span key={d} className="bg-card py-2 text-center text-xs text-muted-foreground">{d}</span>
              ))}
              {days.map((d) => (
                <Day key={keyOf(d)} date={d} inMonth={d.getMonth() === month.getMonth()} posts={byDay.get(keyOf(d)) ?? []} onOpen={() => setOpenDay(d)} />
              ))}
            </div>
          </div>
          <DragOverlay dropAnimation={{ duration: 180, easing: "cubic-bezier(0.22, 1, 0.36, 1)" }}>
            {dragging ? <div className="w-40"><Chip p={dragging} lifted /></div> : null}
          </DragOverlay>
        </DndContext>

        <ul className="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
          <li className="flex items-center gap-1.5"><Clock className="size-3" /> Scheduled (drag to move)</li>
          <li className="flex items-center gap-1.5"><CircleCheck className="size-3" /> Published</li>
          <li className="flex items-center gap-1.5"><CircleAlert className="size-3" /> Failed</li>
        </ul>
      </main>

      <Sheet open={!!openDay} onOpenChange={(o) => !o && setOpenDay(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-md">
          <SheetHeader>
            <SheetTitle className="font-title text-xl">{openDay?.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}</SheetTitle>
            <SheetDescription>{dayPosts.length ? `${dayPosts.length} post${dayPosts.length === 1 ? "" : "s"}` : "Nothing planned for this day."}</SheetDescription>
          </SheetHeader>
          <ul className="space-y-3 px-4 pb-6">
            {dayPosts.map((p) => {
              const meta = platformMeta(p.platform);
              return (
                <li key={p.id} className="rounded-2xl border border-border p-4">
                  <p className="flex items-center gap-2 text-sm">
                    <span className="font-display text-2xl tabular-nums">{formatTime(when(p))}</span>
                    <meta.icon className="size-4" aria-hidden /> {meta.label}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">{p.brand_name}, {p.status}</p>
                  <p className="mt-2 line-clamp-3 text-sm">{p.preview}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button asChild size="sm" variant="outline" className="rounded-full"><Link href={`/studio?run=${p.run_id}`}>Open draft</Link></Button>
                    {p.external_url && (
                      <Button asChild size="sm" variant="ghost" className="rounded-full"><a href={p.external_url} target="_blank" rel="noreferrer">View post</a></Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="px-4 pb-6">
            <Button asChild variant="ghost" className="rounded-full"><Link href="/studio/scheduled">Manage in Scheduled</Link></Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
