[🇯🇵 日本語](design-decisions.md) | [🇬🇧 English](design-decisions.en.md)

# Design Decisions

The full design log of the execution layer. Highlights are in the [README](../README.en.md#design-decisions).

## Separate decisions from orders

`build_signal` (decisions) never connects to the broker; `sender_gate` (orders) never decides. The only thing between them is the append-only `signal.jsonl`. Decisions can be verified and reproduced without credentials; orders alone can be disabled (dry_run); decisions alone can run for observation. When something goes wrong, the layer boundary tells you where.

## One decision, shared by backtest and production

Strategy decisions call the same functions from the bt-dynamic package with the same config JSON. The execution layer holds no copy or variation of the decision logic.

The identity extends beyond code to fill conditions. The backtest is built on a one-bar shift — indicators at bar N's close, entry at bar N+1's open. That kills lookahead bias, and it also matches the live reality that a 5-minute bar is not final the instant it ends: because of the shift, production decides on a completed bar and fills at the head of the next one, exactly as the backtest assumes. The forced end-of-session close (EOD) cuts the same way the engine does. If the formula you validated differs from the formula you run, the validation meant nothing.

## Ask the broker for the position

The first implementation kept local position state (a position file) and blocked signals while a position was open. What production taught us is that computing and holding position state locally looks easy and is far too hard to get right — when do you detect the TP/SL fill and clear the state? how do you reflect partial fills and failures? Asking the broker directly is simpler and correct.

So local position state was removed. Every signal enters; the broker handles netting. OCO quantities are computed not from the send history but from the position the API reports.

## OCO reconciles after the fill

TP/SL is not "place once at entry and forget". On every run, `oco_manager.ensure()` compares the working orders against the current net position: it cancels stale orders whose size no longer matches, places only the missing bracket legs, and sweeps orphan orders when there is no position. Nothing placed is ever trusted; each run converges toward the correct state, so partial failures, rate limits, and manual intervention all self-heal on the next run.

## No resident processes

Every script is started oneshot by a systemd timer, runs to completion, and exits. A resident daemon has a failure mode where it is dead and nobody notices; oneshot has none (and the timers' `Persistent=true` backfills missed runs).

Concurrency is defended with idempotency keys, not locks: orders key on the decision slot (`time_utc`), EOD on the date, the kill-switch action on a 5-minute slot — each checked against the existing record before acting. A duplicate invocation does nothing.

## State is append-only JSONL

Signals, send records, and close records are append-only JSONL files, written atomically (`.tmp` → `os.replace`). With no database, auditing is `grep` and `tail`, and recovery never amounts to more than reading a file. Because records are never rewritten, the files double as the ledger the idempotency keys are checked against.

## Fail toward safety

- The order gate defaults to dry_run (`ENABLE_EXEC_REQUESTS=0`). Run it forgetting the switch and it fails toward not trading
- Three independent layers close positions: the OCO right after the fill, the EOD close at session end, and the external kill switch. Any one can die; the others still flatten
- The kill switch is a one-line flag file — the smallest possible interface. The writer can be a detection system or a human with an editor at 3 a.m. The barrier to stopping is kept at zero

## Continuous sizing: heavier the earlier the trend

Lot size is `LOT_BASE × (recent mean of trend strength / current value)`: the weaker the trend reading (the earlier the move), the larger the size. The first implementation was a 3-step function, which meant carrying two boundary values and three lot values as tuning knobs; it was replaced with a knob-free continuous form. The formula is public; the base lot and decision parameters are injected.

## Keep it small enough to hold in your head

This execution layer has a predecessor: a functionally complete system with a finely decomposed multi-stage pipeline and resident monitoring. The moment it no longer fit in one head, it became hard to fix and hard to trust. A system entrusted with real money should prioritize one person being able to read all of it, at any time, over feature coverage — the decisions, orders, closes, and failure behavior in this repository fit in one evening of reading. Every decision above (the separation, oneshot, JSONL, deleting knobs) is also a consequence of this rule.
