# Plan for spec 0003 — Local cluster bootstrap

**Spec:** `docs/specs/0003-local-cluster-bootstrap/spec.md`
**Status:** done

## Approach
Plain Kustomize under `deploy/`, applied by two small Bash scripts the owner runs. `scripts/cluster-up.sh` creates a single-node `kind` cluster from `deploy/cluster/kind-config.yaml` if it is missing, installs Argo CD with a server-side apply of `deploy/argocd/` (Argo CD 3.x's CRDs are too large for client-side apply), waits for its CRDs and workloads, applies the `stormsafe` `Application`, and polls until it reports **Synced** and **Healthy**. Every step is declarative or guarded, so a second run changes nothing. Argo CD then pulls `deploy/overlays/local` from `trunk`, which renders `deploy/base/`: one `Namespace`.

Every external reference is pinned: the `kind` node image and the Argo CD images by digest, the Argo CD manifest by commit SHA, the CI tools by version and SHA-256, the schema sources by commit. Unit tests guard the pins and the shape of the files. A new CI job renders every kustomization, validates it with `kubeconform`, lints the scripts with `shellcheck`, and checks every pinned digest is a multi-arch index with a `linux/arm64` entry.

## Pinned versions
| What | Version | Pin |
| --- | --- | --- |
| `kind` (CLI, owner installs) | v0.33.0 | — |
| `kind` node image | `kindest/node:v1.37.0` | `sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5` (from the kind v0.33.0 release notes) |
| Argo CD (non-HA `install.yaml`) | v3.5.6, latest stable | commit `c2b1e3017e2cec86b122172e861dcd026453ae44` |
| `quay.io/argoproj/argocd` | v3.5.6 | `sha256:8e5cc5bb008df8a09dba439462e58c94c55b7735888d3ebde0c25fc05e4e5335` |
| `ghcr.io/dexidp/dex` | v2.45.1 (as shipped by Argo CD v3.5.6) | `sha256:8499afd690c437f52301efd2b05b2455da5bd2dfc20332cd697dc9937f808462` |
| `public.ecr.aws/docker/library/redis` | 8.2.3-alpine (as shipped by Argo CD v3.5.6) | `sha256:08ad0b1d280850169a790dba1393ff7a90aef951fc19632cf4d3ce4f78e679ba` |
| `kubectl` (CI, via `azure/setup-kubectl` v5.2.0 by commit) | v1.37.1 | — |
| `kubeconform` (CI) | v0.8.0 | SHA-256 checked |
| `shellcheck` (CI) | v0.11.0 | SHA-256 checked |
| `crane` (CI, digest checks) | v0.22.1 | SHA-256 checked |
| Kubernetes JSON schemas | `yannh/kubernetes-json-schema`, v1.37.0 strict | commit `93153a1458e24e93f386c50f9980d584fcba574b` |
| `Application` CRD schema | `datreeio/CRDs-catalog` | commit `501527ab9c40c827144c8f45945b25a023e344ce` |

## Files
| File | Create / change | Why |
| --- | --- | --- |
| `deploy/cluster/kind-config.yaml` | Create | Single node, image by digest, no host ports |
| `deploy/argocd/kustomization.yaml`, `namespace.yaml` | Create | Argo CD install pinned to a commit, images pinned by digest, into the `argocd` namespace |
| `deploy/argocd/application.yaml` | Create | `stormsafe` `Application`: this repo, `trunk`, `deploy/overlays/local`, automated sync with prune and self-heal. Kept out of the kustomization so it is applied after the CRD exists |
| `deploy/base/kustomization.yaml`, `namespace.yaml` | Create | The `stormsafe` namespace only |
| `deploy/overlays/local/kustomization.yaml` | Create | Local overlay; future home of the deployed digest (ADR 0007) |
| `scripts/cluster-up.sh`, `scripts/cluster-down.sh` | Create | Idempotent bring-up; teardown |
| `scripts/check-image-pins.sh` | Create | CI helper: each `name:tag@digest` must be a multi-arch index with `linux/arm64`; warns, with the current digest, when the tag has moved. Findings are also PR annotations. When `public.ecr.aws` rate-limits (it did on this PR), Docker official images are read from Docker Hub by the same digest |
| `docs/cluster.md` | Create | Prerequisites and tested versions, bring-up, UI, teardown, post-rebuild steps |
| `.claude/agents/infra-reviewer.md` | Create | Read-only persona (`Read`, `Grep`, `Glob`) |
| `tests/unit/test_deploy.py` | Create | Guards on all of the above |
| `.github/workflows/ci.yml` | Change | New `manifests` job; permissions stay `contents: read` |
| `CLAUDE.md` | Change | Infra-config row names `deploy/overlays/local/kustomization.yaml` |
| `docs/adr/0006-container-build-and-registry.md` | Change | `infra-reviewer` arrives with this spec |
| `docs/roadmap.md` | Change | Next actions |

## Tests (written first)
1. `kind` node image pinned by digest → `test_kind_node_image_pinned_by_digest`
2. Argo CD manifest pinned to a commit SHA; every Argo CD image overridden by digest; no `stable`, `latest`, or branch refs → `test_argocd_manifest_pinned_to_commit`, `test_argocd_images_pinned_by_digest`
3. Pinned digests are multi-arch with `linux/arm64` → CI step `scripts/check-image-pins.sh` (needs registry access, so not a unit test)
4. `Application` targets this repo, `trunk`, `deploy/overlays/local`, automated sync with prune and self-heal → `test_application_targets_trunk_overlay`
5. No `Secret` under `deploy/` → `test_no_secrets_under_deploy`; site guard from spec 0001 still runs
6. Kustomizations render and validate, scripts pass `shellcheck` → CI `manifests` job; `test_ci_validates_manifests_read_only` checks the job exists, its tools are pinned and checksummed, and permissions stay read-only. `kubeconform` skips `CustomResourceDefinition` objects (the strict schema set has none; they come verbatim from the pinned Argo CD manifest)
7. `cluster-up.sh` idempotent → owner verifies; `test_cluster_up_is_guarded` checks the create is guarded and applies are declarative
8. `cluster-up.sh` never prints a secret → `test_cluster_up_prints_password_command_only`
9. Demo → owner runs it and attaches a screenshot
- Base holds only the namespace → `test_base_is_the_namespace_only`
10. `infra-reviewer` read-only → `test_infra_reviewer_is_read_only`
11. `docs/cluster.md` sections and versions → `test_cluster_doc_covers_lifecycle`
12. `CLAUDE.md` names the digest file → `test_claude_md_names_digest_file`

## PR slicing
One PR. It is mostly YAML and two short scripts.

## Risks and open questions
- **Demo before merge.** The `Application` tracks `trunk`, so before this PR merges Argo CD would find no `deploy/overlays/local` there. `cluster-up.sh` reads an optional `STORMSAFE_REVISION` (default `trunk`) and, only when it is set, patches the live `Application` to that branch. The committed file still says `trunk` (tested). The owner runs `STORMSAFE_REVISION=spec-0003-local-cluster-bootstrap scripts/cluster-up.sh` for the screenshot, then a plain run after merge moves it back to `trunk`.
- **Argo CD image digests** could not be read from this agent's sandbox (registry hosts are blocked there). The Argo CD and Dex digests were taken from the CI pin check's tag lookups on this PR; CI verifies all of them.
- **Tested versions** in `docs/cluster.md`: `kind` and `kubectl` are the pinned ones above; the Docker Desktop version is filled in by the owner from the demo run.
- **No new Python dependency.** Tests parse the YAML with regular expressions, like `test_agents.py`, rather than adding PyYAML.
