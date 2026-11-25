import type { PlatformId, ProgressEvent } from "./types";

export type StepStatus = "waiting" | "running" | "done" | "reused";

export interface PlatformProgress {
  stage: "queued" | "writing" | "reviewing" | "revising" | "done";
  attempt: number;
  approved?: boolean;
}

export interface Progress {
  profile: StepStatus;
  planning: StepStatus;
  research: StepStatus;
  angle?: string;
  queries?: string[];
  sourceCount?: number;
  /** Platforms whose past best posts are guiding this run. */
  learnedFrom?: PlatformId[];
  platforms: Partial<Record<PlatformId, PlatformProgress>>;
}

export type ProgressAction =
  | { type: "reset"; platforms: PlatformId[]; resumed?: boolean }
  | { type: "event"; event: ProgressEvent };

export const emptyProgress: Progress = { profile: "waiting", planning: "waiting", research: "waiting", platforms: {} };

export function progressReducer(state: Progress, action: ProgressAction): Progress {
  if (action.type === "reset") {
    const done = action.resumed ? ("done" as const) : ("waiting" as const);
    return {
      profile: done,
      planning: done,
      research: done,
      platforms: Object.fromEntries(action.platforms.map((p) => [p, { stage: "queued", attempt: 0 }])),
    };
  }
  const ev = action.event;
  if (ev.platform) {
    const prev = state.platforms[ev.platform] ?? { stage: "queued", attempt: 0 };
    return {
      ...state,
      platforms: {
        ...state.platforms,
        [ev.platform]: {
          stage: ev.stage as PlatformProgress["stage"],
          attempt: ev.attempt ?? prev.attempt,
          approved: ev.approved ?? prev.approved,
        },
      },
    };
  }
  const status: StepStatus = ev.status === "reused" ? "reused" : ev.status === "done" ? "done" : "running";
  switch (ev.stage) {
    case "profile":
      return { ...state, profile: status };
    case "planning":
      return { ...state, planning: status, angle: ev.angle ?? state.angle };
    case "learning":
      return { ...state, learnedFrom: (ev as ProgressEvent & { platforms?: PlatformId[] }).platforms ?? [] };
    case "research":
      return { ...state, research: status, queries: ev.queries ?? state.queries, sourceCount: ev.count ?? state.sourceCount };
    default:
      return state;
  }
}
