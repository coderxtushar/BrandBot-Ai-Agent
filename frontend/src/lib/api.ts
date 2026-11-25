import type {
  Brand,
  BrandInput,
  BrandProfile,
  Content,
  Draft,
  DraftImage,
  DraftStatus,
  DraftVersion,
  ImageStyle,
  PlanDecision,
  ProgressEvent,
  RewritePreset,
  RunDetail,
  RunSettings,
  RunSummary,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

/** Absolute URL for a path the API returns (e.g. an image's /media/... url). */
export const apiUrl = (path: string) => `${API_URL}${path}`;

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      // Pydantic validation errors -> "field.path: message"
      return body.detail
        .map((e: { loc?: (string | number)[]; msg: string }) =>
          `${(e.loc ?? []).filter((x) => x !== "body").join(".")}: ${e.msg}`.replace(/^: /, ""),
        )
        .join("; ");
    }
  } catch {
    /* not JSON */
  }
  return `Request failed (${res.status})`;
}

async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      method: init.method ?? "GET",
      headers: init.body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the Brand Bot API. Start the backend and try again.", 0);
  }
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  return (res.status === 204 ? null : await res.json()) as T;
}

export const api = {
  listBrands: () => request<Brand[]>("/brands"),
  createBrand: (name: string, input: BrandInput) => request<Brand>("/brands", { method: "POST", body: { name, input } }),
  updateBrand: (id: string, patch: { name?: string; input?: BrandInput }) =>
    request<Brand>(`/brands/${id}`, { method: "PATCH", body: patch }),
  deleteBrand: (id: string) => request<null>(`/brands/${id}`, { method: "DELETE" }),
  saveProfile: (id: string, profile: BrandProfile) =>
    request<Brand>(`/brands/${id}/profile`, { method: "PUT", body: profile }),

  listRuns: (brandId: string, limit = 40) => request<RunSummary[]>(`/brands/${brandId}/runs?limit=${limit}`),
  getRun: (id: string) => request<RunDetail>(`/runs/${id}`),
  deleteRun: (id: string) => request<null>(`/runs/${id}`, { method: "DELETE" }),
  cancelRun: (id: string) => request<RunDetail>(`/runs/${id}/cancel`, { method: "POST" }),

  updateDraft: (id: string, patch: { content?: Content; status?: DraftStatus }) =>
    request<Draft>(`/drafts/${id}`, { method: "PATCH", body: patch }),
  rewriteDraft: (id: string, body: { preset?: RewritePreset; instruction?: string; fresh?: boolean }) =>
    request<Draft>(`/drafts/${id}/rewrite`, { method: "POST", body }),
  listVersions: (id: string) => request<DraftVersion[]>(`/drafts/${id}/versions`),
  restoreVersion: (id: string, versionId: string) =>
    request<Draft>(`/drafts/${id}/versions/${versionId}/restore`, { method: "POST" }),

  generateImage: (draftId: string, body: { idea?: string; style?: ImageStyle | null }) =>
    request<DraftImage>(`/drafts/${draftId}/images`, { method: "POST", body }),
  deleteImage: (id: string) => request<null>(`/images/${id}`, { method: "DELETE" }),
};

export type StreamOutcome = { type: "result" | "awaiting"; run: RunDetail };

interface StreamHandlers {
  onProgress?: (event: ProgressEvent) => void;
  onRun?: (runId: string) => void;
  signal?: AbortSignal;
}

/** POST and read Server-Sent Events (EventSource can't POST, so the stream is parsed by hand). */
async function streamSSE(path: string, payload: unknown, { onProgress, onRun, signal }: StreamHandlers): Promise<StreamOutcome> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Can't reach the Brand Bot API. Start the backend and try again.", 0);
  }
  if (!res.ok || !res.body) throw new ApiError(await errorMessage(res), res.status);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (!data.length) continue;
      const parsed = JSON.parse(data.join("\n"));
      if (event === "progress") onProgress?.(parsed);
      else if (event === "run") onRun?.(parsed.run_id);
      else if (event === "result") return { type: "result", run: parsed };
      else if (event === "awaiting") return { type: "awaiting", run: parsed };
      else if (event === "error") throw new ApiError(parsed.detail || "The run failed.", 500);
    }
  }
  throw new ApiError("The connection closed before the run finished.", 0);
}

export const streamBrandRun = (brandId: string, body: RunSettings & { regenerate_profile: boolean }, h: StreamHandlers) =>
  streamSSE(`/brands/${brandId}/runs/stream`, body, h);

export const streamResume = (runId: string, decision: PlanDecision, h: StreamHandlers) =>
  streamSSE(`/runs/${runId}/resume/stream`, decision, h);
