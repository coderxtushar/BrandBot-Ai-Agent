import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthForm } from "@/components/auth/auth-form";

export const metadata: Metadata = { title: "Make an account" };

export default function SignupPage() {
  return (
    <Suspense fallback={<div className="min-h-dvh" />}>
      <AuthForm mode="signup" />
    </Suspense>
  );
}
