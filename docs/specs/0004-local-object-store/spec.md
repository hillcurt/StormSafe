# Spec 0004 — Local object store

**Status:** approved
**Phase:** 2

## Goal
A single-node Garage object store runs in the `kind` cluster, deployed by Argo CD, as ADR 0008 decides. After this lands:
- The owner's laptop can reach the store's S3 API on `127.0.0.1` through a port-forward wrapper, and nothing listens when no forward is running.
- The `dvc` and `mlflow` buckets exist.
- The store's data survives `cluster-down.sh` followed by `cluster-up.sh`.

This is the first real workload in the cluster, so it also adds the least-privilege Argo CD `AppProject` the roadmap asks for before the first workload.

## Inputs / outputs
- **Creates:**
  - `deploy/base/garage/`:
    - a single-replica StatefulSet running Garage, image pinned by digest, as a non-root user, with a readiness probe on Garage's health endpoint;
    - a ConfigMap with the non-secret `garage.toml`: replication factor 1, data and metadata paths on the mounted volume, S3 API on 3900, admin API on 3903;
    - one ClusterIP Service for the S3 API only. In-cluster clients use it, and the laptop's port-forward targets it;
    - the volume: a hostPath-backed PersistentVolume and PersistentVolumeClaim on the node's mount path.

    Garage's RPC secret and admin token are read from a Secret the manifests reference but never define.
  - `scripts/store-init.sh`, the one-time setup, run by the owner and idempotent:
    - assigns and applies the node layout if none exists;
    - creates the `dvc` and `mlflow` buckets if they are missing;
    - prints the `garage key create` and `garage bucket allow` commands for both keys (ADR 0008) without running them.

    It runs `garage` through `kubectl exec`. It never prints a token or key.
  - `scripts/store-forward.sh`, the laptop's way in (ADR 0008):
    - opens `kubectl port-forward` to the S3 Service on `127.0.0.1:3900`, waits until the port answers, runs the command it is given, then closes the forward;
    - with no command, it holds the forward until Ctrl-C;
    - exits with the command's status, or with an error saying the forward dropped;
    - fails clearly if port 3900 is already in use.
  - `deploy/argocd/appproject.yaml`: a `stormsafe` `AppProject`. Sources are limited to this repo, destinations to the `stormsafe` namespace, and the only cluster-scoped kinds allowed are the namespace and the PersistentVolume.
  - `tests/unit/test_store.py`: guards on the files above.
- **Changes:**
  - `deploy/cluster/kind-config.yaml`:
    - `extraMounts`: a host folder mounted at a fixed node path. The committed file holds a placeholder for the host side, never a real path. No port mappings: Spec 0003's rule and its test stay as they are.
  - `scripts/cluster-up.sh`:
    - Reads the host folder from `STORMSAFE_STORE_HOST_DIR` (environment or `.env`) and refuses to run without it.
    - Renders the placeholder only when creating a cluster.
    - Creates the host folder if it is missing.
    - On a running cluster that lacks the mount, warns and says to rebuild, as it already does for a stale node image.
    - Before waiting for Synced and Healthy, creates Garage's Secret (RPC secret and admin token, from `openssl rand`) if it's missing, and never prints the values. An existing Secret is left as it is, so re-runs change nothing.
  - `deploy/argocd/application.yaml`: uses the `stormsafe` project instead of `default`.
  - `deploy/base/kustomization.yaml`: includes `garage/`.
  - `.env.example`: a blank `STORMSAFE_STORE_HOST_DIR=`.
  - `docs/cluster.md`:
    - the one rebuild, and what it keeps;
    - `store-init.sh` and the key steps;
    - the Garage Secret in "After a rebuild";
    - checking the store from the laptop through `store-forward.sh`;
    - Docker Desktop file sharing for the host folder.
  - `docs/roadmap.md`: Next actions updated.

## Acceptance criteria
- [ ] The Garage image is pinned by digest and is a multi-arch index with `linux/arm64` (test; existing CI image check)
- [ ] The `kind` config still has no port mappings (the existing Spec 0003 test, unchanged)
- [ ] The committed `kind-config.yaml` holds a placeholder for the host folder, never a real path. `cluster-up.sh` refuses to create a cluster without `STORMSAFE_STORE_HOST_DIR` (test)
- [ ] Nothing under `deploy/` defines a `Secret`. `garage.toml` in the ConfigMap has no `rpc_secret` or `admin_token` value (test; existing Secret guard still applies)
- [ ] Garage runs as non-root with one replica. Its only Service is ClusterIP and exposes only the S3 port; nothing is a NodePort or LoadBalancer (test)
- [ ] `store-forward.sh` binds the forward to `127.0.0.1` only and closes it on exit, error, or Ctrl-C (test checks the script)
- [ ] The `Application` uses the `stormsafe` `AppProject`. That project allows only this repo as a source and only the `stormsafe` namespace as a destination, plus the namespace and the PersistentVolume as cluster-scoped kinds (test)
- [ ] `store-init.sh` never prints a token or key, and never runs `garage key create` itself (test checks the script)
- [ ] `cluster-up.sh` creates Garage's Secret only when it's missing, from generated random values, and never prints them (test checks the script)
- [ ] Every kustomization renders and passes schema validation, including the `AppProject` CRD, and the new script passes `shellcheck` (existing CI job)
- [ ] `cluster-up.sh` stays idempotent: a second run on a running, rebuilt cluster changes nothing and exits 0 (owner verifies)
- [ ] `store-init.sh` is idempotent: a second run changes nothing and exits 0 (owner verifies)
- [ ] **Demo**, on the owner's machine, recorded on the implementation PR without keys, endpoints beyond `127.0.0.1`, or host paths:
  1. Rebuild the cluster, run `store-init.sh`, and create the laptop key.
  2. `scripts/store-forward.sh aws s3 ls --endpoint-url http://127.0.0.1:3900` lists `dvc` and `mlflow`.
  3. Upload a test object, run `cluster-down.sh` then `cluster-up.sh`, and the object is still there.
  4. With no forward running, nothing on the Mac listens on 3900 (`lsof -nP -iTCP:3900 -sTCP:LISTEN` prints nothing).
- [ ] Argo CD shows `stormsafe` Synced and Healthy with Garage running (owner verifies)
- [ ] `docs/cluster.md` and `docs/roadmap.md` updated as above

## Out of scope
- `dvc init`, the DVC remote config, MLflow settings, and any `src/` code that reads or writes the store (the next spec: DVC and MLflow wiring)
- Creating keys, the cluster workload key Secret, or any Secret value in the repo
- Multi-node Garage, replication, or erasure coding
- A second DVC remote or any backup tooling (ADR 0008 accepts the machine backup for now)
- Garage's web endpoint (3902), metrics, or ingress
- A host port mapping for the store (ADR 0008 keeps it as a fallback)
- An operator or Helm chart for Garage; plain manifests, like the rest of `deploy/`

## Human-only touchpoints
- **Running** `cluster-down.sh`, `cluster-up.sh`, `store-init.sh`, and any `kubectl` or Argo CD action against the cluster (`CLAUDE.md`). This spec needs one rebuild.
- **Creating** Garage's Secret: `cluster-up.sh` generates it when it's missing, on the owner's run (open question 1).
- **Creating** both access keys and the bucket grants: the owner runs the commands `store-init.sh` prints.
- **`STORMSAFE_STORE_HOST_DIR`** in the owner's `.env`: a path on his machine, never committed.

## Open questions
Answered by the owner:
1. **Garage's Secret:** `cluster-up.sh` generates the RPC secret and admin token with `openssl rand` and creates the Secret only when it's missing, on the owner's run. It never prints the values. They are random values nobody types, and this keeps a rebuild to one command.
2. **`AppProject`:** included in this spec, as written above. Garage is the first real workload.
3. **Laptop access:** port-forward through `store-forward.sh` on `127.0.0.1:3900`, instead of a fixed port mapping. Spec 0003's no-host-ports rule and its test stay unchanged (owner, after discussing the trade-off; ADR 0008 amended in #19).
4. **Garage version:** the latest stable v2 release at implementation time. Its digest is recorded in `plan.md`.
