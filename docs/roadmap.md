# Roadmap

Each milestone ends with something demo-able and a passed gate (see `docs/sdlc.md`). Every PR updates "Next actions."

| Milestone | Delivers | Gates |
| --- | --- | --- |
| M0 Foundations | Process docs, `CLAUDE.md`, agent roles, project skeleton and CI, reviewer agent in CI, local `kind` cluster with Argo CD | 0 |
| M1 Framing | Signed-off problem spec, private site config, recall-first target | 1 |
| M2 Reliable data | GLM + weather ingestion, label builder, resumable training-set build, data contract | 2 |
| M3 Gated model | Baselines, XGBoost + calibration in MLflow, model card, `train.yml` regression gate | 3, 4 |
| M4 Live loop | FastAPI service in shadow mode, nightly outcomes, drift monitoring, runbook | 5, 6 |

## Next actions

- [x] Phase 0 foundations: process docs, ADR 0001 (record decisions), ADR 0002 (trunk-based development)
- [ ] ADR: agent roles
- [ ] ADR: site location is private config
- [ ] Gate 1: problem spec + recall-first ADR
- [ ] Spec 0001: project skeleton and CI (spec, then implementation)
- [ ] Spec 0002: reviewer agent (spec, then implementation)
- [ ] ADRs: container build and registry; deployment target
- [ ] Spec 0003: local cluster bootstrap (spec, then implementation)

## Later
- ADR + spec: Claude Code hooks for rules that must always hold (no `git add -A`, no site values, no test edits during bug fixes, `plan.md` kept current)
- Phase 2: evals for agent personas (seeded PRs the reviewer must catch), run when agent config changes
- Phase 6: monitoring breaches generate `intent.md`; escalation bands 1σ / 2σ / 3σ
- Process metrics: first-pass CI success for agent-written PRs, time to first review, DORA metrics
