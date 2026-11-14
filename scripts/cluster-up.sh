#!/usr/bin/env bash
# Build the local StormSafe cluster: kind + Argo CD + the stormsafe Application (spec 0003),
# with the Garage object store's host folder and Secret (spec 0004).
# Idempotent: a second run on a running cluster changes nothing and exits 0.
# Human-only (CLAUDE.md): the owner runs this; agents only edit it.
#
# Required: STORMSAFE_STORE_HOST_DIR, in the environment or .env. An absolute path outside the
# repo where Garage keeps its data, so the data survives cluster-down.sh (ADR 0008).
#
# Optional: STORMSAFE_REVISION=<branch> points the live Application at a branch instead of
# trunk, for a demo before that branch merges. Run again without it to go back to trunk.
# A re-run with the same value leaves the Application unchanged.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER="stormsafe"
CONTEXT="kind-${CLUSTER}"
APP="stormsafe"
REVISION="${STORMSAFE_REVISION:-trunk}"
TIMEOUT_SECONDS=300
STORE_NODE_PATH="/var/lib/stormsafe/store"
STORE_PLACEHOLDER="__STORMSAFE_STORE_HOST_DIR__"

log() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

for tool in docker kind kubectl openssl; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is not installed (see docs/cluster.md)"
done
docker info >/dev/null 2>&1 || die "Docker is not running"

[[ "$REVISION" =~ ^[A-Za-z0-9._/-]+$ ]] || die "STORMSAFE_REVISION must be a branch name, got '$REVISION'"

# Garage's host folder (ADR 0008): the environment wins, then .env. Only this one key is read
# from .env; the file is never sourced.
store_dir="${STORMSAFE_STORE_HOST_DIR:-}"
if [[ -z "$store_dir" && -f "$ROOT/.env" ]]; then
  store_dir="$(sed -n 's/^STORMSAFE_STORE_HOST_DIR=//p' "$ROOT/.env" | tail -n 1)"
  store_dir="${store_dir#[\"\']}"
  store_dir="${store_dir%[\"\']}"
fi
[[ -n "$store_dir" ]] \
  || die "set STORMSAFE_STORE_HOST_DIR in .env: a folder outside the repo for the store's data (docs/cluster.md)"
if [[ "$store_dir" == \~/* ]]; then
  store_dir="$HOME/${store_dir#\~/}"
fi
[[ "$store_dir" == /* ]] || die "STORMSAFE_STORE_HOST_DIR must be an absolute path"
# The path goes into a sed replacement, where | ends the expression and & and \ are special.
[[ "$store_dir" != *[\|\&\\]* ]] || die "STORMSAFE_STORE_HOST_DIR must not contain | & or \\"
store_dir="${store_dir%/}"
outside_repo() {
  case "$1/" in
    "$2"/*) die "STORMSAFE_STORE_HOST_DIR must be outside the repo, so the data is never committed" ;;
  esac
}
outside_repo "$store_dir" "$ROOT"
mkdir -p "$store_dir"
# Again on resolved paths, so a symlink into the repo is caught too.
store_dir="$(cd "$store_dir" && pwd -P)"
outside_repo "$store_dir" "$(cd "$ROOT" && pwd -P)"

kc() { kubectl --context "$CONTEXT" "$@"; }

if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  log "kind cluster '$CLUSTER' already exists"
  want="$(sed -n 's/^ *image: *//p' "$ROOT/deploy/cluster/kind-config.yaml")"
  have="$(docker inspect --format '{{.Config.Image}}' "${CLUSTER}-control-plane" 2>/dev/null || true)"
  # Compare digests only: how the container records its image ref may differ from the config.
  if [[ "$have" == *@sha256:* && "${have##*@}" != "${want##*@}" ]]; then
    printf 'warning: the running node uses %s, but kind-config.yaml pins %s.
' "$have" "$want" >&2
    printf '         Run scripts/cluster-down.sh, then this script, to rebuild on the pinned image.
' >&2
  fi
  # extraMounts can't be added to a running node (ADR 0008).
  mounts="$(docker inspect --format '{{range .Mounts}}{{.Destination}} {{end}}' \
    "${CLUSTER}-control-plane" 2>/dev/null || true)"
  if [[ " $mounts " != *" $STORE_NODE_PATH "* ]]; then
    printf 'warning: the running node has no store mount at %s, so Garage cannot start.\n' \
      "$STORE_NODE_PATH" >&2
    printf '         Run scripts/cluster-down.sh, then this script, to rebuild. The data folder is kept.\n' >&2
  fi
else
  log "creating kind cluster '$CLUSTER'"
  # Render the host folder into a temporary copy; the committed config keeps the placeholder.
  config="$(mktemp)"
  trap 'rm -f "$config"' EXIT
  sed "s|$STORE_PLACEHOLDER|$store_dir|" "$ROOT/deploy/cluster/kind-config.yaml" >"$config"
  if grep -qF "$STORE_PLACEHOLDER" "$config" || ! grep -qF "hostPath: $store_dir" "$config"; then
    die "could not set the store's host folder in deploy/cluster/kind-config.yaml"
  fi
  kind create cluster --name "$CLUSTER" --config "$config"
fi

log "installing Argo CD (server-side apply)"
kc apply --server-side --force-conflicts -k "$ROOT/deploy/argocd"

log "waiting for Argo CD"
kc wait --for=condition=Established crd/applications.argoproj.io --timeout=120s
kc wait --for=condition=Established crd/appprojects.argoproj.io --timeout=120s
kc -n argocd rollout status deployment/argocd-server --timeout=300s
kc -n argocd rollout status deployment/argocd-repo-server --timeout=300s
kc -n argocd rollout status deployment/argocd-redis --timeout=300s
kc -n argocd rollout status statefulset/argocd-application-controller --timeout=300s

log "applying the '$APP' project and Application"
if [[ "$REVISION" != "trunk" ]]; then
  log "targeting '$REVISION' (demo only; the repo still says trunk)"
fi
# One apply at the requested revision, so a re-run never points the live Application at trunk
# and back. $REVISION is validated above, so it is safe in the sed expression. The AppProject
# (spec 0004) goes in the same apply: it needs its CRD, so it can't be in deploy/argocd's
# kustomization, which creates that CRD.
application="$(sed "s|^\( *targetRevision:\) trunk\$|\1 $REVISION|" "$ROOT/deploy/argocd/application.yaml")"
[[ "$(sed -n 's/^ *targetRevision: *//p' <<<"$application")" == "$REVISION" ]] \
  || die "could not set targetRevision to '$REVISION' in deploy/argocd/application.yaml"
manifest="$(cat "$ROOT/deploy/argocd/appproject.yaml"; printf -- '---\n%s\n' "$application")"
kc apply --server-side --force-conflicts -f - <<<"$manifest"

# Garage's Secret (spec 0004): random values nobody types, created only when missing and never
# printed. printf is a shell builtin, so the values never appear in a process's arguments, and
# `create` fails instead of replacing a Secret that appeared in between.
log "waiting for Argo CD to create the '$APP' namespace"
deadline=$((SECONDS + TIMEOUT_SECONDS))
until kc get namespace "$APP" >/dev/null 2>&1; do
  (( SECONDS < deadline )) || die "namespace '$APP' missing after ${TIMEOUT_SECONDS}s"
  sleep 2
done
if kc -n "$APP" get secret garage >/dev/null 2>&1; then
  log "Garage's Secret exists; leaving it as it is"
else
  log "creating Garage's Secret from random values (not printed)"
  rpc_secret="$(openssl rand -hex 32)"
  admin_token="$(openssl rand -hex 32)"
  printf 'apiVersion: v1\nkind: Secret\nmetadata:\n  name: garage\n  namespace: %s\ntype: Opaque\nstringData:\n  rpc-secret: "%s"\n  admin-token: "%s"\n' \
    "$APP" "$rpc_secret" "$admin_token" | kc -n "$APP" create -f - >/dev/null
  unset rpc_secret admin_token
fi

log "waiting for '$APP' to be Synced and Healthy"
deadline=$((SECONDS + TIMEOUT_SECONDS))
status=""
while (( SECONDS < deadline )); do
  status="$(kc -n argocd get application "$APP" \
    -o jsonpath='{.status.sync.status} {.status.health.status}' 2>/dev/null || true)"
  if [[ "$status" == "Synced Healthy" ]]; then
    break
  fi
  sleep 5
done
[[ "$status" == "Synced Healthy" ]] || die "'$APP' is '${status:-unknown}' after ${TIMEOUT_SECONDS}s"

log "'$APP' is Synced and Healthy"
cat <<EOF

Open the Argo CD UI:
  kubectl --context $CONTEXT -n argocd port-forward svc/argocd-server 8080:443
  then browse to https://localhost:8080 and sign in as admin.

Read the initial admin password yourself with:
EOF
echo '  kubectl --context kind-stormsafe -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo'
cat <<EOF

First time with the store, or after emptying its data folder: run scripts/store-init.sh
(docs/cluster.md).
EOF
