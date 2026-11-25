"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { keys } from "@/hooks/use-studio-data";
import { api } from "@/lib/api";
import { AuthShell, safeNext } from "./auth-shell";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const signup = mode === "signup";
  const next = safeNext(params.get("next"));
  const other = signup ? "/login" : "/signup";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = signup ? await api.register({ name, email, password }) : await api.login({ email, password });
      qc.setQueryData(keys.me, user);
      router.replace(next);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <AuthShell
      title={signup ? "Make an account" : "Welcome back"}
      subtitle={signup ? "Your brands, runs and connected accounts stay private to you." : "Sign in to your studio."}
      footer={
        <>
          {signup ? "Already have an account? " : "New to Brand Bot? "}
          <Link href={`${other}${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-medium text-primary underline-offset-2 hover:underline">
            {signup ? "Sign in" : "Make an account"}
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        {signup && (
          <div className="space-y-1.5">
            <Label htmlFor="name">Your name</Label>
            <Input id="name" autoComplete="name" required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete={signup ? "new-password" : "current-password"}
            required
            minLength={signup ? 10 : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-describedby={signup ? "password-hint" : undefined}
          />
          {signup && <p id="password-hint" className="text-xs text-muted-foreground">At least 10 characters.</p>}
        </div>
        {error && (
          <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" disabled={busy} className="shadow-misprint h-12 w-full rounded-full text-base">
          {busy ? (signup ? "Making your account…" : "Signing in…") : signup ? "Make my account" : "Sign in"}
        </Button>
      </form>
    </AuthShell>
  );
}
