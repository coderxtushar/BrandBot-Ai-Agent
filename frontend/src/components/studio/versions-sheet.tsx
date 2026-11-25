"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { keys } from "@/hooks/use-studio-data";
import { api } from "@/lib/api";
import type { DraftVersion } from "@/lib/types";

const SOURCE: Record<DraftVersion["source"], string> = {
  generated: "Written by Brand Bot",
  edited: "Edited by you",
  rewrite: "AI rewrite",
  regenerate: "Fresh draft",
  restored: "Restored",
};

const when = (iso: string) =>
  new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export function VersionsSheet({
  draftId,
  open,
  onOpenChange,
  onRestore,
}: {
  draftId: string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onRestore: (versionId: string) => Promise<unknown>;
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: keys.versions(draftId),
    queryFn: () => api.listVersions(draftId),
    enabled: open,
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="font-title text-xl">Version history</SheetTitle>
          <SheetDescription>Every change to this draft. Restoring keeps the newer versions too.</SheetDescription>
        </SheetHeader>
        <div className="px-4 pb-6">
          {isLoading && (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}
            </div>
          )}
          {error && <p className="text-sm text-destructive">{(error as Error).message}</p>}
          {/* a timeline: newest at the top */}
          <ol className="relative space-y-4 border-l border-border pl-5">
            {data?.map((v, i) => (
              <motion.li
                key={v.id}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="relative"
              >
                <span
                  aria-hidden
                  className={`absolute top-1.5 -left-[26px] size-3 rounded-full border-2 border-background ${i === 0 ? "bg-riso-blue" : "bg-muted-foreground/40"}`}
                />
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      {SOURCE[v.source] ?? v.source}
                      {i === 0 && <span className="ml-2 rounded-full bg-riso-blue/10 px-2 py-0.5 text-xs font-normal text-primary">Current</span>}
                    </p>
                    <p className="text-xs text-muted-foreground">{when(v.created_at)}</p>
                    {v.note && <p className="mt-1 text-xs text-muted-foreground">{v.note}</p>}
                  </div>
                  {i > 0 && (
                    <Button size="sm" variant="outline" onClick={() => onRestore(v.id)}>
                      <RotateCcw className="size-3.5" /> Restore
                    </Button>
                  )}
                </div>
                <p className="mt-2 line-clamp-3 rounded-lg bg-muted p-2.5 text-xs leading-relaxed">{v.text}</p>
              </motion.li>
            ))}
          </ol>
        </div>
      </SheetContent>
    </Sheet>
  );
}
