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
- [x] Spec 0003: implementation (plan, tests, code)
- [x] Spec 0003: tested Docker Desktop version in `docs/cluster.md` (v4.96.1)
- [x] Spec 0003: owner's demo, Synced and Healthy (recorded on the PR; screenshot waived); spec status → `done`
- [x] Spec 0003: owner re-ran `cluster-up.sh` on the fixed script; the Application's generation stayed the same (the first second-run had exposed an apply-then-patch flip)
- [x] `CLAUDE.md`: the agent runs `infra-reviewer` locally before opening infra PRs and answers its findings in the PR
- [x] Owner picked Phase 2 first; the container build spec waits until before Phase 5
- [x] ADR 0008: data and artifact versioning (Garage in the `kind` cluster on a host folder; DVC remote + MLflow artifact buckets; credentials human-only; no cloud)
- [x] ADR 0008 amendment: the laptop reaches the store through a `127.0.0.1`-only `kubectl port-forward` wrapper, not a host port mapping; Spec 0003's no-host-ports rule stays
- [x] Spec 0004: local object store — spec approved (owner answered the four open questions)
- [x] Spec 0004: implementation (plan, tests, code); readiness is a TCP probe, `store-init.sh` checks `/health` (owner's call, `plan.md`)
- [ ] Owner: rebuild the cluster, run `store-init.sh`, create the keys, and record the Spec 0004 demo (human-only)
- [ ] Then spec: DVC and MLflow wiring per ADR 0008 (`dvc init`, remote via `.dvc/config.local`, settings keys, a guard that no endpoint keys or host paths are committed)

## Later
- Revisit a fixed `127.0.0.1` port mapping for the store if port-forwards prove unreliable for daily `dvc` and MLflow work (ADR 0008 fallback; needs a rebuild and a change to Spec 0003's test)
- `infra-reviewer` follows `REVIEW.md` like `reviewer`: reads earlier comments, treats unanswered findings as blocking (pass 8); a test keeps both personas pointed at `REVIEW.md`. Before wiring it into `ai-review.yml`
- Spec: throwaway `kind` cluster in CI that runs `cluster-up.sh` on PRs touching `deploy/`; first settle in `CLAUDE.md` whether a disposable CI cluster counts as "a live cluster" (human-only). Worth it once there's a real workload
- Automated dependency update PRs (Renovate or Dependabot) for the commit- and digest-pinned actions and images; also pin the CI runner image or the tools it supplies (`jq`, used by the image pin check)
- ADR 0003 amendment + spec: AI findings as inline review threads, with "Require conversation resolution before merging" on `trunk`, so every finding must be resolved (acknowledged, not agreed) before merge. Makes findings a merge gate, so the owner decides
- `CLAUDE.md` rule: the agent may write workflows, but any new or widened `permissions:` is human-accepted. Lands with the container build spec, the first workflow with `packages: write` (from the reviewer on #12)
- Spec: container build (`Dockerfile`, `build.yml`, `sha-*` retention), per ADR 0006, before Phase 5
- ADR + spec: Claude Code hooks for rules that must always hold (no `git add -A`, no site values, no test edits during bug fixes, `plan.md` kept current)
- ADR: where the MLflow tracking server and registry run (tracking metadata is local, ADR 0004; serving in the cluster needs a reachable registry, ADR 0006). Before the Phase 3 training spec (from ADR 0008)
- Phase 3: how training runs now that GitHub-hosted runners can't reach the store (locally, or a cluster Job from a reviewed change); update `train.yml` in `docs/sdlc.md` to match (from ADR 0008)
- Phase 2: evals for agent personas (seeded PRs the reviewer must catch), run when agent config changes
- Helm for the StormSafe service when we add more than one environment: one chart version, promoted unchanged through the environments with a values file each, and an Argo CD ApplicationSet with one Application per environment. Needs an ADR at that point (it amends ADR 0007's Kustomize layout and moves the release lever from the overlay digest to the chart version). Until then the service stays Kustomize, like everything else. Infra (Argo CD, Garage) stays Kustomize either way. The same ADR decides whether deploy config moves to a separate repo; until then everything stays in this one (owner's call)
- Phase 6: an upstream monitoring stack (for example kube-prometheus-stack) as a pinned third-party Helm chart through Argo CD, with values committed here and upgrades reviewed as rendered diffs
- Phase 6: monitoring breaches generate `intent.md`; escalation bands 1σ / 2σ / 3σ
- Process metrics: first-pass CI success for agent-written PRs, time to first review, DORA metrics
