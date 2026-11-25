"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Trash2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { platform } from "@/lib/platforms";
import type { RunStatus, RunSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS: Partial<Record<RunStatus, { text: string; cls: string }>> = {
  running: { text: "Writing", cls: "bg-riso-pink/15 text-riso-pink" },
  awaiting_plan: { text: "Needs your review", cls: "bg-riso-sun/40 text-foreground" },
  failed: { text: "Failed", cls: "bg-destructive/10 text-destructive" },
  cancelled: { text: "Stopped", cls: "bg-muted text-muted-foreground" },
};

function when(iso: string) {
  const d = new Date(iso);
  return new Date().toDateString() === d.toDateString()
    ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
    : d.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function HistoryList({
  runs,
  loading,
  activeId,
  onOpen,
  onDelete,
}: {
  runs: RunSummary[];
  loading: boolean;
  activeId: string | null;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [confirm, setConfirm] = useState<RunSummary | null>(null);

  return (
    <section>
      <h2 className="font-title text-lg">Past runs</h2>
      {loading && (
        <div className="mt-3 space-y-2">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 w-full rounded-xl" />)}
        </div>
      )}
      {!loading && runs.length === 0 && (
        <p className="mt-2 text-sm text-muted-foreground">Every run is saved here, so you can come back to it.</p>
      )}
      <ul className="mt-3 space-y-1">
        <AnimatePresence initial={false}>
          {runs.map((r) => {
            const badge = STATUS[r.status];
            const openable = r.status === "completed" || r.status === "awaiting_plan";
            const active = r.id === activeId;
            return (
              <motion.li
                key={r.id}
                layout
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -24, height: 0 }}
                className="group relative"
              >
                <button
                  type="button"
                  disabled={!openable}
                  onClick={() => onOpen(r.id)}
                  className={cn(
                    "relative w-full rounded-xl px-3 py-2.5 pr-10 text-left transition-colors disabled:cursor-default",
                    active ? "bg-card ring-1 ring-ink/15" : openable && "hover:bg-card/70",
                  )}
                >
                  {active && <motion.span layoutId="history-ink" className="absolute top-3 bottom-3 left-0 w-[3px] rounded-full bg-riso-blue" />}
                  <p className="line-clamp-2 text-sm leading-snug">{r.angle || r.topic || "Untitled run"}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span>{when(r.created_at)}</span>
                    <span className="flex gap-1" aria-label={r.platforms.map((p) => platform(p).label).join(", ")}>
                      {r.platforms.map((p) => {
                        const Icon = platform(p).icon;
                        return <Icon key={p} className="size-3" aria-hidden />;
                      })}
                    </span>
                    {r.status === "completed" && <span>{r.approved} of {r.platforms.length} approved</span>}
                    {badge && <span className={cn("rounded-full px-2 py-0.5", badge.cls)}>{badge.text}</span>}
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => setConfirm(r)}
                  aria-label="Delete run"
                  className="absolute top-2 right-2 rounded-md p-1.5 text-muted-foreground opacity-0 transition group-hover:opacity-100 hover:bg-background hover:text-destructive focus-visible:opacity-100 max-sm:opacity-100"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ul>

      <AlertDialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogTitle>Delete this run?</AlertDialogTitle>
          <AlertDialogDescription>
            Its drafts, versions and images are deleted too. This can&apos;t be undone.
          </AlertDialogDescription>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => {
                if (confirm) onDelete(confirm.id);
                setConfirm(null);
              }}
            >
              Delete run
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
