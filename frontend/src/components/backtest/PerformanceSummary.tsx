import { Badge } from "@/components/ui/Badge";
import type { BacktestStatistics } from "@/lib/api/types";

function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return "—";
  if (!Number.isFinite(n as number)) return "—";
  return (n as number).toFixed(digits);
}
function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return String(n);
}

export function PerformanceSummary({ stats, initialCapital, finalEquity }: { stats: BacktestStatistics; initialCapital: number; finalEquity: number }) {
  const total = stats.total_trades ?? stats.completed_trades ?? 0;
  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">Performance — backend-provided</h3>
        <Badge variant="neutral">PAPER</Badge>
      </div>
      <div className="grid gap-2 md:grid-cols-4 lg:grid-cols-6">
        <Stat label="Total P&L" value={fmt(stats.total_realized_pnl, 2)} mono tone={stats.total_realized_pnl !== null && (stats.total_realized_pnl as number) >= 0 ? "bull" : "bear"} />
        <Stat label="Trades" value={fmtInt(stats.total_trades)} />
        <Stat label="Completed" value={fmtInt(stats.completed_trades)} />
        <Stat label="Wins" value={fmtInt(stats.wins)} mono tone="bull" />
        <Stat label="Losses" value={fmtInt(stats.losses)} mono tone="bear" />
        <Stat label="Breakevens" value={fmtInt(stats.breakevens)} />
        <Stat label="Win rate" value={stats.win_rate !== null ? `${(stats.win_rate * 100).toFixed(1)}%` : "—"} sub="wins/(wins+losses), breakevens excluded" />
        <Stat label="Profit factor" value={stats.profit_factor !== null ? fmt(stats.profit_factor, 2) : "—"} sub="∞ → — per backend" />
        <Stat label="Expectancy" value={fmt(stats.expectancy, 4)} sub="per trade" />
        <Stat label="Avg R" value={fmt(stats.average_r, 3)} />
        <Stat label="Max DD" value={fmt(stats.max_drawdown, 2)} mono />
        <Stat label="Equity" value={`${fmt(initialCapital, 0)} → ${fmt(finalEquity, 0)}`} mono />
      </div>
      <div className="mono mt-2 text-[11px] text-[var(--color-text-tertiary)]">Win rate, profit factor, expectancy, R, drawdown — all backend-derived, not frontend calculations. “—” means null per backend, not 0.</div>
    </div>
  );
}

function Stat({ label, value, mono, tone, sub }: { label: string; value: string; mono?: boolean; tone?: "bull" | "bear"; sub?: string }) {
  const toneCls = tone === "bull" ? "text-[var(--color-bull)]" : tone === "bear" ? "text-[var(--color-bear)]" : "text-[var(--color-text-primary)]";
  return (
    <div className="rounded-md border border-[var(--color-border-subtle)] bg-[var(--color-bg-surface-1)] px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-tertiary)]">{label}</div>
      <div className={`${mono ? "mono" : ""} mt-0.5 text-[13px] font-medium ${toneCls}`}>{value}</div>
      {sub && <div className="mono text-[10px] text-[var(--color-text-tertiary)]">{sub}</div>}
    </div>
  );
}
