# Contextual ranges — September 2026

Implemented from the September 30 chart review: local sideways structures can
coexist with directional market context. Example references are SOL 4H
05.18.36, TIA 4H 07.05.25, and XRP 4H 07.17.38 in the user's chart folder.
Screenshots are qualitative references, not candle-level regression fixtures or
proof of performance. No images or personal paths are published with this file.

## Recognition and entry

- `range_policy=contextual` is the default. Two supported pivot clusters, minimum
  ATR height and contained closes establish a local range independently of ADX.
- Search the configured lookback first, then trailing 60/40/24 bars when the broad
  window does not qualify. Pivots need both confirmation sides already closed.
- Unsupported boxes are developing observations, never approved entry sources.
- `strict` remains selectable for ADX/EMA balance gating.
- Established bounds stay fixed through excursions; held breaks invalidate them.
  A later reclaim starts a new lifecycle at the original bounds. Prior stopped
  trades are never revived or rewritten.
- Weekly/daily opposing trends still block confirmed entries. Entries remain on
  1m/5m/15m against the highest available confirmed 4H/1H range.
- Preceding move describes the net move over up to 20 closed candles before the
  first boundary touch, using a 2 ATR threshold. It is not a reversal prediction.
- Nearby POIs are chart-timeframe pivot support/resistance confirmed before range
  formation, within 1 ATR of the corresponding edge. They do not represent every
  discretionary key level, round number, or higher-timeframe supply/demand zone.

## Midpoint observations

Use the range known before the observed candle. A deadband of max(3% of range,
0.1 ATR) separates midpoint reclaims/losses from rejection/support candles.
Identical events are spaced at least three candles apart. A second rejection or
support event within 20 bars of the same lifecycle is labelled repeated.
These observations live in a collapsible history (latest 20 shown), not extra
chart markers or entry triggers. No future breakout direction is inferred.

## Exit plan

New starting preset: 50% midpoint, 30% opposite edge, 20% runner, 2% trail.
These are editable research assumptions, not optimised settings. Existing saved
runner allocations are retained; zero means close the balance at TP2.

After TP1 the stop moves to entry. After TP2 the residual trails closed prices,
with changes applying only to the next candle. Stops take priority on ambiguous
bars. Adverse held range breaks still invalidate the trade; favourable breaks
do not. End of data closes the residual. Fees/slippage apply to all quantities.
TP1 plus runner must be below 100%, preserving a positive TP2 allocation.
Reward/risk assumes the runner exits at entry after costs, never projected profit.
Engine version is 2.1.0 so new replay identities differ from older results.

## Validation limits

Synthetic tests cover causality, trend/range separation, POI chronology, midpoint
observations, allocation validation, long/short runner fills and terminal exits.
Real venue/date replay against the screenshot examples is still needed to tune
recognition quality. The implementation does not claim to match every drawn box.

## Saved observations and personal review

The Manual range panel can save an account-private example, including user
boundaries, notes/reason, original automatic bounds, and the loaded analysis and
candles. Snapshots are labelled user-supplied, not authoritative execution data.
My ranges reopens that fixed snapshot or applies the saved bounds to a live chart.
Deleting an example removes it from subsequent reviews. Examples are immutable;
save another observation to document a later revision.

The optional 75% level is the midpoint of the upper half of the displayed range.
It defaults off and resets when market, venue or timeframe changes.

Review groups examples by symbol/venue/timeframe, counts a repeated closed-candle
snapshot once, and reports median boundary offsets normalised by automatic range
width. With at least 10 distinct observations it fits median offsets on the older
70% of saves and measures absolute boundary error on the remaining newer labels,
compared with unchanged automatic boundaries. This simple experimental model is
not automatically applied, is not an LLM, does not parse free-text reasoning, and
does not measure returns. Overlapping chart periods still introduce dependence;
the chronological check alone is not proof of generalisation. No model is shared
between accounts, and owners cannot read other users' saved observations.
