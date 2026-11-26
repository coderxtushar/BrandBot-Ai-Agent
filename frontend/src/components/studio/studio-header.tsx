"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { BarChart3, CalendarClock, CalendarDays, KeyRound, LogOut, PenLine, Plug } from "lucide-react";
import { BrandMark } from "@/components/brand-mark";
import { PasswordDialog } from "@/components/studio/password-dialog";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useMe } from "@/hooks/use-studio-data";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export const STUDIO_NAV = [
  { href: "/studio", label: "Write", icon: PenLine },
  { href: "/studio/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/studio/scheduled", label: "Scheduled", icon: CalendarClock },
  { href: "/studio/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/studio/connections", label: "Connections", icon: Plug },
] as const;

function UserMenu() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const router = useRouter();
  const [passwordOpen, setPasswordOpen] = useState(false);
  if (!me) return null;
  const initials = me.name.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();

  const signOut = async () => {
    await api.logout().catch(() => {});
    qc.clear();
    router.replace("/login");
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="rounded-full" aria-label="Account menu">
            <span className="grid size-8 place-items-center rounded-full bg-riso-sun text-xs font-semibold text-[#1d2340]">{initials || "?"}</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-60">
          <DropdownMenuLabel className="font-normal">
            <p className="text-sm font-medium">{me.name}</p>
            <p className="truncate text-xs text-muted-foreground">{me.email}</p>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {STUDIO_NAV.map((n) => (
            <DropdownMenuItem key={n.href} asChild className="md:hidden">
              <Link href={n.href}>
                <n.icon className="size-4" /> {n.label}
              </Link>
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator className="md:hidden" />
          <DropdownMenuItem onSelect={() => setPasswordOpen(true)}>
            <KeyRound className="size-4" /> Change password
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={signOut}>
            <LogOut className="size-4" /> Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <PasswordDialog open={passwordOpen} onOpenChange={setPasswordOpen} />
    </>
  );
}

export function StudioHeader({ children }: { children?: ReactNode }) {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur">
      <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-6">
          <BrandMark />
          <nav aria-label="Studio" className="hidden items-center gap-1 md:flex">
            {STUDIO_NAV.map((n) => {
              const active = n.href === "/studio" ? pathname === "/studio" : pathname.startsWith(n.href);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  aria-current={active ? "page" : undefined}
                  className={cn("relative rounded-md px-3 py-1.5 text-sm transition-colors", active ? "text-foreground" : "text-muted-foreground hover:text-foreground")}
                >
                  {active && <motion.span layoutId="studio-nav" className="absolute inset-0 rounded-md bg-accent" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
                  <span className="relative">{n.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-1.5">
          {children}
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
