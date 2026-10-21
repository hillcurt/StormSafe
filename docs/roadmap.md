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
- [x] ADR 0003: agent roles
- [x] ADR 0004: site location is private config
- [x] Gate 1: problem spec + ADR 0005 (recall-first target)
- [x] Spec 0001: project skeleton and CI — spec approved
- [x] Spec 0001: implementation (plan, tests, code)
- [x] Spec 0002: reviewer agent — spec approved
- [x] Spec 0002: implementation (plan, tests, code)
- [x] Spec 0002 fix: note a skipped AI review; pin `actions/checkout` v6.1.0 by commit
- [x] Spec 0002 fix: run the reviewer directly in CI (no subagent hop); the workflow posts its review
- [x] ADR 0006: container build and registry (GHCR, immutable tags, deploy by digest)
- [x] ADR 0007: deployment target (`kind` + Argo CD, pull-based GitOps, shadow mode only)
- [x] Spec 0002 fix: earlier AI findings must be fixed or answered (REVIEW.md pass 8, PR template "Review findings")
- [x] `CLAUDE.md`: agent may draft in-repo infra config in PRs; applying it to a cluster, Secrets, and credentials stay human-only
- [x] Spec 0003: local cluster bootstrap — spec approved
- [x] Spec 0003: implementation (plan, tests, code) — owner runs the demo (`scripts/cluster-up.sh`, screenshot on the PR)
- [ ] Spec 0003: owner's demo screenshot on the implementation PR; tested Docker Desktop version in `docs/cluster.md`; spec status → `done`
- [ ] Next spec: container build (`Dockerfile`, `build.yml`, `sha-*` retention, ADR 0006) or Phase 2's data and artifact versioning ADR — owner picks

## Later
- Dedicated Argo CD `AppProject` for `stormsafe`: source limited to this repo, destination to the `stormsafe` namespace, no cluster-scoped kinds (least privilege with prune and self-heal; from the infra review on #15). Before the first real workload
- Spec: throwaway `kind` cluster in CI that runs `cluster-up.sh` on PRs touching `deploy/`; first settle in `CLAUDE.md` whether a disposable CI cluster counts as "a live cluster" (human-only). Worth it once there's a real workload
- Automated dependency update PRs (Renovate or Dependabot) for the commit- and digest-pinned actions and images
- ADR 0003 amendment + spec: AI findings as inline review threads, with "Require conversation resolution before merging" on `trunk`, so every finding must be resolved (acknowledged, not agreed) before merge. Makes findings a merge gate, so the owner decides
- `CLAUDE.md` rule: the agent may write workflows, but any new or widened `permissions:` is human-accepted. Lands with the container build spec, the first workflow with `packages: write` (from the reviewer on #12)
- Spec: container build (`Dockerfile`, `build.yml`, `sha-*` retention), per ADR 0006, before Phase 5
- ADR + spec: Claude Code hooks for rules that must always hold (no `git add -A`, no site values, no test edits during bug fixes, `plan.md` kept current)
- Phase 2, first: ADR + spec for data and artifact versioning. The ADR chooses the object store (for example, AWS S3 or a self-hosted S3-compatible store) and records why. Constraints: works as a DVC remote and for MLflow artifacts; data stays private (ADR 0004)
- Phase 2: evals for agent personas (seeded PRs the reviewer must catch), run when agent config changes
- Phase 6: monitoring breaches generate `intent.md`; escalation bands 1σ / 2σ / 3σ
- Process metrics: first-pass CI success for agent-written PRs, time to first review, DORA metrics
