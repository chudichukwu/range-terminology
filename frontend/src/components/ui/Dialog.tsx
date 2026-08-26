"use client";

import { useEffect, useRef } from "react";

export function Dialog({
  open,
  onClose,
  title,
  description,
  children
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    // focus trap simple: focus first input
    const el = ref.current?.querySelector<HTMLElement>("input, select, button, textarea");
    el?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button aria-label="Close dialog" className="absolute inset-0 bg-[var(--color-bg-overlay)] backdrop-blur-sm" onClick={onClose} />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative w-full max-w-[480px] rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-bg-surface-1)] shadow-lg"
      >
        <div className="border-b border-[var(--color-border-subtle)] px-4 py-3">
          <h2 className="text-[14px] font-semibold tracking-tight text-[var(--color-text-primary)]">{title}</h2>
          {description && <p className="mt-1 text-[12px] leading-relaxed text-[var(--color-text-secondary)]">{description}</p>}
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
