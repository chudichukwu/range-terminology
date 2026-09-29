# Grandblue

A personal watchlist scanner, chart workspace, alert inbox and historical replay tool.

## Start locally

Requires Python 3.12+ and Node.js 20+.

```sh
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn dev_server:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm install
npm run dev -- --hostname 127.0.0.1
```

Open http://127.0.0.1:3000. Sign in or create your local account; the first account owns the workspace. Watchlists, playbooks, historical runs and alerts persist in `backend/range-trading-terminal.db`. Set `RANGE_DB_PATH` to use another database. The frontend proxies `/api` to the backend; set `API_SERVER_URL` if it runs elsewhere.

## Your workflow

1. Add your own markets in **Watchlists**, choosing their price source: Hyperliquid, Binance USDT perps or Binance spot. Exact symbols differ: for example `BTC/USDC:USDC`, `BTC/USDT:USDT`, or `BTC/USDT`.
2. Scan any combination of **1m, 5m, 15m, 30m, 1h, 4h, 1d and 1w**. Open a result to see real candles, range boundaries and confirmed swing-failure markers.
3. Save a **Playbook** to change range lookback, repeated touches, entry, invalidation, sizing assumptions and breakout runner.
4. Save a watchlist monitor in **Alerts**. The server runs scans even with the browser closed while the server process stays running.
5. Use **Backtests** with a source, exact symbol, timeframe, period, fees and slippage. Runs preserve configuration and data fingerprints.

## Confirmed range strategy (v2)

New/default playbooks use the revised balanced-range specification. Saved legacy playbooks retain their old rules.

- Weekly/daily supply context. Prefer the highest clean 4H/1H range. Only 15m/5m/1m confirm entries; 30m remains available for inspection.
- At least two confirmed pivot touches per side (three or more stronger), clustered boundaries, closes contained, range height at least 2.5× ATR14.
- ADX14 below 22, flat EMA20/50 slopes (five-bar slope ≤0.15 ATR per bar), no three-pivot HH+HL or LH+LL sequence. ADX ≥25 and direction from EMA-side holding or swing structure flags a strong trend. Opposing weekly/daily trends block entries.
- Range boundaries freeze once accepted. Two consecutive closes beyond a 0.375 ATR buffer retire the range. New pivots must establish a new range.
- Extremes occupy 15% of range width. Confirm with a boundary SFP reclaim within one to three closed candles or rejection wick. Optional alternatives: engulfing or a close through the previous three-bar high/low. Optional volume multiple uses the preceding 20 bars. Long confirmations stay below midpoint; shorts above.
- A+ is a rule category, not a win probability. Entry confirmation uses already-closed higher-timeframe candles; no future or forming context.
- Stop beyond the sweep/trigger wick or range boundary, whichever is farther, plus 0.375× range-timeframe ATR. TP1: 50% at midpoint, remaining stop to entry. TP2: 2% of range width inside the opposite boundary, full exit. No runner; breakout/retest entries are a separate strategy and are not generated here.
- Require at least 2:1 **weighted** reward/risk after modeled costs across both partial exits. This is stricter than measuring only the full-range target.
- Live previews assume 10,000 quote-currency equity, 0.05% fees and 0.02% slippage; backtests use their entered values. Default risk is 1%, leverage cap 3×. All approximate thresholds are editable in Playbooks.

Indicators use seeded Wilder averages; reference: [TA-Lib ADX](https://ta-lib.github.io/ta-doc/indicator/ADX.htm) and [ATR](https://ta-lib.github.io/ta-doc/indicator/ATR.htm).

## Alerts and historical limitations

In-app events are persistent and deduplicated. Browser notifications require permission and an open app tab; mobile support varies. Telegram requires a bot created through BotFather, `TELEGRAM_BOT_TOKEN` in the backend environment, and the destination chat ID in the monitor. Start a conversation with your bot before enabling delivery. No token belongs in frontend code.

Scanning pauses 30 seconds between cycles. A large watchlist or source rate limits can lengthen this; alerts are candle polling, not tick-level guarantees. Incomplete/stale data suppresses signals. Source outages surface as errors.

Backtests fetch up to 5,000 closed candles per timeframe including warm-up; source history limits may be shorter. Confirmed-range replays automatically fetch weekly/daily and 4H/1H history, and reject incomplete context. All five source histories contribute to the run fingerprint. Confirmed entries fill at the next open and recheck reward/risk after any gap. Ambiguous stop/target bars favor the stop, including a same-bar TP1/breakeven-stop test. Two held entry-timeframe closes beyond the adverse boundary plus buffer exit at the confirming close. Remaining positions close at end of data. Legacy touch/runner rules apply only to legacy playbooks. Results model fees/slippage but not funding, liquidation or order-book liquidity. Equity and drawdown summarize completed trades, not intratrade mark-to-market or interim partial-fill equity. This app does not place orders.

## Checks

```sh
cd backend
.venv/bin/pytest -q
```

```sh
cd frontend
npm run typecheck
npm run build
```
