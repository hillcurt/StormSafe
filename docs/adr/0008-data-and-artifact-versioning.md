# ADR 0008 — Data and artifact versioning

**Status:** accepted
**Date:** 2026-11-08

## Context
Phase 2 builds training sets from GOES-19 GLM lightning and weather data. Phase 3 logs models to MLflow, and Phase 5 serving loads the registered model at startup (ADR 0006). The governance rule in `docs/sdlc.md` asks for versioned data snapshots, and Gate 2 asks for a pull that resumes after interruption. Every dataset and model has to trace back to the code and data that made it.

The derived datasets are clipped to the site's radius, so anyone who can read them can work out the location. They must stay private (ADR 0004). Expected volumes are small: site-clipped strike events plus hourly weather features come to a few GB at most, even over several seasons.

The project has no cloud budget. ADR 0007 already runs everything on the owner's machine in a `kind` cluster, with no cloud cost and no exposed endpoints. The owner already has AWS experience, so a cloud bucket would add an ongoing bill without adding anything new to the portfolio.

## Decision
- **Object store:** a single-node **Garage** instance (S3-compatible, self-hosted) in the `kind` cluster, deployed by Argo CD from `deploy/` like every other workload (ADR 0007). Its image is pinned by digest.
- **The data outlives the cluster.**
  - Garage's data and metadata live in a folder on the host, outside the repo, mounted into the node with `kind`'s `extraMounts`. The folder's path is set in local config, not committed.
  - `cluster-down.sh` deletes the cluster, not that folder.
- **Reachable from the laptop only.** Garage's S3 port is mapped to `127.0.0.1` with `extraPortMappings`, so DVC and MLflow on the laptop reach it and nothing else on the network can. ADR 0007's "no exposed endpoints" still holds.
- **Two buckets:**
  - `dvc`: the DVC remote.
  - `mlflow`: the MLflow artifact root.

  Garage grants access per bucket, so two buckets give each identity only what it needs.
- **Data versioning with DVC.** DVC versions the derived, site-specific datasets: daily GLM strike chunks, weather features, labels, and the built training set, each as one Parquet file per day. A snapshot is a git commit, because the committed `.dvc` / `dvc.lock` files pin the content hashes. Raw GLM files are not versioned: they are public and can be fetched again from NOAA, so they live only in a git-ignored local cache.
- **Resume and publish are separate steps.** Long builds write chunks to local disk so they can resume (`CLAUDE.md` conventions). `dvc push` publishes a finished snapshot.
- **Model artifacts:** stored in the `mlflow` bucket. Every training run logs its git commit and the DVC hash of its training set, so the chain runs registered model → run → commit + data snapshot. MLflow tracking metadata stays local (ADR 0004). Where the tracking server and registry run is not decided here (see Consequences).
- **Config, not code.** The endpoint, bucket names, and the host data path are config. The DVC remote's settings live in the git-ignored `.dvc/config.local`, and app settings read them from `STORMSAFE_*` variables in `.env`. The repo stays usable for any site and any S3-compatible store.
- **Credentials are human-only** (`CLAUDE.md`). The owner creates Garage's admin token and access keys with the `garage` CLI, and none are committed:
  - Owner's laptop: one key, read and write on both buckets, kept in `.dvc/config.local` and `.env`.
  - Cluster workloads: one key, read-only on `mlflow`, kept in a hand-made Secret (ADR 0007). A later spec that needs a cluster job to write (for example, the nightly outcomes job) widens this in its own PR.
  - CI: none. Tests use local fixtures and never touch the store.

## Consequences
- No cloud account, no bill, and no cloud credentials. The data never leaves the owner's machine, which settles ADR 0004 for data and models.
- The storage layer is itself a GitOps-managed, stateful Kubernetes workload, which shows platform skills a cloud bucket would not.
- The code speaks plain S3, so moving to a cloud store later means changing an endpoint and credentials, not code.
- Lineage runs end to end: image digest → commit (ADR 0006), and model → run → commit + data snapshot.
- **One rebuild of the cluster is needed** to add the mount and the port mapping. `extraMounts` and `extraPortMappings` can't be added to a running `kind` cluster.
- **After a rebuild,** the data folder survives, but Garage's admin token Secret and the workload key Secret are recreated by hand. `docs/cluster.md` lists the steps.
- **Garage needs a one-time setup** after its first start: assign the node's layout, create the buckets, and create and grant the keys. Key creation is human-only. The spec decides whether the rest runs as a Job or as documented commands.
- **Availability follows the owner's machine,** as ADR 0007 already accepts: when the laptop sleeps, so does the store.
- **No copy off the machine.** That is acceptable because everything in the store can be rebuilt. The datasets come from public NOAA and Open-Meteo data plus committed code, and models can be retrained. The owner's normal machine backup covers the host folder. A second DVC remote (for example, an external drive) can be added later without changing this decision.
- **GitHub-hosted runners can't reach the store.** Training needs the data, so `train.yml` can't simply run on a hosted runner. The Phase 3 training spec decides how training runs: locally, or as a Job in the cluster, triggered by a reviewed change.
- **Open:** tracking metadata stays local for now, but serving in the cluster needs a reachable registry (ADR 0006). Where the tracking server and registry run gets its own ADR before the Phase 3 training spec.

## Alternatives considered
- **SeaweedFS:** the other strong self-hosted option. It is Apache-2.0, and `weed mini` runs the whole store in one process. It supports S3 object versioning, which DVC doesn't need because DVC is content-addressed. It runs more components (master, volume, filer, gateway), and it serves S3 without authentication when no credentials are configured, which is an easy mistake to make. Garage does one job: a small S3 store, built for self-hosting. It is AGPL-3.0, actively maintained, and widely recommended since MinIO's community edition ended.
- **MinIO community edition:** upstream went into maintenance mode in December 2025, stopped publishing binaries and images in October 2025, and archived its repo in February 2026 (unarchived briefly, then archived again in April 2026).
- **AWS S3 (or Google Cloud Storage, Cloudflare R2):** reachable from CI and off the machine, and cheap at this volume. But each is an ongoing bill with no hard cap, plus an account, credentials, and IaC to keep up. The owner already has AWS experience, so S3 adds little to the portfolio.
- **A plain-directory DVC remote and a file-based MLflow artifact store:** simplest, with no service to run. But cluster pods would need host mounts into the artifact folder, and the code would no longer speak S3, which is what makes a later move to the cloud cheap.
- **Git LFS on GitHub:** the repo is public, so its LFS objects would be public too. This fails ADR 0004.
- **lakeFS instead of DVC:** built for data lakes far larger than this, and a server to run. DVC is file-level, git-native, and fits one owner. lakeFS took over stewardship of DVC in November 2025, and DVC stays open source with continued maintenance ([DVC FAQ](https://dvc.org/blog/dvc-joins-lakefs-your-questions-answered/)), which lowers the maintenance risk.

## References
- Garage: [project site](https://garagehq.deuxfleurs.fr/) and [source](https://git.deuxfleurs.fr/Deuxfleurs/garage)
- SeaweedFS: [repository](https://github.com/seaweedfs/seaweedfs)
- MinIO community edition status: [It's FOSS, "MinIO moves away from open source"](https://itsfoss.com/news/minio-moves-away-from-open-source/)
- DVC stewardship: [lakeFS acquires DVC](https://lakefs.io/blog/lakefs-acquires-dvc/) (November 18, 2025)
