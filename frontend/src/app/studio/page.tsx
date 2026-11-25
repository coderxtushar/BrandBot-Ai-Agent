import type { Metadata } from "next";
import { Suspense } from "react";
import { Studio } from "@/components/studio/studio";

export const metadata: Metadata = { title: "Studio" };

export default function StudioPage() {
  // Studio reads ?run= from the URL, so it renders in the browser inside a Suspense boundary.
  return (
    <Suspense fallback={<div className="min-h-dvh" />}>
      <Studio />
    </Suspense>
  );
}
