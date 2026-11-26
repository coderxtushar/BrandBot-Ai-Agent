"use client";

import Markdown from "react-markdown";
import { motion } from "framer-motion";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api";
import { aspect } from "@/lib/platforms";
import type { Content, DraftImage, PlatformId } from "@/lib/types";
import { cn } from "@/lib/utils";

/* Content shapes per platform (mirror backend/schemas.py) */
interface LinkedInPost { hook: string; body: string; closing_question?: string; hashtags: string[] }
interface XThread { tweets: string[]; hashtags: string[] }
interface ThreadsPost { posts: string[]; topic_tag: string }
interface Slide { headline: string; text: string }
interface InstagramPost { caption: string; hashtags: string[]; slides: Slide[]; image_prompt: string; alt_text: string }
interface MediumArticle { title: string; subtitle: string; body_markdown: string; tags: string[] }
interface Beat { seconds: string; voiceover: string; on_screen_text: string; visual: string }
interface ShortsScript { title: string; hook: string; beats: Beat[]; cta: string; description: string; hashtags: string[] }

const tags = (list: string[] = []) => list.map((t) => `#${t.replace(/^#/, "").replace(/\s+/g, "")}`).join(" ");

function Counter({ value, max }: { value: number; max: number }) {
  return (
    <span className={cn("text-[11px] tabular-nums", value > max ? "font-semibold text-destructive" : "text-muted-foreground")}>
      {value}/{max}
    </span>
  );
}

function Avatar() {
  return <div aria-hidden className="size-9 shrink-0 rounded-full bg-gradient-to-br from-riso-blue/50 to-riso-pink/50" />;
}

/** A generated image, revealed like a print coming off the press. */
export function PrintedImage({ image, className, rounded = "rounded-xl" }: { image: DraftImage; className?: string; rounded?: string }) {
  return (
    <motion.div
      key={image.id}
      className={cn("relative overflow-hidden bg-muted", rounded, className)}
      style={{ aspectRatio: aspect(image.aspect_ratio) }}
      initial={{ clipPath: "inset(0 0 100% 0)" }}
      animate={{ clipPath: "inset(0 0 0% 0)" }}
      transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- served by the API, sizes vary */}
      <img src={apiUrl(image.url)} alt={image.alt_text} className="size-full object-cover" />
    </motion.div>
  );
}

function LinkedIn({ item, image }: { item: LinkedInPost; image?: DraftImage }) {
  const full = [item.hook, item.body, item.closing_question, tags(item.hashtags)].filter((x) => x?.trim()).join("\n\n");
  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="min-w-0 flex-1 text-[15px] leading-relaxed whitespace-pre-wrap">
        <p className="font-semibold">{item.hook}</p>
        <p className="mt-3">{item.body}</p>
        {item.closing_question?.trim() && <p className="mt-3">{item.closing_question}</p>}
        <p className="mt-3 text-primary">{tags(item.hashtags)}</p>
        {image && <PrintedImage image={image} className="mt-4 max-w-md" />}
        <div className="mt-2 text-right"><Counter value={full.length} max={3000} /></div>
      </div>
    </div>
  );
}

function Thread({ posts, max, image, footer }: { posts: string[]; max: number; image?: DraftImage; footer?: string }) {
  return (
    <ol>
      {posts.map((t, i) => (
        <li key={i} className="flex gap-3">
          <div className="flex flex-col items-center">
            <Avatar />
            {i < posts.length - 1 && <div className="w-px flex-1 bg-border" />}
          </div>
          <div className="min-w-0 flex-1 pb-5">
            <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{t}</p>
            {i === 0 && image && <PrintedImage image={image} className="mt-3 max-w-md" />}
            {i === 0 && footer && <p className="mt-1 text-sm text-muted-foreground">{footer}</p>}
            <div className="mt-1 text-right"><Counter value={t.length} max={max} /></div>
          </div>
        </li>
      ))}
    </ol>
  );
}

function X({ item, image }: { item: XThread; image?: DraftImage }) {
  const n = item.tweets.length;
  const posts = item.tweets.map(
    (t, i) => (i > 0 && n > 1 ? `${i + 1}/${n} ` : "") + t + (i === n - 1 && item.hashtags?.length ? ` ${tags(item.hashtags)}` : ""),
  );
  return <Thread posts={posts} max={280} image={image} />;
}

function Threads({ item, image }: { item: ThreadsPost; image?: DraftImage }) {
  return <Thread posts={item.posts} max={500} image={image} footer={item.topic_tag ? `› ${item.topic_tag}` : undefined} />;
}

function Instagram({ item, image }: { item: InstagramPost; image?: DraftImage }) {
  return (
    <div className="space-y-4">
      <div className="-mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-2" tabIndex={0} aria-label="Carousel slides">
        {item.slides.map((s, i) => (
          <motion.div
            key={i}
            whileHover={{ rotate: i % 2 ? 1.5 : -1.5, y: -3 }}
            className="relative flex aspect-[4/5] w-52 shrink-0 snap-start flex-col justify-between overflow-hidden rounded-xl bg-ink p-4 text-paper"
          >
            {i === 0 && image ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={apiUrl(image.url)} alt={image.alt_text} className="absolute inset-0 size-full object-cover" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent" />
              </>
            ) : (
              <div aria-hidden className={cn("absolute -right-8 -bottom-8 size-28 rounded-full opacity-90", i % 2 ? "bg-riso-blue" : "bg-riso-pink")} />
            )}
            <span className="relative text-[10px] text-white/60">{i + 1}/{item.slides.length}</span>
            <div className="relative text-white">
              <p className="font-title text-lg leading-tight">{s.headline}</p>
              <p className="mt-1.5 text-xs leading-snug text-white/80">{s.text}</p>
            </div>
          </motion.div>
        ))}
      </div>
      <div className="text-[15px] leading-relaxed">
        <p className="whitespace-pre-wrap">{item.caption}</p>
        <p className="mt-2 text-primary">{tags(item.hashtags)}</p>
      </div>
    </div>
  );
}

function downloadMarkdown(item: MediumArticle) {
  const md = `# ${item.title}\n\n_${item.subtitle}_\n\n${item.body_markdown}\n`;
  const url = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
  const a = Object.assign(document.createElement("a"), {
    href: url,
    download: `${item.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 60) || "article"}.md`,
  });
  a.click();
  URL.revokeObjectURL(url);
}

function Medium({ item, image }: { item: MediumArticle; image?: DraftImage }) {
  const words = item.body_markdown.split(/\s+/).filter(Boolean).length;
  return (
    <article className="mx-auto max-w-[68ch]">
      {image && <PrintedImage image={image} className="mb-6" rounded="rounded-lg" />}
      <h3 className="font-display text-4xl">{item.title}</h3>
      <p className="mt-2 text-lg text-muted-foreground">{item.subtitle}</p>
      <div className="mt-3 flex items-center justify-between gap-3 text-sm text-muted-foreground">
        <span>
          {words} words, about {Math.max(1, Math.round(words / 230))} min read
        </span>
        <Button variant="outline" size="sm" onClick={() => downloadMarkdown(item)}>
          <Download className="size-3.5" /> Markdown
        </Button>
      </div>
      <div className="prose-press mt-6 font-serif text-[17px] leading-8">
        <Markdown>{item.body_markdown}</Markdown>
      </div>
      <ul className="mt-6 flex flex-wrap gap-2">
        {item.tags.map((t) => (
          <li key={t} className="rounded-full bg-muted px-3 py-1 text-xs">{t}</li>
        ))}
      </ul>
    </article>
  );
}

function Shorts({ item, image }: { item: ShortsScript; image?: DraftImage }) {
  const words = item.hook.split(/\s+/).length + item.beats.reduce((n, b) => n + b.voiceover.split(/\s+/).length, 0);
  return (
    <div className="grid gap-6 md:grid-cols-[180px_1fr]">
      <div className="relative mx-auto aspect-[9/16] w-44 overflow-hidden rounded-2xl bg-ink text-white md:w-full">
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={apiUrl(image.url)} alt={image.alt_text} className="absolute inset-0 size-full object-cover" />
        ) : (
          <div aria-hidden className="absolute top-1/4 -left-6 size-28 rounded-full bg-riso-pink opacity-90" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/75 to-transparent" />
        <p className="absolute right-3 bottom-4 left-3 font-title text-base leading-tight">{item.title}</p>
      </div>
      <div className="min-w-0 space-y-4 text-sm">
        <p className="text-muted-foreground">
          About {Math.round(words / 2.5)} seconds of voiceover ({words} words)
        </p>
        <div className="rounded-xl bg-riso-sun/25 p-3">
          <p className="text-xs font-medium">Hook, first 2 seconds</p>
          <p className="mt-1 font-title text-lg leading-snug">{item.hook}</p>
        </div>
        <ol className="space-y-3">
          {item.beats.map((b, i) => (
            <li key={i} className="grid grid-cols-[3.5rem_1fr] gap-3">
              <span className="pt-0.5 text-xs tabular-nums text-muted-foreground">{b.seconds}s</span>
              <div>
                <p>{b.voiceover}</p>
                <p className="mt-1 text-xs">
                  <span className="font-medium">On screen:</span> {b.on_screen_text}
                </p>
                <p className="text-xs text-muted-foreground">{b.visual}</p>
              </div>
            </li>
          ))}
        </ol>
        <p>
          <span className="font-medium">Call to action:</span> {item.cta}
        </p>
        <div className="rounded-xl bg-muted p-3 text-xs">
          <p className="font-medium">Description</p>
          <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{item.description}</p>
          <p className="mt-2 text-primary">{tags(item.hashtags)}</p>
        </div>
      </div>
    </div>
  );
}

export function Preview({ platform, item, image }: { platform: PlatformId; item: Content; image?: DraftImage }) {
  switch (platform) {
    case "linkedin":
      return <LinkedIn item={item as unknown as LinkedInPost} image={image} />;
    case "x":
      return <X item={item as unknown as XThread} image={image} />;
    case "threads":
      return <Threads item={item as unknown as ThreadsPost} image={image} />;
    case "instagram":
      return <Instagram item={item as unknown as InstagramPost} image={image} />;
    case "medium":
      return <Medium item={item as unknown as MediumArticle} image={image} />;
    case "youtube_shorts":
      return <Shorts item={item as unknown as ShortsScript} image={image} />;
  }
}
