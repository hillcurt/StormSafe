# Local cluster

StormSafe runs on a local `kind` cluster with Argo CD, which pulls `deploy/overlays/local` from `trunk` and keeps the cluster matching it (ADR 0007). This page is for the owner: every command here touches a live cluster, which is human-only (`CLAUDE.md`). Agents edit the files; the owner runs them.

## Prerequisites

| Tool | Tested version | Install |
| --- | --- | --- |
| Docker Desktop | v4.96.1 | [docker.com](https://www.docker.com/products/docker-desktop/), running, Apple Silicon build |
| `kind` | v0.33.0 | `brew install kind` (the node image in `deploy/cluster/kind-config.yaml` comes from this release) |
| `kubectl` | v1.37.0 | `brew install kubectl` (within one minor version of the node's Kubernetes v1.37.0) |

Give Docker Desktop at least 4 GB of memory. For the store (spec 0004) you also need the AWS CLI (`brew install awscli`) to check it from the laptop. Every pinned image is a multi-arch build with `linux/arm64`; CI checks this on every PR. When `public.ecr.aws` rate-limits CI, the redis image's manifest is read from Docker Hub by the same digest, so the first `cluster-up.sh` run is what proves the pull from ECR works.

If `kind-config.yaml` pins a newer node image than the running cluster uses, `cluster-up.sh` warns and keeps the running cluster; rebuild with `cluster-down.sh` then `cluster-up.sh`.

## The store's data folder

Garage keeps its data and metadata in a folder on your Mac, outside the repo, so the data survives `cluster-down.sh` (ADR 0008). Pick a folder and set it in your local `.env`, which is git-ignored:

```bash
STORMSAFE_STORE_HOST_DIR=/Users/<you>/stormsafe-store
```

The path is private (ADR 0004): it never goes in the repo, a PR, or a log. It must be absolute (`~/` is expanded) and outside the repo, and `cluster-up.sh` refuses to run without it. It creates the folder if it is missing.

**Docker Desktop file sharing:** the folder must be under a path Docker Desktop shares with its VM. `/Users` is shared by default. For anywhere else, add the path under Settings → Resources → File sharing. `kind` mounts the folder into the node at `/var/lib/stormsafe/store`, and Garage's volume points there.

## Bring up

```bash
scripts/cluster-up.sh
```

The script creates the `stormsafe` cluster if it is missing, installs Argo CD v3.5.6 (pinned in `deploy/argocd/`), applies the `stormsafe` `AppProject` and Application, creates Garage's Secret if it is missing, and waits until it is **Synced** and **Healthy**. A second run on a running cluster changes nothing and exits 0. Its `kubectl` context is `kind-stormsafe`.

To demo a branch before it merges, point the live Application at that branch:

```bash
STORMSAFE_REVISION=<branch> scripts/cluster-up.sh
```

The repo still says `trunk`. Re-running with the same value leaves the Application unchanged. Running without the variable applies the committed `trunk`, which is how you switch back.

The script applies with `--server-side --force-conflicts`, so it takes back any field changed by hand on the Argo CD install or the `stormsafe` Application. Change those in the repo, not in the cluster.

### Adding the store to an existing cluster: one rebuild

`kind` can't add a mount to a running node, so a cluster made before spec 0004 needs one rebuild. `cluster-up.sh` warns when the running node has no store mount. Set `STORMSAFE_STORE_HOST_DIR` first, then:

```bash
scripts/cluster-down.sh && scripts/cluster-up.sh
```

The rebuild keeps the data folder (on a first rebuild it is empty anyway) and nothing else: recreate what "After a rebuild" lists.

## Set up the store (once)

On a new, empty data folder, Garage needs a node layout, the buckets, and keys:

```bash
scripts/store-init.sh
```

It assigns the layout (only if there is none), waits until Garage's `/health` is OK, and creates the `dvc` and `mlflow` buckets if they are missing. A second run changes nothing. It never creates a key: creating keys is human-only, so it prints the commands, and you run them yourself:

- `garage key create stormsafe-laptop`, then `garage bucket allow --read --write` on `dvc` and `mlflow`. This is the laptop's key: keep its ID and secret in `.dvc/config.local` and `.env` (the DVC and MLflow wiring spec says exactly where).
- `garage key create stormsafe-cluster`, then `garage bucket allow --read` on `mlflow` only. This is the cluster workloads' key. Nothing uses it yet; the spec for the first workload that reads the store adds the Secret command here.

`garage key create` prints the secret once. Copy it where it belongs and don't paste it anywhere else. Garage's own Secret (`garage`: RPC secret and admin token) is made by `cluster-up.sh` from random values, and it never prints them.

## Reach the store from the laptop

Nothing on the Mac listens for the store until you ask. `store-forward.sh` forwards `127.0.0.1:3900` to Garage's S3 Service for as long as one command runs:

```bash
export AWS_REGION=garage   # Garage's S3 region (deploy/base/garage/configmap.yaml)
scripts/store-forward.sh aws s3 ls --endpoint-url http://127.0.0.1:3900
```

With the laptop key's ID and secret in `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, that lists `dvc` and `mlflow`. With no command, the forward stays open until Ctrl-C. The script exits with the command's status, fails if 3900 is already in use, and says so if the forward drops (for example when the Garage pod restarts). Run the command again then. Check that nothing listens afterwards:

```bash
lsof -nP -iTCP:3900 -sTCP:LISTEN   # prints nothing
```

## Open the Argo CD UI

```bash
kubectl --context kind-stormsafe -n argocd port-forward svc/argocd-server 8080:443
```

Browse to <https://localhost:8080> (the certificate is self-signed) and sign in as `admin`. The script prints the command that reads the initial admin password; run it yourself. It never prints the password. After signing in, change the password and delete the `argocd-initial-admin-secret` Secret, as the Argo CD docs recommend.

## Tear down

```bash
scripts/cluster-down.sh
```

This deletes the cluster and everything in it, including any Secrets created by hand. It doesn't touch the store's data folder: the buckets, objects, and keys in it come back with the next `cluster-up.sh`.

## After a rebuild

Nothing secret lives in git (ADR 0004, ADR 0007). The Argo CD install does create two empty Secrets, `argocd-secret` and `argocd-notifications-secret`, which Argo CD fills in itself; CI checks they stay empty in the pinned manifest and that nothing Argo CD syncs is a Secret. So after `cluster-down.sh` and `cluster-up.sh`, recreate by hand:

1. **The Argo CD admin password.** A new one is generated; read it with the printed command.
2. **The `stormsafe-site` Secret** (ADR 0004): the `STORMSAFE_SITE_*` values from your local `.env`, in the `stormsafe` namespace. Nothing reads it yet; the spec for the first workload that does adds the exact command here.
3. **Garage's Secret** (`garage`, spec 0004): nothing to do. `cluster-up.sh` creates it again with new random values, which Garage accepts on a single node. The layout, buckets, and keys live in the data folder, so `store-init.sh` and the key commands are not needed again unless you emptied it.
4. Any other credentials added by later specs. Each spec that adds one lists it here.

## Troubleshooting

- **`stormsafe` stays OutOfSync or Missing before a branch merges:** the Application tracks `trunk`. Use `STORMSAFE_REVISION` (above).
- **Images fail to pull:** check Docker Desktop is running and has network access; the cluster pulls from `quay.io`, `ghcr.io`, `public.ecr.aws`, and Docker Hub (`dxflrs/garage`).
- **Garage stays Pending or can't start:** check `cluster-up.sh`'s output for the missing-mount warning, and that the data folder is shared with Docker Desktop (above). `kubectl --context kind-stormsafe -n stormsafe logs garage-0` shows Garage's own errors.
- **`store-init.sh` can't read the layout version:** Garage's CLI output changed. The script stops rather than guess; update its `sed` pattern for the pinned version.
- **Start clean:** `scripts/cluster-down.sh && scripts/cluster-up.sh`. To start the store from nothing as well, empty the data folder before `cluster-up.sh`, then run `store-init.sh` and create the keys again.
