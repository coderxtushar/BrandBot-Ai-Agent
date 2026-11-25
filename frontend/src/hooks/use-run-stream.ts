"use client";

import { useCallback, useReducer, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { streamBrandRun, streamResume, type StreamOutcome } from "@/lib/api";
import { emptyProgress, progressReducer } from "@/lib/progress";
import type { PlanDecision, PlatformId, RunDetail, RunSettings } from "@/lib/types";
import { keys } from "./use-studio-data";

type Phase = "idle" | "running" | "error";

/**
 * Drives a streaming run (new or resumed) to its next stop: finished, paused for review, or failed.
 * Results land in the TanStack Query cache, so every view of that run updates.
 */
export function useRunStream(onSettled: (run: RunDetail) => void) {
  const qc = useQueryClient();
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [progress, dispatch] = useReducer(progressReducer, emptyProgress);
  const abort = useRef<AbortController | null>(null);

  const drive = useCallback(
    async (brandId: string, platforms: PlatformId[], resumed: boolean, start: (signal: AbortSignal) => Promise<StreamOutcome>) => {
      const controller = new AbortController();
      abort.current = controller;
      setPhase("running");
      setError(null);
      dispatch({ type: "reset", platforms, resumed });
      try {
        const outcome = await start(controller.signal);
        qc.setQueryData(keys.run(outcome.run.id), outcome.run);
        setPhase("idle");
        onSettled(outcome.run);
      } catch (err) {
        if ((err as Error).name === "AbortError") setPhase("idle");
        else {
          setError((err as Error).message);
          setPhase("error");
        }
      } finally {
        qc.invalidateQueries({ queryKey: keys.runs(brandId) });
        qc.invalidateQueries({ queryKey: keys.brands }); // a run can create or refresh the profile
      }
    },
    [qc, onSettled],
  );

  const start = useCallback(
    (brandId: string, settings: RunSettings, regenerateProfile: boolean) =>
      drive(brandId, settings.platforms, false, (signal) =>
        streamBrandRun(
          brandId,
          { ...settings, regenerate_profile: regenerateProfile },
          { signal, onProgress: (event) => dispatch({ type: "event", event }) },
        ),
      ),
    [drive],
  );

  const resume = useCallback(
    (run: RunDetail, decision: PlanDecision) =>
      drive(run.brand_id, run.platforms, true, (signal) =>
        streamResume(run.id, decision, { signal, onProgress: (event) => dispatch({ type: "event", event }) }),
      ),
    [drive],
  );

  const stop = useCallback(() => abort.current?.abort(), []);
  const dismissError = useCallback(() => {
    setError(null);
    setPhase("idle");
  }, []);

  return { phase, error, progress, start, resume, stop, dismissError, running: phase === "running" };
}
