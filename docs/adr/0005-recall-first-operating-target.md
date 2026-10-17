# ADR 0005 — Recall-first operating target

**Status:** accepted
**Date:** 2026-10-17

## Context
StormSafe is a safety system. A missed lightning event can put swimmers in danger; a false alarm costs swim time and some staff trust. These costs are not symmetric.

## Decision
Choose the **closure-tier** threshold to achieve **recall ≥ 0.9** on the time-based holdout, then maximize precision subject to that constraint. The advisory tier sits below it, routing marginal cases to a softer action. Report precision openly; do not tune it at recall's expense.

## Consequences
- Expect relatively low precision; this is a deliberate tradeoff, documented in the model card.
- The advisory tier absorbs some of the false-alarm cost: marginal cases warn swimmers instead of clearing the water.
- Any change to the recall target needs a new ADR that supersedes this one.

## Alternatives considered
- **Maximize F1** — treats misses and false alarms as equally bad; wrong for a safety context.
- **Fixed probability threshold (e.g., 0.5)** — ignores class imbalance and the cost asymmetry.
