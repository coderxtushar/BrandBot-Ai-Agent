"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Download, ImagePlus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { api, apiUrl } from "@/lib/api";
import { IMAGE_STYLES, aspect } from "@/lib/platforms";
import type { DraftImage, ImageStyle } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Placeholder while an image is generated: pink halftone "developing" on the plate. */
function Developing({ ratio }: { ratio: string }) {
  return (
    <div className="relative overflow-hidden rounded-xl bg-riso-pink/10" style={{ aspectRatio: aspect(ratio) }}>
      <motion.div
        aria-hidden
        className="halftone absolute -inset-6 text-riso-pink"
        animate={{ x: [0, 9], y: [0, 9], opacity: [0.35, 0.7, 0.35] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
      />
      <p className="absolute inset-x-0 bottom-3 text-center text-xs font-medium text-riso-pink">Art-directing and printing…</p>
    </div>
  );
}

async function download(image: DraftImage) {
  const res = await fetch(apiUrl(image.url));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const ext = image.url.split(".").pop() || "png";
  Object.assign(document.createElement("a"), { href: url, download: `brand-bot-${image.id.slice(0, 8)}.${ext}` }).click();
  URL.revokeObjectURL(url);
}

export function Visuals({
  draftId,
  ratio,
  images,
  onAdded,
  onRemoved,
}: {
  draftId: string;
  ratio: string;
  images: DraftImage[];
  onAdded: (img: DraftImage) => void;
  onRemoved: (id: string) => void;
}) {
  const [style, setStyle] = useState<ImageStyle | "">("");
  const [idea, setIdea] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<DraftImage | null>(null);

  const generate = async () => {
    setBusy(true);
    try {
      onAdded(await api.generateImage(draftId, { idea: idea.trim(), style: style || null }));
      toast.success("Image added. It now shows in the preview.");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (img: DraftImage) => {
    try {
      await api.deleteImage(img.id);
      onRemoved(img.id);
      setOpen(null);
      toast("Image deleted.");
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  return (
    <div className="space-y-4 rounded-2xl border border-border bg-background/60 p-4">
      <div className="space-y-3">
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={style}
          onValueChange={(v) => setStyle(v as ImageStyle | "")}
          aria-label="Image style"
          className="flex-wrap"
        >
          {IMAGE_STYLES.map((s) => (
            <ToggleGroupItem key={s.id} value={s.id} className="px-3 data-[state=on]:bg-ink data-[state=on]:text-paper">
              {s.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (!busy) generate();
          }}
        >
          <Input
            aria-label="Your idea for the image"
            placeholder="Your idea, or leave empty and the art director decides"
            value={idea}
            maxLength={500}
            onChange={(e) => setIdea(e.target.value)}
          />
          <Button type="submit" disabled={busy} className="shrink-0">
            <ImagePlus className="size-4" /> {busy ? "Generating…" : "Generate image"}
          </Button>
        </form>
        <p className="text-xs text-muted-foreground">Sized {ratio} for this platform, in your brand&apos;s visual style.</p>
      </div>

      {(busy || images.length > 0) && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <AnimatePresence initial={false}>
            {busy && (
              <motion.li key="developing" layout initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}>
                <Developing ratio={ratio} />
              </motion.li>
            )}
            {images.map((img, i) => (
              <motion.li
                key={img.id}
                layout
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                className="relative"
              >
                <button
                  type="button"
                  onClick={() => setOpen(img)}
                  className={cn("block w-full overflow-hidden rounded-xl ring-offset-2 ring-offset-background transition hover:ring-2 hover:ring-ink/30", i === 0 && "ring-2 ring-riso-blue")}
                  style={{ aspectRatio: aspect(img.aspect_ratio) }}
                  aria-label={`View image: ${img.alt_text}`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={apiUrl(img.url)} alt={img.alt_text} className="size-full object-cover" />
                </button>
                {i === 0 && (
                  <span className="absolute top-2 left-2 rounded-full bg-riso-blue px-2 py-0.5 text-[10px] font-medium text-white">In preview</span>
                )}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}

      <Dialog open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        <DialogContent className="max-w-2xl">
          {open && (
            <>
              <DialogTitle className="font-title">Generated image</DialogTitle>
              <DialogDescription>{open.alt_text}</DialogDescription>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={apiUrl(open.url)}
                alt={open.alt_text}
                className="max-h-[60vh] w-full rounded-xl object-contain"
                style={{ aspectRatio: aspect(open.aspect_ratio) }}
              />
              <details className="text-sm">
                <summary className="cursor-pointer text-muted-foreground">Prompt the art director wrote</summary>
                <p className="mt-2">{open.prompt}</p>
              </details>
              <div className="flex flex-wrap justify-end gap-2">
                <Button variant="ghost" className="text-destructive hover:text-destructive" onClick={() => remove(open)}>
                  <Trash2 className="size-4" /> Delete
                </Button>
                <Button variant="outline" onClick={() => download(open)}>
                  <Download className="size-4" /> Download
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
