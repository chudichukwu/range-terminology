import Link from "next/link";
import { Button } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--color-bg-base)] p-6">
      <div className="rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-8 py-10 text-center">
        <div className="mono text-[11px] uppercase tracking-wide text-[var(--color-purple-accent)]">404</div>
        <h1 className="mt-2 text-[18px] font-semibold text-[var(--color-text-primary)]">Page not found</h1>
        <p className="mt-2 text-[13px] text-[var(--color-text-secondary)]">The page you’re looking for doesn’t exist.</p>
        <div className="mt-6 flex justify-center">
          <Link href="/">
            <Button variant="primary">Go to Dashboard</Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
