# ADR 0007 — Deployment target

**Status:** accepted
**Date:** 2026-10-19

## Context
StormSafe needs somewhere to run the prediction service (Phase 5, in shadow mode) and its scheduled jobs, such as the nightly outcomes join (Phase 6). It is a single-owner portfolio project with no budget for always-on cloud infrastructure, and it should show the deployment practices an ML platform team uses: declarative config in git, reviewed changes, traceable releases, and fast rollback. GitHub Actions runners cannot reach a cluster on the owner's network without exposing it.

## Decision
- **Cluster:** a local Kubernetes cluster built with `kind` on the owner's machine. The cluster's own config (`kind` config, versions) is committed so it can be rebuilt from scratch.
- **Delivery:** pull-based GitOps with **Argo CD**, running inside the cluster. Argo CD watches this public repo's `trunk` and syncs the manifests under `deploy/`. CI never holds cluster credentials.
- **Manifests:** plain Kubernetes YAML under `deploy/`, composed with Kustomize: a `base/` and a `local` overlay. Images are referenced by digest (ADR 0006).
- **Deploy and rollback are git changes.** A release is a PR that sets the image digest in the `local` overlay to a tagged release. Rollback is a PR that sets it back. Argo CD auto-syncs `trunk` and self-heals drift.
- **Secrets stay out of git.** The `stormsafe-site` Secret (ADR 0004) and any credentials are created by hand in the cluster. Argo CD manages no Secret objects.
- **Scope of this target:** shadow mode only. Predictions are logged and compared with observed strikes; nothing alerts the facility. Running StormSafe as a live safety alert would need an always-on target and a new ADR.

## Consequences
- The whole deploy path is reviewable in PRs, and `trunk` always describes what should run.
- No cloud cost and no exposed endpoints.
- **Availability follows the owner's machine.** When it sleeps or is off, the service is down and shadow predictions have gaps. The nightly outcomes job and shadow-mode metrics must count coverage (hours predicted vs. operating hours) and treat gaps as missing, not as misses. This is acceptable for shadow mode and is the main reason the live-alert scope is excluded.
- Rebuilding the cluster means recreating its Secrets by hand. The runbook (Phase 6) lists the steps.
- Argo CD itself must be pinned and bootstrapped reproducibly; Spec 0003 covers that.
- `deploy.yml` (manual + approval, human-only) becomes the workflow that opens the release PR, not one that talks to the cluster.

## Alternatives considered
- **Managed cloud Kubernetes (EKS, GKE, AKS):** realistic, but costs money every hour it runs, for a project with no live users.
- **`k3s` on an always-on home server:** better availability; worth revisiting if StormSafe ever moves past shadow mode. Needs hardware the project doesn't have yet.
- **`minikube` or `k3d`:** comparable to `kind`. `kind` is the common choice for CI-style, disposable clusters and is well documented with Argo CD.
- **Docker Compose or a single VM:** simpler, but skips the Kubernetes and GitOps practices the project is meant to show.
- **Push-based deploys from GitHub Actions:** would need cluster credentials in CI and a cluster endpoint reachable from the internet, or a self-hosted runner on the owner's machine.
- **Flux instead of Argo CD:** an equally sound GitOps tool. Argo CD's UI makes sync state and history easy to show in a portfolio.
