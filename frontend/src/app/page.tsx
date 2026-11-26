import Link from "next/link";
import { BrandMark } from "@/components/brand-mark";
import { PressHero } from "@/components/landing/press-hero";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { SiteFooter } from "@/components/site-footer";
import { PLATFORMS } from "@/lib/platforms";

const STEPS = [
  {
    title: "Research",
    body: "Brand Bot picks a timely angle from your content pillars and searches the web for facts to back it up.",
  },
  {
    title: "Write",
    body: "Each platform gets its own native format, written in your voice from your past posts.",
  },
  {
    title: "Review",
    body: "An editor agent checks every draft against platform rules and your brand, and sends weak ones back.",
  },
  {
    title: "Polish",
    body: "Approve, edit, ask for a rewrite, or generate an on-brand image. Every change is kept as a version.",
  },
];

const FORMAT_NOTES: Record<string, string> = {
  linkedin: "A hook that survives the “see more” fold, short paragraphs, one question to start the comments.",
  x: "A thread where every tweet stands alone and fits in 280 characters.",
  threads: "Casual and conversational, closer to talking than publishing.",
  instagram: "A carousel that teaches one idea slide by slide, with a caption and cover image.",
  medium: "A 1,000-word article with real sources linked inline.",
  youtube_shorts: "A 45-second script with a two-second hook, beats and on-screen text.",
};

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <BrandMark />
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <Button asChild variant="ghost">
            <Link href="/login">Sign in</Link>
          </Button>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="mx-auto grid w-full max-w-6xl items-center gap-10 px-4 pt-8 pb-16 sm:px-6 lg:grid-cols-[1fr_1.05fr] lg:pt-16 lg:pb-24">
          <div className="max-w-xl">
            <h1 className="font-display text-[clamp(3.4rem,9vw,6.5rem)] [text-shadow:0.035em_0.03em_0_var(--riso-pink)]">
              One idea, written six ways.
            </h1>
            <p className="mt-6 max-w-[34rem] text-lg leading-relaxed text-muted-foreground">
              Tell Brand Bot who you are once. It researches a timely angle and writes a LinkedIn post, an X thread,
              a Threads conversation, an Instagram carousel, a Medium article and a Shorts script, each in your voice.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button asChild size="lg" className="shadow-misprint h-12 rounded-full px-6 text-base">
                <Link href="/signup">Start writing</Link>
              </Button>
              <span className="text-sm text-muted-foreground">Write it here, then publish or schedule it to your accounts.</span>
            </div>
          </div>
          <PressHero />
        </section>

        {/* The process is a real sequence, so it's numbered. */}
        <section className="border-y border-border bg-card/60">
          <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6">
            <h2 className="font-title text-3xl sm:text-4xl">What happens to your idea</h2>
            <ol className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((s, i) => (
                <li key={s.title} className="relative">
                  <span aria-hidden className="font-display text-5xl text-riso-blue">
                    {i + 1}
                  </span>
                  <h3 className="mt-3 font-title text-xl">{s.title}</h3>
                  <p className="mt-2 leading-relaxed text-muted-foreground">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Formats */}
        <section className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6">
          <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <h2 className="font-title text-3xl sm:text-4xl">Six formats, not six copies</h2>
              <p className="mt-4 max-w-md leading-relaxed text-muted-foreground">
                Pasting the same text everywhere reads like it. Each platform gets the structure its readers expect,
                checked against its limits before you see it.
              </p>
            </div>
            <dl className="divide-y divide-border border-y border-border">
              {PLATFORMS.map((p) => (
                <div key={p.id} className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 py-4 sm:grid-cols-[12rem_1fr]">
                  <dt className="flex items-center gap-2 font-medium">
                    <p.icon className="size-4 text-riso-blue" aria-hidden />
                    {p.label}
                    <span className="text-sm font-normal text-muted-foreground">{p.format}</span>
                  </dt>
                  <dd className="col-span-2 text-muted-foreground sm:col-span-1">{FORMAT_NOTES[p.id]}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className="mx-auto w-full max-w-6xl px-4 pb-20 sm:px-6">
          <div className="relative overflow-hidden rounded-3xl bg-ink px-6 py-12 text-paper sm:px-12">
            <div aria-hidden className="overprint absolute -top-16 -right-10 size-56 rounded-full bg-riso-blue" />
            <div aria-hidden className="overprint absolute -right-24 -bottom-24 size-64 rounded-full bg-riso-pink" />
            <h2 className="relative max-w-lg font-display text-5xl">Your next week of posts starts with one idea.</h2>
            <Button asChild size="lg" variant="secondary" className="relative mt-8 h-12 rounded-full px-6 text-base">
              <Link href="/signup">Make your account</Link>
            </Button>
          </div>
        </section>
      </main>

      <SiteFooter note="Brand Bot runs on LangGraph, Gemini and Tavily." />
    </div>
  );
}
