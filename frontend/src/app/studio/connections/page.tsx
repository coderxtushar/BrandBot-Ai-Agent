import type { Metadata } from "next";
import { Suspense } from "react";
import { ConnectionsView } from "@/components/studio/connections-view";

export const metadata: Metadata = { title: "Connections" };

export default function ConnectionsPage() {
  return (
    <Suspense fallback={<div className="min-h-dvh" />}>
      <ConnectionsView />
    </Suspense>
  );
}
