"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PaperReadOnlyBanner } from "@/components/state/StatePrimitives";

export default function RegisterPage() {
  return (
    <div className="space-y-4">
      <div className="text-center">
        <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-sm text-[12px] font-bold text-white" style={{ background: "linear-gradient(135deg,#7c5cff 0%,#5b3bd6 100%)" }}>
          R
        </div>
        <h1 className="mt-3 text-[18px] font-semibold tracking-tight text-[var(--color-text-primary)]">Create account</h1>
        <p className="mono mt-1 text-[11px] tracking-wide text-[var(--color-text-tertiary)]">First account becomes workspace OWNER</p>
      </div>

      <div className="rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-5 shadow-md">
        <div className="mb-4 flex items-center justify-between">
          <Badge variant="purple">Auth shell</Badge>
          <Link href="/login" className="text-[12px] text-[var(--color-purple-accent)] hover:underline">
            Sign in →
          </Link>
        </div>

        <form onSubmit={(e) => e.preventDefault()} className="space-y-3" aria-label="Register form">
          <div>
            <label htmlFor="reg-email" className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">
              Email
            </label>
            <input id="reg-email" type="email" placeholder="you@example.com" className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-3 py-2 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-disabled)] focus:border-[var(--color-border-strong)] focus:outline-none focus:ring-2 focus:ring-[var(--color-border-focus)]" />
          </div>
          <div>
            <label htmlFor="reg-password" className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">
              Password
            </label>
            <input id="reg-password" type="password" placeholder="Min 8 characters" className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-3 py-2 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-disabled)] focus:border-[var(--color-border-strong)] focus:outline-none focus:ring-2 focus:ring-[var(--color-border-focus)]" />
          </div>
          <Button variant="primary" className="w-full" type="submit">
            Create Account
          </Button>
          <p className="text-center text-[11px] text-[var(--color-text-tertiary)]">
            Foundation placeholder — connects via <span className="mono text-[var(--color-text-secondary)]">POST /auth/register</span>; no call yet.
          </p>
        </form>
      </div>

      <PaperReadOnlyBanner compact />
      <div className="text-center text-[11px] text-[var(--color-text-tertiary)]">
        <Link href="/" className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]">
          Back to app →
        </Link>
      </div>
    </div>
  );
}
