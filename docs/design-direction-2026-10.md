# Grandblue — reference review and product direction

12 October 2026 · First-pass proposal · No application changes in this pass

## Product direction

A focused workspace for discretionary range traders: discover a setup, understand
its context, mark a range, monitor it, and learn from the outcome. Crypto spot and
perps first; preserve exact venue and market identity throughout the workflow.

The defining feature is the connection between automated range detection and a
trader's own interpretation. Manual markings, reclaim context, midpoint reactions,
quiet SFP annotations and optional runners should feel native to the workspace.

## What was reviewed

- Visual contact-sheet review of all 45 top-level image files in
  `/Users/mac/grandblue design ideas/`; closer inspection of Origin, the purple
  staking dashboard concept and the Edgewonk journal image.
- Metadata from the saved HTML files. The Figma files identify generic Community
  pages; this pass does not establish access to editable Figma components.
- Public product pages and selected official help pages for the eleven products
  below. This is reference research, not hands-on testing of logged-in products.
- The folder's MP4 has not been reviewed for motion or interaction behavior.
- Current Grandblue scanner, analysis view, journal/performance routes and risk
  placeholder. Existing DESIGN.md is an older baseline; this proposal does not
  silently supersede its technical contracts.

## Visual references → decisions

| Local reference | Useful detail | Grandblue interpretation |
| --- | --- | --- |
| Origin Web 326.png | Quiet black surfaces, thin borders, clear primary panel | Graphite workspace with one dominant chart or task; blue for selected controls |
| original-da19059e6b93db48b8e91b499c768751.webp | Restrained highlights and consistent card grouping | Use similar hierarchy, with Grandblue blue; keep glow away from market data |
| original-da59c9605e1e9a2228d8244101a26fb6.webp | Compact scanner table and separate contextual panels | One market row with a timeframe matrix and a small setup summary |
| Copilot Money Web 145.png / 98.png | Readable numerical hierarchy, overview/detail separation | Small useful summaries above the work area; avoid a wall of KPI cards |
| Trading-Journal-Home-2025-xl.webp | Edgewonk calendar, reports and trade counts | Calendar as an optional journal view; every metric drills into its sample |
| e3636944-5ab9-4844-8ab4-8269a91708be_thumb.jpg | Mobile filter sheet with Reset and Apply | Filters in a bottom sheet; one deliberate Apply instead of rescanning on every tap |
| e62f6704-3708-4771-9058-199a43f81311_thumb.jpg | Manage-watchlist sheet | Add/reorder markets without leaving the current workspace |
| Phantom iOS 74.png / Public iOS 45.png / Coinbase Wallet iOS 14.png | Short market lists, clear page identity, bottom navigation | Mobile task views with accessible controls and fewer simultaneous panels |
| Dense terminal screenshots and download.png | Chart priority and aligned controls | Compact toolbar, large chart, collapsible setup inspector |

The journal image is Edgewonk, not TradeZella. Both are useful references, but
their identities should remain distinct. Splash screens, promotional panels and
order books are low-priority references for the current range-research workflow.

Suggested starting tokens: canvas #07090D, surface #10141B, raised surface
#171D27, border #29313E, primary text #F2F5FA, secondary text #A3ADBD, action blue
#326BFF. Verify contrast in actual components before adopting. Use 12–16px panel
radii, tabular numerals, readable 14px data text, and 44px touch targets.
Green/red communicate direction or results; blue communicates selection/action.
Every state also needs a text label or icon. Respect reduced motion; cursor glow
remains subtle on pointer devices and does not appear on touch screens.

## Product research → what to borrow

These are design recommendations drawn from the cited capabilities, not claims
that Grandblue already implements them.

| Product and source | Reference value | Grandblue application |
| --- | --- | --- |
| [Cryptohopper Strategy Designer](https://www.cryptohopper.com/features/strategy-designer) | Strategy construction with access to testing | Keep editing and backtest results in one Strategy Lab workflow |
| [3Commas](https://3commas.io/) | Distinct bot categories and trading tools | Separate rule definition, monitoring status and any future execution mode |
| [Altrady multi-charts](https://www.altrady.com/features/multi-charts) | Multiple markets/layouts in one workspace | Optional paired context/entry charts on desktop; single chart on phone |
| [Coinrule Build a Rule](https://help.coinrule.com/articles/247956-build-a-rule) | Conditions followed by actions | Readable IF / AND / THEN rules with validation and a plain-language summary |
| [Hummingbot controllers](https://hummingbot.org/strategies/v2-strategies/controllers/) | Strategy controllers separated from execution actions | Architectural reference for later automation, rather than our visual template |
| [TrendSpider multi-timeframe analysis](https://help.trendspider.com/kb/automated-technical-analysis/multi-timeframe-analysis) | Context from multiple timeframes and multi-timeframe scanning | Make weekly/daily context, 4H/1H range and minute entries explicit |
| [TradingView features](https://www.tradingview.com/features/) | Chart analysis, layouts and strategy testing | Chart-first navigation and results linked back to the relevant candles |
| [TradeZella journaling](https://help.tradezella.com/en/articles/10440247-journaling-backtesting-trades-while-backtesting) | Notes, trade tags and strategy links during review | Link thoughts and screenshots to setups, playbooks and outcomes |
| [Composer strategy creation](https://help.composer.trade/article/54-create-tutorial) | Composable conditions and groups with backtest feedback | Start with a guided range playbook; expose advanced branching progressively |
| [TraderSync](https://tradersync.com/) | Filtered performance reports, replay playlists and plan-adherence tracking | Link saved setups to review sessions; compare followed-plan and deviated-plan trades with sample counts |
| [Edgewonk](https://edgewonk.com/) | Trading journal and performance review; the supplied screenshot shows calendar and evaluation panels | Connect daily notes and trade records to a filterable calendar and drill-down reports |

### Journal synthesis

Combine TradeZella's setup-linked notes, TraderSync's review/practice workflow and
the Edgewonk calendar/report structure. The first action stays **Write a thought**;
logging a completed trade is a separate optional action. A note never requires an
entry price, exit price or P&L.

Use three record types: Thought, Setup and Trade. Each may reference a market,
timeframe, playbook, screenshot and saved range. Setup records can be marked
Watching, Taken, Missed or Invalidated; missed opportunities never count as
realized returns. Trade reviews can record plan adherence and optional mistake
tags without turning the whole journal into a compulsory questionnaire.

Performance filters should answer range-specific questions: clean range versus
trend continuation; SFP versus rejection entry; midpoint rejection; manual versus
automatic range; runner enabled versus full exit. These require explicit stored
labels and complete trades. Reports show missing data and sample counts, and
distinguish descriptive findings from evidence that a rule improves future results.

## Navigation and responsibilities

Keep eight product areas, grouped by task rather than eight equal destinations.

- **Trade:** Overview, Scanner, Watchlist. Analysis opens from a market and keeps
  the scanner filters, selected token and scroll position when returning.
- **Research:** Strategy Lab, Journal, Performance.
- **Risk:** Risk Center, once supported by reliable position/account inputs.
- **Account:** settings and data preferences. Admin remains owner-only, enforced
  on both the navigation and backend routes.

On mobile: Overview, Scanner, Journal, More. A market opens a focused Analysis
view. More contains Watchlist, Strategy Lab, Performance, Risk and account tools.
On iPad: collapsible navigation, chart plus optional inspector in landscape;
single-column layout in portrait. Avoid shrinking desktop tables onto a phone.

| Area | Main question | Primary content / action |
| --- | --- | --- |
| Overview | What needs attention? | Watchlist regime summary, fresh edge/reclaim events, recent notes, resume last chart |
| Scanner | Which markets match my setup? | One row per token; timeframe states; edge distance; freshness; explain why it matched |
| Analysis | Is this range worth watching? | Large chart, range context, latest SFP, manual levels, setup checklist; save or alert |
| Strategy Lab | What are my rules and how do they behave? | Guided editor → test → inspect trades → save a version |
| Watchlist | What should Grandblue monitor? | Exact venue/market, groups, timeframes, alert rules and monitor health |
| Journal | What did I see and what happened? | Quick thought, setup note or completed trade; screenshots and linked range context |
| Performance | Where is the strategy working? | Net results, expectancy, drawdown and sample count by playbook/regime/timeframe |
| Risk Center | What is my current risk? | Explicitly sourced exposure, limits and gate reasons; unknown when inputs are absent |

## First screen to redesign: Scanner → Analysis

Scanner desktop columns: Market / Weekly / Daily / 4H / 1H / selected entry
timeframe / Setup / Updated. Clicking a timeframe opens that exact chart.
Use separate labels for regime, range validity and entry confirmation: a ranging
market is not automatically a valid range, and an edge touch is not confirmation.

Offer Context, Range and Entry timeframe groups, with custom selections retained.
Apply filter changes together; preserve previous results while updating, display
their age, and clearly distinguish failed refreshes from a fresh no-setup result.
Define counts as markets or market/timeframe combinations, never ambiguously.

Analysis desktop: compact symbol/venue toolbar, timeframe strip, chart occupying
most of the width, collapsible right inspector. Inspector tabs: Setup, My range,
Notes. Show RH/RL/50% by default; 25% and 75% are optional and off initially.
Show only recent relevant SFPs initially, with historical annotations available
through a control. Keep manual and automatic boundaries distinguishable.

Manual range saving captures exact market, venue, timeframe, time window, levels,
reason and candle snapshot when available. Screenshot-only labels remain marked
as unverified historical context. Saving an observation does not silently change
live strategy rules. Optional runner plans belong in the trade plan, with a
defined remainder and exit rule when enabled.

Mobile Analysis: chart first, persistent symbol/timeframe control, and a sheet
for Setup / My range / Notes. Preserve chart pan/zoom through background refresh.
Test gestures on real iPad/iPhone; viewport checks alone are insufficient.

## Phases and completion checks

1. **Workspace foundation:** navigation, typography, surfaces, loading/error/
   stale states, scanner matrix and chart hierarchy. Complete when a user can
   find a setup, switch timeframes, return without losing context, and see data
   freshness on desktop, iPad and phone.
2. **Analysis and observation:** range editing, optional levels, SFP decluttering,
   linked notes/screenshots and alert creation. Complete when a saved observation
   reopens its original context and manual levels cannot masquerade as automatic
   confirmations.
3. **Strategy Lab:** guided rules, versioning, backtests and trade inspection.
   Complete when saved versions reproduce their tests with date range, fees,
   slippage and data-quality assumptions visible. RSI divergence needs a defined
   detector, causal timing and API contract before appearing as a live signal.
4. **Journal and Performance:** distinguish thoughts, setups and completed trades;
   add calendar/review views and meaningful breakdowns. Keep backtest, paper and
   actual results separate. Every report needs sample size, period and fee basis.
5. **Risk and operations:** reliable position sources, account isolation, recovery,
   monitoring and always-on background jobs. Risk gates are advisory until an
   execution integration can actually enforce them. Automation is a separate
   explicitly scoped phase, not implied by borrowing a bot platform's UI.

## Current gaps to respect

The current root view combines scanner and market detail. Saved ranges and journal
notes exist; performance-related UI is under journal/history. Risk Center is a
placeholder and RSI divergence lacks a live backend contract. The proposed map
organizes future work; it is not a claim that all listed capabilities are ready.

Next deliverable: desktop and mobile Scanner/Analysis wireframes using the actual
available fields, including empty, stale and provider-error states. Use original
Grandblue components; reference screenshots are research material, not app assets.
