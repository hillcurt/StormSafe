# ADR 0008 — Data and artifact versioning

**Status:** accepted
**Date:** 2026-11-07

## Context
Phase 2 builds training sets from GOES-19 GLM lightning and weather data. Phase 3 logs models to MLflow, and Phase 5 serving loads the registered model at startup (ADR 0006). The governance rule in `docs/sdlc.md` asks for versioned data snapshots, and Gate 2 asks for a pull that resumes after interruption. Every dataset and model has to trace back to the code and data that made it.

The derived datasets are clipped to the site's radius, so anyone who can read them can work out the location. They must stay private (ADR 0004). The repo is public and the owner is on the GitHub Free plan. Expected volumes are small: site-clipped strike events plus hourly weather features come to a few GB at most, even over several seasons.

The store must be reachable from the owner's machine and from pods in the `kind` cluster. If `train.yml` runs on GitHub-hosted runners, it must be reachable from there too. GitHub runners cannot reach the owner's network (ADR 0007).

## Decision
- **Object store:** one private AWS S3 bucket in `us-east-1`, defined in Terraform like every AWS resource (ADR 0009), the same region as NOAA's public GOES-19 bucket. Block Public Access is on, default encryption (SSE-S3) is on, and bucket versioning is on. A lifecycle rule expires noncurrent versions after 90 days and aborts incomplete multipart uploads after 7 days.
- **Layout:** two prefixes in one bucket, each with its own permissions:
  - `dvc/`: the DVC remote.
  - `mlflow/`: the MLflow artifact root.
- **Data versioning with DVC.** DVC versions the derived, site-specific datasets: daily GLM strike chunks, weather features, labels, and the built training set, each as one Parquet file per day. A snapshot is a git commit, because the committed `.dvc` / `dvc.lock` files pin the content hashes. Raw GLM files are not versioned: they are public and can be fetched again from NOAA, so they live only in a git-ignored local cache.
- **Resume and publish are separate steps.** Long builds write chunks to local disk so they can resume (`CLAUDE.md` conventions). `dvc push` publishes a finished snapshot.
- **Model artifacts:** stored under `mlflow/`. Every training run logs its git commit and the DVC hash of its training set, so the chain runs registered model → run → commit + data snapshot. Where the MLflow tracking server and registry run is not decided here (see Consequences).
- **Config, not code.** The bucket name and region are not committed. The DVC remote's URL lives in the git-ignored `.dvc/config.local`, and app settings read it from `STORMSAFE_*` variables in `.env`. The repo stays usable for any site and any bucket.
- **Identities are defined in Terraform (ADR 0009). Credentials are human-only** (`CLAUDE.md`) and never committed:
  - Owner's machine: an IAM role with read and write on both prefixes, assumed through the owner's SSO session, with no long-lived keys.
  - Cluster: an IAM user with read-only access on `mlflow/`. The owner creates its access key by hand, so the key is never in Terraform state, and stores it in a hand-made Secret (ADR 0007). A later spec that needs a cluster job to write (for example, the nightly outcomes job) widens this scope in its own PR.
  - CI: none. Tests use local fixtures and never touch the bucket. If `train.yml` later runs on GitHub-hosted runners, it assumes a scoped IAM role through GitHub OIDC, with no long-lived keys; that spec decides the details.
- **Cost guard:** an AWS Budgets alert at $5 per month, defined in Terraform.

## Consequences
- Lineage runs end to end: image digest → commit (ADR 0006), and model → run → commit + data snapshot.
- The store is reachable from the laptop, the cluster, and later from CI, without exposing the owner's network.
- Rebuilding the cluster loses no data or models; only the cluster's read-only Secret has to be recreated. The runbook (Phase 6) lists the steps.
- New dependency: an AWS account, plus the Terraform stacks that manage it (ADR 0009). The cluster's access key is rotated by hand, and the runbook covers it.
- Cost at this volume is cents per month (S3 Standard is about $0.023 per GB-month). AWS has no hard spend cap, so the budget alert is the guard.
- The data sits on a third party's infrastructure. It is private, encrypted at rest, and readable only by the two identities above, plus the owner's admin identity that runs Terraform.
- A fresh clone without credentials can't `dvc pull`. Results stay reproducible for the owner, as ADR 0004 already accepts.
- **Open:** ADR 0004 keeps MLflow tracking local, but serving in the cluster needs a reachable registry (ADR 0006). Where the tracking server and registry run gets its own ADR before the Phase 3 training spec.

## Alternatives considered
- **Cloudflare R2:** S3-compatible, so DVC and MLflow work against it through an endpoint URL. It has a 10 GB free tier and no egress fees. It is the close second. At this volume, egress doesn't matter and both cost about nothing. S3 with IAM roles and GitHub OIDC is the pattern ML platform teams use most, which this project is meant to show.
- **A self-hosted S3-compatible store in the `kind` cluster (Garage, SeaweedFS):** no cloud account, and the data never leaves the machine. But the data would live in a cluster built to be disposable, so every rebuild becomes a restore. It is unreachable from CI, its availability follows the laptop, and it is one more stateful service to back up. MinIO's community edition is out: upstream went into maintenance mode in December 2025, stopped publishing binaries and images, and archived its repo in 2026.
- **A local or external-drive DVC remote:** simplest, but there is no copy off the machine, and cluster pods and CI can't reach it without host mounts.
- **Git LFS on GitHub:** the repo is public, so its LFS objects would be public too. This fails ADR 0004.
- **Google Cloud Storage or Backblaze B2:** comparable, with no advantage for this project.
- **S3 object versioning alone, without DVC:** keeps old bytes, but no git commit points at the exact dataset a run used.
- **lakeFS instead of DVC:** built for data lakes far larger than this, and a server to run. DVC is file-level, git-native, and fits one owner. lakeFS took over stewardship of DVC in November 2025, which lowers the maintenance risk.
