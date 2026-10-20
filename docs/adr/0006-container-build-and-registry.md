# ADR 0006 — Container build and registry

**Status:** accepted
**Date:** 2026-10-19

## Context
StormSafe's serving layer (Phase 5) and its scheduled jobs run as containers in a Kubernetes cluster (ADR 0007). Images need a reproducible build, a registry the cluster can pull from, and tags that make every deploy traceable to a commit on `trunk` (ADR 0002). The repo is public and the owner is on the GitHub Free plan. Anything published must hold no site values (ADR 0004).

## Decision
- **Registry:** GitHub Container Registry, `ghcr.io/hillcurt/stormsafe`, as a public package. Free for public packages, authenticated with the workflow's own `GITHUB_TOKEN`, and pullable by the cluster without credentials.
- **What an image holds:** code and pinned dependencies only. No model, no data, no site config. The model is loaded at runtime from the MLflow registry and site config from the `stormsafe-site` Secret (ADR 0004). The same image runs for any site.
- **Build:** one multi-stage `Dockerfile` at the repo root. `uv sync --locked` in a builder stage; a slim runtime stage with the virtualenv only. Base image pinned by digest. Runs as a non-root user. Platforms `linux/amd64` and `linux/arm64`, so the image runs on the owner's machine whatever its CPU.
- **Where it builds:** a `build.yml` workflow. On every PR it builds without pushing, so a broken `Dockerfile` fails before merge. On a push to `trunk` it pushes `sha-<short commit>`. On a `vX.Y.Z` tag it pushes `vX.Y.Z`. Only the push jobs get `packages: write`; the PR job stays read-only. Actions pinned by commit.
- **Tags are immutable, and there is no `latest`.** A deploy references an image by digest, recorded next to its tag in the deploy manifests (ADR 0007). Rollback means pointing back at the previous release's digest.

## Consequences
- Every running pod traces to a commit: digest → tag → commit on `trunk`.
- A public image exposes code that is already public, and nothing else. The privacy guarantees of ADR 0004 hold as long as the image never contains a model or data; the reviewer and `infra-reviewer` personas check Dockerfile changes for this.
- Serving needs a reachable MLflow registry at startup. Where model artifacts live is decided in the data and artifact versioning ADR (roadmap, "Later"), before Phase 5.
- Two-platform builds take longer in CI. Layer caching through the GitHub Actions cache keeps that down.
- `sha-*` images pile up. A retention rule (keep releases, prune old `sha-*`) is part of the build spec.

## Alternatives considered
- **Docker Hub:** works, but needs a separate account and token, and has pull rate limits for anonymous clients.
- **A local registry next to the `kind` cluster:** no internet dependency, but images built in CI can't reach it, and it would make CI-built images untraceable. Local builds remain fine for development (`kind load docker-image`).
- **A cloud registry (ECR, Artifact Registry):** cost and cloud credentials for no benefit at this scale.
- **Bake the model into the image:** simpler startup, but couples code releases to model releases and would publish a model trained on private site data.
- **A `latest` tag:** makes what is running ambiguous and rollback unreliable.
