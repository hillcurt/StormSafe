#!/usr/bin/env bash
# One-time setup of the Garage object store (ADR 0008, spec 0004): assign the node layout,
# create the dvc and mlflow buckets, and print the key commands for the owner to run.
# Idempotent: a second run changes nothing and exits 0.
# Human-only (CLAUDE.md): the owner runs this; agents only edit it.
# It never reads or prints a token or key, and never creates a key itself.
set -euo pipefail

CONTEXT="kind-stormsafe"
NAMESPACE="stormsafe"
POD="garage-0"
ZONE="local"
# Matches the PersistentVolume in deploy/base/garage/volume.yaml. Garage uses it to balance
# data across nodes; with one node it only has to be set.
CAPACITY="20G"
BUCKETS=(dvc mlflow)
TIMEOUT_SECONDS=120

log() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

command -v kubectl >/dev/null 2>&1 || die "kubectl is not installed (see docs/cluster.md)"

kc() { kubectl --context "$CONTEXT" -n "$NAMESPACE" "$@"; }
garage() { kc exec "$POD" -c garage -- /garage "$@"; }

log "waiting for $POD to be Ready"
kc wait --for=condition=Ready "pod/$POD" --timeout=300s

# Layout: assign only when none exists (version 0). Stop rather than guess if the output changed.
layout="$(garage layout show)"
version="$(sed -n 's/^Current cluster layout version: *\([0-9][0-9]*\).*/\1/p' <<<"$layout")"
[[ -n "$version" ]] \
  || die "could not read 'Current cluster layout version' from 'garage layout show'; update this script for this Garage version"
if [[ "$version" == "0" ]]; then
  node="$(garage node id -q)"
  node="${node%%@*}"
  [[ "$node" =~ ^[0-9a-f]{16,}$ ]] || die "unexpected node id from 'garage node id -q'"
  log "assigning the node layout (zone $ZONE, capacity $CAPACITY)"
  garage layout assign -z "$ZONE" -c "$CAPACITY" "$node"
  garage layout apply --version 1
else
  log "layout is at version $version; leaving it as it is"
fi

# /health is 200 once the layout gives the node a quorum. Read it through the API server's pod
# proxy, so no port is opened.
log "waiting for Garage's /health"
deadline=$((SECONDS + TIMEOUT_SECONDS))
until kubectl --context "$CONTEXT" get --raw \
  "/api/v1/namespaces/$NAMESPACE/pods/$POD:3903/proxy/health" >/dev/null 2>&1; do
  (( SECONDS < deadline )) || die "Garage's /health is not OK after ${TIMEOUT_SECONDS}s"
  sleep 2
done
log "Garage is healthy"

for bucket in "${BUCKETS[@]}"; do
  if garage bucket info "$bucket" >/dev/null 2>&1; then
    log "bucket '$bucket' exists"
  else
    log "creating bucket '$bucket'"
    garage bucket create "$bucket" >/dev/null
  fi
done

log "the store is set up"
echo
echo 'Create the two keys yourself (human-only, ADR 0008). Each key create prints its secret once:'
echo '  kubectl --context kind-stormsafe -n stormsafe exec garage-0 -c garage -- /garage key create stormsafe-laptop'
echo '  kubectl --context kind-stormsafe -n stormsafe exec garage-0 -c garage -- /garage bucket allow --read --write --key stormsafe-laptop dvc'
echo '  kubectl --context kind-stormsafe -n stormsafe exec garage-0 -c garage -- /garage bucket allow --read --write --key stormsafe-laptop mlflow'
echo '  kubectl --context kind-stormsafe -n stormsafe exec garage-0 -c garage -- /garage key create stormsafe-cluster'
echo '  kubectl --context kind-stormsafe -n stormsafe exec garage-0 -c garage -- /garage bucket allow --read --key stormsafe-cluster mlflow'
echo 'Keep the laptop key in .dvc/config.local and .env; docs/cluster.md says where the cluster key goes.'
