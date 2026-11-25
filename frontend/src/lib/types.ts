// Mirrors backend/schemas.py. Keep in sync when the API changes.

export type PlatformId = "linkedin" | "x" | "threads" | "instagram" | "medium" | "youtube_shorts";
export type RunStatus = "running" | "awaiting_plan" | "completed" | "failed" | "cancelled";
export type DraftStatus = "draft" | "approved" | "rejected";
export type ImageStyle = "photo" | "illustration" | "3d" | "minimal";
export type RewritePreset = "shorter" | "punchier" | "data" | "personal" | "simpler";

export interface BrandInput {
  target_audience: string;
  expertise: string;
  tone_of_voice: string;
  content_pillars: string;
  past_posts: string;
}

export interface BrandProfile {
  positioning: string;
  audience_persona: string;
  voice: { traits: string[]; do: string[]; dont: string[] };
  pillars: string[];
  hashtags: string[];
  visual_style: string;
}

export interface Brand {
  id: string;
  name: string;
  input: BrandInput;
  profile: BrandProfile | null;
  profile_updated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Source {
  title: string;
  url: string;
  snippet: string;
}

export interface ContentPlan {
  angle: string;
  pillar: string;
  queries: { query: string; topic: string; time_range: string | null }[];
}

export interface Review {
  approved: boolean;
  score: number;
  issues: string[];
}

export interface DraftImage {
  id: string;
  draft_id: string;
  url: string;
  prompt: string;
  alt_text: string;
  aspect_ratio: string;
  style: ImageStyle | null;
  model: string;
  created_at: string;
}

export interface DraftRef {
  id: string;
  status: DraftStatus;
  review: Review | null;
  lint: string[];
  images: DraftImage[];
}

/** Platform content is a different shape per platform; the previews know each one. */
export type Content = Record<string, unknown>;

export interface PlatformResult {
  platform: PlatformId;
  items: Content[];
  text: string[];
  review: Review | null;
  attempts: number;
  error: string | null;
  drafts: DraftRef[];
}

export interface RunSummary {
  id: string;
  brand_id: string;
  status: RunStatus;
  platforms: PlatformId[];
  topic: string;
  angle: string | null;
  approved: number;
  created_at: string;
  finished_at: string | null;
}

export interface RunDetail extends RunSummary {
  variants: number;
  error: string | null;
  brand_profile: BrandProfile | null;
  plan: ContentPlan | null;
  sources: Source[];
  results: PlatformResult[];
}

export interface Draft {
  id: string;
  run_id: string;
  platform: PlatformId;
  position: number;
  content: Content;
  text: string;
  status: DraftStatus;
  review: Review | null;
  lint: string[];
  updated_at: string;
}

export interface DraftVersion {
  id: string;
  source: "generated" | "edited" | "rewrite" | "regenerate" | "restored";
  note: string | null;
  text: string;
  created_at: string;
}

export interface PlanDecision {
  angle?: string | null;
  pillar?: string | null;
  source_urls?: string[] | null;
  guidance?: string;
}

export interface RunSettings {
  platforms: PlatformId[];
  topic: string;
  variants: number;
  review_plan: boolean;
}

export type ProgressEvent = {
  stage: string;
  status?: string;
  platform?: PlatformId;
  attempt?: number;
  approved?: boolean;
  angle?: string;
  queries?: string[];
  count?: number;
};
