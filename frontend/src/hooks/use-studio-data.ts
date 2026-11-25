"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Draft, DraftImage, PlatformId, RunDetail, RunSummary } from "@/lib/types";

export const keys = {
  brands: ["brands"] as const,
  runs: (brandId: string) => ["runs", brandId] as const,
  run: (runId: string) => ["run", runId] as const,
  versions: (draftId: string) => ["versions", draftId] as const,
};

export function useBrands() {
  return useQuery({ queryKey: keys.brands, queryFn: api.listBrands });
}

export function useRuns(brandId: string | null) {
  return useQuery({
    queryKey: keys.runs(brandId ?? "none"),
    queryFn: () => api.listRuns(brandId!),
    enabled: !!brandId,
  });
}

export function useRun(runId: string | null) {
  return useQuery({ queryKey: keys.run(runId ?? "none"), queryFn: () => api.getRun(runId!), enabled: !!runId });
}

/** Patch one draft inside a cached run, so edits show instantly without refetching the run. */
export function useDraftCache(runId: string) {
  const qc = useQueryClient();

  const patch = (platform: PlatformId, index: number, fn: (r: RunDetail["results"][number]) => RunDetail["results"][number]) =>
    qc.setQueryData<RunDetail>(keys.run(runId), (run) =>
      run && {
        ...run,
        results: run.results.map((r) => (r.platform === platform ? fn(r) : r)),
      },
    );

  const swap = <T,>(list: T[], i: number, value: T) => list.map((x, j) => (j === i ? value : x));

  return {
    applyDraft(platform: PlatformId, index: number, draft: Draft) {
      patch(platform, index, (r) => ({
        ...r,
        items: swap(r.items, index, draft.content),
        text: swap(r.text, index, draft.text),
        drafts: swap(r.drafts, index, { ...r.drafts[index], status: draft.status, review: draft.review, lint: draft.lint }),
      }));
      qc.invalidateQueries({ queryKey: keys.versions(draft.id) });
    },
    addImage(platform: PlatformId, index: number, image: DraftImage) {
      patch(platform, index, (r) => ({
        ...r,
        drafts: swap(r.drafts, index, { ...r.drafts[index], images: [image, ...r.drafts[index].images] }),
      }));
    },
    removeImage(platform: PlatformId, index: number, imageId: string) {
      patch(platform, index, (r) => ({
        ...r,
        drafts: swap(r.drafts, index, {
          ...r.drafts[index],
          images: r.drafts[index].images.filter((i) => i.id !== imageId),
        }),
      }));
    },
  };
}

export function useDeleteRun(brandId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteRun,
    onSuccess: (_, runId) => {
      // Drop it from the cached list first, so nothing derives the deleted run as "open" and refetches it.
      if (brandId) qc.setQueryData<RunSummary[]>(keys.runs(brandId), (list) => list?.filter((r) => r.id !== runId));
      qc.removeQueries({ queryKey: keys.run(runId) });
      if (brandId) qc.invalidateQueries({ queryKey: keys.runs(brandId) });
    },
  });
}
