# StormSafe

Predicts the risk of lightning near an outdoor pool facility, so staff know when to clear the water and when to warn swimmers.

**What this repo demonstrates:** an end-to-end ML system (data → model → serving → monitoring) built under an AI SDLC:

- **Track A – ML lifecycle with gates.** Every phase ends in a written artifact and a pass/fail gate. See [`docs/sdlc.md`](docs/sdlc.md).
- **Track B – AI-assisted development.** Coding agents implement from versioned specs; a human approves every gate and owns every safety-relevant decision. See [`CLAUDE.md`](CLAUDE.md).

## Status

| Phase | Artifact | Gate |
| --- | --- | --- |
| 0 Foundations | `CLAUDE.md`, `docs/sdlc.md`, project skeleton, CI | ⏳ |
| 1 Frame | `docs/problem-spec.md` | ✅ passed |
| 2 Data | `docs/data-contract.md` | — |
| 3 Develop | MLflow runs vs. baselines | — |
| 4 Evaluate | `docs/model-card.md` | — |
| 5 Deploy | shadow prediction log | — |
| 6 Monitor | `docs/runbook.md`, nightly outcomes | — |

## Repo map

```
CLAUDE.md            agent context + guardrails (read this first if you're an agent)
docs/sdlc.md         the process: phases, gates, dev loop
docs/roadmap.md      milestones and next actions
docs/adr/            architecture decision records
docs/specs/          one folder per spec: spec.md (approved) + plan.md (the agent's input)
```
