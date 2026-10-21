#!/usr/bin/env bash
# Build the local StormSafe cluster: kind + Argo CD + the stormsafe Application (spec 0003).
# Idempotent: a second run on a running cluster changes nothing and exits 0.
# Human-only (CLAUDE.md): the owner runs this; agents only edit it.
#
# Optional: STORMSAFE_REVISION=<branch> points the live Application at a branch instead of
# trunk, for a demo before that branch merges. Run again without it to go back to trunk.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER="stormsafe"
CONTEXT="kind-${CLUSTER}"
APP="stormsafe"
REVISION="${STORMSAFE_REVISION:-trunk}"
TIMEOUT_SECONDS=300

log() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

for tool in docker kind kubectl; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is not installed (see docs/cluster.md)"
done
docker info >/dev/null 2>&1 || die "Docker is not running"

[[ "$REVISION" =~ ^[A-Za-z0-9._/-]+$ ]] || die "STORMSAFE_REVISION must be a branch name, got '$REVISION'"

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
else
  log "creating kind cluster '$CLUSTER'"
  kind create cluster --name "$CLUSTER" --config "$ROOT/deploy/cluster/kind-config.yaml"
fi

log "installing Argo CD (server-side apply)"
kc apply --server-side --force-conflicts -k "$ROOT/deploy/argocd"

log "waiting for Argo CD"
kc wait --for=condition=Established crd/applications.argoproj.io --timeout=120s
kc -n argocd rollout status deployment/argocd-server --timeout=300s
kc -n argocd rollout status deployment/argocd-repo-server --timeout=300s
kc -n argocd rollout status deployment/argocd-redis --timeout=300s
kc -n argocd rollout status statefulset/argocd-application-controller --timeout=300s

log "applying the '$APP' Application"
kc apply --server-side --force-conflicts -f "$ROOT/deploy/argocd/application.yaml"
if [[ "$REVISION" != "trunk" ]]; then
  log "pointing the live Application at '$REVISION' (demo only; the repo still says trunk)"
  kc -n argocd patch application "$APP" --type merge \
    -p "{\"spec\":{\"source\":{\"targetRevision\":\"$REVISION\"}}}"
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
