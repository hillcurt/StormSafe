# Spec 0003 — Local cluster bootstrap

**Status:** approved
**Phase:** 0

## Goal
A local `kind` cluster with Argo CD that the owner can build from scratch with one script, and that syncs `trunk` (ADR 0007). After this lands, Argo CD shows a `stormsafe` application, **Synced** and **Healthy**, that deploys an empty `stormsafe` namespace. That is the GitOps loop working end to end before there is anything to serve. It also adds the `infra-reviewer` persona, because this is the first infrastructure spec (ADR 0003).

## Inputs / outputs
- **Creates:**
  - `deploy/cluster/kind-config.yaml` — single-node cluster; node image pinned by digest. No host ports: Argo CD is reached with `kubectl port-forward`.
  - `deploy/argocd/kustomization.yaml` — installs Argo CD from its upstream manifest, into the `argocd` namespace. The manifest URL is pinned to the release's **commit SHA** (tags can move), and Argo CD's images are pinned **by digest** through a Kustomize `images:` override, matching how the `kind` node image and the `Dockerfile` base are pinned.
  - `deploy/argocd/application.yaml` — the `stormsafe` `Application`: this repo, revision `trunk`, path `deploy/overlays/local`, automated sync with prune and self-heal, destination namespace `stormsafe`.
  - `deploy/base/` — the `stormsafe` namespace, and nothing else yet.
  - `deploy/overlays/local/kustomization.yaml` — the local overlay. When images exist, the deployed image digest lives here (ADR 0007).
  - `scripts/cluster-up.sh` — idempotent: creates the cluster if missing, installs Argo CD, applies the `Application`, waits for it to be Synced and Healthy, then prints how to open the UI. It prints the *command* to read the initial admin password, never the password itself.
  - `scripts/cluster-down.sh` — deletes the cluster.
  - `docs/cluster.md` — prerequisites (Docker, `kind`, `kubectl`, with tested versions), bring-up, opening the UI, teardown, and what to recreate by hand after a rebuild (Secrets, ADR 0004).
  - `.claude/agents/infra-reviewer.md` — read-only persona (`Read`, `Grep`, `Glob`) for manifests, scripts, the `Dockerfile`, and workflows: pinned versions, no Secrets or credentials, least-privilege permissions, drift from ADR 0006 and ADR 0007.
  - `tests/unit/test_deploy.py` — guards on the files above.
- **Changes:**
  - `.github/workflows/ci.yml` — a new job that renders every kustomization (`kubectl kustomize`), validates the output against Kubernetes schemas (`kubeconform`), and lints the scripts (`shellcheck`). Tools pinned. Permissions stay `contents: read`.
  - `CLAUDE.md` — the infra-config row names `deploy/overlays/local/kustomization.yaml` as the file that holds the deployed digest (deferred from the reviewer on #12).
  - `docs/adr/0006-container-build-and-registry.md` — correct the consequence that says `infra-reviewer` arrives with the container build spec: it arrives here, as ADR 0003 says.

## Acceptance criteria
- [ ] The `kind` node image is pinned by digest (test)
- [ ] Argo CD is installed from a manifest pinned to a commit SHA, with every Argo CD image pinned by digest: no tags, `stable`, `latest`, or branch refs (test)
- [ ] The `Application` targets this repo at revision `trunk`, path `deploy/overlays/local`, with automated sync, prune, and self-heal (test)
- [ ] No `Secret` object anywhere under `deploy/`, and no site values (test; site guard from Spec 0001 still applies)
- [ ] Every kustomization renders and passes schema validation, and the scripts pass `shellcheck` (CI job)
- [ ] `cluster-up.sh` is idempotent: a second run on a running cluster changes nothing and exits 0 (owner verifies)
- [ ] `cluster-up.sh` never prints a password or token: it only prints the command that reads the admin password and never runs that command itself (test checks the script)
- [ ] **Demo:** on the owner's machine, `scripts/cluster-up.sh` ends with the `stormsafe` application Synced and Healthy (owner runs it and attaches a screenshot of the Argo CD UI to the implementation PR)
- [ ] `infra-reviewer` is read-only, `Read`, `Grep`, `Glob` only (test, same guard as `reviewer`)
- [ ] `docs/cluster.md` covers bring-up, UI access, teardown, and post-rebuild steps
- [ ] `CLAUDE.md` and ADR 0006 updated as above; `docs/roadmap.md` Next actions updated

## Out of scope
- `Dockerfile`, `build.yml`, or any application workload (container build spec, before Phase 5)
- Creating the `stormsafe-site` Secret or any other Secret
- Ingress, TLS, monitoring stack, Argo CD notifications
- Argo CD managing its own install (app-of-apps); the script installs it
- Running `infra-reviewer` in CI; it is used locally until a later spec wires it into `ai-review.yml`

## Human-only touchpoints
- **Running** `cluster-up.sh`, `cluster-down.sh`, `kind create`, `kubectl apply`, and any Argo CD sync (`CLAUDE.md`). The agent writes the files; the owner runs them.
- **`infra-reviewer` tool list** (ADR 0003).
- **ADR 0006 text change:** a correction to an accepted ADR; merging the implementation PR accepts it.
- **`CLAUDE.md` guardrail row:** naming the digest file.

## Open questions
Answered by the owner:
1. **Owner's machine:** macOS on Apple Silicon (arm64), Docker Desktop. Every pinned image must have an `arm64` build; `docs/cluster.md` lists the tested Docker Desktop, `kind`, and `kubectl` versions.
2. **Argo CD:** the latest stable release at implementation time, full **non-HA** install (the UI is needed for the demo). Its commit SHA and image digests are recorded in `plan.md`.
3. **Manifest checks in CI:** render with `kubectl kustomize` and validate with `kubeconform` (pinned), using the published CRD schema for the Argo CD `Application`. A throwaway `kind` cluster in CI is deferred (roadmap "Later").
