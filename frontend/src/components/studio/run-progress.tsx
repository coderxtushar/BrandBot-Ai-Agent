"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, CircleAlert, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { platform } from "@/lib/platforms";
import type { PlatformProgress, Progress, StepStatus } from "@/lib/progress";
import type { PlatformId } from "@/lib/types";
import { cn } from "@/lib/utils";

function StepDot({ status }: { status: StepStatus }) {
  if (status === "done" || status === "reused")
    return (
      <motion.span
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", stiffness: 500, damping: 22 }}
        className="grid size-6 place-items-center rounded-full bg-ink text-paper"
      >
        <Check className="size-3.5" strokeWidth={3} />
      </motion.span>
    );
  if (status === "running")
    return (
      <span className="relative grid size-6 place-items-center">
        <motion.span
          className="absolute inset-0 rounded-full bg-riso-pink"
          animate={{ scale: [0.7, 1.15, 0.7], opacity: [0.9, 0.35, 0.9] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
        />
        <span className="relative size-2.5 rounded-full bg-riso-pink" />
      </span>
    );
  return <span className="grid size-6 place-items-center"><span className="size-2 rounded-full bg-border" /></span>;
}

function Step({ status, title, children }: { status: StepStatus; title: string; children?: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <StepDot status={status} />
      <div className="min-w-0 flex-1 pt-0.5">
        <p className={cn("text-sm font-medium", status === "waiting" && "text-muted-foreground")}>{title}</p>
        {children}
      </div>
    </li>
  );
}

/** The angle "prints" word by word as it arrives. */
function Angle({ text }: { text: string }) {
  return (
    <p className="mt-1 font-title text-lg leading-snug">
      {text.split(" ").map((w, i) => (
        <motion.span
          key={`${w}-${i}`}
          className="inline-block"
          initial={{ opacity: 0, y: 6, filter: "blur(4px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ delay: i * 0.035, duration: 0.3 }}
        >
          {w}&nbsp;
        </motion.span>
      ))}
    </p>
  );
}

const FILL: Record<PlatformProgress["stage"], number> = { queued: 0.04, writing: 0.4, revising: 0.55, reviewing: 0.8, done: 1 };
const LABEL: Record<PlatformProgress["stage"], string> = {
  queued: "Waiting for research",
  writing: "Writing",
  reviewing: "Editor is reviewing",
  revising: "Rewriting after feedback",
  done: "Done",
};

function Lane({ id, p }: { id: PlatformId; p: PlatformProgress }) {
  const meta = platform(id);
  const done = p.stage === "done";
  const label = done ? (p.approved ? "Approved by the editor" : "Ready, with editor notes") : LABEL[p.stage];
  return (
    <li className="rounded-xl border border-border bg-card p-3">
      <div className="flex items-center gap-2">
        <meta.icon className="size-4 text-muted-foreground" aria-hidden />
        <span className="text-sm font-medium">{meta.short}</span>
        <AnimatePresence>
          {done && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className={cn(
                "ml-auto grid size-5 place-items-center rounded-full",
                p.approved ? "bg-riso-green text-white" : "bg-riso-sun text-ink",
              )}
            >
              {p.approved ? <Check className="size-3" strokeWidth={3} /> : <CircleAlert className="size-3" />}
            </motion.span>
          )}
        </AnimatePresence>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
        <motion.div
          className={cn("h-full origin-left rounded-full", p.stage === "revising" ? "bg-riso-pink" : done ? "bg-ink" : "bg-riso-blue")}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: FILL[p.stage] }}
          transition={{ type: "spring", stiffness: 60, damping: 18 }}
        />
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.p
          key={label + p.attempt}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.18 }}
          className="mt-2 text-xs text-muted-foreground"
        >
          {label}
          {p.attempt > 1 && !done ? `, draft ${p.attempt}` : ""}
        </motion.p>
      </AnimatePresence>
    </li>
  );
}

export function RunProgress({ progress, onStop }: { progress: Progress; onStop: () => void }) {
  const lanes = Object.entries(progress.platforms) as [PlatformId, PlatformProgress][];
  return (
    <div className="space-y-8" aria-live="polite">
      <div className="flex items-center justify-between gap-4">
        <h2 className="font-title text-2xl">On the press</h2>
        <Button variant="outline" size="sm" onClick={onStop}>
          <Square className="size-3.5" /> Stop
        </Button>
      </div>

      <ol className="space-y-5">
        <Step status={progress.profile} title={progress.profile === "reused" ? "Using your saved brand profile" : "Reading your brand"} />
        <Step status={progress.planning} title="Choosing today's angle">
          {progress.angle && <Angle text={progress.angle} />}
        </Step>
        <Step status={progress.research} title="Researching the web">
          {progress.research === "done" && progress.sourceCount !== undefined ? (
            <p className="text-sm text-muted-foreground">{progress.sourceCount} sources found</p>
          ) : (
            progress.queries && (
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {progress.queries.map((q) => (
                  <li key={q} className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">
                    {q}
                  </li>
                ))}
              </ul>
            )
          )}
        </Step>
      </ol>

      {lanes.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {lanes.map(([id, p]) => (
            <Lane key={id} id={id} p={p} />
          ))}
        </ul>
      )}
    </div>
  );
}
