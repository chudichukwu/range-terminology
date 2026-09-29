"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { api, ApiError } from "@/lib/api/client";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; requestId: string; code: string } | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || password.length < 8) {
      setError({ message: "Enter your email and a password of 8–200 characters", requestId: "", code: "validation_error" });
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.register({ email: email.trim(), password });
      localStorage.setItem("rt.accessToken", data.access_token);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) setError({ message: err.message, requestId: err.requestId, code: err.code });
      else setError({ message: String(err), requestId: "", code: "unknown" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="text-center">
        <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-sm text-[12px] font-bold text-white" style={{ background: "var(--color-purple-accent)", color: "#061020" }}>
          G
        </div>
        <h1 className="mt-3 text-[18px] font-semibold tracking-tight text-[var(--color-text-primary)]">Create account</h1>
        <p className="mono mt-1 text-[11px] tracking-wide text-[var(--color-text-tertiary)]">Build your trading workspace</p>
      </div>

      <div className="rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] p-5 shadow-md">
        <div className="mb-4 flex items-center justify-between">
          <span className="text-sm text-[var(--color-text-secondary)]">Grandblue</span>
          <Link href="/login" className="text-[12px] text-[var(--color-purple-accent)] hover:underline">
            Sign in →
          </Link>
        </div>

        <form onSubmit={onSubmit} className="space-y-3" aria-label="Register form">
          <div>
            <label htmlFor="reg-email" className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">
              Email
            </label>
            <input
              id="reg-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-3 py-2 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-disabled)] focus:border-[var(--color-border-strong)] focus:outline-none focus:ring-2 focus:ring-[var(--color-border-focus)]"
            />
          </div>
          <div>
            <label htmlFor="reg-password" className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">
              Password
            </label>
            <input
              id="reg-password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min 8 characters"
              className="w-full rounded-sm border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-2)] px-3 py-2 text-[13px] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-disabled)] focus:border-[var(--color-border-strong)] focus:outline-none focus:ring-2 focus:ring-[var(--color-border-focus)]"
            />
          </div>
          {error && (
            <div role="alert" className="rounded-sm border border-amber-500/20 bg-[var(--color-danger-bg)] px-3 py-2">
              <div className="text-[12px] font-medium text-[var(--color-danger)]">{error.code}</div>
              <div className="text-[12px] leading-relaxed text-[var(--color-text-secondary)]">{error.message}</div>
              {error.requestId && <div className="mono mt-1 text-[11px] text-[var(--color-text-tertiary)]">Request ID: {error.requestId}</div>}
            </div>
          )}
          <Button variant="primary" className="w-full" type="submit" disabled={loading}>
            {loading ? "Creating…" : "Create Account"}
          </Button>

        </form>
      </div>

      <p className="text-center text-xs text-[var(--color-text-tertiary)]">Scan markets, track setups and test your playbook.</p>
      <div className="text-center text-[11px] text-[var(--color-text-tertiary)]">
        <Link href="/" className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]">
          Back to app →
        </Link>
      </div>
    </div>
  );
}
