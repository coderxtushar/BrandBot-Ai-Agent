"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Clapperboard, Newspaper, Unplug } from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { keys, useConnections } from "@/hooks/use-studio-data";
import { api } from "@/lib/api";
import { platform as platformMeta } from "@/lib/platforms";
import type { Connection } from "@/lib/types";
import { StudioHeader } from "./studio-header";

const since = (iso: string) => new Date(iso).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });

export function ConnectionsView() {
  const qc = useQueryClient();
  const router = useRouter();
  const params = useSearchParams();
  const { data, isLoading, error } = useConnections();
  const [connecting, setConnecting] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<Connection | null>(null);

  // Coming back from a platform's consent screen.
  useEffect(() => {
    const connected = params.get("connected");
    const failed = params.get("error");
    if (!connected && !failed) return;
    if (connected) toast.success(`${platformMeta(connected as never).label} connected.`);
    if (failed) toast.error(failed);
    qc.invalidateQueries({ queryKey: keys.connections });
    router.replace("/studio/connections", { scroll: false });
  }, [params, qc, router]);

  const connect = async (p: string) => {
    setConnecting(p);
    try {
      const { url } = await api.startConnection(p);
      window.location.assign(url); // off to the platform's consent screen
    } catch (err) {
      toast.error((err as Error).message);
      setConnecting(null);
    }
  };

  const disconnect = async (account: Connection) => {
    try {
      await api.disconnect(account.id);
      qc.invalidateQueries({ queryKey: keys.connections });
      qc.invalidateQueries({ queryKey: ["publications"] });
      toast(`Disconnected ${account.display_name}. Its scheduled posts were cancelled.`);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  return (
    <div className="flex flex-1 flex-col">
      <StudioHeader />
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6">
        <h1 className="font-display text-5xl sm:text-6xl">Connections</h1>
        <p className="mt-3 max-w-xl text-muted-foreground">
          Connect the accounts Brand Bot can post to. Nothing goes out until you publish or schedule a draft.
        </p>

        {error && <p className="mt-8 text-destructive">{(error as Error).message}</p>}

        <div className="mt-10 grid gap-4 md:grid-cols-2">
          {isLoading &&
            [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-48 rounded-3xl" />)}
          {data?.platforms.map(({ platform: id, available, note }) => {
            const meta = platformMeta(id);
            const accounts = data.accounts.filter((a) => a.platform === id);
            return (
              <section key={id} className="flex flex-col rounded-3xl border border-border bg-card p-6">
                <div className="flex items-start gap-4">
                  <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-ink text-paper">
                    <meta.icon className="size-5" aria-hidden />
                  </span>
                  <div className="min-w-0">
                    <h2 className="font-title text-xl">{meta.label}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">{note}</p>
                  </div>
                </div>

                <ul className="mt-5 space-y-2">
                  <AnimatePresence initial={false}>
                    {accounts.map((a) => (
                      <motion.li
                        key={a.id}
                        layout
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="flex items-center justify-between gap-3 overflow-hidden rounded-xl bg-muted/70 px-3 py-2.5"
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-medium">{a.display_name}</span>
                          <span className="block text-xs text-muted-foreground">
                            {a.username ? `@${a.username}, ` : ""}connected {since(a.created_at)}
                          </span>
                        </span>
                        <Button variant="ghost" size="sm" onClick={() => setConfirm(a)} className="shrink-0 text-muted-foreground hover:text-destructive">
                          <Unplug className="size-3.5" /> Disconnect
                        </Button>
                      </motion.li>
                    ))}
                  </AnimatePresence>
                </ul>

                <div className="mt-auto pt-5">
                  <Button
                    onClick={() => connect(id)}
                    disabled={!available || connecting !== null}
                    variant={accounts.length ? "outline" : "default"}
                    className="rounded-full"
                  >
                    {connecting === id ? "Opening " + meta.label + "…" : accounts.length ? "Connect another account" : `Connect ${meta.label}`}
                  </Button>
                </div>
              </section>
            );
          })}
        </div>

        <section className="mt-6 flex flex-col gap-4 rounded-3xl border border-dashed border-border p-6 sm:flex-row sm:items-center">
          <span className="flex gap-2 text-muted-foreground">
            <Newspaper className="size-5" aria-hidden />
            <Clapperboard className="size-5" aria-hidden />
          </span>
          <p className="text-sm text-muted-foreground">
            Medium and YouTube Shorts don&apos;t offer posting APIs. Copy those drafts, or download the article as Markdown
            and use Medium&apos;s import.
          </p>
        </section>
      </main>

      <AlertDialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogTitle>Disconnect {confirm?.display_name}?</AlertDialogTitle>
          <AlertDialogDescription>
            Posts already published stay where they are. Posts scheduled for this account are cancelled.
          </AlertDialogDescription>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep connected</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => {
                if (confirm) disconnect(confirm);
                setConfirm(null);
              }}
            >
              Disconnect
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
