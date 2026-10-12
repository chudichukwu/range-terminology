# Grandblue integration — phase 1

Implemented the first phase of the reference direction in `design-direction-2026-10.md`:

- Scanner is setup discovery: one market per row, timeframe cells, fresh-only filters and counts, progressive results, explicit scan progress and 60-second refresh after completion.
- Watchlists are market curation: named collections, exact venue symbols, notes, add/remove markets, and links into Scanner or a chart. Opening Watchlists makes no analysis requests.
- Analysis puts the chart first, groups timeframe controls by purpose, and moves manual ranges into a dedicated inspector. Context and event history are expandable below the chart.
- Calm black surfaces, restrained blue accents, quieter borders, and responsive card layouts retain Grandblue's identity.

## Scan performance

`summary=true` on pair analysis preserves the same closed candle history, range engine, entry decision, higher-timeframe context, risk plan and freshness checks. It returns only the latest candle and latest closed-candle SFP observations, and skips historical range annotations. Scanner and the alert monitor use it; chart analysis defaults to the full response. Legacy strategies retain their existing analysis behavior.

Local warm-cache benchmark, 200 synthetic candles, ten repetitions: median full analysis 87.34 ms / 35,416 JSON bytes; summary 2.03 ms / 3,424 bytes. This isolates computation and serialization size, not provider latency or end-to-end scan time. Cold provider fetches and free-host wake-up delays remain.

## Validation

- Production Next build succeeds with type checking.
- Existing backend suite: 625 tests passed (PostgreSQL tests required permission to start a temporary local database).
- 19 additional summary tests cover six timeframes, gaps, stale candles, and current versus historical SFP observations.

This phase does not add broker execution, an AI model, strategy-builder integrations, or the future performance/risk dashboards.
