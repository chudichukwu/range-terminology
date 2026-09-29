"use client";

import { useEffect, useRef } from "react";

/** A decorative halo; the native cursor still handles precise pointing. */
export function CursorGlow() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const glow = ref.current;
    if (!glow) return;
    const enabled = window.matchMedia("(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)");
    let frame = 0;
    let x = 0;
    let y = 0;
    const hide = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      glow.style.opacity = "0";
    };
    const move = (event: PointerEvent) => {
      if (!enabled.matches || event.pointerType !== "mouse") { hide(); return; }
      x = event.clientX;
      y = event.clientY;
      if (!frame) frame = requestAnimationFrame(() => {
        glow.style.transform = `translate3d(${x - 90}px, ${y - 90}px, 0)`;
        glow.style.opacity = "1";
        frame = 0;
      });
    };
    const leave = (event: PointerEvent) => { if (!event.relatedTarget) hide(); };
    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerout", leave);
    window.addEventListener("blur", hide);
    window.addEventListener("keydown", hide);
    document.addEventListener("visibilitychange", hide);
    enabled.addEventListener("change", hide);
    return () => {
      hide();
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerout", leave);
      window.removeEventListener("blur", hide);
      window.removeEventListener("keydown", hide);
      document.removeEventListener("visibilitychange", hide);
      enabled.removeEventListener("change", hide);
    };
  }, []);
  return <div ref={ref} className="cursor-glow" aria-hidden="true" />;
}
