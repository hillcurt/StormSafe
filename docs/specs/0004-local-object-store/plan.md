# Plan for spec 0004 — Local object store

**Spec:** `docs/specs/0004-local-object-store/spec.md`
**Status:** proposed

## Approach
Plain Kustomize manifests for a single-node Garage under `deploy/base/garage/`, synced by Argo CD like the rest of `deploy/` (ADR 0007, ADR 0008). Garage's data and metadata live in a host folder outside the repo. `kind` mounts it into the node at a fixed path, and a hostPath PersistentVolume, bound to one claim, mounts that path into the pod. Two owner-run scripts complete the setup. `store-init.sh` does the one-time layout and buckets through `kubectl exec`, and prints the key commands without running them. `store-forward.sh` opens a `127.0.0.1`-only port-forward for as long as one command needs it.

`cluster-up.sh` gains three things: the host folder, a mount check on a running cluster, and Garage's Secret. It reads `STORMSAFE_STORE_HOST_DIR` from the environment or `.env`, and refuses to run without it. It renders the `kind` config's placeholder into a temporary file only when creating a cluster. After it applies the Application, it waits for Argo CD to create the `stormsafe` namespace. Then it creates Garage's Secret from `openssl rand` if the Secret is missing, and only then waits for Synced and Healthy. The Garage pod waits for the Secret to appear (`CreateContainerConfigError`, retried by the kubelet).

A new `stormsafe` `AppProject` replaces `default`. It allows this repo as the only source and `stormsafe` as the only destination namespace, plus `Namespace` and `PersistentVolume` as cluster-scoped kinds. It also denies `Secret`, so Argo CD can't sync one even if it reached `trunk` (added after infra review). It is applied in the same apply as the Application, after Argo CD's CRDs are established. It can't go in `deploy/argocd/kustomization.yaml`: that apply also creates the `AppProject` CRD, and a CR in the same apply as its CRD fails on a fresh cluster.

## Pinned versions
| What | Version | Pin |
| --- | --- | --- |
| `dxflrs/garage` | v2.5.0, the latest stable v2 release (Oct 24, 2026) | Index digest from CI's tag lookup on this PR. This sandbox can't reach Docker Hub, the same limit Spec 0003 had. The first push carries a placeholder digest so `check-image-pins.sh` reports the tag's current digest; the next commit pins it here and in the manifest |

## Decisions within the spec
- **Readiness probe: TCP on the admin port (3903), not `/health`.** Owner's call on 2026-11-14. Garage's `/health` returns 503 until a node layout is assigned. `store-init.sh` assigns the layout after `cluster-up.sh` finishes, and `cluster-up.sh` waits for Synced and Healthy, so a `/health` readiness probe would time out on every first rebuild. The TCP probe means "the process is up and serving its admin API". `store-init.sh` checks `/health` itself after it applies the layout, through the API server's pod proxy (`kubectl get --raw .../pods/garage-0:3903/proxy/health`), so nothing new is exposed. Trade-off: after setup, a quorum loss leaves the pod Ready. On one node, the next S3 call fails loudly, and Phase 6 monitoring can watch `/health`. This departs from the spec's wording "a readiness probe on Garage's health endpoint".
- **Garage's Secret is created, not applied.** `cluster-up.sh` checks with `kubectl get secret garage`, and if it's missing, pipes a generated manifest to `kubectl create -f -` on stdin. `create` fails instead of overwriting if the Secret appeared in between, so an existing Secret is never replaced. The values go through `printf`, a shell builtin, so they never appear in a process's arguments, and they are never echoed. Garage reads them from `GARAGE_RPC_SECRET` and `GARAGE_ADMIN_TOKEN`, set from the Secret with `secretKeyRef`.
- **Metadata engine: `sqlite`.** Garage v2 defaults to LMDB, which memory-maps its file. The metadata lives on a Docker Desktop shared folder (virtiofs), where memory-mapped databases are a known corruption risk. SQLite is slower, but it is plenty for one user's DVC and MLflow traffic.
- **S3 region `garage`.** Clients must send the same region. `docs/cluster.md` sets `AWS_REGION=garage` for the demo commands.
- **Bind addresses `0.0.0.0`.** The cluster is IPv4-only (kind's default). RPC listens on 3901 inside the pod only; the Service exposes 3900 alone.
- **Host folder checks.** `STORMSAFE_STORE_HOST_DIR` must be an absolute path (a leading `~/` is expanded), must not contain `|` (the `sed` delimiter), and must not be inside the repo, checked again on the resolved path so a symlink can't get around it. That way data can't be committed by accident (ADR 0008).

## Files
| File | Create / change | Why |
| --- | --- | --- |
| `deploy/base/garage/kustomization.yaml` | Create | Lists the Garage resources |
| `deploy/base/garage/configmap.yaml` | Create | Non-secret `garage.toml`: replication factor 1, sqlite, data and metadata on the volume, S3 on 3900, admin on 3903 |
| `deploy/base/garage/statefulset.yaml` | Create | One replica, image by digest, non-root (UID/GID 1000), read-only root filesystem, no capabilities, no service-account token, TCP readiness probe on 3903, secrets from `secretKeyRef` |
| `deploy/base/garage/service.yaml` | Create | One ClusterIP Service, S3 port only |
| `deploy/base/garage/volume.yaml` | Create | hostPath PV at the node mount path, `Retain`, bound to the `garage-data` claim by `claimRef`; the PVC with an empty storage class, so kind's default provisioner never takes it |
| `deploy/base/kustomization.yaml` | Change | Include `garage/` |
| `deploy/argocd/appproject.yaml` | Create | `stormsafe` `AppProject` |
| `deploy/argocd/application.yaml` | Change | `project: stormsafe` |
| `deploy/cluster/kind-config.yaml` | Change | `extraMounts` with a placeholder host path and a fixed node path; still no port mappings |
| `scripts/cluster-up.sh` | Change | Host folder, mount check, render on create, project applied with the Application, Garage Secret |
| `scripts/store-init.sh` | Create | Layout if version 0, wait for `/health`, buckets if missing, print key commands |
| `scripts/store-forward.sh` | Create | `127.0.0.1` port-forward around one command, or held until Ctrl-C |
| `.env.example` | Change | Blank `STORMSAFE_STORE_HOST_DIR=` |
| `.github/workflows/ci.yml` | Change | `kubeconform` also validates `deploy/argocd/appproject.yaml` (the datreeio catalog has the `AppProject` schema) |
| `tests/unit/test_store.py` | Create | Guards on all of the above |
| `tests/unit/test_deploy.py` | Change | `test_base_is_the_namespace_only` becomes `test_base_kinds_are_exact` (see Risks) |
| `docs/cluster.md` | Change | Rebuild, file sharing, `store-init.sh` and keys, Garage Secret after a rebuild, `store-forward.sh` |
| `docs/roadmap.md` | Change | Next actions; the `AppProject` item leaves "Later" |

## Tests (written first)
1. Garage image pinned by digest, multi-arch with `linux/arm64` → `test_garage_image_pinned_by_digest`; the CI pin check picks the image up from the rendered `deploy/base`
2. No port mappings → existing `test_kind_node_image_pinned_by_digest`, unchanged
3. Placeholder host path; refuses without `STORMSAFE_STORE_HOST_DIR` → `test_kind_config_mounts_placeholder_only`; `test_cluster_up_refuses_without_store_dir` runs a copy of `cluster-up.sh` with stub `docker`, `kind`, and `kubectl` and checks it exits non-zero before `kind create`
4. No `Secret` under `deploy/`; no `rpc_secret` or `admin_token` in `garage.toml` → existing `test_no_secrets_under_deploy`, plus `test_garage_config_has_no_secret_values`
5. Non-root, one replica, one ClusterIP Service with only the S3 port, no NodePort or LoadBalancer → `test_garage_runs_non_root_single_replica`, `test_garage_service_is_s3_clusterip_only`
6. `store-forward.sh` binds `127.0.0.1` only and closes the forward on exit, error, and Ctrl-C → `test_store_forward_binds_loopback_and_cleans_up`
7. Application uses the `stormsafe` project; the project's sources, destinations, and cluster-scoped kinds → `test_appproject_is_least_privilege`, `test_application_uses_stormsafe_project`
8. `store-init.sh` never prints a token or key and never runs `garage key create` → `test_store_init_prints_key_commands_only`
9. `cluster-up.sh` creates Garage's Secret only when missing, from random values, never printed → `test_cluster_up_creates_garage_secret_once` (script text) and `test_cluster_up_renders_mount_and_secret` (runs the copy with stubs: checks the rendered `kind` config, that the Secret goes to `kubectl create` on stdin with both keys, and that no value appears in the output)
10. Kustomizations render and validate, including the `AppProject`; scripts pass `shellcheck` → existing CI `manifests` job; `test_ci_validates_appproject` checks `ci.yml` passes the file to `kubeconform`
11. `cluster-up.sh` and `store-init.sh` idempotent → owner verifies; `test_store_init_is_guarded` checks the layout and bucket steps are guarded
12. Demo; Argo CD Synced and Healthy → owner, recorded on this PR
13. Docs → `test_cluster_doc_covers_store`

## PR slicing
One PR. It is manifests, two short scripts, and a change to a third. Splitting it would leave `trunk` with a Garage that can't start (no mount) or a mount with nothing using it.

## Risks and open questions
- **Changed existing test.** `test_base_is_the_namespace_only` asserts that `deploy/base` holds only a `Namespace`, which this spec's Garage manifests break. With the owner's go-ahead (2026-11-14), it becomes `test_base_kinds_are_exact`: an exact match on the new set of kinds, so it stays as strict as before. Changing an existing test is human-only, so the PR flags it at the top.
- **Writing to the host folder as UID 1000.** On Docker Desktop's shared folders, writes from containers are usually allowed whatever the UID, but that can't be checked from here. If Garage can't create its directories, the fix is an init container that only `chown`s the volume, which needs root. That would be a change to this plan, and the owner's demo is what tests it.
- **Parsing `garage` CLI output.** `store-init.sh` reads `Current cluster layout version: N` from `garage layout show`, and stops with an error if it can't find it, rather than guessing. The owner's first run confirms the wording for v2.5.0.
- **Image digest.** It comes from CI, as above. Until the digest is pinned, the PR's `manifests` job fails on purpose.
