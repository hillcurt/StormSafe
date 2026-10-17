# ADR 0001 — Record architecture decisions

**Status:** accepted
**Date:** 2026-10-17

## Context
StormSafe is a safety system built largely by coding agents. Decisions that trade safety against cost (thresholds, label definitions, process rules) need to be visible, reviewable, and stable, so neither a future agent nor a future maintainer quietly reverses them.

## Decision
Record each significant decision as an ADR in `docs/adr/`, using `TEMPLATE.md`:
- Numbers follow the order ADRs are merged and are never reused or renumbered.
- An ADR lands in the same PR as the change it governs. Merging that PR accepts it.
- An accepted ADR is never edited to change its decision; a new ADR supersedes it, and the old one's status links forward.
- Agents may draft ADRs when asked. Only the human changes an ADR's status (see `CLAUDE.md`).

## Consequences
- Every value in the "Human only" guardrails traces back to an ADR or the problem spec.
- Some overhead per decision, kept small by the one-page template.

## Alternatives considered
- **Decisions in PR descriptions only**: hard to find later, and agents don't read PR history.
- **A single design doc**: decisions get edited in place and lose their history.
