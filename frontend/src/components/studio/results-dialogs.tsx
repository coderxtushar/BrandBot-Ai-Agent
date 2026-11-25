"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { platform as platformMeta } from "@/lib/platforms";
import { toLocalInput } from "@/lib/time";
import type { Metrics, PlatformId, Publication } from "@/lib/types";

const FIELDS = [
  { key: "views", label: "Views", optional: true },
  { key: "likes", label: "Likes" },
  { key: "comments", label: "Comments" },
  { key: "shares", label: "Shares or reposts" },
  { key: "saves", label: "Saves" },
] as const;

/** Type in a post's numbers, for platforms that don't share stats (or to correct them). */
export function ResultsDialog({
  pub,
  open,
  onOpenChange,
  onSaved,
}: {
  pub: Pick<Publication, "id" | "platform" | "metrics">;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSaved?: (p: Publication) => void;
}) {
  const qc = useQueryClient();
  const start = (m: Metrics | null) => ({
    views: m?.views != null ? String(m.views) : "",
    likes: String(m?.likes ?? ""),
    comments: String(m?.comments ?? ""),
    shares: String(m?.shares ?? ""),
    saves: String(m?.saves ?? ""),
  });
  const [values, setValues] = useState(() => start(pub.metrics));
  const [busy, setBusy] = useState(false);
  const num = (v: string) => (v.trim() === "" ? 0 : Math.max(0, Math.floor(Number(v)) || 0));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const saved = await api.addResults(pub.id, {
        views: values.views.trim() === "" ? null : num(values.views),
        likes: num(values.likes),
        comments: num(values.comments),
        shares: num(values.shares),
        saves: num(values.saves),
      });
      qc.invalidateQueries({ queryKey: ["publications"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
      onSaved?.(saved);
      toast.success("Results saved.");
      onOpenChange(false);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (o) setValues(start(pub.metrics));
        onOpenChange(o);
      }}
    >
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle className="font-title text-2xl">Add results</DialogTitle>
          <DialogDescription>Copy the numbers from {platformMeta(pub.platform).label}. Analytics and future runs use them.</DialogDescription>
        </DialogHeader>
        <form id={`results-${pub.id}`} onSubmit={save} className="grid grid-cols-2 gap-3">
          {FIELDS.map((f) => (
            <div key={f.key} className="space-y-1.5">
              <Label htmlFor={`${pub.id}-${f.key}`}>
                {f.label} {"optional" in f && <span className="font-normal text-muted-foreground">(if shown)</span>}
              </Label>
              <Input
                id={`${pub.id}-${f.key}`}
                type="number"
                inputMode="numeric"
                min={0}
                value={values[f.key]}
                onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
              />
            </div>
          ))}
        </form>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
          <Button type="submit" form={`results-${pub.id}`} disabled={busy}>{busy ? "Saving…" : "Save results"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** "I posted this myself": record a manual post (Medium, Shorts, or anything posted outside Brand Bot). */
export function PostedMyselfDialog({
  draftId,
  platform,
  open,
  onOpenChange,
  onSaved,
}: {
  draftId: string;
  platform: PlatformId;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSaved: (p: Publication) => void;
}) {
  const qc = useQueryClient();
  const [url, setUrl] = useState("");
  const [when, setWhen] = useState(() => toLocalInput(new Date()));
  const [busy, setBusy] = useState(false);
  const meta = platformMeta(platform);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const pub = await api.postedMyself(draftId, { url: url.trim() || null, published_at: new Date(when).toISOString() });
      qc.invalidateQueries({ queryKey: ["publications"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
      onSaved(pub);
      toast.success(`Marked as posted on ${meta.label}. Add its results any time from Scheduled.`);
      onOpenChange(false);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle className="font-title text-2xl">I posted this myself</DialogTitle>
          <DialogDescription>Track a post you published on {meta.label} outside Brand Bot, so its results count.</DialogDescription>
        </DialogHeader>
        <form id={`manual-${draftId}`} onSubmit={save} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor={`url-${draftId}`}>Link to the post <span className="font-normal text-muted-foreground">(optional)</span></Label>
            <Input id={`url-${draftId}`} type="url" placeholder="https://" value={url} onChange={(e) => setUrl(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`when-${draftId}`}>Posted on</Label>
            <Input id={`when-${draftId}`} type="datetime-local" max={toLocalInput(new Date())} value={when} onChange={(e) => setWhen(e.target.value)} required />
          </div>
        </form>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
          <Button type="submit" form={`manual-${draftId}`} disabled={busy}>{busy ? "Saving…" : "Mark as posted"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
