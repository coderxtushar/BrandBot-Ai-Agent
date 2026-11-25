"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useMe } from "@/hooks/use-studio-data";

/** Studio pages need a signed-in user; others are sent to sign in and brought back afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const signedOut = me.isSuccess && me.data === null;

  useEffect(() => {
    if (signedOut) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [signedOut, router, pathname]);

  if (me.isError)
    return (
      <div className="grid min-h-dvh place-items-center p-6 text-center">
        <div className="max-w-sm">
          <p className="font-display text-4xl">Can&apos;t reach the Brand Bot API.</p>
          <p className="mt-3 text-muted-foreground">Start the backend (uvicorn backend.main:app) and reload this page.</p>
        </div>
      </div>
    );
  if (!me.data) return <div className="min-h-dvh" aria-busy="true" />;
  return <>{children}</>;
}
