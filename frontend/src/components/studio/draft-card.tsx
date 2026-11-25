"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { BadgeCheck, CalendarClock, Copy, ExternalLink, History, ImagePlus, Pencil, Send, Sparkles, ThumbsDown, ThumbsUp, TriangleAlert, type LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useDraftCache } from "@/hooks/use-studio-data";
import { api } from "@/lib/api";
import { REWRITE_PRESETS, platform as platformMeta } from "@/lib/platforms";
import { formatWhen } from "@/lib/time";
import type { Content, DraftRef, DraftStatus, PlatformId, Publication, RewritePreset } from "@/lib/types";
import { cn } from "@/lib/utils";
import { DraftEditor } from "./draft-editor";
import { Preview } from "./previews";
import { PUBLISHABLE, PublishDialog } from "./publish-dialog";
import { PostedMyselfDialog, ResultsDialog } from "./results-dialogs";
import { compact } from "@/lib/analytics";
import { VersionsSheet } from "./versions-sheet";
import { Visuals } from "./visuals";

type Mode = null | "edit" | "rewrite" | "visuals";

const panel = {
  initial: { height: 0, opacity: 0 },
  animate: { height: "auto", opacity: 1 },
  exit: { height: 0, opacity: 0 },
  transition: { duration: 0.28, ease: [0.22, 1, 0.36, 1] as const },
};

/** "Approved" lands like a rubber stamp. */
function Stamp({ status }: { status: DraftStatus }) {
  return (
    <AnimatePresence>
      {status !== "draft" && (
        <motion.span
          key={status}
          initial={{ scale: 2.2, opacity: 0, rotate: -18 }}
          animate={{ scale: 1, opacity: 1, rotate: -6 }}
          exit={{ scale: 0.6, opacity: 0 }}
          transition={{ type: "spring", stiffness: 420, damping: 18 }}
          className={cn(
            "pointer-events-none rounded-md border-2 px-2 py-0.5 font-display text-sm tracking-wide",
            status === "approved" ? "border-riso-green text-riso-green" : "border-riso-red text-riso-red",
          )}
        >
          {status === "approved" ? "Approved" : "Rejected"}
        </motion.span>
      )}
    </AnimatePresence>
  );
}

function Tool({
  icon: Icon,
  label,
  active,
  onClick,
  disabled,
  className,
}: {
  icon: LucideIcon;
  label: string;
  active?: boolean;
  onClick: () => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant={active ? "default" : "outline"}
          size="sm"
          aria-pressed={active}
          aria-label={label}
          onClick={onClick}
          disabled={disabled}
          className={cn("rounded-full", active && "bg-ink text-paper hover:bg-ink/90", className)}
        >
          <Icon className="size-3.5" />
          <span className="hidden lg:inline">{label}</span>
        </Button>
      </TooltipTrigger>
      <TooltipContent className="lg:hidden">{label}</TooltipContent>
    </Tooltip>
  );
}

/** Where this draft has gone, or will go. */
function PublicationChips({ pubs, onAddResults }: { pubs: Publication[]; onAddResults: (p: Publication) => void }) {
  if (!pubs?.length) return null;
  return (
    <ul className="mb-4 flex flex-wrap gap-2">
      {pubs.slice(0, 4).map((p) => {
        const cls =
          p.status === "published"
            ? "bg-riso-green/12 text-riso-green"
            : p.status === "failed"
              ? "bg-destructive/10 text-destructive"
              : p.status === "cancelled"
                ? "bg-muted text-muted-foreground line-through"
                : "bg-riso-blue/10 text-primary";
        const stats = p.metrics
          ? p.metrics.views != null
            ? `, ${compact(p.metrics.views)} views`
            : `, ${p.metrics.interactions.toLocaleString()} interactions`
          : "";
        const label =
          p.status === "published"
            ? `Published${stats}`
            : p.status === "scheduled"
              ? `Scheduled for ${formatWhen(p.scheduled_at)}`
              : p.status === "publishing"
                ? "Publishing now"
                : p.status === "failed"
                  ? "Failed to publish"
                  : "Cancelled";
        return (
          <motion.li key={p.id} initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="flex items-center gap-1">
            {p.status === "published" && !p.metrics && (
              <button type="button" onClick={() => onAddResults(p)} className="order-last rounded-full px-2 py-1 text-xs text-primary hover:underline">
                Add results
              </button>
            )}
            {p.status === "published" && p.external_url ? (
              <a href={p.external_url} target="_blank" rel="noreferrer" className={cn("inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium", cls)}>
                {label} <ExternalLink className="size-3" />
              </a>
            ) : (
              <Link href="/studio/scheduled" title={p.error ?? undefined} className={cn("inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium", cls)}>
                {p.status === "scheduled" && <CalendarClock className="size-3" />}
                {label}
              </Link>
            )}
          </motion.li>
        );
      })}
    </ul>
  );
}

function RewritePanel({ onRewrite, busy }: { onRewrite: (b: { preset?: RewritePreset; instruction?: string; fresh?: boolean }) => void; busy: boolean }) {
  const [instruction, setInstruction] = useState("");
  return (
    <div className="space-y-3 rounded-2xl border border-border bg-background/60 p-4">
      <div className="flex flex-wrap gap-2">
        {REWRITE_PRESETS.map((p) => (
          <Button key={p.id} type="button" variant="outline" size="sm" className="rounded-full" disabled={busy} onClick={() => onRewrite({ preset: p.id, instruction: instruction.trim() })}>
            {p.label}
          </Button>
        ))}
      </div>
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          if (instruction.trim()) onRewrite({ instruction: instruction.trim() });
        }}
      >
        <Input
          aria-label="What to change"
          placeholder="Say what to change, e.g. “mention our launch next week”"
          value={instruction}
          maxLength={500}
          onChange={(e) => setInstruction(e.target.value)}
        />
        <Button type="submit" disabled={busy || !instruction.trim()} className="shrink-0">Rewrite</Button>
      </form>
      <button
        type="button"
        disabled={busy}
        onClick={() => onRewrite({ fresh: true, instruction: instruction.trim() })}
        className="text-sm text-primary underline-offset-2 hover:underline disabled:opacity-50"
      >
        Write a completely new draft instead{instruction.trim() ? ", using your note" : ""}
      </button>
    </div>
  );
}

export function DraftCard({
  runId,
  platform,
  index,
  title,
  item,
  text,
  draft,
}: {
  runId: string;
  platform: PlatformId;
  index: number;
  title: string;
  item: Content;
  text: string;
  draft: DraftRef;
}) {
  const cache = useDraftCache(runId);
  const [mode, setMode] = useState<Mode>(null);
  const [rewriting, setRewriting] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [postedOpen, setPostedOpen] = useState(false);
  const [resultsFor, setResultsFor] = useState<Publication | null>(null);
  const publishable = PUBLISHABLE.includes(platform);
  const toggle = (m: Mode) => setMode((cur) => (cur === m ? null : m));
  const meta = platformMeta(platform);

  const setStatus = async (status: DraftStatus) => {
    try {
      cache.applyDraft(platform, index, await api.updateDraft(draft.id, { status: draft.status === status ? "draft" : status }));
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const rewrite = async (body: { preset?: RewritePreset; instruction?: string; fresh?: boolean }) => {
    setRewriting(true);
    try {
      cache.applyDraft(platform, index, await api.rewriteDraft(draft.id, body));
      setMode(null);
      toast.success(body.fresh ? "New draft written and reviewed." : "Rewritten and reviewed.");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setRewriting(false);
    }
  };

  const save = async (content: Content) => {
    cache.applyDraft(platform, index, await api.updateDraft(draft.id, { content }));
    setMode(null);
    toast.success("Changes saved.");
  };

  const restore = async (versionId: string) => {
    try {
      cache.applyDraft(platform, index, await api.restoreVersion(draft.id, versionId));
      toast.success("Version restored.");
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`Copied, ready to paste into ${meta.label}.`);
    } catch {
      toast.error("Your browser blocked copying. Select the text and copy it manually.");
    }
  };

  return (
    <motion.section layout="position" className="rounded-3xl border border-border bg-card p-4 sm:p-6">
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h3 className="font-title text-lg">{title}</h3>
          <Stamp status={draft.status} />
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Tool icon={ThumbsUp} label="Approve" active={draft.status === "approved"} onClick={() => setStatus("approved")} />
          <Tool icon={ThumbsDown} label="Reject" active={draft.status === "rejected"} onClick={() => setStatus("rejected")} />
          <Tool icon={Pencil} label="Edit" active={mode === "edit"} onClick={() => toggle("edit")} disabled={rewriting} />
          <Tool icon={Sparkles} label="Rewrite" active={mode === "rewrite"} onClick={() => toggle("rewrite")} disabled={rewriting} />
          <Tool icon={ImagePlus} label="Visuals" active={mode === "visuals"} onClick={() => toggle("visuals")} />
          <Tool icon={History} label="History" onClick={() => setHistoryOpen(true)} />
          <Tool icon={Copy} label="Copy" onClick={copy} />
          <Tool icon={BadgeCheck} label="I posted it" onClick={() => setPostedOpen(true)} />
          {publishable && (
            <Tool icon={Send} label="Publish" onClick={() => setPublishOpen(true)} className="border-riso-blue/40 text-primary" />
          )}
        </div>
      </header>

      <PublicationChips pubs={draft.publications} onAddResults={setResultsFor} />

      {draft.lint.length > 0 && (
        <div role="status" className="mb-4 flex gap-2 rounded-xl bg-riso-sun/25 p-3 text-sm">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">Breaks {meta.label} rules</p>
            <ul className="mt-1 list-disc pl-5 text-[13px]">{draft.lint.map((l, i) => <li key={i}>{l}</li>)}</ul>
          </div>
        </div>
      )}
      {draft.review && (
        <p className={cn("mb-4 text-sm", draft.review.approved ? "text-riso-green" : "text-foreground")}>
          Re-reviewed after your change: {draft.review.score}/10
          {!draft.review.approved && draft.review.issues.length > 0 && `. ${draft.review.issues.join(" ")}`}
        </p>
      )}

      <AnimatePresence initial={false} mode="wait">
        {mode === "rewrite" && (
          <motion.div key="rewrite" {...panel} className="overflow-hidden">
            <div className="pb-5"><RewritePanel onRewrite={rewrite} busy={rewriting} /></div>
          </motion.div>
        )}
        {mode === "visuals" && (
          <motion.div key="visuals" {...panel} className="overflow-hidden">
            <div className="pb-5">
              <Visuals
                draftId={draft.id}
                ratio={meta.imageAspect}
                images={draft.images}
                onAdded={(img) => cache.addImage(platform, index, img)}
                onRemoved={(id) => cache.removeImage(platform, index, id)}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="relative">
        {mode === "edit" ? (
          <DraftEditor key={text} draftId={draft.id} content={item} onSave={save} onCancel={() => setMode(null)} />
        ) : (
          <div className={cn("min-w-0 [overflow-wrap:anywhere] transition", rewriting && "opacity-30 blur-[1px]")}>
            <Preview platform={platform} item={item} image={draft.images[0]} />
          </div>
        )}
        <AnimatePresence>
          {rewriting && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 grid place-items-center overflow-hidden rounded-2xl"
              aria-live="polite"
            >
              <motion.div
                aria-hidden
                className="halftone absolute -inset-8 text-riso-pink"
                animate={{ x: [0, 9], opacity: [0.15, 0.35, 0.15] }}
                transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}
              />
              <p className="relative rounded-full bg-card px-4 py-2 text-sm font-medium shadow-sm">
                Rewriting, then the editor reviews it…
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <VersionsSheet draftId={draft.id} open={historyOpen} onOpenChange={setHistoryOpen} onRestore={restore} />
      <PostedMyselfDialog
        draftId={draft.id}
        platform={platform}
        open={postedOpen}
        onOpenChange={setPostedOpen}
        onSaved={(p) => cache.addPublication(platform, index, p)}
      />
      {resultsFor && (
        <ResultsDialog
          pub={resultsFor}
          open={!!resultsFor}
          onOpenChange={(o) => !o && setResultsFor(null)}
          onSaved={(p) => cache.replacePublication(platform, index, p)}
        />
      )}
      {publishable && (
        <PublishDialog
          open={publishOpen}
          onOpenChange={setPublishOpen}
          platform={platform}
          draft={draft}
          onPublished={(p) => cache.addPublication(platform, index, p)}
        />
      )}
    </motion.section>
  );
}
