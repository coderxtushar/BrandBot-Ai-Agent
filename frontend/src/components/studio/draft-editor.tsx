"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Content } from "@/lib/types";

/*
 * One editor for every platform: it walks the draft's own structure.
 *   string            -> textarea
 *   hashtags / tags   -> space-separated input
 *   list of strings   -> one textarea per item (tweets, Threads posts)
 *   list of objects   -> a group of fields per item (carousel slides, Shorts beats)
 */

type Value = string | string[] | Record<string, string>[];

const TAG_KEYS = new Set(["hashtags", "tags"]);
const ROWS: Record<string, number> = { body: 8, body_markdown: 16, caption: 6, description: 4, image_prompt: 3 };
const LABELS: Record<string, string> = { closing_question: "Closing question", body_markdown: "Article", on_screen_text: "On screen", cta: "Call to action", topic_tag: "Topic tag", image_prompt: "Image idea", alt_text: "Alt text" };

const humanize = (key: string) => LABELS[key] ?? key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
const singular = (key: string) => humanize(key).replace(/s$/, "");

function TagInput({ id, value, onChange }: { id: string; value: string[]; onChange: (v: string[]) => void }) {
  const [raw, setRaw] = useState(() => value.map((t) => `#${t}`).join(" "));
  return (
    <Input
      id={id}
      value={raw}
      onChange={(e) => {
        setRaw(e.target.value);
        onChange(e.target.value.split(/[\s,]+/).map((t) => t.replace(/^#/, "")).filter(Boolean));
      }}
    />
  );
}

function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button type="button" variant="ghost" size="icon" className="size-7 shrink-0 text-muted-foreground hover:text-destructive" aria-label={`Remove ${label}`} onClick={onClick}>
      <X className="size-3.5" />
    </Button>
  );
}

function Field({ path, name, value, onChange }: { path: string; name: string; value: Value; onChange: (v: Value) => void }) {
  const id = `edit-${path}`;

  if (typeof value === "string") {
    return (
      <div className="space-y-1.5">
        <Label htmlFor={id}>{humanize(name)}</Label>
        <Textarea
          id={id}
          rows={ROWS[name] ?? (value.length > 90 ? 3 : 2)}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={name === "body_markdown" ? "min-h-0 resize-y font-mono text-xs" : "min-h-0 resize-y"}
        />
      </div>
    );
  }

  if (TAG_KEYS.has(name)) {
    return (
      <div className="space-y-1.5">
        <Label htmlFor={id}>{humanize(name)}</Label>
        <TagInput id={id} value={value as string[]} onChange={onChange} />
      </div>
    );
  }

  const list = value as (string | Record<string, string>)[];
  const objects = list.length > 0 && typeof list[0] === "object";
  const blank = objects ? Object.fromEntries(Object.keys(list[0] as object).map((k) => [k, ""])) : "";
  const set = (i: number, v: string | Record<string, string>) => onChange(list.map((x, j) => (j === i ? v : x)) as Value);
  const remove = (i: number) => onChange(list.filter((_, j) => j !== i) as Value);

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">
        {humanize(name)} <span className="font-normal text-muted-foreground">({list.length})</span>
      </legend>
      <AnimatePresence initial={false}>
        {list.map((item, i) => (
          <motion.div
            key={i}
            layout
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            {typeof item === "object" ? (
              <div className="rounded-xl border border-border p-3">
                <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
                  <span>{singular(name)} {i + 1}</span>
                  <RemoveButton label={`${singular(name)} ${i + 1}`} onClick={() => remove(i)} />
                </div>
                <div className="space-y-2">
                  {Object.entries(item).map(([k, v]) => (
                    <Field key={k} path={`${path}-${i}-${k}`} name={k} value={v} onChange={(nv) => set(i, { ...item, [k]: nv as string })} />
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-1">
                <Textarea
                  aria-label={`${singular(name)} ${i + 1}`}
                  rows={2}
                  value={item}
                  onChange={(e) => set(i, e.target.value)}
                  className="min-h-0 resize-y"
                />
                <RemoveButton label={`${singular(name)} ${i + 1}`} onClick={() => remove(i)} />
              </div>
            )}
          </motion.div>
        ))}
      </AnimatePresence>
      <Button type="button" variant="outline" size="sm" onClick={() => onChange([...list, blank] as Value)}>
        <Plus className="size-3.5" /> Add {singular(name).toLowerCase()}
      </Button>
    </fieldset>
  );
}

export function DraftEditor({
  draftId,
  content,
  onSave,
  onCancel,
}: {
  draftId: string;
  content: Content;
  onSave: (c: Content) => Promise<unknown>;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(content as Record<string, Value>);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        setSaving(true);
        setError(null);
        try {
          await onSave(value);
        } catch (err) {
          setError((err as Error).message);
          setSaving(false);
        }
      }}
    >
      {Object.entries(value).map(([k, v]) => (
        <Field key={k} path={`${draftId}-${k}`} name={k} value={v} onChange={(nv) => setValue({ ...value, [k]: nv })} />
      ))}
      {error && <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Save changes"}</Button>
        <Button type="button" variant="ghost" onClick={onCancel} disabled={saving}>Cancel</Button>
      </div>
    </form>
  );
}
