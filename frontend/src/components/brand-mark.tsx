import Link from "next/link";
import { cn } from "@/lib/utils";

/** Wordmark: two overprinted ink dots and the name in condensed display type. */
export function BrandMark({ className, href = "/" }: { className?: string; href?: string }) {
  return (
    <Link href={href} className={cn("group flex items-center gap-2 rounded-md", className)} aria-label="Brand Bot home">
      <span aria-hidden className="relative block size-6">
        <span className="overprint absolute inset-y-0 left-0 size-4 rounded-full bg-riso-blue transition-transform duration-300 ease-press group-hover:-translate-x-0.5" />
        <span className="overprint absolute right-0 bottom-0 size-4 rounded-full bg-riso-pink transition-transform duration-300 ease-press group-hover:translate-x-0.5" />
      </span>
      <span className="font-display text-xl leading-none">Brand Bot</span>
    </Link>
  );
}
