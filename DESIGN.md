# Range Trading Terminal — UI/UX Design Specification

**Status:** Authoritative — Source of Truth for Figma/Stitch and Frontend Implementation  
**Version:** 1.0 — Phase 9 Baseline  
**Scope:** Covers all 13 core UI areas through Phase 9 backend. No frontend implementation — this document is the implementation contract.  
**Stack target:** Next.js (App Router) + React + TypeScript + Tailwind + Lightweight Charts / TradingView Lightweight Charts (or equivalent canvas chart) + FastAPI backend.

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
14. [Validation Against Phases 1–9](#14-validation-against-phases-19)

---

## 1. Product UI Philosophy

### 1.1 Positioning

This is a **professional trading/research workstation**, not a marketing dashboard, not a DeFi portfolio tracker. The user is a discretionary or systematic range trader who lives in the chart. Every pixel must justify itself by answering: *"does this help me decide to trade, size, or stay out?"*

- **Research-first trading.** The path is: detect range → evaluate price position → confirm → size via risk → execute → journal. The UI makes each gate explicit.
- **Personal-first, multi-user capable.** Single-user mental model by default (your watchlists, your strategies, your trades). Multi-user is an architecture constraint (isolation via `owner_user_id`), not a social feature. No feed, no copy-trading, no public profiles.
- **Crypto first, market-agnostic second.** Symbols are `BASE/QUOTE` (e.g., `BTC/USDT`). Timeframes are canonical (`1m–1d`). Venue is a property of the symbol/connection, not the identity of the market. Future markets (FX, equities) arrive by adding symbols/venues, not by redesigning IA.
- **No invented intelligence.** Confidence is a heuristic score in `[0,1]`, not a probability. Efficiency Ratio and regime labels are explainable math. The UI never implies predictive certainty (no "90% win chance" language).

### 1.2 Visual Posture

- **Dark-first, near-black.** The chart is the hero; chrome recedes. Surfaces are desaturated graphite/ink, not tinted navy.
- **Information-dense, not chaotic.** Dense tables, compact rows, small type for data, generous whitespace only where it separates decisions.
- **Terminal, not toy.** Monospace where numbers live. Sharp corners over pill shapes. Flat surfaces over glass. Borders over shadows for separation.
- **Color is data, not decoration.** Green/red mean price direction only. Risk/danger has its own channel. Range has its own neutral channel. Oscillator has its own muted channel. If a color does not encode one of these domains, it should be gray.

### 1.3 Hierarchy of Information

Strict visual hierarchy, reinforced by type, weight, size, and position:

1. **Market data** — price, candles, volume. Largest, highest contrast, monospace, always visible.
2. **Analysis** — range high/low, zones, regime, confidence, position-in-range. Neutral accent, directly overlaid on market data.
3. **Decisions** — signal direction/reason, confirmation state, divergence. Muted tertiary accent, in the signal panel adjacent to the chart — never competing with candles.
4. **Controls** — order sizing, risk gates, strategy config, venue connection. Lowest chroma, standard UI gray, in side panels and dialogs.

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
| **Research** | Backtesting · Analytics (Performance) | All authenticated users |
| **Configure** | Strategies · Risk · Exchange Connections | All authenticated users |
| **System** | Admin (Users, Audit Log, System Health, Trading Activity) | `OWNER` only — nav item hidden entirely for `USER` |
| **Account** | Alerts / Activity, User menu (Me, Logout) | All authenticated users |

**Top ticker ribbon** sits above page content, below any app header. Shows compact pair chips for the active watchlist (or pinned favorites). Each chip: `BTC/USDT  67,421.10  +1.24%  ● VALID  0.72`. Clicking a chip navigates to Dashboard focused on that pair/timeframe. Ribbon is the fastest way to context-switch.

**Command palette** (`Cmd+K` / `Ctrl+K`): jump to pair, timeframe, strategy, backtest run, trade.

### 2.3 Route Map

| Route | Page | Auth |
|-------|------|------|
| `/login` | Sign In | public |
| `/register` | Create Account (first user becomes OWNER) | public |
| `/` | Main Trading Dashboard | authed → redirects if unauth |
| `/watchlists` | Watchlist Manager | authed |
| `/watchlists/:id` | Watchlist Detail | authed |
| `/positions` | Position / Trade Management | authed |
| `/journal` | Trade Journal / Performance Analytics | authed |
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

The primary workstation. This is where a trader spends 80% of time.

**Layout (desktop):**
- Pair selector + timeframe selector row (sticky, 44px) directly beneath the ribbon.
- Primary chart (flex, 55–65% height, min 380px) with range overlay, current price line, entry/target/stop, signal markers, range status badge.
- Signal & Confirmation panel (right dock, 380px) — adjacent to chart, not below.
- RSI/Oscillator panel (sub-panel, 120px) docked to chart bottom — shares time axis.
- Risk Summary strip (below chart, 88px) — equity, available balance, exposure, next-trade sizing preview.
- Watchlist mini-table (collapsible, 160–220px) at bottom: the active watchlist's items with compact status.
- Mobile: chart full-width, panels stack vertically in order: chart → signal → RSI → risk → watchlist.

**Data contract consumed:**
`RangeState` (`range_high`, `range_low`, `range_width`, `confidence`, `status`, `metadata`), `Signal` (`direction`, `reason`, `position_in_range`, `confirmation`), `RiskDecision` (when previewing), `CandleDataset` + `DataQualityReport`.

### 3.3 Multi-Pair Watchlist

**`/watchlists` (manager) and `/watchlists/:id` (detail)**
- Manager: table of watchlists (`name, item count, updated_at`) + Create. Search by name.
- Detail: header with name (inline rename), list of `WatchlistItem` rows.
- Row columns (compact, monospace numbers, 44px row height):
  `Symbol | Venue | Last Price | 24h % | Range Status (badge) | Range High/Low | Width | Confidence (bar) | Position-in-Range (meter) | Signal (dot+label) | Enabled (toggle)`
- Bulk: add pair (symbol + venue_id + notes), remove, reorder (drag handle, persists `sort_order`), enable/disable toggle.
- Status cells use the canonical status semantics (§6) — never color-only.

### 3.4 Range Analysis / Chart (integrated in Dashboard)

Described fully in §7. Key requirement: range detection is **observable**. The trader can see, for the selected pair/timeframe, the exact `range_high`/`range_low` lines, the three zones, where the current price sits, the `RangeStatus`, and `confidence` — without opening a tooltip.

### 3.5 Signal & Confirmation Panel (right dock on Dashboard)

- **Signal card** (top): direction (`LONG`/`SHORT`/`NONE`), reason (`SUPPORT_EDGE_SETUP`, `RESISTANCE_EDGE_SETUP`, `PRICE_MID_RANGE`, `PRICE_OUTSIDE_RANGE`, `NON_TRADABLE_RANGE`, `CONFIRMATION_NOT_MET`), confidence as a segmented bar + numeric, `position_in_range` meter.
- **Confirmation row:** policy badge (`required`/`optional`/`ignored`), oscillator value (`RSI 28.4` / `Stoch %K 22.1`), threshold context, `confirmation: true/false/null` with explicit label.
- **Divergence sub-section:** independent visual treatment (see §7.7). Collapsed when no divergence detected; explicit "No divergence detected" empty state — never a missing section that looks like a loading failure.
- **Gate summary:** if `RiskDecision` preview is active, show `APPROVED` or `REJECTED` + `rejection_reason` (e.g., `MAX_OPEN_POSITIONS`, `INSUFFICIENT_BALANCE`).

### 3.6 Position / Trade Management (`/positions`)

- **Open positions table** (if positions model is used in future live trading): `Symbol | Side | Quantity | Entry | Mark | Unrealized PnL | Liquidation | Leverage`.
- **Trade history table** (always — backed by `StoredTrade`): see §8.11. Filters by `symbol`, `result` (`win`/`loss`/`breakeven`), `status`. Click row → trade detail drawer with `TradeContext` breakdown.
- **Execution/Order panel** (Phase 9: paper/read-only posture): shows that live order placement is disabled; displays the validated `RiskDecision` (entry/stop/target/quantity/notional/reward-risk/fees/slippage) as a preview. No button claims to place a live order.

### 3.7 Strategy Configuration (`/strategies`)

- List of `StrategyConfig` cards: `name | schema_version | active | updated_at`.
- Editor (drawer or page): three grouped sections mirroring the backend payload exactly:
  - `range_config` — `mode` (`structural`/`volatility`/`manual`/`oscillator_confirmed`), `params` (mode-specific: `lookback`, `volatility_window`, `manual_high/low`, `oscillator`/`osc_period`/`overbought`/`oversold` etc.).
  - `signal_config` — `lower_edge_zone`, `upper_edge_zone`, `confirmation_policy` (`required`/`optional`/`ignored`).
  - `risk_config` — `risk_per_trade`, `stop_method`, `target_method`, `max_open_positions`, `max_drawdown`, `fee_rate`, `slippage_rate`, caps, leverage, etc. (see `risk_engine/engine.py:_DEFAULTS`).
- Validation is inline with engine rules (single source of truth). JSON preview toggle for power users.
- Versioning: `config_hash` displayed (short hash, copyable), `strategy_id` + `config_version`.

### 3.8 Risk / Account Overview (`/risk`)

- **Risk summary header:** `Equity | Available Balance | Total Exposure | Peak Equity | Drawdown % | Daily Drawdown | Consecutive Losses | Open Positions`.
- **Gates panel:** each gate (`max_drawdown`, `max_daily_drawdown`, `max_consecutive_losses`, `max_open_positions`, notional/exposure caps, leverage) with current value vs. limit, progress bar, and `OK` / `AT LIMIT` / `BLOCKED` state using danger treatment (not red candle color).
- **Preview calculator:** select a signal + price, run `RiskEngine.evaluate` preview, show `RiskDecision` breakdown (quantity, notional, stop/target, reward-risk, fees/slippage).

### 3.9 Alerts / Activity Feed (`/alerts`)

- Feed of range/signal/quality events. Each item: `timestamp | symbol/timeframe | kind (badge) | detail | quality_issues if any`.
- Quality issues explicitly raised: gaps, unclosed candles, `INSUFFICIENT_DATA` — surfaced as warnings, not hidden.
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
- Compare view: side-by-side stats + overlaid equity curves (distinct line styles, not just color).

### 3.11 Trade Journal / Performance Analytics (`/journal`)

- **Statistics cards** (derived via `compute_trade_statistics`): `total_trades | completed | open | wins | losses | breakevens | win_rate | profit_factor | expectancy | average_win | average_loss | average_r | total_realized_pnl`. Each card shows `null → "—"` when not derivable (e.g., `profit_factor` with no losses).
- **Equity curve:** cumulative realized PnL curve derived from closed trades (trade-close granularity). Not an intraday equity curve — label explicitly.
- **Trade history / journal table:** `trade_id | symbol/timeframe | direction | quantity | entry → exit | realized_pnl | realized_r | fees | result badge | opened_at → closed_at | strategy | context preview`. Click → drawer with `TradeContext` full breakdown (range bounds, confidence, position_in_range, risk_percent, regime/zone extra).
- Filters: `symbol`, `result`, `status`, `strategy`, date range. Pagination (server supports `limit`).

### 3.12 Exchange Connections (`/exchanges`)

- Cards per `ExchangeConnection`: `venue_id | display_name | status badge (connected/error/disabled) | sandbox badge | updated_at`.
- Connect form: `venue_id | display_name | api_key | secret | password (optional) | sandbox toggle`. Secrets use password inputs, never echoed after creation. Shows `credential_ref` not the secret.
- Disconnect (delete) with confirm dialog.
- Status semantics: verified via backend, not invented on the client.

### 3.13 Admin Dashboard

**`/admin`** (overview)
- KPI row: `user_count | dataset_count | market_data_provider (configured/unconfigured) | schema_version | engine_versions | time`.
- **Trading activity** panel (from `GET /admin/trading-activity`): `totals {trades, wins, losses, open, backtest_runs}` + `recent_backtests` table.
- Quick links: Users, Audit Log, Trading Activity detail.

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
  Row 4: Risk strip (88px)
  Row 5: Watchlist mini (collapsible, max 240px, table density compact)
  ```
- **Panel gutters:** 16px (`space-4`) between chart and side panel. Card gaps 12px (`space-3`).
- **Density default:** `comfortable` (44px table rows, 36px inputs). Toggle to `compact` (36px rows, 32px inputs) in user preference — applies to tables/lists only, never to chart or controls requiring precise clicks.

### 4.2 Tablet (768–1279px)

- Sidebar becomes overlay drawer (hamburger). Ribbon remains but shows fewer chips + overflow count (`+6`).
- Dashboard: chart full-width, signal panel drops below chart (full-width card), RSI panel stays docked to chart.
- Tables: horizontal scroll with sticky first column, column-chooser to hide low-priority columns (confidence, width).

### 4.3 Mobile (≤767px)

- Sidebar: drawer only. Ribbon: horizontal swipe, 2–3 chips visible, "+N" overflow.
- Dashboard: single column. Chart 320px min-height. Timeframe selector becomes segmented control with horizontal scroll. Pair selector becomes full-width search + bottom sheet.
- Tables: card/list view fallback. Each trade/signal renders as a compact card rather than a row.
- Forms: stacked single-column, full-width inputs.

### 4.4 Spacing & Rhythm

All spacing derived from tokens (`space-1` = 4px base). No arbitrary pixel values. Page section gaps use `space-6` (24px), card internal padding `space-4` (16px), tight element gaps `space-2` (8px). Vertical rhythm is 4px baseline.

---

## 5. Design Tokens

Tokens are the single source of visual truth. Figma Styles / Variables map 1:1 to these. Tailwind config extends from them. Never hardcode hex values in components.

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

/* ——— Market Semantics (GREEN/RED — reserved) ——— */
--color-bull:          #1DB954;  /* bullish candle body, +price, long */
--color-bull-subtle:   #1DB95414;/* bullish bg tint (8%) */
--color-bear:          #EF4444;  /* bearish candle body, -price, short */
--color-bear-subtle:   #EF444414;

/* ——— Range (NEUTRAL ACCENT) ——— */
--color-range:         #8EA1BE;  /* range high/low lines, boundary */
--color-range-subtle:  #8EA1BE18;/* zone fill base */
--color-range-strong:  #B0C4DE;  /* emphasized boundary */
--color-zone-lower:    #8EA1BE14;/* lower edge zone fill (8%) */
--color-zone-middle:   #6B7A9010;/* middle NO-TRADE zone fill + hatch */
--color-zone-upper:    #8EA1BE14;/* upper edge zone fill */

/* ——— Oscillator / Confirmation (MUTED TERTIARY) ——— */
--color-osc:           #9A8BB5;  /* RSI line, confirmation accent */
--color-osc-subtle:    #9A8BB514;
--color-osc-strong:    #B8A9D6;
--color-divergence-bull: #22C55E;/* bullish divergence marker (green but distinct shape) */
--color-divergence-bear: #F97316;/* bearish divergence — uses orange, not red, to avoid candle confusion */

/* ——— Risk / Danger (DISTINCT from bearish red) ——— */
--color-danger:        #F59E0B;  /* amber — risk gate blocked, rejected, danger */
--color-danger-strong: #D97706;
--color-danger-subtle: #F59E0B14;
--color-danger-bg:     #F59E0B1A;

/* ——— Status additional ——— */
--color-info:          #38BDF8;  /* informative, trending regime */
--color-warning:       #FACC15;  /* degenerate, warnings */
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

**Rules:**
- Green/red appear only for `candle direction`, `price change`, `signal LONG/SHORT direction`, and `trade result WIN/LOSS` (where WIN is profit, LOSS is loss — still market-semantic).
- Risk rejections, drawdown breaches, `DEGENERATE`, system errors use amber/danger, never red.
- Range uses neutral slate-accent (`--color-range`). Oscillator uses muted lavender (`--color-osc`). They never swap channels.

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
--shadow-glow-range: 0 0 0 1px rgba(142,161,190,0.15), 0 0 12px rgba(142,161,190,0.08);
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

Every domain enum has a single visual encoding. The same `VALID` color in the watchlist, the chart badge, and the signal panel. No synonyms.

### 6.1 Range Status (`RangeState.status` + `RangeStatus` enum)

| Status | Label | Color | Icon | Usage |
|--------|-------|-------|------|-------|
| `VALID` | Valid | `--color-success` (green) badge fill `success-subtle` | ● solid dot | Tradable range; bounds are actionable |
| `DEGENERATE` | Degenerate | `--color-warning` (yellow) / amber | ◐ half-dot / warning triangle | Detection ran, no tradable structure — `metadata.reason` shown alongside |
| `INSUFFICIENT_DATA` | Insufficient Data | `--color-neutral` (gray) | ○ hollow dot | Too few rows; chart shows placeholder + rows needed |
| `TRENDING` (client label) | Trending | `--color-info` (sky) | ↗ / ↘ trend arrow | Not a formal `RangeStatus` — derived from `MarketRegime` when `RANGING` is false; means non-range market |

Global rule: **bounds are only actionable when `VALID` + `is_tradable` (positive width, finite bounds).** Degenerate/insufficient states render bounds as dashed, muted, with explanatory annotation — never as solid lines a trader could mistake for tradable levels.

### 6.2 Market Regime (`MarketRegime`)

| Regime | Badge | Chart Underlay |
|--------|-------|----------------|
| `RANGING` | neutral/sky subtle | no overlay — normal range zones |
| `TRENDING_UP` | `--color-bull` subtle, `↗ Trending Up` | subtle green tint on right 25% of chart |
| `TRENDING_DOWN` | `--color-bear` subtle, `↘ Trending Down` | subtle red tint |
| `TRANSITIONAL` | `--color-warning` subtle, `⟡ Transitional` | hatched subtle overlay |
| `INSUFFICIENT_DATA` | `--color-neutral` | muted, chart shows "Collecting data" |

Regime is research context — never conflated with `RangeStatus`. Both shown simultaneously when relevant (e.g., `RangeStatus: VALID` + `Regime: TRANSITIONAL`).

### 6.3 Price Zones (Signal domain)

Visualized on the chart as horizontal bands between `range_low` and `range_high` (`§7`):

| Zone | Fill | Label on chart | Semantics |
|------|------|----------------|-----------|
| Lower edge (`[low, low + lower_edge_zone*width]`) | `--color-zone-lower` (neutral tint) | `LONG ZONE` (small, muted) | Potential LONG setup area |
| Middle (`(low+lower_zone, high-upper_zone)`) | `--color-zone-middle` + 45° hatch pattern, 6px repeat | `NO-TRADE` (centered, `text-tertiary`, uppercase, `tracking-wide`) | Explicit no-trade area — visually dominant so it cannot be mistaken for a setup region |
| Upper edge | `--color-zone-upper` | `SHORT ZONE` | Potential SHORT setup area |
| Outside (`price < low` or `> high`) | no fill, price line rendered beyond bounds, outside indicator arrow | `OUTSIDE` | `SignalReason.PRICE_OUTSIDE_RANGE` |

**Critical:** Middle zone hatch + label must be obvious at a glance, even when chart is heavily overlaid. It is the most important negative space in the product.

`position_in_range = (price - low) / width` displayed as a thin meter in signal panel and as dot position on a vertical scale adjacent to chart y-axis (see §7).

### 6.4 Signal (`Signal.direction` + `SignalReason`)

| Signal | Display |
|--------|---------|
| `LONG` (`SUPPORT_EDGE_SETUP`) | Green pill `▲ LONG`, confidence bar, reason line "Support edge setup" |
| `SHORT` (`RESISTANCE_EDGE_SETUP`) | Red pill `▼ SHORT`, confidence bar, reason line "Resistance edge setup" |
| `NONE` — `PRICE_MID_RANGE` | Gray `— NO SETUP`, reason "Price in middle (no-trade) zone" |
| `NONE` — `PRICE_OUTSIDE_RANGE` | Gray `— OUTSIDE`, reason "Price outside range bounds" |
| `NONE` — `NON_TRADABLE_RANGE` | Amber `— NO RANGE`, reason from `range_state.metadata.reason` |
| `NONE` — `CONFIRMATION_NOT_MET` | Muted lavender `○ AWAITING CONFIRMATION`, reason "Oscillator confirmation required" |

`confidence` shown as 4-segment bar + numeric `0.72`. Label always clarifies "Heuristic score — not a win probability." Never a progress-circle that implies probability.

### 6.5 Confirmation (`confirmation` + `ConfirmationPolicy`)

| State | Badge |
|-------|-------|
| `confirmation == true` | lavender solid dot + `Confirmed (RSI 28.4 ≤ 30)` |
| `confirmation == false` | hollow lavender dot + `Not confirmed (RSI 54.1)` |
| `confirmation == null` + `policy == required` | amber warning + `Awaiting confirmation` |
| `confirmation == null` + `policy == optional` | muted `—` + `Confirmation not present (optional)` |
| `policy == ignored` | gray `Ignored` |

Always show `policy` badge alongside the value so a `NONE` due to missing confirmation is never mistaken for a weak range.

### 6.6 Risk Decision (`RiskDecision.status` + `RejectionReason`)

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

All rejections use **amber danger treatment**, never red. Red is reserved for market/bearish context.

Reward/risk line shows `1:2.8 (required 1:2.0) → PASS/FAIL` with color only as secondary cue; label always explicit.

### 6.7 Trade Result (`TradeResult`) & Status

| Result | Badge |
|--------|-------|
| `WIN` | green `WIN` + `+421.50` (PnL) |
| `LOSS` | red `LOSS` + `-180.00` |
| `BREAKEVEN` | gray `BREAKEVEN` + `≈ 0.00` |
| `OPEN` (`TradeStatus.OPEN`) | sky/neutral `OPEN` + no PnL/result (not "0") |
| `CLOSED` (`CLOSED`) | result badge as above + PnL |

`OPEN` trades never show a result chip — empty state is absence, not a zero.

### 6.8 Oscillator (RSI / Stochastic)

RSI panel line uses `--color-osc` (#9A8BB5). Overbought/oversold bands (e.g., 70/30) shown as dashed horizontal lines in the same muted color family, labeled. Confirmation-relevant region highlighted with subtle `osc-subtle` fill. Divergence markers (see §7.7) have their own accent so they are not mistaken for confirmation.

### 6.9 Data Quality (`DataQualityReport` / `CandleDataset`)

| Quality | Badge |
|---------|-------|
| Clean (`is_clean`) | green dot `Clean` |
| Warnings (`WARNINGS`) | amber dot `Warnings — N issues` |
| Gaps | amber `Gaps` + expandable list of `gap_start_ms → gap_end_ms` |
| Unclosed candles | sky `Includes forming candle` — analysis uses `closed_candles()` only; label makes this explicit |

`is_analysis_safe` is shown as a single boolean chip on the dataset selector/chart header.

---

## 7. Chart Specifications

### 7.1 Purpose & Non-Goals

The primary chart is the **single source of visual truth** for market + analysis + decisions. It answers: *What is price doing? Where is the range? Where am I inside it? Is there a setup? If so, what would execution look like?*

Non-goals: drawing tools, indicator playground, TradingView clone. Indicators beyond RSI/oscillator and divergence are out of scope for v1.

### 7.2 Layout Anatomy

```
┌─────────────────────────────────────────────────────────┐
│ Chart Header (44px)                                     │
│  Pair  ● Status badge  Confidence  Regime  Quality chip │
├─────────────────────────────────────────────────────────┤
│                        Y-axis                          │
│  ┌──────────────────────────────────────┐  ┌─────────┐ │
│  │  Candles + Range overlay + Zones     │  │ Price   │ │
│  │  Entry / Stop / Target lines         │  │ Scale   │ │
│  │  Signal markers                      │  │ + Range │ │
│  │  Current price line (dashed, live)  │  │ labels  │ │
│  │  Position-in-range vertical meter → │  │         │ │
│  └──────────────────────────────────────┘  └─────────┘ │
│  ┌──────────────────────────────────────┐               │
│  │  Volume (optional, 24px, collapsed by default)     │ │
│  └──────────────────────────────────────┘               │
│  ┌──────────────────────────────────────┐               │
│  │  RSI / Stochastic panel (120px)      │  shared X    │
│  │  + divergence markers                │  time axis   │
│  └──────────────────────────────────────┘               │
│  ←──────────── Time Axis (shared, monospace) ─────────→ │
│  Timeframe selector (segmented) + Crosshair readouts    │
└─────────────────────────────────────────────────────────┘
```

- **Header** left-to-right: pair (`BTC/USDT  67,421.10`), `RangeStatus` badge (VALID/DEGENERATE...), confidence bar+value, regime badge, quality chip. Right-aligned: timeframe-mini + settings (cog) for toggling volume/zones.
- **Price/y-axis** on the right (trading convention). Monospace, `text-xs`, `tabular-nums`. Range high/low price labels are pinned to y-axis in `--color-range` pills. Current price line label is highest contrast (`--color-text-primary` on `--color-bg-surface-3`).
- **Time/x-axis** shared between candles + RSI. Monospace. Labels show date when span > 24h, otherwise time.
- **Crosshair** (`--color-chart-crosshair`) dashed, shows coordinated tooltip for both panes: `OHLCV`, `RSI value`, `position_in_range`, `regime` at that candle.

### 7.3 Candlesticks

- **Body:** `bull` solid green, `bear` solid red, 1px border in same color. Minimum body width 3px, max 14px (scales with time/zoom). No hollow candles in v1.
- **Wick:** 1px `--color-chart-candle-wick`, centered.
- **Volume:** optional histogram behind candles (low opacity 20%), `volume-bull/bear` fills. Toggleable; collapsed by default to preserve vertical space.
- **Hover:** candle highlights with 8% surface-3 overlay; tooltip shows `O H L C V` monospace.

### 7.4 Range Overlay

- **Boundary lines:** 1.5px solid `--color-range` when `VALID`, 1.5px dashed `--color-range` at 60% opacity when `DEGENERATE`/`INSUFFICIENT_DATA`. Label on y-axis pill: `R HIGH 68,400.00` / `R LOW 65,100.00`, same color.
- **Width annotation:** small mono label mid-range on right gutter: `W 3,300 (4.9%)`.
- **Zones:** full-width horizontal bands (see §6.3) with correct opacity. Middle zone hatch pattern (SVG pattern, 45°, `color-mix` with `--color-zone-middle`, stroke 0.5px). Zone labels rendered inside bands, `text-xs` uppercase `tracking-wide`.
- **Current price line:** 1px dashed `--color-chart-price-line`, label pill `67,421.10` with arrow pointer to y-axis. When price is outside range, line extends beyond zones and label gets `OUTSIDE` suffix badge.
- **Outside arrow:** small chevron at chart edge pointing outward when price is outside, labeled distance from nearest bound (e.g., `+2.1% above high`).

### 7.5 Entry / Target / Stop (when a `RiskDecision` is previewed)

- **Entry:** 1px solid `--color-chart-entry` (sky), label `ENTRY 67,100.00`.
- **Stop:** 1px solid `--color-danger` (amber) dashed `4-3`, label `STOP 64,800.00`, shaded loss area between entry and stop in `danger-subtle` with `−1R` label.
- **Target:** 1px solid `--color-success` (green) dashed, label `TARGET 68,900.00`, shaded profit area in `bull-subtle` with `+2.4R` label.
- **Quantity/notional:** callout on entry line: `Qty 0.142  Notional $9,534`.
- All three lines only appear when `RiskDecision.approved == true` or when previewing a hypothetical sizing; rejected decisions show stops/targets muted + rejection reason banner rather than notional.

### 7.6 Signal Markers

- **LONG setup:** upward triangle marker below the candle at signal time, fill `--color-chart-signal-long`, 10px, white `▲` glyph, tooltip "Support edge setup — confidence 0.68 — zone depth 0.82".
- **SHORT setup:** downward triangle above the candle, red.
- **NONE:** small gray dot on the candle's close with tooltip stating the `SignalReason` (e.g., "Price in middle — no setup"). Not a triangle — visually distinct from actionable setups.
- **Confirmation-not-met:** triangle outline (stroke only) + small lavender dot underneath indicating "edge reached, confirmation missing."

All markers have a vertical guide line (1px dotted, low opacity) connecting to the RSI panel when confirmation is relevant.

### 7.7 RSI / Oscillator Panel

- **Line:** 1.5px `--color-osc`, no fill. Point markers only on the latest value (4px dot).
- **Overbought/oversold:** dashed horizontal lines at `oversold`/`overbought` thresholds (default 30/70), labeled `OS 30` / `OB 70` on y-axis, subtle tint bands beyond them in `osc-subtle`.
- **Confirmation highlight:** when a signal is at an edge and oscillator is in confirming region, highlight that segment of the RSI line with a 3px glow in `--color-osc-strong`.
- **Divergence markers — independent treatment:**
  - Bullish divergence: green polyline connecting two RSI troughs with price troughs, endpoint marker `◆` in `--color-divergence-bull` on both price pane and RSI pane, labeled `BULL DIV` in small mono badge. Bearish divergence analog with `--color-divergence-bear` and orange.
  - Divergence lines are **thicker (2px) and use a distinct dot-dash pattern** so they are never mistaken for RSI or range lines.
  - Divergence is a separate toggle/layer ("Divergence" eye icon in chart header). Off by default; information density preserved.

### 7.8 Timeframe Selector

- **Control:** segmented/pill group showing canonical timeframes `1m 5m 15m 30m 1h 4h 1d` (from `Timeframe` enum). Active timeframe: filled `surface-3` + `text-primary`, `font-mono`, `text-sm`. Inactive: `text-secondary`. Gaps unavailable for the current provider shown disabled with tooltip "Not available from this venue."
- **Selector location:** bottom bar of chart, centered, sharing the time axis. On mobile, horizontally scrollable.
- **Multi-timeframe observability:** the Dashboard exposes a "Multi-timeframe" strip: up to 4 miniature sparklines (one per timeframe) showing the same pair's `RangeStatus`, confidence, and `position_in_range` compactly, so a trader can compare strategy across timeframes without switching the main chart. Each mini shows: `1h  ● VALID  0.68  ──●──  LONG?` Clicking promotes that timeframe to the main chart.

### 7.9 Pair Selector

- **Control:** search/combobox (`BTC/USDT`) with venue badge (`Binance`, `Coinbase`, etc.). Recent + watchlist favorites pinned on top. Shows `last price` and `RangeStatus` dot per search result.
- **Path convention:** URL uses dash form (`BTC-USDT`) to keep URLs unescaped, matching the API (`/markets/BTC-USDT/candles`). Display always uses slash form.

### 7.10 Readability Under Overlays

Layer order (back to front):
`zone fills (lowest) → grid → volume → candles → range boundary lines → entry/stop/target → current price line → signal markers → divergence lines → crosshair → y-axis labels (top)`.
Opacity caps: zone fills ≤ 10%, volume ≤ 20%, glow/shadow only on interactive elements. No overlay may reduce candle body contrast below WCAG 4.5:1 against its zone background — tested via token contrast pairs.

---

## 8. Component Inventory

Each component spec defines: **anatomy, states, props/data, and Figma/Stitch notes**. All components consume design tokens; no hardcoded values.

### 8.1 Global Navigation / Sidebar

- **Anatomy:** logo/wordmark (24px), nav groups with section labels (`TRADING` etc. `text-xs` `tracking-wide` `text-tertiary`), nav item (icon 16px + label `text-sm` `font-medium`), active indicator (2px left border `--color-range` + `surface-3` bg), collapse toggle at bottom.
- **States:** active, hover (`surface-2`), collapsed (icon rail + tooltip on hover), drawer (mobile overlay with scrim).
- **Fig stch:** Auto-layout vertical, 8px gap between items, 16px section gap. Component variant `collapsed=true/false`.

### 8.2 Top Market/Ticker Ribbon

- **Anatomy:** horizontal flex, 36px tall, `bg-subtle` + bottom border `border-subtle`. Chips: `symbol (mono text-sm medium)` + `last (mono text-sm)` + `change% (mono text-xs, bull/bear color)` + `status dot + label (text-xs)`.
- **States:** hover chip `surface-2`, active chip (current pair) `surface-3` + range color border. Overflow scrolled with edge fade. Skeleton chips on load.
- **Data:** derived from watchlist or pinned favorites + `ticker` endpoint.

### 8.3 Watchlist (Table + Mini Variant)

- **Table anatomy:** header row `text-xs` `tracking-wide` `text-tertiary` uppercase, sortable via click (arrow indicator). Row 44px (compact 36px), zebra none — separation via `border-subtle` 1px row dividers. Cells: symbol (mono medium + venue badge xs), last/change, badges/meters.
- **Position-in-range meter:** 60px wide horizontal bar, background `surface-3`, fill `range` with middle hatch overlay; dot marks current position. Also shown as `0.42` mono numeric.
- **Confidence bar:** 4 vertical segments (2px wide each, 2px gap), filled count = `confidence * 4`, color `success` when valid, `neutral` otherwise.
- **Signal cell:** pill badge + reason tooltip. Dot indicators as per §6.4.
- **Fig stch:** Table uses auto-layout with fixed column widths; sticky header. Mini variant omits venue/width columns.

### 8.4 Pair Selector

- **Anatomy:** combobox input (mono, `surface-1`, `border-subtle`, `radius-sm`, 36px), dropdown list (max 320px, `surface-2`, `shadow-md`), list item 36px with symbol + venue + last + status dot, group headers ("Watchlist", "Recent").
- **States:** idle, focused (`border-focus` ring), dropdown open, no results ("No pairs found"), loading skeleton.
- **A11y:** `combobox` role, `aria-expanded`, keyboard nav (Arrow, Enter, Esc).

### 8.5 Timeframe Selector

- **Anatomy:** segmented control group, `surface-1` track, pill buttons `text-sm` mono, 32px tall. Active: `surface-3` + `text-primary` + inner shadow. Disabled: `text-disabled` + strikethrough.
- **States:** active, hover (`surface-2`), disabled (with tooltip), loading (pulse).
- **Fig stch:** Component set variant `active`.

### 8.6 Primary Trading Chart

- See §7. Implementation: canvas-based (Lightweight Charts or Apache ECharts). Header + chart canvas + RSI pane canvas + time axis are separate components composed together. All colors, fonts, line widths from tokens.

### 8.7 Range Overlay

- **Anatomy:** two horizontal lines + two zone fills + hatch + labels. Implemented as chart overlays (series/price lines), not a separate React component layer over canvas (to keep crosshair sync). Config: `showZones (bool)`, `showHatch (bool)`, `opacity`.

### 8.8 Signal Card

- **Anatomy:** card `surface-1` `radius-md` `border-subtle`. Header: direction pill + confidence bar+numeric + position meter. Body: reason line (`text-sm` `text-secondary`), policy+confirmation row (lavender badges), zone depth micro-bar, metadata collapse ("Details" disclosure shows `range_mode`, `range_status`, `confirmation_present`, `oscillator_value`).
- **States:** LONG/SHORT/NONE variants (distinct accent), loading (skeleton pill+bar), error (amber banner with reason), no-data (muted "No range — no signal").
- **Data:** `Signal` + `RangeState` (for context) + `RiskDecision` preview (optional).

### 8.9 RSI / Divergence Panel

- **Anatomy:** 120px chart pane sharing x-axis. Y 0–100. Gridlines at 30/50/70. RSI line, threshold bands, confidence highlight segment, latest value dot + label on y-axis.
- **Divergence layer:** polyline + endpoint diamonds + badge. Toggle in chart header controls visibility.
- **Empty:** when `oscillator_value` is NaN (insufficient rows), show dashed 50 line + "Insufficient data for oscillator" centered label.

### 8.10 Position Table

- **Anatomy:** table with open/closed tabs. Columns: `Symbol | Side (LONG/SHORT pill) | Qty (mono) | Entry | Mark | Unrealized PnL (bull/bear/neutral, with R multiple) | Liquidation | Leverage`.
- **States:** no positions empty state, loading skeleton rows, error banner.

### 8.11 Order / Execution Panel

- **Anatomy (Phase 9 paper mode):** card `surface-1`, header `EXECUTION PREVIEW — PAPER MODE` (amber subtle badge + info icon tooltip explaining no live orders). Fields: `Entry | Stop | Target | Qty | Notional | Leverage | Reward:Risk | Fees | Slippage`. Status banner: `APPROVED` (green) or `REJECTED — reason` (amber) with metadata expansion. CTA button disabled with label "Live trading not enabled" + tooltip.
- **Future (post-Phase 9):** CTA becomes `Place Order` when execution mode allows; confirmation dialog shows same breakdown. Never `HTTP → Exchange` bypass.

### 8.12 Risk Summary

- **Anatomy:** horizontal strip card `surface-1`, 88px, 4–6 metric cells (`label text-xs tertiary` + `value mono md medium` + `progress bar xs`). Metrics: `Equity`, `Available`, `Exposure`, `Drawdown`, `Daily DD`, `Consecutive Losses`. Each cell shows a 2px progress bar toward its limit (0–100% of cap), color `success` → `warning` (80%) → `danger` (100%).
- **Preview row** (when evaluating): `Next trade: Qty 0.142  Notional $9,534  Risk $95  R:R 1:2.8  ✓ Approved`.
- **Blocked state:** amber background tint + warning icon when any gate is at limit.

### 8.13 Strategy Configuration Panel

- **Anatomy:** form with three section cards (`Range` / `Signal` / `Risk`), each with field groups. Inputs: select for enums (`mode`, `stop_method` etc.), number for numeric params, toggle for booleans. Each field shows engine validation message inline. Footer: `Save` (primary) + `JSON Preview` toggle + `config_hash` display.
- **States:** pristine, dirty (Save enabled), saving (spinner), validation error (field red ring + message, but card border amber since error is domain, not system), success toast.
- **Fig stch:** Form layout uses 2-column grid on desktop, 1 on mobile.

### 8.14 Alert Feed

- **Anatomy:** vertical feed, grouped by day. Item: 56px row with `icon (16px) | symbol/timeframe (mono sm) | badge (kind) | detail (sm) | timestamp (xs tertiary)` + right-aligned quality chip if present. Kinds: `Range` (neutral), `Signal` (bull/bear/gray), `Quality` (amber), `System` (info).
- **States:** empty ("No alerts"), loading skeleton, error.
- **Interaction:** click → navigates to relevant chart/timeframe; dismiss/archive (optional).

### 8.15 Equity Curve

- **Anatomy:** area/line chart (monotone curve, `surface-3` grid, `--color-range` or `--color-success` line, `success-subtle` fill). Y = equity, X = time (`timestamp_ms`). Tooltip: `Equity | Peak | Drawdown` per `EquityPoint`. Zoom via brush, reset button. Max drawdown segment highlighted with amber dashed bracket + label.
- **Comparison mode:** up to 4 curves overlaid, distinct line styles (solid, dashed, dotted, dash-dot) + legend, not color-only.

### 8.16 Performance / Statistics Cards

- **Anatomy:** grid of 8–12 stat cards, each `surface-1` `radius-md` `border-subtle` `padding 16px`. Layout: `label xs tertiary uppercase` top, `value 2xl mono bold` center, `context xs secondary` bottom (e.g., "of 42 completed"). Null values display `—` (em dash) + tooltip "No data — needs N wins/losses" — never `0` when undefined.
- **Stats:** `total_trades | wins/losses/breakevens | win_rate | profit_factor | expectancy | average_win/loss | average_r | total_realized_pnl | max_drawdown`.
- **Motion:** numbers animate with count-up (120ms) on data change; respects reduced-motion.

### 8.17 Trade History / Journal Table

- **Anatomy:** table, 44px rows, `trade_id` shown as short hash (first 8) + copy icon, monospace. Columns: `Trade ID | Symbol | Side pill | Qty | Entry → Exit (with arrow) | Realized PnL (colored) | Fees/Slippage (xs muted) | Result badge | R (realized_r) | Opened → Closed (date mono xs) | Strategy (badge)`. Row click opens drawer.
- **Drawer:** shows `TradeContext` breakdown: range bounds/width/confidence, `position_in_range`, `confirmation`, `risk_percent`, regime/zone extra JSON collapsed. Fees/slippage/drawdown explicit.
- **States:** empty, filtered-empty ("No trades match filters — clear filters"), loading, error.

### 8.18 Backtesting Configuration / Results

- **Config form:** card with date pickers (`start_ms`/`end_ms`), strategy select, numeric inputs (`initial_capital`, `fee_rate`, `slippage_rate`, `warmup_candles`). Inline validation per `BacktestConfig` rules (e.g., `start_ms < end_ms`, `warmup_candles >= 2`).
- **Results header:** identity row (`run_id short` + copy, `config_hash` short + copy, `engine_version` badge, `period`).
- **Results body:** statistics cards (§8.16) + equity curve (§8.15) + regime/zone bar charts + trades table (scoped).
- **Compare view:** selector checkboxes on history table + "Compare 2–4 selected" button → split view with overlaid curves + stat diff table (Δ values with `+`/`−` and neutral color for negative when it is a market loss vs. amber when it is a risk deterioration).

### 8.19 System Status

- **Anatomy:** card row: `status pill (ok/degraded/down)` + `schema_version` + `engine_versions` + `user_count` + `dataset_count` + `market_data_provider` + `time`. Status dot green/amber/red (system health red is allowed — this is infrastructure, not market data; distinct from candle red by using a filled circle + label, and the red is `#DC2626` infrastructure red, never the candle red token).
- **States:** ok (green), degraded (amber), down (red) — with explicit text label; not color-only.

### 8.20 Exchange Connection Cards

- **Anatomy:** card `surface-1` `radius-md` `border-subtle`, header with `venue_id` (mono medium) + `display_name` + `status badge` (`connected` green / `error` amber / `disabled` gray) + `sandbox` pill (sky when true). Body: `credential_ref` (mono xs truncated) + `updated_at`. Actions: `Test` (optional) + `Disconnect` (danger button, confirm dialog).
- **Connect dialog:** form with validation (required `venue_id`, `api_key`, `secret`), shows never to store secrets client-side.

### 8.21 Admin User Table

- **Anatomy:** table with columns `id short | email | role pill (OWNER sky / USER gray) | active (toggle) | created_at | last_login | actions`. Actions menu (kebab): `Activate/Deactivate`, `Change Role`, `Revoke Sessions`. Create User button opens dialog (email/password/role).
- **States:** loading, empty, error, action loading (row spinner).

### 8.22 Audit Log

- **Anatomy:** table `timestamp (mono xs) | actor | action (mono sm) | resource_type | resource_id (short) | outcome (success/failure pill) | metadata (collapsible JSON monospace xs)`. Filters: action, resource_type, actor, date range. Virtualized rows for large logs.
- **States:** empty, loading, error.

### 8.23 Modal / Dialog

- **Anatomy:** centered card `surface-2` `radius-lg` `shadow-lg` + scrim `bg-overlay` (backdrop blur 4px). Header: `title lg medium` + close `×` (16px). Body: `text-base` `text-secondary`. Footer: right-aligned actions (`Cancel` ghost + `Confirm` primary or `Danger` amber). Widths: sm 400px, md 560px, lg 720px.
- **States:** open (fade + scale 98→100, 180ms), closing (reverse), focus-trapped, Esc to close, click scrim to close (except destructive confirms).
- **A11y:** `role="dialog"`, `aria-modal`, focus trap, return focus on close.

### 8.24 Toast / Notification

- **Anatomy:** stack bottom-right (desktop) / top-center (mobile), 360px wide, `surface-2` `radius-md` `shadow-md` + left accent bar 3px (success green / danger amber / info sky). Content: `title sm medium` + `message sm secondary` + optional action link. Auto-dismiss 4s (success/info), sticky (danger/error until dismissed). Queue max 3 visible, overflow count.
- **Variants:** `success`, `warning` (amber), `danger` (amber), `info` (sky). No red toasts for market losses — red is not a notification color.
- **Motion:** slide-in from bottom (16px, 180ms `ease-out`), respect reduced-motion (fade only).

### 8.25 Empty / Loading / Error States

- **Empty:** centered illustration (outline, 48px, `text-tertiary`), `title md` ("No watchlists yet"), `description sm secondary` (one sentence explaining why and what to do), primary CTA button. Never a blank table that looks broken.
- **Loading:** skeleton — shimmer `surface-2 → surface-3` gradient, 800ms loop. Table skeletons use 4–6 rows of rounded bars. Chart skeleton shows axes + grid + pulsing candle placeholders. Skeletons match the layout of the content they replace (no generic spinners on tables).
- **Error:** card `danger-bg` + amber left border, `icon 20px` + `title sm medium` ("Failed to load trades") + `message sm` (human, not raw exception) + `Retry` button + `request_id` mono xs (from `RequestIdMiddleware` for support). Form errors shown inline + banner.

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

- **No content loss.** Every data point available on desktop is reachable on mobile — via progressive disclosure (drawers, tabs, "Show more") not omission.
- **No table as-is on mobile.** Tables either horizontally scroll with sticky first column + column chooser, or collapse to cards at `<768px`. Never a squashed table where numbers are truncated without affordance.
- **Chart always visible above the fold** on every route where it appears, even on mobile (min 320px height).
- **Touch targets:** minimum 44×44px on mobile, per WCAG 2.5.5. Selector pills, table row actions, badges that are tappable all meet this.
- **Typography scales down 1 step** on mobile (base 13px → 12px) to preserve density without horizontal scroll.

### 9.3 Navigation Adaptation

- `≥1024px`: sidebar fixed, collapsible to 64px rail.
- `<1024px`: sidebar is an overlay drawer triggered by hamburger in top bar; ribbon becomes swipeable; global search/command palette remains available.

---

## 10. Accessibility

### 10.1 Contrast

- All text meets WCAG AA: `text-primary` (#E6EAF0) on `bg-surface-1` (#11161E) = 13.2:1. `text-secondary` (#9AA6B8) on same = 6.8:1. `text-tertiary` never used below `text-sm` on dark backgrounds; when used, it is always ≥4.5:1 via careful pairing (never tertiary on subtle).
- Chart grid/axis at 3:1 minimum (non-text graphics). Candle bodies exceed 4.5:1 against zone fills.
- Status badges use a fill + text + icon trio; contrast tested for each pairing. Amber danger on dark passes AA for large text (≥14px bold).

### 10.2 Keyboard Navigation

- Full keyboard operability: Tab through interactive elements in logical order (nav → ribbon chips → selectors → chart controls → tables). No keyboard trap.
- **Focus states:** 2px solid `--color-border-focus` outer ring + 1px `bg-base` inner ring (double ring for visibility on dark). Never rely on `outline: none` without replacement. Focus visible only via `:focus-visible`.
- **Shortcuts:** `Cmd+K` command palette, `G then D` go to dashboard, `G then W` watchlists, `G then B` backtests, `?` shortcut help overlay. All shortcuts listed in a `?` dialog.
- **Chart keyboard:** Arrow keys move crosshair; `+`/`−` zoom; `0` reset; focus ring on chart canvas.

### 10.3 Non-Color Status Indicators

Every status uses **at least two channels**: color + icon/shape + text label.

- Range: color badge + dot/hollow + text ("Valid", "Degenerate — flat data").
- Regime: color + arrow/hatch + text.
- Signal: color + triangle direction + text reason.
- Risk: color + check/block icon + text reason.
- Trade result: color + `WIN`/`LOSS` text + `+`/`−` sign.

Never color alone. Icons have `aria-label` and are not the sole conveyor.

### 10.4 Tables & Forms

- Tables: `role="table"`, proper `th` with `scope="col"`, sortable headers have `aria-sort`, row selection uses `aria-selected`, pagination with `aria-label`.
- Forms: each `input` has associated `label` (visible or `aria-label`), `aria-invalid` + `aria-describedby` pointing to error message. Required fields marked with `*` and `aria-required`.
- Inputs: `autocomplete` hints for auth fields, `inputmode="numeric"` for price/quantity.

### 10.5 Motion

- All transitions respect `prefers-reduced-motion: reduce` → duration 0, no movement (fade only or instant).
- No auto-playing animation. Skeletons and spinners are the only continuous motion; they pause when the tab is hidden.

### 10.6 Screen Reader Considerations

- Chart has a `table` fallback (visually hidden) with the same OHLCV + range data for SR users; canvas has `role="img"` + `aria-label` summarizing the market state ("BTC/USDT 1h — Valid range 65,100 to 68,400, price at 67,421 in middle no-trade zone, no setup").
- Live price updates use `aria-live="polite"` on the price hero, not on every tick (throttled to 5s) to avoid SR spam.
- Toasts use `role="status"` (info/success) or `role="alert"` (danger).

---

## 11. Core User Flows

Each flow lists: **entry → steps → success → error branches**. Screens reference §3 routes.

### 11.1 Flow 1 — Sign In → Dashboard

1. User visits `/` unauthenticated → redirect to `/login`.
2. Enters `email` + `password` → clicks `Sign In`.
3. `POST /auth/login` → `200 {access_token, user}`. Token stored (memory + `localStorage` for persistence, or httpOnly cookie if later adopted — abstracted behind auth client).
4. Redirect to `/` Dashboard. Ribbon and sidebar appear. Dashboard fetches `GET /watchlists` (default watchlist), then `GET /markets/BTC-USDT/candles?timeframe=1h&limit=200` for default pair/timeframe, then derives `RangeState` + `Signal`.
5. **Success:** chart renders with candles + range overlay + signal card. No flashes of unauth content.
6. **Errors:** 401 → "Invalid credentials" banner, fields preserved. 423/inactive → "Account disabled — contact owner." Network failure → retry banner with request_id. Token expired mid-session → intercept 401, redirect to login, toast "Session expired."

### 11.2 Flow 2 — Add Pair → Watchlist → Inspect Range

1. On `/watchlists/:id` or Dashboard mini-watchlist, clicks `Add Pair`.
2. Dialog: `Symbol` (search, e.g., `BTC/USDT` — validates against known symbols or free-form with backend normalization), `Venue` (select), `Notes` (optional).
3. `POST /watchlists/:id/items` → 201 `WatchlistItem`. Row appears optimistically, reconciled on success.
4. Clicks the new row (or ribbon chip) → navigates to Dashboard focused on `BTC/USDT`. Dashboard fetches candles for that symbol/timeframe.
5. Chart shows range overlay: if `VALID` → solid boundaries + zones; if `DEGENERATE` → dashed + reason "Flat data — no tradable structure"; if `INSUFFICIENT_DATA` → placeholder + "Need 20 candles, have 8."
6. **Errors:** 400 invalid symbol → field error "Unsupported symbol format." 409 duplicate → "Already in this watchlist." 404 watchlist not found → toast + redirect to `/watchlists`.

### 11.3 Flow 3 — Select Timeframe → Compare Range Conditions

1. On Dashboard chart header, clicks timeframe pill (e.g., `4h`).
2. Dashboard refetches `GET /markets/BTC-USDT/candles?timeframe=4h&limit=200`. Range detection re-runs for that timeframe's data.
3. Chart redraws: boundaries/width/confidence update; signal re-evaluates; RSI panel redraws.
4. **Multi-timeframe comparison (without leaving):** trader glances at the multi-timeframe strip (4 sparklines: `1h  4h  1d  15m`) — each shows `RangeStatus` dot + confidence bar + position meter + signal dot for the same symbol on that timeframe. The strip indicates at a glance "Range valid on 1h and 4h but degenerate on 5m."
5. Clicking a mini promotes it: main chart timeframe switches to that value (same as step 1).
6. **Errors:** timeframe not supported by provider → pill disabled, tooltip "Not available from Binance — try 1h or 1d." 502 `provider_error` → amber banner "Market data temporarily unavailable — retry in Xs" + cached data shown with staleness badge (e.g., "Data from 4 min ago").

### 11.4 Flow 4 — Evaluate Signal → Inspect RSI/Divergence → Inspect Risk

1. Dashboard signal card shows `LONG` (`SUPPORT_EDGE_SETUP`) with `confidence 0.68`, `position 0.18` (lower edge), `policy: optional`, `confirmation: true (RSI 28.4 ≤ 30)`.
2. Trader looks at RSI panel: RSI line dips to 28.4 inside oversold band — confirms. Toggles Divergence layer: a `BULL DIV` polyline connects two higher RSI troughs while price made lower lows — bullish divergence confluence.
3. Trader clicks `Preview Risk` (or panel auto-previews when a signal is actionable): `RiskEngine.evaluate` runs with current `AccountRiskState` (mock or account endpoint). Returns `RiskDecision`.
4. Risk strip updates: `APPROVED — Qty 0.142  Notional $9,534  Stop 64,800  Target 68,900  R:R 1:2.8  Fees ~$9.50  Slippage ~$4.70  Leverage 0.3×`.
5. If `REJECTED` (e.g., `MAX_OPEN_POSITIONS`), banner shows amber "Rejected — Max open positions (5/5) — close a position or raise cap in Risk."
6. **Branch — confirmation required but not met:** signal card shows `○ AWAITING CONFIRMATION` (outline triangle). RSI at 54.1 not in oversold. Trader either waits or changes `confirmation_policy` to `optional` in Strategy config.
7. **Branch — price in middle:** signal card shows `— NO SETUP — Price in middle (no-trade) zone` (gray). No triangle on chart. Trader does not trade — the UI makes the absence explicit, not ambiguous.

### 11.5 Flow 5 — Configure Strategy

1. Navigate to `/strategies`. List shows existing configs (if any) with `active` toggle.
2. Clicks `New Strategy` or edits an existing one.
3. Form: Section 1 `Range` — picks `mode` (e.g., `oscillator_confirmed`), fills `lookback: 100`, `oscillator: rsi`, `oversold: 30`, `overbought: 70`, `osc_period: 14`. Section 2 `Signal` — `lower_edge_zone: 0.25`, `upper_edge_zone: 0.25`, `confirmation_policy: required`. Section 3 `Risk` — `risk_per_trade: 0.01`, `stop_method: range`, `target_method: opposite_range_edge`, `max_open_positions: 5`, etc.
4. Clicks `Save`. Client validates required keys (`range_config`, `signal_config`, `risk_config` must be objects). `POST /strategies` → 201 `StrategyConfig`. `config_hash` displayed (short hash, copyable). Card appears in list.
5. **Errors:** 400 missing key → field error "range_config must be an object." Engine deeper validation (e.g., `edge_zones overlap`) shown inline. 409 duplicate name? — allowed (names not unique); id is the identity. Network error → retry.

### 11.6 Flow 6 — Connect Exchange

1. Navigate to `/exchanges`.
2. Clicks `Connect Exchange`.
3. Dialog: `Venue` (e.g., `binance`), `Display Name` (e.g., "Binance Main"), `API Key` (password input), `Secret` (password input), `Password/Passphrase` (optional), `Sandbox` toggle.
4. `POST /exchanges/connections` → 201 `ExchangeConnection` (no secret in response — only `credential_ref`). Card appears with `status` badge.
5. **Errors:** 400 missing fields → field errors. 502 provider error (invalid keys) → amber banner "Failed to verify credentials — check keys and venue." Secrets never logged or displayed after creation. `DELETE /exchanges/connections/:id` removes metadata + credential.

### 11.7 Flow 7 — Run Backtest → Inspect Results → Compare Performance

1. Navigate to `/backtests`.
2. Fills config form: picks `strategy` (from list), `symbol: BTC/USDT`, `timeframe: 1h`, `period: 2024-01-01 → 2024-06-01` (date pickers map to `start_ms`/`end_ms`), `initial_capital: 10000`, `fee_rate: 0.0005`, `slippage_rate: 0.0002`.
3. Clicks `Run Backtest`. Button shows loading spinner. `POST /backtests` → deterministic replay → returns `BacktestResult` + persisted `BacktestRunRecord`.
4. Result view (`/backtests/:runId`): statistics cards render (wins/losses/win_rate/profit_factor etc. — `profit_factor` shows `—` if no losses). Equity curve renders. Regime/zone bar charts show `regime_counts` + `zone_counts`. Trades table scoped to run.
5. **Compare:** back on `/backtests` list, selects 2–4 runs via checkboxes → `Compare` → split view with stats diff + overlaid equity curves.
6. **Errors:** 400 `start_ms >= end_ms` → field error "Start must be before end." No candles for period → amber empty state "No data for BTC/USDT 1h in this period — try a different range or ingest data." 502 market data failure → amber banner.

### 11.8 Flow 8 — Review Historical Trades / Statistics

1. Navigate to `/journal` (or `/positions` for trade history).
2. Statistics cards auto-compute via `GET /trades?limit=500` + `compute_trade_statistics` (or backend-aggregated stats). Shows headline KPIs.
3. Equity curve (cumulative realized PnL from closed trades) renders. Note label "Trade-close granularity — not intraday."
4. Table shows trades with filters (`symbol`, `result`, `status`). Clicks a row → drawer opens with `TradeContext` detail (range bounds/width/confidence, position_in_range, confirmation, risk_percent, regime/zone).
5. **OWNER branch:** `GET /trades` returns all trades; `GET /admin/trading-activity` aggregates across users. Owner sees strategy filters to slice by user-owned strategies.
6. **Errors:** no trades → empty state "No trades yet — run a backtest or start paper trading." Filter yields zero → "No trades match filters — clear filters."

### 11.9 Flow 9 — Admin → Users / System Health / Audit Activity

1. Owner navigates to `/admin`. Overview shows `SystemHealth` KPIs + trading activity totals.
2. **Users:** goes to `/admin/users` → table of users. Creates a new user: dialog `email/password/role` → `POST /admin/users` → 201 appears in table. Deactivates a user: `POST /admin/users/:id/active {active:false}` → row badge goes gray "inactive" + `last_login` preserved. Changes role, revokes sessions — each with confirm dialog + toast success/failure.
3. **System health:** `GET /admin/system-health` shows `status ok`, `schema_version`, `engine_versions {backtester, persistence_schema}`, `user_count`, `dataset_count`, `market_data_provider`, `time`. Degraded/down states shown with amber/red (infrastructure red allowed).
4. **Audit:** goes to `/admin/audit` → `GET /admin/audit-log?limit=100` → table of `AuditEvent` with `action/resource_type/outcome` filters. Each row's `metadata` collapsible JSON. This is append-only — no delete affordance.
5. **Trading activity:** `GET /admin/trading-activity` shows aggregate `totals` + `recent_backtests` for oversight.
6. **Errors / auth:** non-OWNER navigating to `/admin/*` → client redirects to `/` + toast "Admin access required"; server returns 403 on direct API call (never relying on client hiding). Inactive OWNER token → 401 → logout.

---

## 12. States & Edge Cases

### 12.1 Global

| State | Treatment |
|-------|-----------|
| **Loading** | Skeletons matching layout (not a centered spinner on full pages). Ribbon skeletons, chart skeleton, table row skeletons. |
| **Empty** | Centered outline illustration + title + one-line explanation + primary CTA. Distinct from error (no warning color). |
| **Error (recoverable)** | Amber card/banner with human message + `Retry` + `request_id` (mono xs) + optional `Details` disclosure with raw message. |
| **Error (fatal)** | Full-page error card + "Return to Dashboard" + request_id. |
| **Offline** | Amber top banner "You appear to be offline — data may be stale" + stale badge on data chips. |
| **Stale / auto-refresh** | Data chips show "Updated 3 min ago" (`text-xs tertiary`). Optional auto-refresh toggle per page. |

### 12.2 Chart-Specific Edges

- **INSUFFICIENT_DATA:** chart renders axes + grid, candles if any, but range lines are faint/dashed, zone fills absent, centered placeholder "Insufficient data — need 20 candles, have 8. Add more history or reduce lookback."
- **DEGENERATE:** full candles, dashed range lines, amber badge + reason tooltip ("Flat data — zero volatility"), signal card forced to `NON_TRADABLE_RANGE`, no triangles.
- **TRENDING / RANGING mismatch:** when `Regime` is `TRENDING_UP` but `RangeStatus` is `VALID`, both badges show — the UI does not hide either. The trader decides.
- **Gaps / quality warnings:** banner above chart "⚠ 2 gaps detected (00:00–04:00 UTC) — analysis excludes gap periods" + expandable issue list. Gaps rendered as vertical dashed lines on time axis.
- **Unclosed / forming candle:** rendered with 50% opacity + dashed outline, labeled `FORMING`. Excluded from range/signal calculation (shown in legend: "Based on 199 closed candles; 1 forming excluded").
- **Outside-range:** price line beyond zones, outside arrow + distance label, signal shows `PRICE_OUTSIDE_RANGE`.
- **NaN bounds / zero width:** bounds not rendered; chart shows "No valid range bounds — cannot derive zones."

### 12.3 Data Edges

- **Null stats:** `win_rate`, `profit_factor`, `average_r` etc. show `—` with tooltip "Not derivable — needs at least N wins/losses" — never `0` or `Infinity`.
- **Zero/negative equity, max drawdown at limit:** risk strip shows blocked state (amber fill + warning icon); preview calculator refuses and shows gate reason.
- **Large numbers:** prices use `,` grouping + `2 decimals` (or asset-appropriate precision), percentages `1 decimal`, PnL `2 decimals` + `+`/`−` sign, `R` multiples `2 decimals`.

### 12.4 Auth & Permission Edges

- **First registration:** email/password → becomes `OWNER`. Subsequent `POST /auth/register` calls fail with 400 "Registration closed — ask an owner to create your account" — the UI shows that message when attempting to register while a user already exists.
- **Inactive user:** login returns 401/403 → "Account inactive — contact owner."
- **Token refresh:** stateless bearer tokens; expiry handled via 401 intercept + redirect, not silent refresh.
- **Role escalation:** only `OWNER` can call `POST /admin/users/:id/role` — UI never shows the control to `USER`, but the server is the enforcer.

---

## 13. Design Principles

These are the non-negotiable rules every future frontend PR must satisfy. A proposal that violates any principle must be explicitly justified and approved.

1. **Range is the primary object, not the indicator.** Range detection defines tradability; RSI/oscillator is a confirmation layer. The chart, badges, and signal panel must always make this hierarchy obvious — never let RSI visually compete with range bounds (lavender vs. slate, panels separated).

2. **Middle is NO-TRADE and must look like it.** The middle zone has a hatch pattern and a centered `NO-TRADE` label. A trader scanning quickly must never mistake middle-zone price for a setup. If a design removes the hatch or dims it below recognition, it fails.

3. **VALID / DEGENERATE / INSUFFICIENT_DATA / TRENDING are four distinct looks.** Each has a unique badge color + icon + text + chart treatment (solid vs. dashed vs. hidden). No two may share the same visual encoding.

4. **Green/red mean market direction only.** Green = bullish / long / up; red = bearish / short / down. Risk blocks, rejections, degenerate warnings, and system errors use amber — never red — to avoid conflating "the market went down" with "the system blocked your trade."

5. **Confirmation policy is always visible.** `required` / `optional` / `ignored` appears as a badge next to the confirmation value on every signal presentation. A `NONE` due to `CONFIRMATION_NOT_MET` must explicitly state the policy; absence of information is not information.

6. **Every number gets its expected precision and its expected font.** Prices, quantities, PnL, percentages, and timestamps are monospace, tabular-nums, with consistent decimals and thousand separators. Sans is for prose. Mixing them blurs scanning speed.

7. **No silent zeros, no invented data.** Null stats show `—` not `0`. `profit_factor` with no losses is `—` not `∞`. Unreported `volume` is `—` not `0`. Quality gaps are disclosed, not interpolated. Stolen precision destroys trust.

8. **Dense by default, but never chaotic.** Information density is high (13px base, 44px rows, compact watchlists) — but separation is achieved with borders and subtle surfaces, not with card shadows, gradients, or pill excess. If a design adds glassmorphism or gradient ornament, it must prove the information is more scannable, not just more decorated.

9. **Desktop workstation first, responsive without loss.** All decisions are made for the ≥1280px workstation first. Mobile stacks and collapses but never omits a domain status or metric — it discloses progressively. If a mobile design hides `RangeStatus` or `confirmation` behind a second tap, it must have a strong justification.

10. **Every status shows color + icon + text.** No single-channel encoding. Colorblind users and fast scanners rely on shape and label as much as hue. Every badge, dot, and banner follows this.

11. **Configuration is reproducible and copyable.** `strategy_id`, `config_hash` (short + full on copy), `config_version`, `engine_version`, `run_id`, `request_id` are always shown mono, copyable with a single click, and preserved in shareable URLs where applicable. A trader must be able to reproduce exactly the backtest or live setup they are seeing.

12. **The API owns truth; the UI never invents it.** The UI renders what the backend returns (`RangeStatus`, `Regime`, `Signal`, `RiskDecision`, `DataQualityReport`, `StoredTrade`, `BacktestResult`) without re-deriving or re-interpreting. If a computation belongs to the domain, it lives in the backend engines (single source of truth). The UI's job is presentation, not second-guessing.

---

## 14. Validation Against Phases 1–9

Checked 2026-08-26 against `backend/src/*` and `backend/tests/*`.

| Phase | Domain | Design Alignment |
|-------|--------|------------------|
| **1** | `range_engine` — `RangeDetector`, `RangeState`, `RangeStatus` (`VALID`/`DEGENERATE`/`INSUFFICIENT_DATA`), `confidence` heuristic, modes `structural`/`volatility`/`manual`/`oscillator_confirmed`, `Factory` | Chart §7 renders `range_high/low`, `width`, `confidence`, `status` with distinct visuals per status; strategy editor §8.13 exposes `mode`+`params`; `is_tradable` gate drives signal card §6.1. No invented status values. |
| **2** | `signal_engine` — `RangeSignalEngine`, `Signal` (`direction`/`reason`/`position_in_range`/`confirmation`/`confidence`), `SignalReason` (`NON_TRADABLE_RANGE`, `PRICE_OUTSIDE_RANGE`, `PRICE_MID_RANGE`, `CONFIRMATION_NOT_MET`, `SUPPORT_EDGE_SETUP`, `RESISTANCE_EDGE_SETUP`), `ConfirmationPolicy` (`required`/`optional`/`ignored`), edge zones `lower_edge_zone`/`upper_edge_zone` | Signal card §8.8 shows all reasons + meters; zones visualized §6.3/§7.4; confirmation row shows policy+value+thresholds; optimism bias avoided (confidence labeled heuristic). No new reasons invented. |
| **3** | `risk_engine` — `RiskEngine`, `RiskDecision` (`APPROVED`/`REJECTED` + `RejectionReason`), gates (`max_drawdown`, `max_daily_drawdown`, `max_consecutive_losses`, `max_open_positions`, caps, leverage), `stop_method`/`target_method`, fee/slippage, reward/risk economics, `TradingConstraints` | Risk summary §8.12 and order panel §8.11 show gate progress + preview decision; rejection mapping §6.6 uses all canonical reasons; stop/target lines §7.5 encode `stop_method`/`target_method` outputs; fee/slippage displayed. Danger uses amber, not red. |
| **4** | `exchange` — `CredentialStore`, `TradingConstraints`, `Order`/`Position`/`Ticker`, `OrderBook`, `Balance` | Exchange connections §8.20 stores only metadata+`credential_ref`, never secrets; order/position models inform position table §8.10; `TradingConstraints` (tick, quantity_step, notional) shapes risk preview and is disclosed in decision metadata. No direct `HTTP→Exchange` in UI. |
| **5** | `execution_engine` — deterministic fills, paper/read-only posture | Order/execution panel §8.11 explicitly labels `PAPER MODE` and disables live CTA; Phase 9 posture `PAPER/READ-ONLY` documented in layout (§4) — no endpoint claims to place live orders. |
| **6** | `market_data` — `MarketDataPort`/`MarketDataService`, `CandleDataset`+`CandleSeries`, `Timeframe` (`1m`–`1d`, `duration_ms`), `DataQualityReport` (`issues`, `gap_ranges`, `is_analysis_safe`), `Ticker` | Ticker ribbon + pair selector §8.2/§8.4 use canonical `Timeframe` enum; timeframe selector shows unavailable values disabled; chart quality chip + gap rendering §6.9/§12.2 uses `is_analysis_safe`/`gap_ranges`/`contains_unclosed`; dash-form URLs match `GET /markets/:symbol` contract. |
| **7** | `persistence` — `StoredTrade` (`status` `OPEN`/`CLOSED`, `result` `WIN`/`LOSS`/`BREAKEVEN`, `TradeContext`), `TradeStatistics` (`win_rate`, `profit_factor`, `expectancy`, `average_r`, `total_realized_pnl`, `max_drawdown`), `DatasetSummary`/`IngestionResult`, `BacktestRunRecord` | Journal §8.17/§8.16 maps `TradeStatus`/`TradeResult` badges §6.7 and derived stats definitions verbatim (breakevens excluded from win_rate, profit_factor `None` → `—`); `TradeContext` drawer shows `range_*` + `confirmation` + `extra {regime,zone}`; equity curve label notes trade-close granularity. |
| **8** | `app_layer` — `User`/`Role` (`USER`/`OWNER`), `Watchlist`/`WatchlistItem`, `StrategyConfig` (`range_config`/`signal_config`/`risk_config`, `config_hash`), `ExchangeConnection`, `AuditEvent`, RBAC, ownership via `owner_user_id` | IA §2.2 and flows §11 hide admin for `USER` but enforce server-side; watchlists §8.3 map directly to `Watchlist`/`WatchlistItem` fields (`sort_order`, `enabled`, `venue_id`); strategy config §8.13 validates `REQUIRED_STRATEGY_KEYS`; audit log §8.22 renders `AuditEvent`; all ownership checks via `owner_user_id`. |
| **9** | `api` — FastAPI app, `RequestIdMiddleware`, uniform error envelope, routers: `auth` (`/auth/register` first-is-OWNER, `/auth/login|logout|me`), `watchlists`, `strategies`, `markets` (`/markets/:symbol/ticker|candles?timeframe&limit`), `backtests` (`POST /backtests` → `BacktestResult`+`BacktestRunRecord`, `BacktestConfig` `config_hash`), `trades` (`GET /trades?symbol&result&limit`), `exchanges`, `admin` (`/admin/users|audit-log|system-health|trading-activity`), `/health` | Route map §2.3 mirrors routers exactly; auth flows §11.1 use `Authorization: Bearer`; markets use dash-form symbols; backtest config locks to `BacktestConfig` field set including `fee_rate`/`slippage_rate`/`regime_lookback`; error states §8.25 show `request_id`; `/health` powers system status. |

**Result:** No invented features, no contradicted contracts, no missing enum cases. All statuses, reasons, policies, and value types referenced in this spec exist in the backend codebase. Terminology (wards such as `is_tradable`, `position_in_range`, `confidence heuristic`, `is_analysis_safe`) matches domain language exactly.

---

## Appendix — Figma / Stitch Handoff Checklist

- [ ] Create Figma Variables for every token in §5 (Colors, Typography, Spacing, Radii, Shadows, Motion). Publish as Library.
- [ ] Create Styles for `text-primary/secondary/tertiary` + mono variants.
- [ ] Build component set per §8 with `collapsed`/`active`/`loading`/`empty` variants.
- [ ] Chart: define a Figma component frame with placeholder canvas; annotate overlays per §7 with token references (not hex). Stitch: bind chart colors to CSS variables.
- [ ] Prototyping: wire Flows 1–9 (§11) as Figma prototype; each screen state includes loading/empty/error frame.
- [ ] Responsive: set auto-layout + constraints per breakpoints §9; define `data-density` variant.
- [ ] A11y annotations: add focus-ring, contrast notes, and non-color indicator notes per §10 on each component.

**Do not implement React/Next.js/FastAPI UI components until this spec is reviewed and approved.** This document is the contract; code follows it.

