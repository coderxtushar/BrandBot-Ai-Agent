import { RequireAuth } from "@/components/auth/require-auth";
import { SiteFooter } from "@/components/site-footer";

export default function StudioLayout({ children }: LayoutProps<"/studio">) {
  return (
    <RequireAuth>
      <div className="flex min-h-dvh flex-col">
        {children}
        <SiteFooter />
      </div>
    </RequireAuth>
  );
}
