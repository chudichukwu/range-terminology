# Range Trading Terminal — UI/UX Design Specification

**Status:** Authoritative — Source of Truth for Figma/Stitch and Frontend Implementation  
**Version:** 1.1 — Phase 9 Baseline (Correction Pass 2026-08-26)  
**Scope:** Covers all 13 core UI areas through Phase 9 backend. No frontend implementation — this document is the implementation contract.  
**Stack target:** Next.js (App Router) + React + TypeScript + Tailwind + Lightweight Charts (or equivalent canvas chart) + FastAPI backend.

---

## Table of Contents

1. [Product UI Philosophy](#1-product-ui-philosophy)
2. [Information Architecture](#2-information-architecture)
3. [Page / Screen Inventory](#3-page--screen-inventory)
4. [Layout Specifications](#4-layout-specifications)
5. [Design Tokens](#5-design-tokens)
6. [Color & Status Semantics](#6-color--status-semantics)
7. [Chart Specifications](#7-chart-specifications)
8. [Component Inventory](#8-component-inventory)
9. [Responsive Behavior](#9-responsive-behavior)
10. [Accessibility](#10-accessibility)
11. [Core User Flows](#11-core-user-flows)
12. [States & Edge Cases](#12-states--edge-cases)
13. [Design Principles](#13-design-principles)
14. [Capabilities & Validation](#14-capabilities--validation)

---

## 1. Product UI Philosophy

### 1.1 Positioning

This is a **professional trading/research workstation**, not a marketing dashboard, not a DeFi portfolio tracker. The user is a discretionary or systematic range trader who lives in the chart. Every pixel must justify itself by answering: *"does this help me decide to trade, size, or stay out?"*

- **Research-first trading.** The intended hierarchy is: Market → Range/Regime → Signal/Confirmation → Risk → Execution → Journal (see §4 and §13.12). The UI makes each gate explicit and in that order.
- **Personal-first, multi-user capable.** Single-user mental model by default (your watchlists, your strategies, your trades). Multi-user is an architecture constraint (isolation via `owner_user_id`), not a social feature. No feed, no copy-trading, no public profiles.
- **Crypto first, market-agnostic second.** Symbols are `BASE/QUOTE` (e.g., `BTC/USDT`). Timeframes are canonical (`1m–1d`). Venue is a property of the symbol/connection, not the identity of the market. Future markets (FX, equities) arrive by adding symbols/venues, not by redesigning IA.
- **No invented intelligence.** Confidence is a heuristic score in `[0,1]`, not a probability. Efficiency Ratio and regime labels are explainable math. The UI never implies predictive certainty (no "90% win chance" language).
- **Backend owns domain truth.** The frontend renders analysis provided by the backend/API. It never re-implements `RangeState`, `Signal`, `RiskDecision`, or regime calculations. It may orchestrate multiple API requests, handle per-request loading/stale/error states, and compose results for display — but it does not reproduce engine logic.

### 1.2 Visual Posture

- **Dark-first, near-black.** The chart is the hero; chrome recedes. Surfaces are desaturated graphite/ink, not tinted navy.
- **Information-dense, not chaotic.** Dense tables, compact rows, small type for data, generous whitespace only where it separates decisions.
- **Terminal, not toy.** Monospace where numbers live. Sharp corners over pill shapes. Flat surfaces over glass. Borders over shadows for separation.
- **Color is data, not decoration.** Five semantic channels carry meaning: green for positive/bullish/successful outcomes where appropriate (bullish candles, up-price, long direction, wins), red for bearish/negative market direction where appropriate (bearish candles, down-price, short direction, losses), amber for risk/rejection/warning/blocked actions, slate/neutral for range structure, lavender for oscillator/confirmation. If a color does not encode one of these domains, it should be gray. Red is not used as a generic error or risk color.

### 1.3 Hierarchy of Information

Strict visual hierarchy, reinforced by type, weight, size, and position. This order is the decision flow:

1. **Market data** — price, candles, volume. Largest, highest contrast, monospace, always visible.
2. **Range & Regime analysis** — `RangeStatus`, `MarketRegime`, range high/low, zones, confidence, position-in-range. Slate/neutral for range structure; regime as research context alongside, not merged with range status.
3. **Decisions (Signal/Confirmation)** — signal direction/reason, confirmation state, and — when available — divergence (planned, see §7.7). Lavender/muted tertiary, in the signal panel adjacent to the chart — never competing with candles.
4. **Risk** — sizing, gates, reward/risk, fees/slippage. Amber for blocked/rejected states.
5. **Execution** — order preview. Phase 9 is paper/read-only; execution capability is distinct from connectivity (see §3.12).

A trader must be able to answer in under 3 seconds: *Am I in a valid range? Where is price inside it? Is there a setup?*

---

## 2. Information Architecture

### 2.1 Global Structure

```
┌─────────────────────────────────────────────────────────────┐
│ Top Ticker Ribbon (market pulse — always visible when authed) │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                  │
│  Global  │  Page Content (changing)                        │
│  Sidebar │                                                  │
│  Nav     │  ┌──────────────┬─────────────────────────────┐  │
│ (fixed)  │  │ Primary      │ Context Panel (signal/risk/  │  │
│  240px   │  │ Chart /      │  position / config)          │  │
│  coll.   │  │ Table        │  360–420px                   │  │
│  64px    │  │ (flex)       │                              │  │
│          │  └──────────────┴─────────────────────────────┘  │
│          │  Watchlist / Sub-panels (where applicable)       │
└──────────┴──────────────────────────────────────────────────┘
```

### 2.2 Navigation Model

**Global sidebar** (persistent, collapsible to icon rail on desktop, drawer on mobile).

| Group | Items | Visibility |
|-------|-------|------------|
| **Trading** | Dashboard · Watchlists · Positions · Trade Journal | All authenticated users |
| **Research** | Backtesting · Analytics (Performance) · Research Data (coverage/quality) | All authenticated users |
| **Configure** | Strategies · Risk · Exchange Connections | All authenticated users |
| **System** | Admin (Users, Audit Log, System Health, Trading Activity) | `OWNER` only — nav item hidden entirely for `USER` |
| **Account** | Alerts / Activity, User menu (Me, Logout) | All authenticated users |

**Top ticker ribbon** sits above page content, below any app header. Shows compact pair chips for the active watchlist (or pinned favorites). Each chip: `BTC/USDT  67,421.10  +1.24%  ● VALID  RANGING`. Clicking a chip navigates to Dashboard focused on that pair/timeframe. Ribbon is the fastest way to context-switch.

**Command palette** (`Cmd+K` / `Ctrl+K`): jump to pair, timeframe, strategy, backtest run, trade.

### 2.3 Route Map

| Route | Page | Auth |
|-------|------|------|
| `/login` | Sign In | public |
| `/register` | Create Account (first user becomes OWNER) | public |
| `/` | Main Trading Dashboard | authed → redirects if unauth |
| `/watchlists` | Watchlist Manager | authed |
| `/watchlists/:id` | Watchlist Detail | authed |
| `/positions` | Position / Trade Management (operational state) | authed |
| `/journal` | Trade Journal / Performance Analytics (historical) | authed |
| `/backtests` | Backtesting: config + run history | authed |
| `/backtests/:runId` | Backtest Result Detail | authed |
| `/strategies` | Strategy Configuration (list + editor) | authed |
| `/risk` | Risk / Account Overview | authed |
| `/exchanges` | Exchange Connections | authed |
| `/alerts` | Alerts / Activity Feed | authed |
| `/admin` | Admin Dashboard (health + stats) | OWNER |
| `/admin/users` | User Management | OWNER |
| `/admin/audit` | Audit Log | OWNER |
| `/admin/activity` | Trading Activity (aggregate) | OWNER |
| `/me` | Account (profile, session) | authed |

Every route beyond `/login`/`/register` requires a valid `Authorization: Bearer <token>` session resolved via `container.users.resolve_session`. OWNER routes additionally check `role == OWNER` server-side; the frontend hides them but never relies on hiding for security.

---

## 3. Page / Screen Inventory

### 3.1 Authentication / Account Screens

**`/login` and `/register`**
- Centered card (400px) on near-black page, no sidebar/ribbon.
- Fields: email, password. Register notes "First account becomes workspace owner."
- Primary button: `Sign In` / `Create Account`. Secondary link toggles between login/register.
- Inline field errors, form-level error banner (e.g., "Invalid credentials", "Account inactive").
- On success: store `access_token`, redirect to `/` (dashboard). Token in `Authorization` header for all subsequent requests.
- `/me` (account): read-only card showing `id, email, role, active, created_at, last_login_at`. Logout button. Session list if exposed in future.

**States:** empty, typing, submitting (button loading), error (field + banner), success redirect.

### 3.2 Main Trading Dashboard (`/`)

The primary workstation where chart/range analysis remains the dominant visual element. Watchlist and multi-timeframe context supports the decision; it does not compete with it.

**Layout (desktop):**
- Pair selector + timeframe selector row (sticky, 44px) directly beneath the ribbon.
- Primary chart (flex, 55–65% height, min 380px) with range overlay, current price line, entry/target/stop (when a backend `RiskDecision` preview is available), signal markers, range status + regime badges.
- Signal & Confirmation panel (right dock, 380px) — adjacent to chart, not below.
- RSI/Oscillator panel (sub-panel, 120px) docked to chart bottom — shares time axis.
- Risk Summary strip (below chart, 88px) — equity, available balance, exposure, next-trade sizing preview (from backend).
- Watchlist mini (collapsible, 160–220px) at bottom: scan-oriented summary of the active watchlist (see §3.3).
- Multi-timeframe strip (4 small cards) below chart header: per-timeframe status for the same symbol (see §7.8). Each card is independently evaluated; loading/error/stale per timeframe.
- Mobile: chart full-width, panels stack vertically in order: chart → signal → RSI → risk → multi-timeframe strip → watchlist mini.

**Data consumed (frontend does not derive):**
The dashboard composes backend-provided results: `CandleDataset` + `DataQualityReport`, `RangeState` (`range_high`, `range_low`, `range_width`, `confidence`, `status`, `metadata`), `MarketRegime`, `Signal` (`direction`, `reason`, `position_in_range`, `confirmation`), and `RiskDecision` previews. The frontend requests these via the available market/analysis APIs and renders whatever the backend returns, including per-timeframe partial failures.

### 3.3 Multi-Pair Watchlist (Scan-Oriented)

**`/watchlists` (manager) and `/watchlists/:id` (detail)**

The watchlist is a **scanning workflow**, not a generic table. Its job is to let a trader quickly identify: pairs with valid ranges, pairs classified as `RANGING`, price proximity to lower/upper edges, signal availability, confirmation state, and data freshness/quality (including stale or unsafe analysis).

- Manager: table of watchlists (`name, item count, updated_at`) + Create. Search by name.
- Detail: header with name (inline rename), list of `WatchlistItem` rows. Filters and sort are first-class: filter by `RangeStatus`, `MarketRegime`, signal availability, confirmation state, and data quality/freshness; sort by edge proximity, confidence, or freshness.
- **Scan-prioritized columns (primary, always visible):**
  `Symbol | Range Status | Market Regime | Last Price + Position-in-Range (meter + numeric) | Edge Proximity | Signal | Confirmation | Freshness/Quality (age + quality chip)`
- **Secondary / progressively disclosed:**
  `Venue | Range High/Low | Width | Confidence (bar) | 24h % | Enabled (toggle) | Notes`
  Secondary columns are collapsible behind a column-chooser or disclosure. On mobile they move into the row card's expanded detail.
- Bulk: add pair (symbol + venue_id + notes), remove, reorder (drag handle, persists `sort_order`), enable/disable toggle.
- Status cells use the canonical status semantics (§6) — never color-only. Stale or unsafe analysis is explicitly flagged per row (e.g., "Stale — 12 min ago" or "Unsafe — gaps detected") and reflected in row tint, not hidden.
- **Implementation note:** There is no dedicated multi-pair aggregation endpoint in Phase 9. The watchlist UI achieves scanning by coordinating independent per-symbol/timeframe requests through the available market-data/analysis APIs (one request per symbol/timeframe). Backend aggregation/orchestration for scanning performance is a future implementation decision — the UI must not fabricate analysis for a symbol it has not received from the backend.

### 3.4 Range Analysis / Chart (integrated in Dashboard)

Described fully in §7. Key requirement: range detection is **observable**. The chart must show, for the selected pair/timeframe, the exact `range_high`/`range_low` lines, the three zones (lower / middle NO-TRADE / upper) plus outside-range indication, the current price position, the `RangeStatus`, the `MarketRegime` (as separate context), and `confidence` — without requiring a tooltip. Frontend renders only what the backend returns.

### 3.5 Signal & Confirmation Panel (right dock on Dashboard)

- **Signal card** (top): direction (`LONG`/`SHORT`/`NONE`), reason (`SUPPORT_EDGE_SETUP`, `RESISTANCE_EDGE_SETUP`, `PRICE_MID_RANGE`, `PRICE_OUTSIDE_RANGE`, `NON_TRADABLE_RANGE`, `CONFIRMATION_NOT_MET`), confidence as a segmented bar + numeric, `position_in_range` meter. All values come from the backend `Signal`.
- **Confirmation row:** policy badge (`required`/`optional`/`ignored`), oscillator value (`RSI 28.4` / `Stoch %K 22.1`) when provided by the backend, threshold context, `confirmation: true/false/null` with explicit label. `confirmation` reflects the backend's oscillator confirmation (e.g., `OscillatorConfirmedRangeDetector` metadata), not a frontend calculation.
- **Divergence sub-section (planned):** Reserved area with its own visual treatment (see §7.7). In Phase 9 there is no canonical backend divergence contract — the section therefore shows an explicit planned-state empty treatment ("Divergence analysis — planned. No backend divergence signal in this version.") rather than a loading failure. See §6.8 / §7.7 for intended UX direction; backend/domain support is a future implementation requirement. No API fields, enums, or endpoints are invented for it.
- **Gate summary:** if a backend `RiskDecision` preview is available, show `APPROVED` or `REJECTED` + `rejection_reason` (e.g., `MAX_OPEN_POSITIONS`, `INSUFFICIENT_BALANCE`). Display is read-only.

### 3.6 Position / Trade Management

**Distinction:** Positions = operational/current trading state; Journal = historical trades, performance and research. Both use `Positions` terminology only for live/open state.

**`/positions`**
- **Open positions table** (operational; present for future live trading, read-only in Phase 9): `Symbol | Side | Quantity | Entry | Mark | Unrealized PnL | Liquidation | Leverage`. In Phase 9 this may be empty or reflect paper state.
- **Recent trades snippet** (backed by `StoredTrade`): compact table with filters by `symbol`, `result` (`win`/`loss`/`breakeven`), `status`. Click row → trade detail drawer with `TradeContext` breakdown. Full history lives in `/journal`.
- **Execution/Order panel** (Phase 9: paper/read-only posture): shows that live order placement is disabled; when a backend `RiskDecision` preview is available, displays entry/stop/target/quantity/notional/reward-risk/fees/slippage as received from the backend. No button claims to place a live order.

### 3.7 Strategy Configuration (`/strategies`)

- List of `StrategyConfig` cards: `name | schema_version | active | updated_at`.
- Editor (drawer or page): three grouped sections mirroring the backend payload exactly:
  - `range_config` — `mode` (`structural`/`volatility`/`manual`/`oscillator_confirmed`), `params` (mode-specific: `lookback`, `volatility_window`, `manual_high/low`, `oscillator`/`osc_period`/`overbought`/`oversold` etc.).
  - `signal_config` — `lower_edge_zone`, `upper_edge_zone`, `confirmation_policy` (`required`/`optional`/`ignored`).
  - `risk_config` — `risk_per_trade`, `stop_method`, `target_method`, `max_open_positions`, `max_drawdown`, `fee_rate`, `slippage_rate`, caps, leverage, etc. (see `risk_engine/engine.py:_DEFAULTS`).
- Validation is inline with engine rules (single source of truth). JSON preview toggle for power users.
- Versioning: `config_hash` displayed (short hash, copyable), `strategy_id` + `config_version`.

### 3.8 Risk / Account Overview (`/risk`)

- **Risk summary header:** `Equity | Available Balance | Total Exposure | Peak Equity | Drawdown % | Daily Drawdown | Consecutive Losses | Open Positions` — all values as provided by the relevant backend/account APIs; the frontend does not compute gates locally.
- **Gates panel:** each gate (`max_drawdown`, `max_daily_drawdown`, `max_consecutive_losses`, `max_open_positions`, notional/exposure caps, leverage) with current value vs. limit, progress bar, and `OK` / `AT LIMIT` / `BLOCKED` state using amber treatment (not red). Data source is backend-provided; UI is display.
- **Preview:** when a backend `RiskDecision` preview is requested (e.g., for the current actionable signal), show the backend's breakdown (quantity, notional, stop/target, reward-risk, fees/slippage, rejection reason if any). Frontend does not re-derive sizing.

### 3.9 Alerts / Activity Feed (`/alerts`)

- Feed of range/signal/quality events. Each item: `timestamp | symbol/timeframe | kind (badge) | detail | quality_issues if any`.
- Quality issues explicitly raised: gaps, unclosed candles, `INSUFFICIENT_DATA` — surfaced as warnings, not hidden. Future alert types include `MarketRegime.RANGING` transitions and watchlist-scan hits (see §6.2 / §3.3) — planned, not yet backend-driven.
- Filters: `symbol`, `kind`, `timeframe`, `severity`.
- Empty state when no alerts; not mistaken for "feed broken."

### 3.10 Backtesting & Research

**`/backtests`**
- Config form: `symbol | timeframe | start_ms/end_ms (date pickers) | strategy selector | initial_capital | fee_rate | slippage_rate | regime_lookback | warmup_candles`. Validates against `BacktestConfig` rules.
- History table: `run_id (short) | symbol/timeframe | period | total_trades | final_equity | max_drawdown | created_at | owner`.
- Actions: Run New Backtest, View Result, Compare (select 2–4 runs).

**`/backtests/:runId`**
- Header: run identity (`run_id`, `config_hash` short+copy, `engine_version`, `strategy_id`, `config_version`).
- Statistics cards: `total_trades | wins/losses/breakevens | win_rate | profit_factor | expectancy | average_r | total_realized_pnl | max_drawdown`.
- Equity curve (step/area chart) with zoom, tooltip shows `equity/peak/drawdown` per `EquityPoint`.
- Regime + zone breakdown: bar/strip showing `regime_counts` (`ranging`, `trending_up`, `trending_down`, `transitional`, `insufficient_data`) and `zone_counts` (`lower_edge`, `middle`, `upper_edge`, `outside`).
- Trades table: same as journal but scoped to this run.
- Backtest segmentation by `MarketRegime` is supported (filter/segment results by regime). This treats `RANGING` as a first-class research dimension alongside the other regimes.
- Compare view: side-by-side stats + overlaid equity curves (distinct line styles, not just color).

### 3.11 Trade Journal / Performance Analytics (`/journal`)

Historical trades and performance. Not operational positions.

- **Statistics cards** (derived via backend `compute_trade_statistics` or equivalent API-computed results): `total_trades | completed | open | wins | losses | breakevens | win_rate | profit_factor | expectancy | average_win | average_loss | average_r | total_realized_pnl`. Each card shows `null → "—"` when not derivable (e.g., `profit_factor` with no losses). No values are invented on the frontend.
- **Equity curve:** cumulative realized PnL curve derived from closed trades (trade-close granularity). Not an intraday equity curve — label explicitly. Curve data comes from the backend.
- **Trade history / journal table:** `trade_id | symbol/timeframe | direction | quantity | entry → exit | realized_pnl | realized_r | fees | result badge | opened_at → closed_at | strategy | context preview`. Click → drawer with `TradeContext` full breakdown (range bounds, confidence, position_in_range, risk_percent, regime/zone extra).
- Research segmentation: allow filtering/grouping historical trades by `MarketRegime` (including `RANGING`) and by zone at entry, to evaluate range-trading edge per regime. Backend provides the regime/zone context used for segmentation.
- Filters: `symbol`, `result`, `status`, `strategy`, date range. Pagination (server supports `limit`).

### 3.12 Exchange Connections (`/exchanges`)

Four distinct capabilities are visualized separately; a connected exchange does not imply trading is enabled.

| Capability | What it means | UI representation |
|------------|---------------|-------------------|
| **Connection / credentials** | User has registered a venue via `ExchangeConnection` + `CredentialStore` (`credential_ref` stored) | Connection card with `venue_id`, `display_name`, `sandbox` |
| **Market-data availability** | Whether that venue can serve `GET /markets/:symbol/ticker|candles` for a symbol/timeframe | Per-symbol/timeframe availability chip; timeframe pills disabled when unavailable |
| **Account / balance availability** | Whether the venue can return balances/positions (authenticated read) | Account section shows "Balance data unavailable until credentials verified" when not available; never a zero balance fabricated |
| **Execution capability** | Whether the system may place orders | Phase 9: always `PAPER/READ-ONLY`; UI shows paper-mode banner and disables live CTAs. Live execution is not introduced in this spec. |

- Cards per `ExchangeConnection`: `venue_id | display_name | status badge (connected/error/disabled) | sandbox badge | updated_at`.
- Connect form: `venue_id | display_name | api_key | secret | password (optional) | sandbox toggle`. Secrets use password inputs, never echoed after creation. Shows `credential_ref` not the secret.
- Disconnect (delete) with confirm dialog.
- Status semantics are determined by backend responses, not invented on the client.

#### DEX Future Boundary

DEX connectivity is acknowledged as a separate architectural concern and is **not** part of Phase 9. Future DEX support may require wallet-based authentication, message/transaction signing, RPC access, routing, slippage/price-impact handling, gas estimation, and chain-specific semantics. The design must not force these into the CEX API-key (`api_key | secret | password`) model. In the IA the `/exchanges` area may later gain a distinct "DEX" subsection with its own connection flow, but no DEX UI, flows, or tokens are specified here.

### 3.13 Historical Research Data (Product Requirement — Observable Coverage & Quality)

The product must make historical research data observable so a trader/researcher can answer "what data do we actually have?" before trusting analysis or backtests. This is a product requirement to be implemented through the appropriate future application/API work; no new Phase 9 endpoints are assumed or invented.

The research data view (within Research/Backtests or a dedicated Research Data page) should expose, per symbol/timeframe:

- **Symbol coverage** — which `BASE/QUOTE` symbols have stored history.
- **Timeframe coverage** — which canonical `Timeframe` values (`1m–1d`) are available for each symbol.
- **Historical date coverage** — earliest and latest candle timestamps (`first_timestamp_ms` / `last_timestamp_ms`) and any interior coverage gaps.
- **Accumulated historical depth** — candle counts / days of history per symbol/timeframe.
- **Ingestion status** — last ingestion time, source/provider, ingestion outcome (inserted/updated/unchanged) where available.
- **Data freshness** — age since last successful fetch/ingest, with stale threshold.
- **Data quality** — `DataQualityReport` summary (`is_clean`, `issue_kinds`, gap ranges, unclosed-candle inclusion), and whether the dataset is `is_analysis_safe`.
- **Gaps** — explicit list of gap intervals (`gap_start_ms → gap_end_ms`) that analysis excludes.
- **Provider / source** — which venue or data source supplied the history.

Until dedicated coverage endpoints exist, the UI should surface whatever coverage/quality metadata the current APIs already return (e.g., `CandleDataset.quality`, `DatasetSummary` via admin/system-health where available) and present unavailable dimensions as "Not yet available — requires future backend work" rather than fabricating them.

### 3.14 Admin Dashboard

**`/admin`** (overview)
- KPI row: `user_count | dataset_count | market_data_provider (configured/unconfigured) | schema_version | engine_versions | time`.
- **Trading activity** panel (from `GET /admin/trading-activity`): `totals {trades, wins, losses, open, backtest_runs}` + `recent_backtests` table.
- Quick links: Users, Audit Log, Trading Activity detail.
- **Research data summary** (when available via backend): total symbols/timeframes covered, total candle depth, quality summary. Unavailable fields show planned-state placeholders.

**`/admin/users`**
- User table: `id | email | role (OWNER/USER) | active | created_at | last_login`.
- Row actions (OWNER only): Activate/Deactivate, Change Role, Revoke Sessions, Create User.
- Create user form: `email | password | role (user/owner)`.

**`/admin/audit`**
- Audit log table: `timestamp | actor_user_id | action | resource_type | resource_id | outcome | metadata (collapsed JSON)`. Infinite scroll / pagination, `limit` param.

**`/admin/activity`**
- Expanded trading activity: totals + recent backtests + recent trades (OWNER sees all trades via `store.list_trades`).

---

## 4. Layout Specifications

### 4.1 Desktop Workstation (Primary — 1280px+)

The entire design is built for 1440×900 and up. Below that, the layout adapts (see §9) but never sacrifices the chart.

- **Viewport:** full-height flex column. No double scrollbars. Sidebar + main scroll independently.
- **Sidebar:** 240px expanded, 64px collapsed (icon rail, tooltips on hover). Persistent on ≥1024px, collapsible via toggle; state persisted in localStorage.
- **Top ribbon:** 36px height, horizontal scroll on overflow (scroll shadows), sticky under header. Never wraps.
- **Main content:** `max-width: 1920px`, centered, `padding: 16px` (token `space-4`). On ultra-wide, content does not stretch beyond 1920.
- **Dashboard grid:**
  ```
  Row 1: Pair + Timeframe selectors (48px, sticky top-36px)
  Row 2: Chart (flex 1, min-height 420px, ideal 52vh) | Signal panel (400px, sticky)
  Row 3: RSI/Divergence panel (140px, aligned to chart width, shares x-axis)
  Row 4: Multi-timeframe strip (80px, aligned to chart width)
  Row 5: Risk strip (88px)
  Row 6: Watchlist mini — scan-oriented (collapsible, max 240px, compact)
  ```
- Visual weight: chart and its directly adjacent signal/RSI panels are primary; the watchlist and multi-timeframe strip are secondary supporting context. Supporting panels use lower-contrast chrome so they do not visually compete with the chart (see §6, §12).
- **Panel gutters:** 16px (`space-4`) between chart and side panel. Card gaps 12px (`space-3`).
- **Density default:** `comfortable` (44px table rows, 36px inputs). Toggle to `compact` (36px rows, 32px inputs) in user preference — applies to tables/lists only, never to chart or controls requiring precise clicks.

### 4.2 Tablet (768–1279px)

- Sidebar becomes overlay drawer (hamburger). Ribbon remains but shows fewer chips + overflow count (`+6`).
- Dashboard: chart full-width, signal panel drops below chart (full-width card), RSI panel stays docked to chart, multi-timeframe strip remains full-width below RSI.
- Tables: horizontal scroll with sticky first column, column-chooser to hide low-priority columns.

### 4.3 Mobile (≤767px)

- Sidebar: drawer only. Ribbon: horizontal swipe, 2–3 chips visible, "+N" overflow.
- Dashboard: single column. Chart 320px min-height. Timeframe selector becomes segmented control with horizontal scroll. Pair selector becomes full-width search + bottom sheet.
- Tables: card/list view fallback. Each trade/signal renders as a compact card rather than a row.
- Forms: stacked single-column, full-width inputs.

### 4.4 Spacing & Rhythm

All spacing derived from tokens (`space-1` = 4px base). No arbitrary pixel values. Page section gaps use `space-6` (24px), card internal padding `space-4` (16px), tight element gaps `space-2` (8px). Vertical rhythm is 4px baseline.

---

## 5. Design Tokens

Tokens are the single source of visual truth. Figma Styles / Variables map 1:1 to these. Tailwind config extends from them. Never hardcode hex values in components. This section defines tokens; component sections describe how to apply them — not every CSS declaration needed to build a component is enumerated here.

### 5.1 Colors

**Mode:** Dark only for v1. Tokens named semantically, not by appearance.

```css
/* ——— Background ——— */
--color-bg-base:       #07090D;  /* page, near-black, never pure #000 */
--color-bg-subtle:     #0D1117;  /* subtle lift behind ribbon */
--color-bg-surface-1:  #11161E;  /* cards, panels, primary chrome */
--color-bg-surface-2:  #161E2A;  /* elevated cards, dropdowns */
--color-bg-surface-3:  #1C2533;  /* hover, active surface */
--color-bg-overlay:    #0D1117CC;/* modal scrim (80% via hex alpha) */

/* ——— Border ——— */
--color-border-subtle: #1E2A3A;  /* default dividers */
--color-border-strong: #263548;  /* focused/active borders */
--color-border-focus:  #3B82F670;/* focus ring (with alpha) */

/* ——— Text ——— */
--color-text-primary:  #E6EAF0;  /* primary reading, price */
--color-text-secondary:#9AA6B8;  /* secondary labels */
--color-text-tertiary: #6B7A90;  /* captions, muted meta */
--color-text-inverse:  #07090D;  /* text on light/accent fills */
--color-text-disabled: #4A5A72;

/* ——— Semantic channels ——— */
/* Green: positive / bullish / successful outcomes where appropriate */
--color-bull:          #1DB954;  /* bullish candle body, +price, LONG, WIN */
--color-bull-subtle:   #1DB95414;/* bullish bg tint (8%) */
/* Red: bearish / negative market direction where appropriate */
--color-bear:          #EF4444;  /* bearish candle body, -price, SHORT, LOSS */
--color-bear-subtle:   #EF444414;
/* Amber: risk / rejection / warning / blocked actions */
--color-danger:        #F59E0B;  /* risk gate blocked, rejected, warning, danger */
--color-danger-strong: #D97706;
--color-danger-subtle: #F59E0B14;
--color-danger-bg:     #F59E0B1A;
/* Slate/neutral: range structure */
--color-range:         #8EA1BE;  /* range high/low lines, boundary */
--color-range-subtle:  #8EA1BE18;/* zone fill base */
--color-range-strong:  #B0C4DE;  /* emphasized boundary */
--color-zone-lower:    #8EA1BE14;/* lower edge zone fill (8%) */
--color-zone-middle:   #6B7A9010;/* middle NO-TRADE zone — restrained, see §6.3 */
--color-zone-upper:    #8EA1BE14;/* upper edge zone fill */
/* Lavender: oscillator / confirmation */
--color-osc:           #9A8BB5;  /* RSI line, confirmation accent */
--color-osc-subtle:    #9A8BB514;
--color-osc-strong:    #B8A9D6;

/* ——— Planned — divergence palette (intended direction, no backend contract yet) ——— */
--color-divergence-bull: #22C55E;/* intended for bullish divergence — distinct shape, not just color */
--color-divergence-bear: #F97316;/* intended for bearish divergence — orange, not candle red */

/* ——— Status additional ——— */
--color-info:          #38BDF8;  /* informative, regime context */
--color-warning:       #FACC15;  /* degenerate structure, quality warning (amber family) */
--color-success:       #22C55E;  /* valid, approved, win */
--color-neutral:       #64748B;  /* insufficient_data, none states */

/* ——— Chart Semantics (explicit) ——— */
--color-chart-grid:    #1E2A3A;
--color-chart-axis:    #6B7A90;
--color-chart-crosshair: #3B4A62;
--color-chart-candle-bull: var(--color-bull);
--color-chart-candle-bear: var(--color-bear);
--color-chart-candle-wick: #6B7A90;
--color-chart-volume-bull: #1DB95433;
--color-chart-volume-bear: #EF444433;
--color-chart-price-line: #E6EAF0;
--color-chart-entry:   #38BDF8;
--color-chart-stop:    #F59E0B;
--color-chart-target:  #22C55E;
--color-chart-signal-long:  #1DB954;
--color-chart-signal-short: #EF4444;
--color-chart-signal-none:  #64748B;
```

**Channel rules:**
- Green where positive/bullish/successful is the meaning (bullish candles, positive price change, LONG direction, WIN trades). Red where bearish/negative market direction is the meaning (bearish candles, negative price change, SHORT direction, LOSS trades).
- Amber (not red) for risk, rejection, warning, and blocked actions — including `DEGENERATE` structure warnings and risk-gate blocks — so "the system blocked your trade" is never confused with "the market went down."
- Range structure uses slate/neutral (`--color-range`), oscillator/confirmation uses lavender (`--color-osc`). Divergence (planned) uses its own distinct palette and shapes.
- The same status color is reused consistently wherever that status appears (watchlist, ribbon, chart header, signal card, scanning strip).

### 5.2 Typography

```css
/* ——— Families ——— */
--font-sans:    'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
--font-mono:    'JetBrains Mono', 'SF Mono', ui-monospace, monospace;
--font-display: 'Inter', ui-sans-serif; /* same as sans, heavier weight */

/* ——— Scale (desktop, rem — 1rem=16px) ——— */
--text-xs:   0.6875rem; /* 11px — captions, axis labels */
--text-sm:   0.75rem;   /* 12px — secondary labels, table meta */
--text-base: 0.8125rem; /* 13px — body, default UI — intentionally small for density */
--text-md:   0.875rem;  /* 14px — emphasized body */
--text-lg:   1rem;      /* 16px — section titles */
--text-xl:   1.125rem;  /* 18px — page titles */
--text-2xl:  1.375rem;  /* 22px — dashboard price hero */
--text-3xl:  1.75rem;   /* 28px — rare, hero numbers */

/* ——— Weights ——— */
--font-regular: 400;
--font-medium:  500;
--font-semibold:600;
--font-bold:    700;

/* ——— Line height ——— */
--leading-tight: 1.2;
--leading-normal:1.4;
--leading-relaxed:1.6;

/* ——— Tracking ——— */
--tracking-tight: -0.015em;
--tracking-normal: 0;
--tracking-wide:  0.05em; /* labels, badges — uppercase wide */

/* ——— Usage ——— */
/* All market data, prices, quantities, PnL, percentages, timestamps → font-mono, tabular-nums */
/* Labels, descriptions, navigation → font-sans */
/* Numeric tables: font-mono + font-variant-numeric: tabular-nums; */
```

### 5.3 Spacing

4px base unit. All spacing is a multiple of 4.

| Token | Value | Usage |
|-------|-------|-------|
| `space-1` | 4px | micro gap, icon-text |
| `space-2` | 8px | tight gap, badge padding y |
| `space-3` | 12px | card gap, input padding y |
| `space-4` | 16px | card padding, panel gutter |
| `space-5` | 20px | — |
| `space-6` | 24px | section gap |
| `space-8` | 32px | page section vertical |
| `space-10` | 40px | — |
| `space-12` | 48px | header/selector row height |

### 5.4 Borders, Radii, Shadows

```css
--border-width-hairline: 1px;
--border-width-strong:   1.5px;

--radius-xs: 4px;   /* badges, small pills */
--radius-sm: 6px;   /* inputs, buttons, table cells */
--radius-md: 8px;   /* cards, panels */
--radius-lg: 10px;  /* modals, large cards */
--radius-pill: 999px;/* status dots, pill badges */

--shadow-sm: 0 1px 2px rgba(0,0,0,0.4);
--shadow-md: 0 4px 12px rgba(0,0,0,0.5);
--shadow-lg: 0 12px 32px rgba(0,0,0,0.6);
```

Shadows are subtle; borders do the heavy lifting for card separation on near-black.

### 5.5 Density

| Mode | Table row | Input height | Card padding |
|------|-----------|--------------|--------------|
| `comfortable` (default) | 44px | 36px | 16px |
| `compact` | 36px | 32px | 12px |

Toggle in user menu. Applies via `data-density="compact"` on root. Chart and selector rows never compact.

### 5.6 Icon Sizing

```css
--icon-xs: 12px; /* inline with xs text */
--icon-sm: 14px; /* buttons, badges */
--icon-md: 16px; /* nav, default */
--icon-lg: 20px; /* page headers */
--icon-xl: 24px; /* empty states */
```
Icon library: Lucide (or Heroicons outline) — stroke 1.75px, rounded caps. No filled icons except status dots.

### 5.7 Motion

```css
--ease-default: cubic-bezier(0.25, 0.1, 0.25, 1);
--ease-out:     cubic-bezier(0.16, 1, 0.3, 1);
--duration-fast: 120ms;
--duration-normal: 180ms;
--duration-slow: 240ms;
```
Motion is for feedback only: hover, focus, drawer slide, toast entry. No chart or data animation that obscures values. Respect `prefers-reduced-motion`.

---

## 6. Color & Status Semantics

Every backend-provided domain value has a single visual encoding. The same `VALID` color in the watchlist, the chart badge, and the signal panel. No synonyms. Where a visual treatment is planned but not yet backed by a backend contract, it is labeled as such.

### 6.1 Range Status (`RangeState.status` — `RangeStatus` enum)

`RangeStatus` has exactly three values. There is no fourth `TRENDING` range status.

| Status | Label | Color | Icon | Usage |
|--------|-------|-------|------|-------|
| `VALID` | Valid | `--color-success` (green) badge fill `success-subtle` | ● solid dot | Tradable range; bounds are actionable |
| `DEGENERATE` | Degenerate | amber family (`--color-danger` / `--color-warning`) | ◐ half-dot / warning triangle | Detection ran, no tradable structure — `metadata.reason` shown alongside |
| `INSUFFICIENT_DATA` | Insufficient Data | `--color-neutral` (gray) | ○ hollow dot | Too few rows; chart shows placeholder + rows needed |

Global rule: **bounds are only actionable when `VALID` + `is_tradable` (positive width, finite bounds).** Degenerate/insufficient states render bounds as dashed, muted, with explanatory annotation — never as solid lines a trader could mistake for tradable levels.

`MarketRegime.TRENDING_UP` / `TRENDING_DOWN` / `TRANSITIONAL` are not range statuses. A non-range market is communicated via `MarketRegime` alongside `RangeStatus` (see §6.2); the two are displayed together but never presented as the same concept.

### 6.2 Market Regime (`MarketRegime`)

A separate research/market-condition concept from `RangeStatus`. Both are shown simultaneously when relevant (e.g., `RangeStatus: VALID` + `MarketRegime: TRANSITIONAL`). Do not conflate `MarketRegime.RANGING` with `RangeStatus.VALID`.

| Regime | Badge | Chart Underlay | Scanning/Research Use |
|--------|-------|----------------|----------------------|
| `RANGING` | neutral/sky subtle, `⟡ Ranging` | no overlay — normal range zones | First-class: watchlist filter, analysis segmentation, backtest segmentation, research statistics, future alerts |
| `TRENDING_UP` | `--color-bull` subtle, `↗ Trending Up` | subtle green tint on right 25% of chart | Segmentation, alerts (planned) |
| `TRENDING_DOWN` | `--color-bear` subtle, `↘ Trending Down` | subtle red tint | Segmentation, alerts (planned) |
| `TRANSITIONAL` | amber subtle, `⟡ Transitional` | hatched subtle overlay | Segmentation |
| `INSUFFICIENT_DATA` | `--color-neutral` | muted, chart shows "Collecting data" | Filter out of research |

`RANGING` is a first-class scanning and research dimension: available as a watchlist filter, an analysis label on the chart header, a backtest `regime_counts` / segmentation dimension, and a research-statistics dimension. Future alerts may trigger on regime transitions, including into/out of `RANGING`.

### 6.3 Price Zones (Signal domain — backend-defined)

Visualized on the chart as horizontal bands between `range_low` and `range_high` when a valid range exists (§7). Zone fractions `lower_edge_zone` / `upper_edge_zone` come from the backend `Signal` config; the frontend does not compute zones.

| Zone | Fill | Label on chart | Semantics |
|------|------|----------------|-----------|
| Lower edge (`[low, low + lower_edge_zone*width]`) | `--color-zone-lower` (neutral tint) | `LONG ZONE` (small, muted) | Potential LONG setup area |
| Middle (`(low+lower_zone, high-upper_zone)`) | `--color-zone-middle` with a restrained indication (subtle fill + `NO-TRADE` label) | `NO-TRADE` (centered, `text-tertiary`, uppercase, `tracking-wide`) | Explicit no-trade area — must be unmistakably legible, but chart readability takes priority over heavy decoration. No excessive hatch, no large opaque block. If the fill would impair candle contrast, reduce to a label + thin edge lines only. |
| Upper edge | `--color-zone-upper` | `SHORT ZONE` | Potential SHORT setup area |
| Outside (`price < low` or `> high`) | no fill, price line rendered beyond bounds, outside indicator arrow | `OUTSIDE` | `SignalReason.PRICE_OUTSIDE_RANGE` — also a NO-TRADE condition |

Rule: lower → potential LONG, middle → explicit NO-TRADE, upper → potential SHORT, outside → NO-TRADE. The middle and outside conditions are both non-actionable and must be visually unambiguous without relying on color alone.

`position_in_range` and edge proximity are backend-provided (or derived strictly from backend-provided `range_high`/`range_low` + market price for display). The meter shows a dot on a vertical scale adjacent to the chart y-axis and a numeric value (see §7).

### 6.4 Signal (`Signal.direction` + `SignalReason`)

All signal values are backend-provided. The frontend maps them to display; it does not decide signal direction.

| Signal | Display |
|--------|---------|
| `LONG` (`SUPPORT_EDGE_SETUP`) | Green pill `▲ LONG`, confidence bar, reason line "Support edge setup" |
| `SHORT` (`RESISTANCE_EDGE_SETUP`) | Red pill `▼ SHORT`, confidence bar, reason line "Resistance edge setup" |
| `NONE` — `PRICE_MID_RANGE` | Gray `— NO SETUP`, reason "Price in middle (no-trade) zone" |
| `NONE` — `PRICE_OUTSIDE_RANGE` | Gray `— OUTSIDE`, reason "Price outside range bounds" |
| `NONE` — `NON_TRADABLE_RANGE` | Amber `— NO RANGE`, reason from backend status/reason |
| `NONE` — `CONFIRMATION_NOT_MET` | Muted lavender `○ AWAITING CONFIRMATION`, reason "Oscillator confirmation required" |

`confidence` shown as a 4-segment bar + numeric `0.72`. Label always clarifies "Heuristic score — not a win probability." Never a progress-circle that implies probability.

### 6.5 Confirmation (`confirmation` + `ConfirmationPolicy`)

Backend-provided via `Signal.confirmation` and the oscillator layer (`OscillatorConfirmedRangeDetector` metadata). The frontend displays the policy alongside the value; it does not compute confirmation.

| State | Badge |
|-------|-------|
| `confirmation == true` | lavender solid dot + `Confirmed (RSI 28.4 ≤ 30)` |
| `confirmation == false` | hollow lavender dot + `Not confirmed (RSI 54.1)` |
| `confirmation == null` + `policy == required` | amber warning + `Awaiting confirmation` |
| `confirmation == null` + `policy == optional` | muted `—` + `Confirmation not present (optional)` |
| `policy == ignored` | gray `Ignored` |

Always show `policy` badge alongside the value so a `NONE` due to missing confirmation is never mistaken for a weak range.

### 6.6 Risk Decision (`RiskDecision.status` + `RejectionReason`)

Backend-provided via `RiskEngine` / preview API. Display is read-only; frontend never re-derives sizing or gates.

| Decision | Visual |
|----------|--------|
| `APPROVED` | green check + `Approved — Risk OK` |
| `REJECTED` | amber block + `Rejected — <RejectionReason>` + diagnostic metadata |

**Rejection reasons** map to human labels (shown in UI, never raw enum):

`NO_SIGNAL` → "No signal"  
`INVALID_SIGNAL` → "Invalid signal bounds"  
`DRAWDOWN_LIMIT` → "Max drawdown reached"  
`DAILY_LOSS_LIMIT` → "Daily loss limit"  
`CONSECUTIVE_LOSS_LIMIT` → "Consecutive loss limit"  
`MAX_OPEN_POSITIONS` → "Max open positions reached"  
`MAX_POSITION_SIZE` / `MAX_PORTFOLIO_EXPOSURE` → "Exposure / size cap"  
`INSUFFICIENT_BALANCE` → "Insufficient balance"  
`LEVERAGE_LIMIT` → "Leverage limit"  
`EXCHANGE_CONSTRAINT` → "Venue constraint (quantity/notional)"  
`MIN_REWARD_RISK` → "Reward/risk below minimum"  
`INVALID_STOP` → "Invalid stop distance"

All rejections use **amber** treatment, never red. Red is reserved for bearish/negative market direction (see §5.1).

Reward/risk line shows `1:2.8 (required 1:2.0) → PASS/FAIL` with color only as secondary cue; label always explicit.

### 6.7 Trade Result (`TradeResult`) & Status

Backend-provided via `StoredTrade`. Green for positive/successful, red for bearish/negative market-aligned losses — consistent with §5.1 — amber not used here.

| Result | Badge |
|--------|-------|
| `WIN` | green `WIN` + `+421.50` (PnL) |
| `LOSS` | red `LOSS` + `-180.00` |
| `BREAKEVEN` | gray `BREAKEVEN` + `≈ 0.00` |
| `OPEN` (`TradeStatus.OPEN`) | sky/neutral `OPEN` + no PnL/result (not "0") |
| `CLOSED` (`CLOSED`) | result badge as above + PnL |

`OPEN` trades never show a result chip — empty state is absence, not a zero.

### 6.8 Oscillator (RSI / Stochastic) — Backend-Provided

RSI/Stochastic values are backend-provided (oscillator detector / analysis API). The frontend renders the line, bands, and confirmation highlights from those values; it does not compute RSI locally for trading decisions.

- **Line:** 1.5px `--color-osc` (lavender), no fill. Point markers only on the latest value when provided.
- **Overbought/oversold:** dashed horizontal lines at backend-configured thresholds (e.g., 30/70), labeled `OS 30` / `OB 70`, tint bands beyond them in `osc-subtle`.
- **Confirmation highlight:** when the backend indicates the oscillator is in a confirming region for the current signal, highlight that segment with a stronger lavender treatment.
- **Divergence (planned — no backend contract in Phase 9):** Intended UX direction is a distinct polyline + endpoint markers on both price and oscillator panes, labeled `BULL DIV` / `BEAR DIV`, with a shape/pattern distinct from the RSI line and range lines (see §7.7). This is a planned product capability. The palette tokens in §5.1 are reserved for this future work. Do not invent API fields, enums, or endpoints; explicitly label backend/domain support as a future implementation requirement wherever divergence appears.

### 6.9 Data Quality & Freshness (`DataQualityReport` / `CandleDataset` / Coverage)

| Quality | Badge |
|---------|-------|
| Clean (`is_clean`) | green dot `Clean` |
| Warnings (`WARNINGS`) | amber dot `Warnings — N issues` |
| Gaps | amber `Gaps` + expandable list of `gap_start_ms → gap_end_ms` |
| Unclosed candles | sky `Includes forming candle` — display notes that analysis uses closed candles only where applicable |
| Stale | amber `Stale — updated Xm ago` (threshold per page, e.g., 5 min) |
| Unavailable | gray `Unavailable` + "No data for this timeframe" (per-timeframe, see §7.8) |

`is_analysis_safe` is shown as a single boolean chip on the chart header/dataset selector. Historical coverage, freshness, gaps, provider/source, and depth are part of the Research Data product requirement (§3.13) and are shown when backend metadata for them is available; otherwise shown as planned/pending.

---

## 7. Chart Specifications

### 7.1 Purpose & Non-Goals

The primary chart is the **single source of visual truth** for market + analysis + decisions. It answers: *What is price doing? Where is the detected range? What regime is the market in? Where am I inside the range? Is there a setup per the backend? If risk approves, what would execution look like per the backend?*

All domain answers are backend-provided. The frontend's job is to make them legible.

Non-goals: drawing tools, indicator playground, TradingView clone. Indicators beyond the backend-provided RSI/oscillator are out of scope for v1.

### 7.2 Layout Anatomy

```
┌─────────────────────────────────────────────────────────┐
│ Chart Header (44px)                                     │
│  Pair  ● RangeStatus  ◆ MarketRegime  Confidence  Quality│
├─────────────────────────────────────────────────────────┤
│                        Y-axis                          │
│  ┌──────────────────────────────────────┐  ┌─────────┐ │
│  │  Candles + Range overlay + Zones     │  │ Price   │ │
│  │  Entry / Stop / Target (backend)     │  │ Scale   │ │
│  │  Signal markers (backend)            │  │ + Range │ │
│  │  Current price line                  │  │ labels  │ │
│  │  Position-in-range vertical meter → │  │         │ │
│  └──────────────────────────────────────┘  └─────────┘ │
│  ┌──────────────────────────────────────┐               │
│  │  Volume (optional, collapsed by default)             │ │
│  └──────────────────────────────────────┘               │
│  ┌──────────────────────────────────────┐               │
│  │  RSI / Stochastic panel (backend)    │  shared X    │
│  │  + divergence (planned, §7.7)        │  time axis   │
│  └──────────────────────────────────────┘               │
│  ←──────────── Time Axis (shared, monospace) ─────────→ │
│  Timeframe selector (segmented) + Crosshair readouts    │
└─────────────────────────────────────────────────────────┘
```

- **Header** left-to-right: pair (`BTC/USDT  67,421.10`), `RangeStatus` badge (VALID/DEGENERATE/INSUFFICIENT_DATA — exactly three), `MarketRegime` badge (including `RANGING`), confidence bar+value, quality/freshness chip. Right-aligned: settings (cog) for toggling volume/zones.
- **Price/y-axis** on the right (trading convention). Monospace, `text-xs`, `tabular-nums`. Range high/low price labels are pinned to y-axis in `--color-range` pills when `RangeStatus` is `VALID` and bounds are actionable; otherwise dashed/muted with explanation.
- **Time/x-axis** shared between candles + oscillator. Monospace. Labels show date when span > 24h, otherwise time. Crosshair shows coordinated tooltip for both panes with backend-provided values.

### 7.3 Candlesticks

- **Body:** `bull` solid green, `bear` solid red, 1px border in same color. Minimum body width 3px, max 14px (scales with time/zoom). No hollow candles in v1.
- **Wick:** 1px `--color-chart-candle-wick`, centered.
- **Volume:** optional histogram behind candles (low opacity 20%), `volume-bull/bear` fills. Toggleable; collapsed by default to preserve vertical space.
- **Hover:** candle highlights with subtle overlay; tooltip shows `O H L C V` monospace for the hovered candle as returned by the backend.

### 7.4 Range Overlay

- **Boundary lines:** 1.5px solid `--color-range` when `RangeStatus` is `VALID` and bounds are actionable, 1.5px dashed at reduced opacity when `DEGENERATE`/`INSUFFICIENT_DATA`. Label on y-axis pill: `R HIGH 68,400.00` / `R LOW 65,100.00`, same color family.
- **Width annotation:** small mono label mid-range on right gutter: `W 3,300 (4.9%)` when width is meaningful.
- **Zones:** full-width horizontal bands between `range_low` and `range_high` (see §6.3) when a valid range exists. Lower/upper edge zones use a restrained neutral tint; the middle NO-TRADE zone uses a restrained indication and a centered `NO-TRADE` label. Readability of candles takes priority — if a strong hatch would impair legibility, the design falls back to a subtle fill or label+edge-lines treatment rather than heavy decoration (§6.3).
- **Current price line:** 1px dashed, label pill with arrow pointer to y-axis. When price is outside the range (backend `PRICE_OUTSIDE_RANGE`), line extends beyond zones and label gets `OUTSIDE` suffix badge.
- **Outside arrow:** small chevron at chart edge pointing outward when outside, with distance from nearest bound (e.g., `+2.1% above high`) calculated for display from backend-provided bounds + market price.

### 7.5 Entry / Target / Stop (when a backend `RiskDecision` preview is available)

- **Entry:** 1px solid sky, label `ENTRY 67,100.00`.
- **Stop:** 1px solid amber dashed, label `STOP 64,800.00`, shaded loss area between entry and stop in `danger-subtle` where applicable.
- **Target:** 1px solid green dashed, label `TARGET 68,900.00`, shaded profit area in `bull-subtle` where applicable.
- **Quantity/notional:** callout on entry line: `Qty 0.142  Notional $9,534` — as provided by the backend decision.
- Entry/stop/target lines appear only when the backend provides an `APPROVED` decision preview (or an explicit hypothetical preview API response); rejected decisions show the attempted levels muted with the rejection reason banner rather than actionable notional.

### 7.6 Signal Markers

All markers reflect the backend `Signal`. Frontend does not decide marker direction or placement beyond mapping the backend result to the chart coordinate.

- **LONG setup:** upward triangle marker below the candle at signal time, green, tooltip "Support edge setup — confidence 0.68 — zone depth 0.82" (values from backend).
- **SHORT setup:** downward triangle above the candle, red.
- **NONE:** small gray dot on the candle's close with tooltip stating the backend `SignalReason` (e.g., "Price in middle — no setup"). Visually distinct from actionable triangles.
- **Confirmation-not-met:** triangle outline (stroke only) + small lavender dot underneath indicating "edge reached, confirmation missing" per backend `confirmation`/`policy`.

Guide lines connecting to the oscillator panel are shown only when the backend indicates confirmation is relevant.

### 7.7 RSI / Oscillator Panel

Values, thresholds, and confirmation context are backend-provided; the panel visualizes them.

- **Line:** 1.5px `--color-osc` (lavender), no fill. Point markers only on the latest value when provided.
- **Overbought/oversold:** dashed lines at backend-configured thresholds (e.g., 30/70), labeled on y-axis, subtle tint bands beyond them.
- **Confirmation highlight:** segment highlight when backend indicates confirming region for the current signal.
- **Divergence — PLANNED (no backend contract in Phase 9):**
  Intended direction: a distinct polyline + endpoint markers on both price and oscillator panes, labeled `BULL DIV` / `BEAR DIV`, using a pattern/shape (e.g., dot-dash + diamond endpoints) and the reserved divergence palette so they are not mistaken for RSI or range lines. Toggleable layer (eye icon in chart header), off by default.
  This section specifies UX intent only. Backend/domain support — divergence detection, canonical fields, and API surface — is explicitly marked as a **future implementation requirement**. The frontend must not invent API fields, enums, or endpoints for it; when no backend data is available it shows the planned-state empty treatment from §3.5 and no markers.

### 7.8 Timeframe Selector & Multi-Timeframe Observability

**Timeframe selector:**
- Segmented/pill group showing canonical timeframes `1m 5m 15m 30m 1h 4h 1d` (from `Timeframe` enum). Active timeframe: filled `surface-3` + `text-primary`. Inactive: `text-secondary`. Timeframes unavailable for the current provider are disabled with tooltip "Not available from this venue."
- Located on the chart's bottom bar, centered. Horizontally scrollable on mobile.

**Multi-timeframe observability (product requirement):**
The terminal must help users compare the same symbol across timeframes. The dashboard provides a multi-timeframe strip (up to 4 cards, e.g., `1h  4h  1d  15m`) so a trader can assess range/regime/signal conditions across timeframes without repeatedly switching the main chart.

- Each card corresponds to an **independent evaluation** for that timeframe (independent `GET /markets/.../candles?timeframe=...` + backend analysis for that timeframe). There is no aggregated multi-timeframe backend endpoint in Phase 9.
- Each card shows the backend-provided status for that timeframe: `RangeStatus`, `MarketRegime`, confidence where applicable, position/edge proximity, signal/confirmation summary, and freshness/quality. Clicking a card promotes that timeframe to the main chart.
- **Per-timeframe states:** each card independently shows loading, stale (`updated Xm ago`), clean/warning, gaps, or unavailable/failed. Partial failures are allowed by design — a failure or staleness in one timeframe does not block the others. The UI must not fabricate analysis for a timeframe where the backend has not returned data.
- Backend aggregation/orchestration for multi-timeframe performance or atomicity is a future implementation decision; the current design specifies UI coordination over available APIs.

### 7.9 Pair Selector

- **Control:** search/combobox (`BTC/USDT`) with venue badge. Recent + watchlist favorites pinned on top. Shows `last price` and `RangeStatus` dot per search result as returned by backend for that symbol/timeframe.
- **Path convention:** URL uses dash form (`BTC-USDT`) to keep URLs unescaped, matching the API (`/markets/BTC-USDT/candles`). Display always uses slash form.

### 7.10 Readability Under Overlays

Layer order (back to front):
`zone fills (lowest, restrained) → grid → volume → candles → range boundary lines → entry/stop/target (when provided) → current price line → signal markers → crosshair → y-axis labels (top)`.
Divergence (when implemented in future) would sit in its own distinct layer and must not be confused with price or indicator lines.
Opacity caps are restrained (zone fills and volume are subtle); no overlay may reduce candle body contrast below WCAG 4.5:1. The middle NO-TRADE zone's legibility must not come at the cost of candle readability.

---

## 8. Component Inventory

Each component spec defines its UX purpose and key visual/behavioral states. All components consume design tokens; no hardcoded values. This section emphasizes domain-facing display semantics and interaction states rather than exhaustive CSS declarations.

### 8.1 Global Navigation / Sidebar

- **Anatomy:** logo/wordmark, nav groups with section labels (`TRADING` etc. `text-xs` `tracking-wide` `text-tertiary`), nav item (icon + label), active indicator (left border `range`), collapse toggle.
- **States:** active, hover, collapsed (icon rail + tooltip), drawer (mobile overlay with scrim).

### 8.2 Top Market/Ticker Ribbon

- **Anatomy:** 36px horizontal flex, chips: `symbol (mono)` + `last (mono)` + `change% (mono, green/red)` + `RangeStatus` + `MarketRegime` chips (two distinct badges, §6.1–6.2). Chips map directly to backend-provided statuses for the active watchlist/timeframe.
- **States:** hover, active (current pair), overflow scrolled with edge fade, skeleton on load, per-chip stale indicator.

### 8.3 Watchlist (Table + Mini Variant) — Scan-Oriented

- **Purpose:** scanning, prioritized by §3.3: symbol, range status, market regime, price/position, edge proximity, signal, confirmation, freshness/quality.
- **Table anatomy:** header row `text-xs` `tracking-wide` `text-tertiary` uppercase, sortable via click with direction indicator. Row 44px (compact 36px), row dividers via `border-subtle`. Cells: symbol (mono + venue badge), last/change (secondary), prioritized scan badges/meters, secondary columns behind column-chooser.
- **Position-in-range meter:** 60px horizontal bar with dot marking backend-provided position; also numeric. Restrained middle indication mirrors chart (§6.3).
- **Confidence bar:** 4 segments, filled per backend `confidence`; color per `RangeStatus` (not a probability).
- **Signal cell:** pill badge + reason tooltip from backend `SignalReason`.
- **Per-row freshness/quality:** age + quality chip (`Clean` / `Warnings` / `Gaps` / `Stale` / `Unavailable`), explicitly flagging unsafe analysis.
- **Mini variant:** shows only the prioritized scan columns + freshness; omits secondary details.

### 8.4 Pair Selector

- **Anatomy:** combobox input (mono, 36px), dropdown list (max 320px), list item 36px with symbol + venue + last + status dots, group headers ("Watchlist", "Recent").
- **States:** idle, focused, dropdown open, no results, loading skeleton.
- **A11y:** `combobox` role, `aria-expanded`, keyboard nav.

### 8.5 Timeframe Selector

- **Anatomy:** segmented control group, `surface-1` track, pill buttons `text-sm` mono, 32px tall. Active: `surface-3` + `text-primary`. Disabled: `text-disabled` with tooltip explaining provider unavailability.
- **States:** active, hover, disabled, per-timeframe loading/stale/unavailable (§7.8).

### 8.6 Primary Trading Chart

- See §7. Canvas-based (e.g., Lightweight Charts). Header + chart canvas + oscillator pane + time axis composed together. Colors, fonts, line widths from tokens. Values are backend-provided.

### 8.7 Range Overlay

- Two horizontal lines + zone fills + labels (see §6.3 / §7.4). Implemented as chart overlays coordinated with backend-provided bounds. Middle zone is restrained per §6.3 — legible but not visually overpowering. Config: `showZones`, with restrained middle indication.

### 8.8 Signal Card

- **Anatomy:** card `surface-1` `radius-md` `border-subtle`. Header: direction pill + confidence bar+numeric + position meter (all backend-provided). Body: reason line, policy+confirmation row (lavender), zone depth, metadata disclosure ("Details" shows `range_mode`, `range_status`, `confirmation_present`, oscillator value as provided by backend).
- **States:** LONG/SHORT/NONE variants, loading (skeleton), error (amber banner with reason), no-data (muted "No range — no signal"), stale/unsafe analysis flag.
- **Data:** `Signal` + `RangeState`/`MarketRegime` context + `RiskDecision` preview as received from backend — display only.

### 8.9 RSI / Divergence Panel

- **Purpose:** visualize backend-provided oscillator values and confirmation context; divergence is planned (§7.7).
- **Anatomy:** 120px pane sharing x-axis. Y 0–100. Gridlines at configured thresholds. RSI line, threshold bands, confirmation highlight segment where backend indicates, latest value dot when provided.
- **Divergence layer (planned):** reserved visual pattern distinct from RSI and range; no markers rendered until backend support exists.
- **Empty:** when backend reports insufficient data for oscillator, show dashed 50 line + "Insufficient data for oscillator" centered label (from backend indication).

### 8.10 Position Table (Operational)

- **Anatomy:** table with open/closed tabs. Columns: `Symbol | Side (LONG/SHORT pill) | Qty (mono) | Entry | Mark | Unrealized PnL (with R multiple) | Liquidation | Leverage` — as provided by the relevant backend/account source when available. Positions are current trading state, distinct from journal history.
- **States:** no positions empty state, loading, error, paper-mode notice where applicable.

### 8.11 Order / Execution Panel (Paper / Read-Only)

- **Anatomy (Phase 9):** card `surface-1`, header `EXECUTION PREVIEW — PAPER MODE` (amber subtle badge + tooltip: paper/read-only, no live orders). Fields as provided by backend `RiskDecision` preview: `Entry | Stop | Target | Qty | Notional | Leverage | Reward:Risk | Fees | Slippage`. Status banner: `APPROVED` (green) or `REJECTED — reason` (amber) with metadata expansion. CTA button disabled with label "Live trading not enabled."
- **Execution capability note:** This panel's capability is determined by system execution mode (paper/read-only in Phase 9), not by whether an exchange connection exists. See §3.12.

### 8.12 Risk Summary

- **Anatomy:** horizontal strip card, 4–6 metric cells (`label xs tertiary` + `value mono md` + progress bar). Metrics as provided by backend: `Equity`, `Available`, `Exposure`, `Drawdown`, `Daily Drawdown`, `Consecutive Losses`. Each cell shows progress toward its limit, with `OK` / `AT LIMIT` / `BLOCKED` using amber for blocked (not red).
- **Preview row** (when backend preview is available): `Next trade: Qty 0.142  Notional $9,534  Risk $95  R:R 1:2.8  ✓ Approved` — values from backend.
- **Blocked state:** amber background tint + warning icon when any backend-reported gate is at limit.

### 8.13 Strategy Configuration Panel

- **Anatomy:** form with three section cards (`Range` / `Signal` / `Risk`) mapping to the backend payload (`range_config` / `signal_config` / `risk_config`). Inputs: selects for enums, numeric fields per engine validation, toggles for booleans. Each field shows engine validation message inline. Footer: `Save` + `JSON Preview` toggle + `config_hash` display (copyable).
- **States:** pristine, dirty, saving, validation error, success.

### 8.14 Alert Feed

- **Anatomy:** vertical feed, grouped by day. Item: 56px row with `icon | symbol/timeframe (mono) | badge (kind) | detail | timestamp` + quality chip if present. Kinds: `Range` (neutral), `Signal` (green/red/gray), `Quality` (amber), `System` (info), and — planned — `Regime` (including `RANGING` transitions) and scan hits.
- **States:** empty, loading, error. Click → navigates to relevant chart/timeframe.

### 8.15 Equity Curve

- **Anatomy:** area/line chart (monotone curve), Y = equity, X = time (`timestamp_ms`) as provided by backend (`EquityPoint` / aggregated stats). Tooltip: `Equity | Peak | Drawdown` per point. Zoom via brush, reset button. Max drawdown segment highlighted with amber dashed bracket when backend reports it.
- **Comparison mode:** up to 4 curves overlaid, distinct line styles + legend, not color-only.

### 8.16 Performance / Statistics Cards

- **Anatomy:** grid of 8–12 stat cards, each `surface-1` `radius-md` `border-subtle` `padding 16px`. Layout: `label xs tertiary uppercase` top, `value 2xl mono bold` center, `context xs secondary` bottom.
- **Stats:** `total_trades | wins/losses/breakevens | win_rate | profit_factor | expectancy | average_win/loss | average_r | total_realized_pnl | max_drawdown` — all as computed/supplied by the backend. Null values display `—` with tooltip — never `0` or invented.
- **Segmentation:** when backend provides regime/zone breakdowns, allow segmentation by `MarketRegime` (including `RANGING`).

### 8.17 Trade History / Journal Table (Historical & Research)

- **Anatomy:** table, 44px rows, `trade_id` short hash + copy icon, monospace. Columns: `Trade ID | Symbol | Side pill | Qty | Entry → Exit | Realized PnL (green/red per §5.1) | Fees/Slippage (muted) | Result badge | R (realized_r) | Opened → Closed | Strategy`. Row click opens drawer with `TradeContext` (range bounds/width/confidence, `position_in_range`, `confirmation`, `risk_percent`, regime/zone extra as provided by backend).
- **Purpose:** historical trades, performance, and research. Distinct from `/positions` operational state.
- **States:** empty, filtered-empty, loading, error.

### 8.18 Backtesting Configuration / Results

- **Config form:** card with date pickers (`start_ms`/`end_ms`), strategy select, numeric inputs (`initial_capital`, `fee_rate`, `slippage_rate`, `warmup_candles`). Inline validation per `BacktestConfig`.
- **Results header:** identity row (`run_id short` + copy, `config_hash` short + copy, `engine_version` badge, `period`).
- **Results body:** statistics cards (§8.16) + equity curve (§8.15) + regime/zone bar charts + trades table (scoped). Regime charts include `RANGING` as a first-class bucket (see §6.2).
- **Compare view:** selector checkboxes + "Compare 2–4 selected" → split view with overlaid curves + stat diff table.

### 8.19 System Status

- **Anatomy:** card row: `status pill (ok/degraded/down)` + `schema_version` + `engine_versions` + `user_count` + `dataset_count` + `market_data_provider` + `time`. System health uses its own infra palette (infrastructure red `#DC2626` is allowed here — it does not conflict with candle red because status is a filled dot + explicit text label and the token is distinct).
- **States:** ok (green), degraded (amber), down (infra red) — always with text label, not color-only.

### 8.20 Exchange Connection Cards

- **Anatomy:** card `surface-1` `radius-md` `border-subtle`, header with `venue_id` (mono) + `display_name` + `status badge` (`connected` green / `error` amber / `disabled` gray) + `sandbox` pill (sky when true). Body: `credential_ref` (mono xs truncated) + `updated_at`. Actions: `Test` (optional) + `Disconnect` (danger button, confirm dialog).
- **Connect dialog:** form with validation (`venue_id`, `api_key`, `secret`); secrets never stored or displayed client-side. See §3.12 for credential / market-data / account / execution separation.
- **DEX note:** no DEX fields are added to this CEX API-key form (see §3.12).

### 8.21 Admin User Table

- **Anatomy:** table with columns `id short | email | role pill (OWNER sky / USER gray) | active | created_at | last_login | actions`. Actions menu: `Activate/Deactivate`, `Change Role`, `Revoke Sessions`. Create User button opens dialog (email/password/role).
- **States:** loading, empty, error, action loading.

### 8.22 Audit Log

- **Anatomy:** table `timestamp (mono xs) | actor | action (mono sm) | resource_type | resource_id (short) | outcome (success/failure pill) | metadata (collapsible JSON monospace xs)`. Filters: action, resource_type, actor, date range. Virtualized rows for large logs.
- **States:** empty, loading, error.

### 8.23 Modal / Dialog

- **Anatomy:** centered card `surface-2` `radius-lg` `shadow-lg` + scrim `bg-overlay` (backdrop blur 4px). Header: `title lg medium` + close `×`. Body: `text-base` `text-secondary`. Footer: right-aligned actions (`Cancel` ghost + `Confirm` primary or `Danger` amber). Widths: sm 400px, md 560px, lg 720px.
- **States:** open (fade + scale, 180ms), focus-trapped, Esc to close.
- **A11y:** `role="dialog"`, `aria-modal`, focus trap, return focus on close.

### 8.24 Toast / Notification

- **Anatomy:** stack bottom-right (desktop) / top-center (mobile), 360px wide, `surface-2` `radius-md` `shadow-md` + left accent bar 3px (success green / amber for warning/danger / sky for info). Content: `title` + `message` + optional action. Auto-dismiss 4s (success/info), sticky (danger/error until dismissed). Queue max 3 visible.
- **Variants:** `success`, `warning` (amber), `danger` (amber), `info` (sky). Red is not used for toasts; market-loss red is not a notification color.
- **Motion:** slide-in (180ms `ease-out`), respect reduced-motion (fade only).

### 8.25 Historical Research Data Coverage Component

- **Purpose:** make §3.13 observable in the UI wherever historical depth matters (Research Data page, backtest setup, watchlist/analysis headers).
- **Anatomy:** per-symbol/timeframe coverage cards: header `symbol + timeframe`, body showing `date range (first → last)`, `candle count / depth`, `freshness (updated Xm ago)`, `quality chip + gap count`, `source/provider`, `analysis-safe` chip. Empty/unavailable fields show planned-state placeholder ("Not yet exposed — requires future backend work").
- **States:** loading per symbol/timeframe, empty (no coverage), error, stale.

### 8.26 Empty / Loading / Error States

- **Empty:** centered outline illustration + title + one-line explanation + primary CTA. Distinct from error (no warning color).
- **Loading:** skeleton — shimmer `surface-2 → surface-3`, matching the layout of the content it replaces (no generic spinner on tables). Per-timeframe skeletons are independent (§7.8).
- **Error:** card `danger-bg` + amber left border + human message + `Retry` + `request_id` mono xs (from `RequestIdMiddleware`) + optional `Details` disclosure. Form errors shown inline + banner.

---

## 9. Responsive Behavior

### 9.1 Breakpoints

| Token | Value | Name |
|-------|-------|------|
| `bp-sm` | 640px | — |
| `bp-md` | 768px | tablet |
| `bp-lg` | 1024px | desktop |
| `bp-xl` | 1280px | workstation |
| `bp-2xl` | 1536px | wide |

Primary design at `bp-xl`. Implement mobile-first CSS, enhance to workstation.

### 9.2 Rules

- **No content loss.** Every data point available on desktop is reachable on mobile — via progressive disclosure (drawers, tabs, "Show more") not omission. Scan-prioritized watchlist columns (§3.3) remain visible on mobile; secondary columns move to expanded card detail.
- **No table as-is on mobile.** Tables either horizontally scroll with sticky first column + column chooser, or collapse to cards at `<768px`. Never a squashed table where numbers are truncated without affordance.
- **Chart always visible above the fold** on every route where it appears, even on mobile (min 320px height). Chart is primary; supporting panels do not displace it.
- **Touch targets:** minimum 44×44px on mobile, per WCAG 2.5.5.
- **Typography scales down 1 step** on mobile (base 13px → 12px) to preserve density without horizontal scroll.

### 9.3 Navigation Adaptation

- `≥1024px`: sidebar fixed, collapsible to 64px rail.
- `<1024px`: sidebar is an overlay drawer triggered by hamburger in top bar; ribbon becomes swipeable; global search/command palette remains available.

---

## 10. Accessibility

### 10.1 Contrast

- All text meets WCAG AA: `text-primary` (#E6EAF0) on `bg-surface-1` (#11161E) = 13.2:1. `text-secondary` (#9AA6B8) on same = 6.8:1. `text-tertiary` never used below `text-sm` on dark backgrounds; when used, it is always ≥4.5:1 via careful pairing.
- Chart grid/axis at 3:1 minimum (non-text graphics). Candle bodies exceed 4.5:1 against zone fills (restrained fills preserve this).
- Status badges use fill + text + icon trio; contrast tested for each pairing. Amber on dark passes AA for large text.

### 10.2 Keyboard Navigation

- Full keyboard operability: Tab through interactive elements in logical order (nav → ribbon chips → selectors → chart controls → tables). No keyboard trap.
- **Focus states:** 2px solid `--color-border-focus` outer ring + 1px `bg-base` inner ring (double ring for visibility on dark). Focus visible only via `:focus-visible`.
- **Shortcuts:** `Cmd+K` command palette, `G then D` go to dashboard, `G then W` watchlists, `G then B` backtests, `?` shortcut help overlay.
- **Chart keyboard:** Arrow keys move crosshair; `+`/`−` zoom; `0` reset; focus ring on chart canvas.

### 10.3 Non-Color Status Indicators

Every status uses **at least two channels**: color + icon/shape + text label.

- Range: color badge + dot/hollow + text ("Valid", "Degenerate — flat data").
- Regime: color + arrow/hatch + text ("Ranging", "Trending Up").
- Signal: color + triangle direction + text reason.
- Risk: color + check/block icon + text reason.
- Trade result: color + `WIN`/`LOSS` text + `+`/`−` sign.

Never color alone.

### 10.4 Tables & Forms

- Tables: `role="table"`, proper `th` with `scope="col"`, sortable headers have `aria-sort`, row selection uses `aria-selected`.
- Forms: each `input` has associated `label`, `aria-invalid` + `aria-describedby` pointing to error message. Required fields marked with `*` and `aria-required`.

### 10.5 Motion

- All transitions respect `prefers-reduced-motion: reduce` → duration 0, no movement (fade only or instant).
- No auto-playing animation. Skeletons and spinners are the only continuous motion; they pause when the tab is hidden.

### 10.6 Screen Reader Considerations

- Chart has a `table` fallback (visually hidden) with the same OHLCV + range/regime data for SR users; canvas has `role="img"` + `aria-label` summarizing the backend-provided state ("BTC/USDT 1h — Valid range 65,100 to 68,400, regime ranging, price in middle no-trade zone, no setup per backend").
- Live price updates use `aria-live="polite"` throttled (5s) to avoid SR spam.
- Toasts use `role="status"` (info/success) or `role="alert"` (danger).

---

## 11. Core User Flows

Each flow lists entry → steps → success → error branches. Screens reference §3 routes. All domain values are interpreted as received from the backend; user-initiated evaluations are requested from the backend and rendered when returned.

### 11.1 Flow 1 — Sign In → Dashboard

1. User visits `/` unauthenticated → redirect to `/login`.
2. Enters `email` + `password` → clicks `Sign In`.
3. `POST /auth/login` → `200 {access_token, user}`. Token stored (memory + `localStorage` or httpOnly cookie if later adopted — abstracted behind auth client).
4. Redirect to `/` Dashboard. Ribbon and sidebar appear. Dashboard fetches `GET /watchlists` (default watchlist), then `GET /markets/BTC-USDT/candles?timeframe=1h&limit=200` and requests available range/regime/signal analysis for that symbol/timeframe via the backend's analysis APIs (frontend does not compute range, regime, or signal locally).
5. **Success:** chart renders with backend-provided candles + range overlay + regime badge + signal card. No flashes of unauth content.
6. **Errors:** 401 → "Invalid credentials" banner. 423/inactive → "Account disabled — contact owner." Network failure → retry banner with request_id. Token expired mid-session → intercept 401, redirect to login, toast "Session expired."

### 11.2 Flow 2 — Add Pair → Watchlist → Inspect Range

1. On `/watchlists/:id` or Dashboard mini-watchlist, clicks `Add Pair`.
2. Dialog: `Symbol` (e.g., `BTC/USDT` — validates against known symbols or free-form with backend normalization), `Venue` (select), `Notes` (optional).
3. `POST /watchlists/:id/items` → 201 `WatchlistItem`. Row appears optimistically, reconciled on success.
4. Clicks the new row (or ribbon chip) → navigates to Dashboard focused on `BTC/USDT`. Dashboard fetches candles and requests backend range/regime/signal analysis for that symbol/timeframe.
5. Chart shows overlay per backend `RangeStatus`: if `VALID` → solid boundaries + restrained zones; if `DEGENERATE` → dashed + reason "Flat data — no tradable structure" (amber, not red); if `INSUFFICIENT_DATA` → placeholder + "Need 20 candles, have 8." `MarketRegime` shown alongside (e.g., `RANGING` vs `TRENDING_UP`) as separate context.
6. Watchlist row scanning state updates to reflect the latest backend-provided freshness/quality for that symbol/timeframe.
7. **Errors:** 400 invalid symbol → field error. 409 duplicate → "Already in this watchlist." 404 watchlist not found → toast + redirect to `/watchlists`.

### 11.3 Flow 3 — Select Timeframe → Compare Range Conditions

1. On Dashboard chart header, clicks timeframe pill (e.g., `4h`).
2. Dashboard fetches candles for that symbol/timeframe and requests the corresponding backend analysis (range/regime/signal) for that timeframe. No client-side detection is performed.
3. Chart redraws with whatever the backend returns for that timeframe: boundaries/width/confidence, signal/confirmation, and oscillator values.
4. **Multi-timeframe comparison (without leaving):** the trader glances at the multi-timeframe strip (§7.8) — up to 4 cards for different timeframes of the same symbol, each populated by an independent backend evaluation. Per-card loading, stale ("updated 4 min ago"), quality warnings, and unavailable/failed states are shown independently; partial failures do not block other cards. The strip might read "Range valid on 1h and 4h but degenerate on 5m" — but only when those are the backend results for those timeframes.
5. Clicking a mini promotes it: main chart timeframe switches to that value (same as step 1).
6. **Errors:** timeframe not supported by provider → pill disabled, tooltip "Not available from this venue." 502 `provider_error` → amber banner "Market data temporarily unavailable — retry in Xs" + cached data shown with per-timeframe staleness badge.

### 11.4 Flow 4 — Evaluate Signal → Inspect RSI/Confirmation → Inspect Risk

1. Dashboard signal card shows a backend-provided `LONG` (`SUPPORT_EDGE_SETUP`) with `confidence 0.68`, `position 0.18` (lower edge), `policy: optional`, `confirmation: true (RSI 28.4 ≤ 30)`.
2. Trader looks at the oscillator panel: the backend-provided RSI at 28.4 inside the oversold band is rendered there. Divergence is not shown — the divergence section displays its planned-state empty treatment (§3.5 / §7.7); no markers are rendered because there is no backend divergence contract in Phase 9.
3. Trader requests a risk preview for the current actionable backend signal (e.g., `Preview Risk` action). The frontend requests the backend's `RiskDecision` preview for that signal and account context and renders the result: `APPROVED — Qty 0.142  Notional $9,534  Stop 64,800  Target 68,900  R:R 1:2.8  Fees ~$9.50  Slippage ~$4.70` or `REJECTED — reason` with diagnostics. No `RiskEngine` calculations are performed on the frontend.
4. If `REJECTED` (e.g., `MAX_OPEN_POSITIONS`), banner shows amber "Rejected — Max open positions (5/5) — close a position or raise cap in Risk."
5. **Branch — confirmation required but not met:** backend `Signal` is `NONE` with `CONFIRMATION_NOT_MET`; signal card shows `○ AWAITING CONFIRMATION` (outline triangle) and the backend-provided oscillator value. Trader either waits or adjusts `confirmation_policy` in Strategy config for future evaluations.
6. **Branch — price in middle or outside:** backend `SignalReason` is `PRICE_MID_RANGE` or `PRICE_OUTSIDE_RANGE`; card shows `— NO SETUP — Price in middle (no-trade) zone` or `— OUTSIDE` (gray). No actionable triangle. The UI makes the backend-determined absence explicit, not ambiguous.

### 11.5 Flow 5 — Configure Strategy

1. Navigate to `/strategies`. List shows existing configs with `active` toggle.
2. Clicks `New Strategy` or edits an existing one.
3. Form: Section 1 `Range` — picks `mode` (e.g., `oscillator_confirmed`), fills `lookback: 100`, `oscillator: rsi`, `oversold: 30`, `overbought: 70`, `osc_period: 14`. Section 2 `Signal` — `lower_edge_zone: 0.25`, `upper_edge_zone: 0.25`, `confirmation_policy: required`. Section 3 `Risk` — `risk_per_trade: 0.01`, `stop_method: range`, `target_method: opposite_range_edge`, `max_open_positions: 5`, etc.
4. Clicks `Save`. Client validates required keys (`range_config`, `signal_config`, `risk_config` must be objects). `POST /strategies` → 201 `StrategyConfig`. `config_hash` displayed (short hash, copyable). Card appears in list.
5. **Errors:** 400 missing key → field error. Engine deeper validation (e.g., `edge_zones overlap`) shown inline from backend response. Network error → retry.

### 11.6 Flow 6 — Connect Exchange

1. Navigate to `/exchanges`.
2. Clicks `Connect Exchange`.
3. Dialog: `Venue` (e.g., `binance`), `Display Name` (e.g., "Binance Main"), `API Key` (password input), `Secret` (password input), `Password/Passphrase` (optional), `Sandbox` toggle. This form is for CEX API-key connections only (see §3.12); DEX flows are out of scope.
4. `POST /exchanges/connections` → 201 `ExchangeConnection` (no secret in response — only `credential_ref`). Card appears with `status` badge. Connection alone does not imply market-data, account, or execution capabilities — those are reported separately by the backend (see §3.12).
5. **Errors:** 400 missing fields → field errors. 502 provider error (invalid keys) → amber banner "Failed to verify credentials — check keys and venue." Secrets never logged or displayed. `DELETE /exchanges/connections/:id` removes metadata + credential. System remains paper/read-only regardless of connection status.

### 11.7 Flow 7 — Run Backtest → Inspect Results → Compare Performance

1. Navigate to `/backtests`.
2. Fills config form: picks `strategy`, `symbol: BTC/USDT`, `timeframe: 1h`, `period: 2024-01-01 → 2024-06-01` (maps to `start_ms`/`end_ms`), `initial_capital: 10000`, `fee_rate: 0.0005`, `slippage_rate: 0.0002`, plus `regime_lookback`/`warmup_candles` where applicable.
3. Clicks `Run Backtest`. Button shows loading. `POST /backtests` → deterministic backend replay → returns `BacktestResult` + persisted `BacktestRunRecord`.
4. Result view (`/backtests/:runId`): statistics cards render (wins/losses/win_rate/profit_factor etc. — `profit_factor` shows `—` if no losses, as computed by backend). Equity curve renders from backend `EquityPoint` data. Regime/zone breakdowns show `regime_counts` (including `RANGING`) and `zone_counts`. Trades table scoped to run. Segmentation by `MarketRegime` (including `RANGING`) is available for research.
5. **Compare:** selects 2–4 runs → `Compare` → split view with stats diff + overlaid equity curves (distinct line styles) + regime-segmented comparison where backend provides breakdowns.
6. **Errors:** 400 `start_ms >= end_ms` → field error. No candles for period → amber empty state including quality/coverage context. 502 market data failure → amber banner.

### 11.8 Flow 8 — Review Historical Trades / Statistics

1. Navigate to `/journal` (historical) or `/positions` (operational). The two routes are distinct (§3.6 / §3.11).
2. Statistics cards render backend-provided `TradeStatistics` (or `GET /trades`-derived aggregations as exposed by the API). Shows `total_trades | wins | losses | breakevens | win_rate | profit_factor | expectancy | average_win/loss | average_r | total_realized_pnl`. No values are computed or invented on the frontend.
3. Equity curve (cumulative realized PnL from closed trades) renders from backend data. Label notes "Trade-close granularity — not intraday."
4. Table shows trades with filters (`symbol`, `result`, `status`). Clicks a row → drawer opens with `TradeContext` detail (range bounds/width/confidence, position_in_range, confirmation, risk_percent, regime/zone extra as provided by backend). Filtering/grouping by `MarketRegime` (including `RANGING`) is available where backend context supports it.
5. **OWNER branch:** `GET /trades` returns all trades; `GET /admin/trading-activity` aggregates across users.
6. **Errors:** no trades → empty state "No trades yet — run a backtest or check positions." Filter yields zero → "No trades match filters — clear filters." Incomplete history is framed as a research-data coverage issue (see §3.13) rather than a UI fabrication.

### 11.9 Flow 9 — Admin → Users / System Health / Audit Activity

1. Owner navigates to `/admin`. Overview shows `SystemHealth` KPIs + trading activity totals + research data summary where backend exposes it.
2. **Users:** goes to `/admin/users` → table of users. Creates a new user: dialog `email/password/role` → `POST /admin/users` → 201 appears in table. Deactivates a user: `POST /admin/users/:id/active {active:false}` → row goes gray "inactive." Changes role, revokes sessions — each with confirm dialog + toast.
3. **System health:** `GET /admin/system-health` shows `status ok`, `schema_version`, `engine_versions`, `user_count`, `dataset_count`, `market_data_provider`, `time`. Degraded/down states use amber / infrastructure red (distinct token, not market red) with text labels.
4. **Audit:** goes to `/admin/audit` → `GET /admin/audit-log?limit=100` → table of `AuditEvent` with filters. Append-only — no delete affordance.
5. **Trading activity:** `GET /admin/trading-activity` shows aggregate `totals` + `recent_backtests`.
6. **Errors / auth:** non-OWNER navigating to `/admin/*` → client redirects to `/` + toast "Admin access required"; server returns 403 on direct API call. Inactive OWNER token → 401 → logout.

---

## 12. States & Edge Cases

### 12.1 Global

| State | Treatment |
|-------|-----------|
| **Loading** | Skeletons matching layout (not a centered spinner on full pages). Per-timeframe skeletons are independent (§7.8). |
| **Empty** | Centered outline illustration + title + one-line explanation + primary CTA. Distinct from error (no warning color). |
| **Error (recoverable)** | Amber card/banner with human message + `Retry` + `request_id` (mono xs) + optional `Details` disclosure. Not red. |
| **Error (fatal)** | Full-page error card + "Return to Dashboard" + request_id. |
| **Offline** | Amber top banner "You appear to be offline — data may be stale" + stale badges per §6.9. |
| **Stale / auto-refresh** | Data chips show "Updated 3 min ago" (`text-xs tertiary`). Per-timeframe stale states (§7.8) and watchlist per-row stale states (§3.3) are explicit. Optional auto-refresh toggle per page. No fabricated data. |

### 12.2 Chart-Specific Edges

- **INSUFFICIENT_DATA (`RangeStatus`):** chart renders axes + grid, candles if any, but range lines are faint/dashed, zone fills absent/restrained, centered placeholder "Insufficient data — need 20 candles, have 8. Add more history or reduce lookback." `MarketRegime` may also be `INSUFFICIENT_DATA` — both shown.
- **DEGENERATE (`RangeStatus`):** full candles, dashed range lines (amber context, not red), warning badge + reason tooltip ("Flat data — zero volatility" or as backend returns), signal forced to `NON_TRADABLE_RANGE` per backend, no actionable triangles.
- **TRENDING vs RANGING context:** when `MarketRegime` is `TRENDING_UP`/`TRENDING_DOWN`/`TRANSITIONAL` and `RangeStatus` is `VALID`, both badges are shown. They are separate concepts (§6.1–6.2); the UI does not hide either, the trader decides. No combined "TRENDING range status" badge exists.
- **RANGING-specific:** `MarketRegime.RANGING` is shown as a distinct badge and may be used for watchlist filtering and research segmentation (see §6.2).
- **Gaps / quality warnings:** banner above chart "⚠ 2 gaps detected (00:00–04:00 UTC) — analysis excludes gap periods" + expandable issue list. Gaps rendered as vertical dashed lines on time axis when backend reports them.
- **Unclosed / forming candle:** rendered with reduced opacity + dashed outline, labeled `FORMING`. Analysis is based on backend-reported closed candles; legend notes "Based on 199 closed candles; 1 forming excluded" when backend so indicates.
- **Outside-range:** price line beyond zones, outside arrow + distance label, backend signal shows `PRICE_OUTSIDE_RANGE` — also NO-TRADE.
- **NaN bounds / zero width:** bounds not rendered; chart shows "No actionable range bounds" as returned/derived from the backend's non-tradable state — not a frontend invention.
- **Per-timeframe unavailable:** when a timeframe has no data for the symbol, its card/strip entry shows `Unavailable — no data for this timeframe` (gray) rather than a fabricated status.

### 12.3 Data Edges

- **Null stats:** `win_rate`, `profit_factor`, `average_r` etc. show `—` with tooltip "Not derivable — needs at least N wins/losses" — never `0` or `Infinity`. Values are backend-determined.
- **Zero/negative equity, max drawdown at limit:** risk strip shows blocked state (amber fill + warning icon) as reported by backend gates; no frontend gate math.
- **Large numbers:** prices use `,` grouping + asset-appropriate precision, percentages `1 decimal`, PnL `2 decimals` + `+`/`−` sign, `R` multiples `2 decimals`. Monospace tabular-nums throughout.

### 12.4 Auth & Permission Edges

- **First registration:** email/password → becomes `OWNER`. Subsequent `POST /auth/register` calls fail with 400 "Registration closed — ask an owner to create your account" — the UI shows that message when attempting to register while a user already exists.
- **Inactive user:** login returns 401/403 → "Account inactive — contact owner."
- **Token refresh:** stateless bearer tokens; expiry handled via 401 intercept + redirect, not silent refresh.
- **Role escalation:** only `OWNER` can call `POST /admin/users/:id/role` — UI never shows the control to `USER`, but the server is the enforcer.

### 12.5 Research Data Edges

- When historical coverage, freshness, gaps, or provider/source metadata is not yet available from the backend, the research data components show explicit planned-state placeholders ("Not yet available — requires future backend work") rather than omitting the dimension or fabricating it. See §3.13 / §8.25.

---

## 13. Design Principles

These are the non-negotiable rules every future frontend PR must satisfy. A proposal that violates any principle must be explicitly justified and approved.

1. **Range is the primary object, not the indicator.** Range detection defines tradability; the oscillator is a confirmation layer. The chart, badges, and signal panel must always make this hierarchy obvious — never let RSI visually compete with range bounds (lavender vs. slate, panels separated).

2. **Middle is NO-TRADE and outside is NO-TRADE — both must be legible, but readability wins.** The middle zone is labeled `NO-TRADE` and given a restrained visual indication that is unmistakable at a glance, without impairing candle/zone readability through heavy hatch or large opaque decoration. Outside-range has its own explicit `OUTSIDE` indication. If a treatment hurts scan or contrast, simplify it per §6.3/§7.4 rather than decorating further.

3. **`RangeStatus` has exactly three values; `MarketRegime` is separate.** `VALID` / `DEGENERATE` / `INSUFFICIENT_DATA` are three distinct looks (badge color + icon + text + chart treatment). `MarketRegime` (`RANGING` / `TRENDING_UP` / `TRENDING_DOWN` / `TRANSITIONAL` / `INSUFFICIENT_DATA`) is a separate research/market-condition concept; the two may be displayed together but must never be presented as the same status. `RANGING` is not a synonym for `VALID`.

4. **Use the correct semantic channel.** Green for positive/bullish/successful outcomes where appropriate (bullish candles, up-price, LONG, WIN), red for bearish/negative market direction where appropriate (bearish candles, down-price, SHORT, LOSS), amber for risk/rejection/warning/blocked actions, slate/neutral for range structure, lavender for oscillator/confirmation. Red is never a generic error or risk color.

5. **Confirmation policy is always visible.** `required` / `optional` / `ignored` appears as a badge next to the confirmation value on every signal presentation. A `NONE` due to `CONFIRMATION_NOT_MET` must explicitly state the policy alongside backend-provided values.

6. **Every number gets its expected precision and its expected font.** Prices, quantities, PnL, percentages, and timestamps are monospace, tabular-nums, with consistent decimals and thousand separators. Sans is for prose.

7. **No silent zeros, no invented data.** Null stats show `—` not `0`. `profit_factor` with no losses is `—` not `∞`. Unreported `volume` is `—` not `0`. Quality gaps are disclosed, not interpolated. Missing analysis is shown as loading/stale/unavailable per source — never fabricated.

8. **Dense by default, but never chaotic.** Information density is high (13px base, 44px rows, compact watchlists) — but separation is achieved with borders and subtle surfaces, not with card shadows, gradients, or pill excess. Supporting information (watchlist, multi-timeframe strip, secondary table columns) is scan-prioritized and progressively disclosed so the chart remains primary.

9. **Desktop workstation first, responsive without loss.** All decisions are made for the ≥1280px workstation first. Mobile stacks and collapses but never omits a backend-provided status or metric — it discloses progressively. If a mobile design hides `RangeStatus`, `MarketRegime`, or `confirmation` behind a second tap, it must have a strong justification.

10. **Every status shows color + icon + text.** No single-channel encoding. Colorblind users and fast scanners rely on shape and label as much as hue. Divergence (planned) must also satisfy this when implemented — its markers use distinct shape/pattern, not color alone.

11. **Configuration is reproducible and copyable.** `strategy_id`, `config_hash` (short + full on copy), `config_version`, `engine_version`, `run_id`, `request_id` are always shown mono, copyable with a single click, and preserved in shareable URLs where applicable.

12. **The backend owns domain truth; the frontend renders it.** The UI requests analysis from the backend and renders what it returns — `RangeStatus`, `MarketRegime`, `Signal`, `RiskDecision`, `DataQualityReport`, `TradeStatistics`, `StoredTrade`, `BacktestResult` — without re-deriving or re-interpreting domain logic. The frontend may orchestrate multiple requests (e.g., per-symbol watchlist scanning, per-timeframe observability) and handle per-request states, but it does not reproduce or invent engine calculations. Missing data is shown as missing.

---

## 14. Capabilities & Validation

**Checked:** 2026-08-26 against `backend/src/*` and `backend/tests/*`. Only `DESIGN.md` was modified; no source code was changed.

### 14.1 What Phase 1–9 Actually Provides (Confirmed)

- **Range detection** — `RangeStatus` (`VALID` / `DEGENERATE` / `INSUFFICIENT_DATA`), `RangeState` (high/low/width/confidence/metadata + `is_tradable`), detectors/modes (`structural`, `volatility`, `manual`, `oscillator_confirmed`), `RangeEngineFactory`.
- **Oscillator confirmation** — `OscillatorConfirmedRangeDetector` layer with RSI / Stochastic, thresholds (`oversold`/`overbought`/`osc_period`), confirmation metadata (`confirmation` boolean + `oscillator_value`), `confirmation` distinct from range definition.
- **Signals** — `Signal` (`direction`, `reason`, `position_in_range`, `confidence` heuristic, `confirmation`), `SignalReason` (`NON_TRADABLE_RANGE`, `PRICE_OUTSIDE_RANGE`, `PRICE_MID_RANGE`, `CONFIRMATION_NOT_MET`, `SUPPORT_EDGE_SETUP`, `RESISTANCE_EDGE_SETUP`), `ConfirmationPolicy` (`required`/`optional`/`ignored`), edge zones `lower_edge_zone`/`upper_edge_zone`.
- **Risk** — `RiskDecision` (`APPROVED`/`REJECTED` + `RejectionReason`), gates (`max_drawdown`, `max_daily_drawdown`, `max_consecutive_losses`, `max_open_positions`, notional/exposure caps, leverage), `stop_method`/`target_method`, fee/slippage and reward/risk economics, `TradingConstraints`.
- **Exchange (CEX)** — `CredentialStore` + `ExchangeConnection` metadata + `credential_ref`, `TradingConstraints`, normalized `Order`/`Position`/`Ticker`/`OrderBook`/`Balance`. Secrets never returned to the frontend.
- **Execution posture** — Phase 9 `PAPER/READ-ONLY`; no endpoint places live orders; the API does not expose a direct `HTTP → Exchange` order path.
- **Market data** — `MarketDataService` + `CandleDataset`/`CandleSeries`, canonical `Timeframe` (`1m`–`1d`), `DataQualityReport` (`issues`, `gap_ranges`, `is_analysis_safe`), `Ticker`.
- **Persistence** — `StoredTrade` (`OPEN`/`CLOSED`, `WIN`/`LOSS`/`BREAKEVEN`, `TradeContext`), `TradeStatistics` (`win_rate`, `profit_factor`, `expectancy`, `average_r`, `total_realized_pnl`, `max_drawdown` with stated derivations), `DatasetSummary`/`IngestionResult`, `BacktestRunRecord`.
- **Backtesting** — `BacktestConfig` / `BacktestRunner` / `BacktestResult` (deterministic replay, `config_hash`, `EquityPoint` curve, `regime_counts`/`zone_counts`, `MarketRegime` via Efficiency Ratio), and the app-layer `BacktestService`.
- **Application/API** — FastAPI + `RequestIdMiddleware` + uniform error envelope; routers for `auth` (first user becomes `OWNER`), `watchlists`, `strategies`, `markets` (`/markets/:symbol/ticker|candles?timeframe&limit`), `backtests`, `trades`, `exchanges`, `admin` (`users`, `audit-log`, `system-health`, `trading-activity`), `/health`.

### 14.2 UI Requirements Supported by Those Capabilities

The design's display semantics for `RangeStatus`, `Signal`/`SignalReason`, `ConfirmationPolicy`, `RiskDecision`/`RejectionReason`, `TradeResult`/`TradeStatus`, `Timeframe`, `DataQualityReport`, `StoredTrade`/`TradeStatistics`, `MarketRegime`, and exchange connection metadata map directly to the enumerated backend contracts above. Watchlist scanning, per-timeframe observability, `RANGING`-aware research segmentation, historical coverage display, and the chart's zone/middle/outside semantics are all framed as **rendering or coordinating backend-provided values**, not as frontend calculations.

### 14.3 Planned / Future — Not Claimed as Present in Phase 9

These are explicitly **product requirements / planned capabilities** retained in the spec with future backend work required. No API fields, enums, or endpoints are invented for them:

- **RSI divergence** — planned product capability with intended UX direction (distinct markers/lines, toggleable layer). No canonical backend divergence contract, fields, or endpoints exist in Phase 9; backend/domain support is a future implementation requirement (§3.5, §6.8, §7.7).
- **Multi-timeframe aggregation endpoint** — no single aggregated multi-timeframe analysis endpoint in Phase 9; the UI coordinates independent per-timeframe requests and shows per-timeframe loading/stale/unavailable/partial-failure (§7.8, §11.3). Backend aggregation/orchestration is a future implementation decision.
- **Multi-pair aggregation endpoint** — no dedicated bulk/scan aggregation endpoint in Phase 9; watchlist scanning is specified as UI coordination of per-symbol requests, with future backend aggregation left as an implementation decision (§3.3).
- **Comprehensive historical research data coverage surface** — symbol/timeframe/date-range coverage, ingestion status, accumulated depth, provider/source as a dedicated browsable surface (§3.13, §8.25). Some quality/coverage metadata already flows via `CandleDataset.quality` / persistence summaries; full exposure is a future application/API task.
- **Live trading execution** — explicitly out of scope; `PAPER/READ-ONLY` is preserved. Connected exchanges do not imply execution capability (§3.12, §8.11).
- **DEX connectivity** — acknowledged as a separate architectural concern (wallet auth, signing, RPC, routing, gas) and not designed or implemented here (§3.12).
- **RANGING-based alerts** — `MarketRegime.RANGING` is a first-class filtering/segmentation dimension; alert triggers on `RANGING` transitions are planned/future (§3.9, §6.2).

### 14.4 What Was Not Re-Validated

This correction pass was scoped to `DESIGN.md`. Source, tests, and runtime behavior were not re-executed beyond the file reads checked above. Claims about enum completeness or provider support should be verified against the backend source/tests at implementation time rather than taken as exhaustive here.

---

## Appendix — Figma / Stitch Handoff Checklist

- [ ] Create Figma Variables for every token in §5 (Colors, Typography, Spacing, Radii, Shadows, Motion). Publish as Library.
- [ ] Create Styles for `text-primary/secondary/tertiary` + mono variants.
- [ ] Build component set per §8 with `collapsed`/`active`/`loading`/`empty`/`stale`/`planned` variants.
- [ ] Chart: define a Figma component frame with placeholder canvas; annotate overlays per §7 with token references (not hex) and separate `RangeStatus` vs `MarketRegime` badges. Stitch: bind chart colors to CSS variables.
- [ ] Watchlist: build scan-oriented table/card variants per §3.3 / §8.3 with prioritized columns and per-row freshness/quality; include column-chooser state.
- [ ] Research data: build coverage/quality summary components per §3.13 / §8.25 with planned-state placeholders.
- [ ] Prototyping: wire Flows 1–9 (§11) as Figma prototype; each screen state includes loading/empty/error/stale/planned frames.
- [ ] Responsive: set auto-layout + constraints per breakpoints §9; define `data-density` variant.
- [ ] A11y annotations: add focus-ring, contrast notes, and non-color indicator notes per §10 on each component. Ensure divergence (planned) also satisfies non-color encoding when specified.

**Do not implement React/Next.js/FastAPI UI components until this spec is reviewed and approved.** This document is the contract; code follows it.
