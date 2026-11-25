"use client";

import { useState } from "react";
import { motion, useReducedMotion, type Variants } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { PLATFORMS } from "@/lib/platforms";
import type { PlatformId } from "@/lib/types";

const IDEA = "Most ML projects fail at the framing, not the model.";

/* Where each proof lands around the idea slip (percent of the stage), and its resting tilt. */
const LAYOUT: Record<PlatformId, { x: number; y: number; r: number; w: string }> = {
  linkedin: { x: 3, y: 4, r: -5, w: "w-[34%]" },
  x: { x: 63, y: 0, r: 4, w: "w-[33%]" },
  threads: { x: 75, y: 45, r: 7, w: "w-[24%]" },
  instagram: { x: 0, y: 53, r: 6, w: "w-[26%]" },
  medium: { x: 30, y: 69, r: -2, w: "w-[38%]" },
  youtube_shorts: { x: 75, y: 72, r: -6, w: "w-[18%]" },
};

const slip: Variants = {
  // x: -50% centres the slip; Framer Motion owns `transform`, so it can't come from a CSS class.
  hidden: { opacity: 0, x: "-50%", y: -60, rotate: -8, scale: 0.9 },
  shown: { opacity: 1, x: "-50%", y: 0, rotate: -1.5, scale: 1, transition: { type: "spring", stiffness: 140, damping: 16 } },
};

const proof: Variants = {
  hidden: { opacity: 0, left: "36%", top: "40%", rotate: 0, scale: 0.4 },
  shown: (id: PlatformId) => ({
    opacity: 1,
    left: `${LAYOUT[id].x}%`,
    top: `${LAYOUT[id].y}%`,
    rotate: LAYOUT[id].r,
    scale: 1,
    transition: { type: "spring", stiffness: 90, damping: 15, mass: 0.9 },
  }),
};

function Lines({ n, last = "60%" }: { n: number; last?: string }) {
  return (
    <div className="space-y-1">
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="h-1.5 rounded-full bg-current opacity-20" style={{ width: i === n - 1 ? last : "100%" }} />
      ))}
    </div>
  );
}

function ProofBody({ id }: { id: PlatformId }) {
  switch (id) {
    case "linkedin":
      return (
        <div className="space-y-2">
          <p className="text-[11px] leading-tight font-semibold">80% of ML projects never ship. Here&apos;s why.</p>
          <Lines n={3} />
        </div>
      );
    case "x":
      return (
        <div className="space-y-1.5">
          {["The model is rarely the problem.", "It's the question you asked it.", "Frame first."].map((t, i) => (
            <p key={i} className="rounded-md bg-current/5 px-1.5 py-1 text-[10px] leading-tight">
              <span className="opacity-50">{i + 1}/3 </span>
              {t}
            </p>
          ))}
        </div>
      );
    case "threads":
      return (
        <div className="space-y-1.5 text-[10px] leading-tight">
          <p>Hot take: your model isn&apos;t the problem.</p>
          <p className="hidden opacity-60 sm:block">What did your last project get wrong?</p>
        </div>
      );
    case "instagram":
      return (
        <div className="relative aspect-[4/5] overflow-hidden rounded-md bg-riso-blue">
          <div className="overprint absolute -right-4 -bottom-4 size-16 rounded-full bg-riso-pink" />
          <div className="overprint absolute top-3 -left-3 size-10 rounded-full bg-riso-sun" />
          <p className="absolute bottom-2 left-2 font-display text-sm text-white">Frame first.</p>
        </div>
      );
    case "medium":
      return (
        <div className="space-y-1.5">
          <p className="font-title text-[13px] leading-tight">The question is the hard part</p>
          <Lines n={4} last="40%" />
        </div>
      );
    case "youtube_shorts":
      return (
        <div className="relative aspect-[9/16] overflow-hidden rounded-md bg-ink text-paper">
          <div className="absolute top-1/4 -left-2 size-12 rounded-full bg-riso-pink opacity-90" />
          <p className="absolute right-1.5 bottom-2 left-1.5 text-[9px] leading-tight font-semibold">Your model is fine.</p>
        </div>
      );
  }
}

/**
 * The hero's one orchestrated moment: an idea slip drops onto the press,
 * then six platform proofs fan out from it.
 */
export function PressHero() {
  const [take, setTake] = useState(0);
  const reduce = useReducedMotion();

  return (
    <div className="relative">
      <motion.div
        key={take}
        className="relative mx-auto aspect-[4/5] w-full max-w-[560px] sm:aspect-[6/5]"
        initial={reduce ? "shown" : "hidden"}
        animate="shown"
        transition={{ staggerChildren: 0.09, delayChildren: 0.55 }}
        aria-label="One idea becoming a LinkedIn post, an X thread, a Threads conversation, an Instagram carousel, a Medium article and a YouTube Shorts script"
        role="img"
      >
        {/* ink blots, overprinted */}
        <motion.div
          aria-hidden
          className="overprint absolute top-[18%] left-[22%] size-[46%] rounded-full bg-riso-sun"
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
        />
        <motion.div
          aria-hidden
          className="overprint absolute top-[30%] left-[38%] size-[38%] rounded-full bg-riso-pink/90"
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 1.1, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
        />
        <div aria-hidden className="halftone absolute inset-[12%] rounded-full text-riso-blue opacity-25 [mask-image:radial-gradient(closest-side,black,transparent)]" />

        {PLATFORMS.map((p) => (
          <motion.div
            key={p.id}
            custom={p.id}
            variants={proof}
            className={`absolute ${LAYOUT[p.id].w} rounded-xl border border-ink/15 bg-card p-2.5 text-ink shadow-[0_1px_0_rgb(29_35_64/0.08)] sm:p-3`}
          >
            <div className="mb-2 flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <p.icon className="size-3" aria-hidden />
              <span>{p.short}</span>
            </div>
            <ProofBody id={p.id} />
          </motion.div>
        ))}

        {/* the idea slip sits on top until the proofs land */}
        <motion.div
          variants={slip}
          className="absolute top-[36%] left-[46%] z-10 w-[50%] rounded-lg bg-ink p-3 text-paper sm:p-4"
        >
          <p className="text-[10px] text-paper/60">Today&apos;s idea</p>
          <p className="mt-1 font-title text-sm leading-snug sm:text-base">{IDEA}</p>
        </motion.div>
      </motion.div>

      <button
        type="button"
        onClick={() => setTake((t) => t + 1)}
        className="mx-auto mt-2 flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted-foreground transition hover:bg-accent hover:text-foreground"
      >
        <RotateCcw className="size-3" aria-hidden /> Print again
      </button>
    </div>
  );
}
