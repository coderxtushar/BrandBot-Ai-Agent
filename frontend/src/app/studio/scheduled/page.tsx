import type { Metadata } from "next";
import { ScheduledView } from "@/components/studio/scheduled-view";

export const metadata: Metadata = { title: "Scheduled" };

export default function ScheduledPage() {
  return <ScheduledView />;
}
