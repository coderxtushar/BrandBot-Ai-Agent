"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, Sparkles } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { PLATFORMS } from "@/lib/platforms";
import type { BrandInput, PlatformId, RunSettings } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface ComposerValue {
  name: string;
  brand: BrandInput;
  settings: RunSettings;
}

const FIELDS: { key: keyof BrandInput; label: string; placeholder: string; rows: number }[] = [
  { key: "target_audience", label: "Who you write for", placeholder: "Startup founders and senior engineers", rows: 2 },
  { key: "expertise", label: "What you know best", placeholder: "Shipping AI features, Python, MLOps", rows: 2 },
  { key: "tone_of_voice", label: "How you sound", placeholder: "Direct and practical, a little dry, never salesy", rows: 2 },
  { key: "content_pillars", label: "Topics you post about", placeholder: "AI in production, career growth, Python tips", rows: 3 },
];

const ago = (iso: string) => {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`;
  return new Date(iso).toLocaleDateString();
};

const reveal = {
  initial: { height: 0, opacity: 0 },
  animate: { height: "auto", opacity: 1 },
  exit: { height: 0, opacity: 0 },
  transition: { duration: 0.28, ease: [0.22, 1, 0.36, 1] as const },
};

export function Composer({
  value,
  onChange,
  onGenerate,
  isNew,
  running,
  profileUpdatedAt,
  reuseProfile,
  onReuseProfile,
}: {
  value: ComposerValue;
  onChange: (v: ComposerValue) => void;
  onGenerate: () => void;
  isNew: boolean;
  running: boolean;
  profileUpdatedAt: string | null;
  reuseProfile: boolean;
  onReuseProfile: (v: boolean) => void;
}) {
  const [detailsOpen, setDetailsOpen] = useState(isNew);
  const [voiceOpen, setVoiceOpen] = useState(Boolean(value.brand.past_posts));
  const open = detailsOpen || isNew;
  const setBrand = (key: keyof BrandInput, v: string) => onChange({ ...value, brand: { ...value.brand, [key]: v } });
  const setSettings = (patch: Partial<RunSettings>) => onChange({ ...value, settings: { ...value.settings, ...patch } });
  const toggle = (id: PlatformId) => {
    const has = value.settings.platforms.includes(id);
    setSettings({ platforms: has ? value.settings.platforms.filter((p) => p !== id) : [...value.settings.platforms, id] });
  };

  const missing = FIELDS.filter((f) => value.brand[f.key].trim().length < 3);
  const ready = value.name.trim() && missing.length === 0 && value.settings.platforms.length > 0;
  const count = value.settings.platforms.length;

  return (
    <form
      className="space-y-7"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready && !running) onGenerate();
      }}
    >
      {/* Brand */}
      <section className="space-y-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="font-title text-2xl">{isNew ? "Set up your brand" : value.name || "Your brand"}</h2>
            <p className="text-sm text-muted-foreground">
              {isNew ? "Saved when you generate, so you only do this once." : "Used for every run of this brand."}
            </p>
          </div>
          {!isNew && (
            <button
              type="button"
              onClick={() => setDetailsOpen((o) => !o)}
              aria-expanded={open}
              className="flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-sm text-muted-foreground transition hover:bg-accent hover:text-foreground"
            >
              {open ? "Hide details" : "Edit details"}
              <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} />
            </button>
          )}
        </div>

        {!open && (
          <p className="line-clamp-2 text-sm text-muted-foreground">
            For {value.brand.target_audience || "…"}, about {value.brand.content_pillars || "…"}
          </p>
        )}

        <AnimatePresence initial={false}>
          {open && (
            <motion.div key="details" {...reveal} className="overflow-hidden">
              <div className="space-y-4 pt-1 pb-1">
                <div className="space-y-1.5">
                  <Label htmlFor="brand-name">Brand name</Label>
                  <Input
                    id="brand-name"
                    value={value.name}
                    maxLength={120}
                    placeholder="My personal brand"
                    onChange={(e) => onChange({ ...value, name: e.target.value })}
                  />
                </div>
                {FIELDS.map((f) => (
                  <div key={f.key} className="space-y-1.5">
                    <Label htmlFor={f.key}>{f.label}</Label>
                    <Textarea
                      id={f.key}
                      rows={f.rows}
                      placeholder={f.placeholder}
                      value={value.brand[f.key]}
                      onChange={(e) => setBrand(f.key, e.target.value)}
                      className="min-h-0 resize-y"
                    />
                  </div>
                ))}
                <div>
                  <button
                    type="button"
                    onClick={() => setVoiceOpen((o) => !o)}
                    aria-expanded={voiceOpen}
                    className="flex w-full items-center justify-between rounded-md py-1 text-left text-sm font-medium"
                  >
                    <span>
                      Teach it your voice <span className="font-normal text-muted-foreground">(optional)</span>
                    </span>
                    <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", voiceOpen && "rotate-180")} />
                  </button>
                  <AnimatePresence initial={false}>
                    {voiceOpen && (
                      <motion.div key="voice" {...reveal} className="overflow-hidden">
                        <Textarea
                          aria-label="Your past posts"
                          rows={6}
                          className="mt-2 min-h-0 resize-y"
                          placeholder="Paste 3–10 of your own posts. The writers mirror how you actually write."
                          value={value.brand.past_posts}
                          onChange={(e) => setBrand("past_posts", e.target.value)}
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      {/* Platforms */}
      <fieldset className="space-y-3">
        <legend className="mb-3 font-title text-lg">Where it goes</legend>
        <div className="grid grid-cols-2 gap-2">
          {PLATFORMS.map((p) => {
            const on = value.settings.platforms.includes(p.id);
            return (
              <motion.button
                key={p.id}
                type="button"
                aria-pressed={on}
                onClick={() => toggle(p.id)}
                whileTap={{ scale: 0.96 }}
                className={cn(
                  "relative flex items-center gap-2.5 overflow-hidden rounded-xl border px-3 py-2.5 text-left transition-colors",
                  on ? "border-ink bg-ink text-paper" : "border-border bg-card hover:border-ink/40",
                )}
              >
                <p.icon className="size-4 shrink-0" aria-hidden />
                <span className="min-w-0">
                  <span className="block text-sm leading-tight font-medium">{p.short}</span>
                  <span className={cn("block text-xs", on ? "text-paper/65" : "text-muted-foreground")}>{p.format}</span>
                </span>
                <AnimatePresence>
                  {on && (
                    <motion.span
                      initial={{ scale: 0, rotate: -45 }}
                      animate={{ scale: 1, rotate: 0 }}
                      exit={{ scale: 0 }}
                      transition={{ type: "spring", stiffness: 500, damping: 25 }}
                      className="ml-auto grid size-5 shrink-0 place-items-center rounded-full bg-riso-pink text-white"
                    >
                      <Check className="size-3" strokeWidth={3} />
                    </motion.span>
                  )}
                </AnimatePresence>
              </motion.button>
            );
          })}
        </div>
      </fieldset>

      {/* Run settings */}
      <section className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="topic">
            Topic <span className="font-normal text-muted-foreground">(optional)</span>
          </Label>
          <Input
            id="topic"
            value={value.settings.topic}
            maxLength={500}
            placeholder="Leave empty and Brand Bot picks a timely angle"
            onChange={(e) => setSettings({ topic: e.target.value })}
          />
        </div>

        <div className="flex items-center justify-between gap-4">
          <Label id="variants-label">Versions per platform</Label>
          <ToggleGroup
            type="single"
            variant="outline"
            aria-labelledby="variants-label"
            value={String(value.settings.variants)}
            onValueChange={(v) => v && setSettings({ variants: Number(v) })}
          >
            {[1, 2, 3].map((n) => (
              <ToggleGroupItem key={n} value={String(n)} className="w-10 data-[state=on]:bg-ink data-[state=on]:text-paper">
                {n}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>

        {profileUpdatedAt && (
          <label className="flex items-start justify-between gap-4">
            <span className="text-sm">
              Reuse your brand profile
              <span className="block text-xs text-muted-foreground">Saved {ago(profileUpdatedAt)}. Turn off to rebuild it.</span>
            </span>
            <Switch checked={reuseProfile} onCheckedChange={onReuseProfile} aria-label="Reuse your brand profile" />
          </label>
        )}
        <label className="flex items-start justify-between gap-4">
          <span className="text-sm">
            Learn from my best posts
            <span className="block text-xs text-muted-foreground">Writers see what performed well for this brand before.</span>
          </span>
          <Switch
            checked={value.settings.learn_from_results}
            onCheckedChange={(v) => setSettings({ learn_from_results: v })}
            aria-label="Learn from my best posts"
          />
        </label>
        <label className="flex items-start justify-between gap-4">
          <span className="text-sm">
            Review the plan before writing
            <span className="block text-xs text-muted-foreground">Pauses after research so you can adjust the angle.</span>
          </span>
          <Switch
            checked={value.settings.review_plan}
            onCheckedChange={(v) => setSettings({ review_plan: v })}
            aria-label="Review the plan before writing"
          />
        </label>
      </section>

      <div className="space-y-2">
        <motion.button
          type="submit"
          disabled={!ready || running}
          whileTap={ready && !running ? { x: 3, y: 3, boxShadow: "0px 0px 0 0 var(--riso-pink)" } : undefined}
          className="shadow-misprint flex h-12 w-full items-center justify-center gap-2 rounded-full bg-primary px-6 font-medium text-primary-foreground transition-opacity disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none"
        >
          <Sparkles className="size-4" aria-hidden />
          {running ? "Writing…" : count ? `Write for ${count} platform${count === 1 ? "" : "s"}` : "Pick a platform"}
        </motion.button>
        {!ready && !running && (
          <p className="text-center text-xs text-muted-foreground">
            {!value.name.trim()
              ? "Give your brand a name to start."
              : missing.length
                ? `Fill in “${missing[0].label.toLowerCase()}” to start.`
                : "Pick at least one platform."}
          </p>
        )}
      </div>
    </form>
  );
}
