import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Range Trading Terminal",
  description: "Professional crypto range-trading research workstation — PAPER / READ-ONLY.",
  robots: { index: false, follow: false }
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
      </head>
      <body>
        <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[100] focus:rounded-sm focus:bg-[var(--color-bg-surface-2)] focus:px-3 focus:py-2 focus:text-[var(--color-text-primary)]">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
