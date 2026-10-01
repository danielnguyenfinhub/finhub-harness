# Quant guardrails — fixed audit rows

These six rows appear in every verdict for any slice that computes returns, P&L, scores, benchmarks or performs data splits (in practice: slice 11 evals/verifiers, and any later strategy or backtest code). Each row is ruled PASS / REJECTED / N/A with a one-line reason. The rows are fixed so a design cannot quietly skip one.

| # | guardrail | PASS requires the design to state | REJECTED when |
|---|---|---|---|
| G1 | Transaction fees | Fee model per trade (bps or fixed), applied on entry and exit, configurable, default > 0 | Returns computed gross; fee defaults to 0; fee applied on one side only |
| G2 | Borrow costs | Short positions accrue borrow (annualised rate × days held); financing on leverage | Shorts are free; leverage without financing cost |
| G3 | Slippage | Fill price differs from signal price (fixed bps, spread-based, or volume-based) | Fills at the same bar's close that generated the signal; zero slippage default |
| G4 | Look-ahead / future-index leakage | Signals use data up to `t-1` (or `t` close with fill at `t+1`); indicators computed on trailing windows; no `shift(-k)` on features | Any feature uses data timestamped after the decision time; centred rolling windows; `.iloc[i+1]` in feature code |
| G5 | Survivorship bias | Universe is point-in-time (includes delisted names) or the limitation is stated in the output | Uses today's constituent list for historical periods without disclosure |
| G6 | Train/test leakage | Time-ordered split (walk-forward or fixed cutoff); scaler/normaliser fit on train only; no shuffle across time | Random shuffle split on time series; normaliser fit on full dataset; hyper-params tuned on test |

## How to apply

- **Rows are per slice.** A slice with no numeric finance logic gets all six `N/A — <reason>` (e.g. "slice 3 safety: no prices or splits").
- **NET-NEW is fine** for these — most references do not implement them. The design must still describe the mechanism; the judge rules on the description.
- **Defaults matter.** A configurable fee that defaults to 0 is REJECTED: defaults are what actually runs.
- **Tests must prove it.** For PASS, the slice's Proof section should include a test that fails if the guardrail is removed (e.g. a synthetic series where a look-ahead feature would score perfectly).

## Synthetic example (for test design only)

```python
# Synthetic: 5 bars, signal on bar t must not see bar t+1.
prices = [100.0, 101.0, 99.5, 102.0, 103.0]
# A leaking feature "next_return" would make a perfect strategy; the test asserts
# the backtester raises or the feature is unavailable at decision time.
```

No real tickers, accounts or client portfolios in any example or fixture.
