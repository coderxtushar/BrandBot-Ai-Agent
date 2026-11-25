"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { BrandMark } from "@/components/brand-mark";
import { ThemeToggle } from "@/components/theme-toggle";

/** Split layout for sign in / sign up: the form on paper, an ink sheet beside it. */
export function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_1.1fr]">
      <div className="flex flex-col px-4 py-5 sm:px-10">
        <div className="flex items-center justify-between">
          <BrandMark />
          <ThemeToggle />
        </div>
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
          <h1 className="font-display text-5xl">{title}</h1>
          <p className="mt-3 text-muted-foreground">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <p className="mt-6 text-sm text-muted-foreground">{footer}</p>
        </div>
      </div>

      {/* Always the dark press sheet, in both themes, so the inks read the same. */}
      <div aria-hidden className="relative hidden overflow-hidden bg-[#1d2340] text-[#f2f3f7] lg:block">
        {/* two inks slide into register, once */}
        <motion.div
          className="absolute top-[18%] left-[16%] aspect-square w-[46%] rounded-full bg-[#0078bf] mix-blend-screen"
          initial={{ x: -40, y: -30, opacity: 0 }}
          animate={{ x: 0, y: 0, opacity: 1 }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
        />
        <motion.div
          className="absolute top-[34%] left-[34%] aspect-square w-[46%] rounded-full bg-[#ff48b0] mix-blend-screen"
          initial={{ x: 40, y: 30, opacity: 0 }}
          animate={{ x: 0, y: 0, opacity: 1 }}
          transition={{ duration: 1.1, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
        />
        <div className="halftone absolute inset-0 opacity-[0.07]" />
        <p className="absolute right-12 bottom-12 left-12 font-display text-6xl leading-[0.9]">
          Write once. Show up everywhere.
        </p>
      </div>
    </div>
  );
}

/** Only follow redirects to pages on this site. */
export function safeNext(next: string | null) {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/studio";
}
