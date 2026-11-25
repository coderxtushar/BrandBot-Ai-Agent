import {
  AtSign,
  Briefcase,
  Clapperboard,
  GalleryHorizontalEnd,
  MessagesSquare,
  Newspaper,
  type LucideIcon,
} from "lucide-react";
import type { PlatformId, RewritePreset, ImageStyle } from "./types";

export interface PlatformMeta {
  id: PlatformId;
  label: string;
  short: string;
  /** What gets written for this platform, in plain words. */
  format: string;
  icon: LucideIcon;
  /** Aspect ratio of generated images (matches backend platform specs). */
  imageAspect: string;
}

export const PLATFORMS: PlatformMeta[] = [
  { id: "linkedin", label: "LinkedIn", short: "LinkedIn", format: "Post", icon: Briefcase, imageAspect: "1:1" },
  { id: "x", label: "X", short: "X", format: "Thread", icon: MessagesSquare, imageAspect: "16:9" },
  { id: "threads", label: "Threads", short: "Threads", format: "Conversation", icon: AtSign, imageAspect: "4:5" },
  { id: "instagram", label: "Instagram", short: "Instagram", format: "Carousel", icon: GalleryHorizontalEnd, imageAspect: "4:5" },
  { id: "medium", label: "Medium", short: "Medium", format: "Article", icon: Newspaper, imageAspect: "16:9" },
  { id: "youtube_shorts", label: "YouTube Shorts", short: "Shorts", format: "Video script", icon: Clapperboard, imageAspect: "9:16" },
];

export const platform = (id: PlatformId) => PLATFORMS.find((p) => p.id === id) ?? PLATFORMS[0];

export const REWRITE_PRESETS: { id: RewritePreset; label: string }[] = [
  { id: "shorter", label: "Shorter" },
  { id: "punchier", label: "Punchier" },
  { id: "data", label: "More data" },
  { id: "personal", label: "More personal" },
  { id: "simpler", label: "Simpler" },
];

export const IMAGE_STYLES: { id: ImageStyle; label: string }[] = [
  { id: "photo", label: "Photo" },
  { id: "illustration", label: "Illustration" },
  { id: "3d", label: "3D" },
  { id: "minimal", label: "Minimal" },
];

/** CSS aspect-ratio value from "4:5". */
export const aspect = (ratio: string) => ratio.replace(":", " / ");
