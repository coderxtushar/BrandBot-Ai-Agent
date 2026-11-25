"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { CircleAlert, History, MoreHorizontal, PenLine, Sparkles, Trash2 } from "lucide-react";
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
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useRunStream } from "@/hooks/use-run-stream";
import { keys, useBrands, useDeleteRun, useRun, useRuns } from "@/hooks/use-studio-data";
import { api } from "@/lib/api";
import { load, save } from "@/lib/storage";
import type { Brand, BrandInput, BrandProfile, RunDetail, RunSettings } from "@/lib/types";
import { cn } from "@/lib/utils";
import { BrandSwitcher } from "./brand-switcher";
import { Composer, type ComposerValue } from "./composer";
import { HistoryList } from "./history-list";
import { PlanReview } from "./plan-review";
import { ProfileDialog } from "./profile-dialog";
import { ResultsView } from "./results-view";
import { RunProgress } from "./run-progress";
import { StudioHeader } from "./studio-header";

const NEW = "__new__";
const EMPTY_INPUT: BrandInput = { target_audience: "", expertise: "", tone_of_voice: "", content_pillars: "", past_posts: "" };
const DEFAULT_SETTINGS: RunSettings = { platforms: ["linkedin", "x"], topic: "", variants: 1, review_plan: false };

type BrandDraft = Pick<ComposerValue, "name" | "brand">;
type MobileTab = "write" | "results" | "history";

const omit = <T,>(obj: Record<string, T>, key: string) => Object.fromEntries(Object.entries(obj).filter(([k]) => k !== key));
const fromBrand = (b: Brand | undefined): BrandDraft => ({ name: b?.name ?? "", brand: { ...EMPTY_INPUT, ...(b?.input ?? {}) } });
const sameInput = (a: BrandInput, b: BrandInput) =>
  (Object.keys(EMPTY_INPUT) as (keyof BrandInput)[]).every((k) => (a[k] ?? "").trim() === (b[k] ?? "").trim());

function EmptyState() {
  return (
    <div className="relative grid min-h-[60vh] place-items-center overflow-hidden rounded-3xl border border-dashed border-border p-8 text-center">
      <div aria-hidden className="overprint absolute -top-10 -left-10 size-56 rounded-full bg-riso-sun/80" />
      <div aria-hidden className="overprint absolute -right-16 -bottom-16 size-72 rounded-full bg-riso-blue/70" />
      <div className="relative max-w-md">
        <p className="font-display text-5xl sm:text-6xl">Nothing on the press yet.</p>
        <p className="mt-4 text-muted-foreground">
          Describe your brand, pick where it goes, and press write. A run takes about a minute and is saved to your
          history.
        </p>
      </div>
    </div>
  );
}

export function Studio() {
  const qc = useQueryClient();
  const router = useRouter();
  const params = useSearchParams();
  const runParam = params.get("run");

  const brandsQ = useBrands();
  const brands = useMemo(() => brandsQ.data ?? [], [brandsQ.data]);

  // Brand selection is derived: an explicit choice, else the last one used, else the first, else a new brand.
  const [chosenBrand, setChosenBrand] = useState<string | null>(null);
  const storedBrand = typeof window !== "undefined" ? load<string | null>("brandbot.brand", null) : null;
  const brandId = brandsQ.isSuccess
    ? (chosenBrand ?? (brands.some((b) => b.id === storedBrand) ? storedBrand : (brands[0]?.id ?? NEW)))
    : null;
  const isNew = brandId === NEW;
  const brand = brands.find((b) => b.id === brandId);

  // Unsaved edits per brand sit on top of the saved brand.
  const [edits, setEdits] = useState<Record<string, BrandDraft>>({});
  const draft = (brandId && edits[brandId]) || fromBrand(brand);
  const [settings, setSettingsState] = useState<RunSettings>(() =>
    typeof window === "undefined" ? DEFAULT_SETTINGS : { ...DEFAULT_SETTINGS, ...load<Partial<RunSettings>>("brandbot.settings", {}) },
  );
  const setSettings = (s: RunSettings) => {
    setSettingsState(s);
    save("brandbot.settings", s);
  };
  const [reuseProfile, setReuseProfile] = useState(true);
  const inputChanged = brand ? !sameInput(draft.brand, brand.input) : true;
  const profile = brand?.profile && !inputChanged ? brand.profile : null;

  const runsQ = useRuns(isNew ? null : brandId);
  const runs = useMemo(() => runsQ.data ?? [], [runsQ.data]);
  // The open run: from the URL, else this brand's latest finished or paused run.
  const latest = runs.find((r) => r.status === "completed" || r.status === "awaiting_plan");
  const runId = runParam && (isNew || runs.some((r) => r.id === runParam) || runsQ.isLoading) ? runParam : (latest?.id ?? null);
  const runQ = useRun(isNew ? null : runId);
  const run = runQ.data;

  const [mobileTab, setMobileTab] = useState<MobileTab>("write");
  const [profileOpen, setProfileOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const deleteRun = useDeleteRun(brandId);

  const openRun = useCallback(
    (id: string | null) => router.replace(id ? `/studio?run=${id}` : "/studio", { scroll: false }),
    [router],
  );
  const stream = useRunStream(useCallback((r: RunDetail) => openRun(r.id), [openRun]));

  const selectBrand = (id: string) => {
    setChosenBrand(id);
    if (id !== NEW) save("brandbot.brand", id);
    openRun(null);
  };

  /** Create or update the brand so the server has exactly what's in the form. */
  const saveBrand = async (): Promise<Brand> => {
    const name = draft.name.trim();
    if (isNew || !brand) {
      const created = await api.createBrand(name, draft.brand);
      qc.setQueryData<Brand[]>(keys.brands, (list) => [created, ...(list ?? [])]);
      setEdits((e) => omit(e, NEW));
      selectBrand(created.id);
      return created;
    }
    if (name === brand.name && !inputChanged) return brand;
    const updated = await api.updateBrand(brand.id, { name, input: draft.brand });
    qc.setQueryData<Brand[]>(keys.brands, (list) => list?.map((b) => (b.id === updated.id ? updated : b)));
    setEdits((e) => omit(e, brand.id));
    return updated;
  };

  const generate = async () => {
    setMobileTab("results");
    try {
      const saved = await saveBrand();
      await stream.start(saved.id, settings, !reuseProfile);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const saveProfile = async (p: BrandProfile) => {
    const updated = await api.saveProfile(brand!.id, p);
    qc.setQueryData<Brand[]>(keys.brands, (list) => list?.map((b) => (b.id === updated.id ? updated : b)));
    setReuseProfile(true);
    toast.success("Profile saved. Your next run uses it.");
  };

  const removeBrand = async () => {
    if (!brand) return;
    try {
      await api.deleteBrand(brand.id);
      const rest = brands.filter((b) => b.id !== brand.id);
      qc.setQueryData<Brand[]>(keys.brands, rest);
      selectBrand(rest[0]?.id ?? NEW);
      toast(`Deleted “${brand.name}”.`);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const discard = async (r: RunDetail) => {
    try {
      qc.setQueryData(keys.run(r.id), await api.cancelRun(r.id));
      qc.invalidateQueries({ queryKey: keys.runs(r.brand_id) });
      toast("Run discarded.");
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  /* ---------- main panel ---------- */
  let main: React.ReactNode;
  if (stream.running) main = <RunProgress progress={stream.progress} onStop={stream.stop} />;
  else if (stream.error)
    main = (
      <div role="alert" className="flex gap-3 rounded-3xl bg-destructive/10 p-6 text-destructive">
        <CircleAlert className="mt-0.5 size-5 shrink-0" />
        <div>
          <p className="font-medium">The run didn&apos;t finish.</p>
          <p className="mt-1 text-sm">{stream.error}</p>
          <Button variant="outline" size="sm" className="mt-3" onClick={stream.dismissError}>Back to results</Button>
        </div>
      </div>
    );
  else if (brandsQ.isError)
    main = (
      <div role="alert" className="rounded-3xl bg-destructive/10 p-6 text-destructive">
        <p className="font-medium">Can&apos;t reach the Brand Bot API.</p>
        <p className="mt-1 text-sm">Start the backend (uvicorn backend.main:app) and reload this page.</p>
      </div>
    );
  else if (run?.status === "awaiting_plan")
    main = <PlanReview key={run.id} run={run} busy={stream.running} onContinue={(d) => stream.resume(run, d)} onDiscard={() => discard(run)} />;
  else if (run?.status === "completed") main = <ResultsView key={run.id} run={run} />;
  else if (run && (run.status === "failed" || run.status === "cancelled"))
    main = (
      <div className="rounded-3xl border border-border p-6">
        <p className="font-title text-xl">{run.status === "failed" ? "This run failed." : "This run was stopped."}</p>
        {run.error && <p className="mt-1 text-sm text-muted-foreground">{run.error}</p>}
      </div>
    );
  else if (runQ.isLoading) main = <div className="h-[60vh] animate-pulse rounded-3xl bg-muted" />;
  else main = <EmptyState />;

  const history = (
    <HistoryList
      runs={runs}
      loading={runsQ.isLoading && !isNew}
      activeId={run?.id ?? null}
      onOpen={(id) => {
        openRun(id);
        setMobileTab("results");
      }}
      onDelete={(id) => {
        if (id === run?.id) openRun(null);
        deleteRun.mutate(id, { onSuccess: () => toast("Run deleted."), onError: (e) => toast.error(e.message) });
      }}
    />
  );

  return (
    <div className="flex min-h-dvh flex-col">
      <StudioHeader>
            {brandsQ.isSuccess && (
              <BrandSwitcher brands={brands} activeId={brandId} isNew={isNew} onSelect={selectBrand} onNew={() => selectBrand(NEW)} disabled={stream.running} />
            )}
            {brand && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label="Brand options" disabled={stream.running}>
                    <MoreHorizontal className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem disabled={!profile} onSelect={() => setProfileOpen(true)}>
                    <PenLine className="size-4" /> Edit brand profile
                  </DropdownMenuItem>
                  <DropdownMenuItem variant="destructive" onSelect={() => setConfirmDelete(true)}>
                    <Trash2 className="size-4" /> Delete brand
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
      </StudioHeader>

      <div className="mx-auto grid w-full max-w-[1440px] flex-1 gap-8 px-4 pt-6 pb-28 sm:px-6 lg:grid-cols-[400px_minmax(0,1fr)] lg:pb-10">
        <aside className={cn("space-y-10 lg:sticky lg:top-20 lg:block lg:max-h-[calc(100dvh-6rem)] lg:self-start lg:overflow-y-auto lg:pr-2", mobileTab === "results" && "max-lg:hidden")}>
          <div className={cn(mobileTab === "history" && "max-lg:hidden")}>
            {brandsQ.isLoading ? (
              <div className="space-y-3">{[0, 1, 2, 3].map((i) => <div key={i} className="h-16 animate-pulse rounded-xl bg-muted" />)}</div>
            ) : (
              <Composer
                key={brandId ?? "loading"}
                value={{ ...draft, settings }}
                onChange={(v) => {
                  setEdits((e) => ({ ...e, [brandId!]: { name: v.name, brand: v.brand } }));
                  if (v.settings !== settings) setSettings(v.settings);
                }}
                onGenerate={generate}
                isNew={isNew}
                running={stream.running}
                profileUpdatedAt={profile ? brand!.profile_updated_at : null}
                reuseProfile={reuseProfile}
                onReuseProfile={setReuseProfile}
              />
            )}
            {profile && (
              <button
                type="button"
                onClick={() => setProfileOpen(true)}
                className="mt-8 block w-full rounded-2xl border border-border bg-card p-4 text-left transition hover:border-ink/30"
              >
                <span className="flex items-center justify-between text-sm font-medium">
                  Brand profile <PenLine className="size-3.5 text-muted-foreground" />
                </span>
                <span className="mt-1 line-clamp-2 block text-sm text-muted-foreground">{profile.positioning}</span>
              </button>
            )}
          </div>
          {!isNew && <div className={cn(mobileTab === "write" && "max-lg:hidden")}>{history}</div>}
        </aside>

        <main className={cn("min-w-0", mobileTab !== "results" && "max-lg:hidden")}>
          <AnimatePresence mode="wait">
            <motion.div
              key={stream.running ? "progress" : (run?.id ?? "empty") + (run?.status ?? "")}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            >
              {main}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {/* Mobile tab bar */}
      <nav aria-label="Studio sections" className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background/90 px-4 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur lg:hidden">
        <div className="mx-auto grid max-w-md grid-cols-3 gap-1">
          {([
            ["write", "Write", Sparkles],
            ["results", "Results", PenLine],
            ["history", "History", History],
          ] as const).map(([id, label, Icon]) => (
            <button
              key={id}
              type="button"
              onClick={() => setMobileTab(id)}
              aria-current={mobileTab === id ? "page" : undefined}
              disabled={id === "history" && isNew}
              className={cn("relative flex flex-col items-center gap-0.5 rounded-xl py-1.5 text-xs transition-colors disabled:opacity-40", mobileTab === id ? "text-paper" : "text-muted-foreground")}
            >
              {mobileTab === id && <motion.span layoutId="mobile-tab" className="absolute inset-0 rounded-xl bg-ink" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
              <Icon className="relative size-4" />
              <span className="relative">{label}</span>
              {id === "results" && stream.running && <span className="absolute top-1 right-[30%] size-2 animate-pulse rounded-full bg-riso-pink" />}
            </button>
          ))}
        </div>
      </nav>

      {profile && brand && <ProfileDialog profile={profile} open={profileOpen} onOpenChange={setProfileOpen} onSave={saveProfile} />}

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogTitle>Delete “{brand?.name}”?</AlertDialogTitle>
          <AlertDialogDescription>All of its runs, drafts and images are deleted too. This can&apos;t be undone.</AlertDialogDescription>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive text-white hover:bg-destructive/90" onClick={removeBrand}>
              Delete brand
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
