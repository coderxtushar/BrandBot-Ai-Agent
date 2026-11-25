"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { BrandProfile } from "@/lib/types";

const lines = (l: string[]) => l.join("\n");
const fromLines = (t: string) => t.split("\n").map((s) => s.trim()).filter(Boolean);
const fromCommas = (t: string) => t.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
const fromTags = (t: string) => t.split(/[\s,]+/).map((s) => s.replace(/^#/, "").trim()).filter(Boolean);

type Draft = Record<"positioning" | "audience_persona" | "traits" | "do" | "dont" | "pillars" | "hashtags" | "visual_style", string>;

const FIELDS: { key: keyof Draft; label: string; hint?: string; rows: number }[] = [
  { key: "positioning", label: "Positioning", rows: 3 },
  { key: "audience_persona", label: "Who it's for", rows: 3 },
  { key: "traits", label: "Voice", hint: "comma-separated", rows: 1 },
  { key: "do", label: "Always", hint: "one per line", rows: 3 },
  { key: "dont", label: "Never", hint: "one per line", rows: 3 },
  { key: "pillars", label: "Topics", hint: "one per line", rows: 3 },
  { key: "hashtags", label: "Hashtags", rows: 2 },
  { key: "visual_style", label: "Visual style", hint: "used for generated images", rows: 2 },
];

function toDraft(p: BrandProfile): Draft {
  return {
    positioning: p.positioning,
    audience_persona: p.audience_persona,
    traits: p.voice.traits.join(", "),
    do: lines(p.voice.do),
    dont: lines(p.voice.dont),
    pillars: lines(p.pillars),
    hashtags: p.hashtags.map((h) => `#${h}`).join(" "),
    visual_style: p.visual_style ?? "",
  };
}

export function ProfileDialog({
  profile,
  open,
  onOpenChange,
  onSave,
}: {
  profile: BrandProfile;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSave: (p: BrandProfile) => Promise<unknown>;
}) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(profile));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (o) setDraft(toDraft(profile));
        onOpenChange(o);
      }}
    >
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="font-title text-2xl">Brand profile</DialogTitle>
          <DialogDescription>Every run writes from this. Your edits are kept until you change your brand details.</DialogDescription>
        </DialogHeader>
        <form
          id="profile-form"
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            const next: BrandProfile = {
              positioning: draft.positioning.trim(),
              audience_persona: draft.audience_persona.trim(),
              voice: { traits: fromCommas(draft.traits), do: fromLines(draft.do), dont: fromLines(draft.dont) },
              pillars: fromLines(draft.pillars),
              hashtags: fromTags(draft.hashtags),
              visual_style: draft.visual_style.trim(),
            };
            if (!next.positioning || !next.audience_persona || next.pillars.length === 0) {
              setError("Positioning, who it's for, and at least one topic are required.");
              return;
            }
            setSaving(true);
            setError(null);
            try {
              await onSave(next);
              onOpenChange(false);
            } catch (err) {
              setError((err as Error).message);
            } finally {
              setSaving(false);
            }
          }}
        >
          {FIELDS.map((f) => (
            <div key={f.key} className="space-y-1.5">
              <Label htmlFor={`profile-${f.key}`}>
                {f.label} {f.hint && <span className="font-normal text-muted-foreground">({f.hint})</span>}
              </Label>
              <Textarea
                id={`profile-${f.key}`}
                rows={f.rows}
                value={draft[f.key]}
                onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}
                className="min-h-0 resize-y"
              />
            </div>
          ))}
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        </form>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={saving}>Cancel</Button>
          <Button type="submit" form="profile-form" disabled={saving}>{saving ? "Saving…" : "Save profile"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
