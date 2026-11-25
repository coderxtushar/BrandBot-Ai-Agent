import { RequireAuth } from "@/components/auth/require-auth";

export default function StudioLayout({ children }: LayoutProps<"/studio">) {
  return <RequireAuth>{children}</RequireAuth>;
}
