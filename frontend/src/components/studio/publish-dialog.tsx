"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { Send, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useConnections } from "@/hooks/use-studio-data";
import { api } from "@/lib/api";
import { platform as platformMeta } from "@/lib/platforms";
import { formatWhen, nextHour, toLocalInput } from "@/lib/time";
import type { DraftRef, PlatformId, Publication } from "@/lib/types";

export const PUBLISHABLE: PlatformId[] = ["linkedin", "x", "threads", "instagram"];

export function PublishDialog({
  open,
  onOpenChange,
  platform,
  draft,
  onPublished,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  platform: PlatformId;
  draft: DraftRef;
  onPublished: (p: Publication) => void;
}) {
  const meta = platformMeta(platform);
  const { data, isLoading } = useConnections();
  const accounts = data?.accounts.filter((a) => a.platform === platform) ?? [];
  const [accountId, setAccountId] = useState<string>("");
  const [when, setWhen] = useState<"now" | "later">("now");
  const [at, setAt] = useState(() => toLocalInput(nextHour()));
  const [withImage, setWithImage] = useState(true);
  const [busy, setBusy] = useState(false);

  const account = accounts.find((a) => a.id === accountId) ?? accounts[0];
  const supportsImage = platform !== "x";
  const needsImage = platform === "instagram";
  const hasImage = draft.images.length > 0;
  const blocker = draft.lint.length
    ? `Fix this first: ${draft.lint[0]}`
    : needsImage && !hasImage
      ? "Instagram posts need an image. Open Visuals and generate one first."
      : null;

  const submit = async () => {
    if (!account) return;
    setBusy(true);
    try {
      const pub = await api.publish(draft.id, {
        account_id: account.id,
        scheduled_at: when === "later" ? new Date(at).toISOString() : null,
        include_image: needsImage || (supportsImage && withImage),
      });
      onPublished(pub);
      onOpenChange(false);
      if (pub.status === "published")
        toast.success(`Published to ${meta.label}.`, pub.external_url ? { action: { label: "View", onClick: () => window.open(pub.external_url!, "_blank") } } : undefined);
      else if (pub.status === "failed") toast.error(pub.error ?? "Publishing failed.");
      else if (when === "now") toast.warning(pub.error ?? "Queued to retry.");
      else toast.success(`Scheduled for ${formatWhen(pub.scheduled_at)}.`);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-title text-2xl">Publish to {meta.label}</DialogTitle>
          <DialogDescription>Post this draft now, or pick a time and Brand Bot posts it for you.</DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="h-24 animate-pulse rounded-xl bg-muted" />
        ) : accounts.length === 0 ? (
          <div className="rounded-2xl bg-muted p-4 text-sm">
            <p>No {meta.label} account is connected yet.</p>
            <Button asChild size="sm" className="mt-3 rounded-full">
              <Link href="/studio/connections">Connect {meta.label}</Link>
            </Button>
          </div>
        ) : (
          <div className="space-y-5">
            <div className="space-y-1.5">
              <Label>Account</Label>
              {accounts.length === 1 ? (
                <p className="rounded-lg border border-border px-3 py-2 text-sm">
                  {account.display_name}
                  {account.username && <span className="text-muted-foreground"> @{account.username}</span>}
                </p>
              ) : (
                <Select value={account.id} onValueChange={setAccountId}>
                  <SelectTrigger aria-label="Account"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {accounts.map((a) => (
                      <SelectItem key={a.id} value={a.id}>{a.display_name}{a.username ? ` @${a.username}` : ""}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="space-y-2">
              <Label id="when-label">When</Label>
              <ToggleGroup type="single" variant="outline" aria-labelledby="when-label" value={when} onValueChange={(v) => v && setWhen(v as "now" | "later")}>
                <ToggleGroupItem value="now" className="px-4 data-[state=on]:bg-ink data-[state=on]:text-paper">Now</ToggleGroupItem>
                <ToggleGroupItem value="later" className="px-4 data-[state=on]:bg-ink data-[state=on]:text-paper">Schedule</ToggleGroupItem>
              </ToggleGroup>
              <AnimatePresence initial={false}>
                {when === "later" && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <Input aria-label="Publish at" type="datetime-local" value={at} min={toLocalInput(new Date())} onChange={(e) => setAt(e.target.value)} className="mt-1" />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {supportsImage && hasImage && !needsImage && (
              <label className="flex items-center justify-between gap-4 text-sm">
                Include the image
                <Switch checked={withImage} onCheckedChange={setWithImage} aria-label="Include the image" />
              </label>
            )}
            {platform === "x" && <p className="text-sm text-muted-foreground">X threads are posted as text, one tweet after another.</p>}
            {blocker && (
              <p role="alert" className="flex gap-2 rounded-xl bg-riso-sun/25 p-3 text-sm">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" /> {blocker}
              </p>
            )}
          </div>
        )}

        {accounts.length > 0 && (
          <DialogFooter>
            <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
            <Button onClick={submit} disabled={busy || !!blocker || (when === "later" && !at)} className="rounded-full">
              <Send className="size-4" />
              {busy ? (when === "now" ? "Publishing…" : "Scheduling…") : when === "now" ? "Publish now" : "Schedule"}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
