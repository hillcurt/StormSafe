# Local cluster

StormSafe runs on a local `kind` cluster with Argo CD, which pulls `deploy/overlays/local` from `trunk` and keeps the cluster matching it (ADR 0007). This page is for the owner: every command here touches a live cluster, which is human-only (`CLAUDE.md`). Agents edit the files; the owner runs them.

## Prerequisites

| Tool | Tested version | Install |
| --- | --- | --- |
| Docker Desktop | _filled in from the spec 0003 demo run_ | [docker.com](https://www.docker.com/products/docker-desktop/), running, Apple Silicon build |
| `kind` | v0.33.0 | `brew install kind` (the node image in `deploy/cluster/kind-config.yaml` comes from this release) |
| `kubectl` | v1.37.0 | `brew install kubectl` (within one minor version of the node's Kubernetes v1.37.0) |

Give Docker Desktop at least 4 GB of memory. Every pinned image is a multi-arch build with `linux/arm64`; CI checks this on every PR. When `public.ecr.aws` rate-limits CI, the redis image's manifest is read from Docker Hub by the same digest, so the first `cluster-up.sh` run is what proves the pull from ECR works.

If `kind-config.yaml` pins a newer node image than the running cluster uses, `cluster-up.sh` warns and keeps the running cluster; rebuild with `cluster-down.sh` then `cluster-up.sh`.

## Bring up

```bash
scripts/cluster-up.sh
```

The script creates the `stormsafe` cluster if it is missing, installs Argo CD v3.5.6 (pinned in `deploy/argocd/`), applies the `stormsafe` Application, and waits until it is **Synced** and **Healthy**. A second run on a running cluster changes nothing and exits 0. Its `kubectl` context is `kind-stormsafe`.

To demo a branch before it merges, point the live Application at that branch:

```bash
STORMSAFE_REVISION=<branch> scripts/cluster-up.sh
```

The repo still says `trunk`. Run `scripts/cluster-up.sh` again without the variable to go back.

## Open the Argo CD UI

```bash
kubectl --context kind-stormsafe -n argocd port-forward svc/argocd-server 8080:443
```

Browse to <https://localhost:8080> (the certificate is self-signed) and sign in as `admin`. The script prints the command that reads the initial admin password; run it yourself. It never prints the password. After signing in, change the password and delete the `argocd-initial-admin-secret` Secret, as the Argo CD docs recommend.

## Tear down

```bash
scripts/cluster-down.sh
```

This deletes the cluster and everything in it, including any Secrets created by hand.

## After a rebuild

Nothing secret lives in git (ADR 0004, ADR 0007). The Argo CD install does create two empty Secrets, `argocd-secret` and `argocd-notifications-secret`, which Argo CD fills in itself; CI checks they stay empty in the pinned manifest and that nothing Argo CD syncs is a Secret. So after `cluster-down.sh` and `cluster-up.sh`, recreate by hand:

1. **The Argo CD admin password.** A new one is generated; read it with the printed command.
2. **The `stormsafe-site` Secret** (ADR 0004): the `STORMSAFE_SITE_*` values from your local `.env`, in the `stormsafe` namespace. Nothing reads it yet; the spec for the first workload that does adds the exact command here.
3. Any other credentials added by later specs. Each spec that adds one lists it here.

## Troubleshooting

- **`stormsafe` stays OutOfSync or Missing before a branch merges:** the Application tracks `trunk`. Use `STORMSAFE_REVISION` (above).
- **Images fail to pull:** check Docker Desktop is running and has network access; the cluster pulls from `quay.io`, `ghcr.io`, and `public.ecr.aws`.
- **Start clean:** `scripts/cluster-down.sh && scripts/cluster-up.sh`.
