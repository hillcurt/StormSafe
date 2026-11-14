#!/usr/bin/env bash
# The laptop's way into the Garage S3 API (ADR 0008, spec 0004): forward 127.0.0.1:3900 to the
# in-cluster Service for as long as one command runs, then close it. Nothing listens otherwise.
#
# Usage:
#   scripts/store-forward.sh <command> [args...]   run one command, then close the forward
#   scripts/store-forward.sh                       hold the forward until Ctrl-C
#
# Exits with the command's status, or with an error if the forward drops.
# Human-only (CLAUDE.md): it touches the live cluster, so the owner runs it.
set -euo pipefail

CONTEXT="kind-stormsafe"
NAMESPACE="stormsafe"
PORT=3900
WAIT_SECONDS=15

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

command -v kubectl >/dev/null 2>&1 || die "kubectl is not installed (see docs/cluster.md)"

port_answers() { (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; }

if port_answers; then
  die "port $PORT on 127.0.0.1 is already in use (another forward?); stop it first, or check with: lsof -nP -iTCP:$PORT -sTCP:LISTEN"
fi

pf_log="$(mktemp)"
pf_pid=""
# shellcheck disable=SC2329 # invoked by the EXIT trap
cleanup() {
  if [[ -n "$pf_pid" ]]; then
    kill "$pf_pid" 2>/dev/null || true
    wait "$pf_pid" 2>/dev/null || true
  fi
  rm -f "$pf_log"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

kubectl --context "$CONTEXT" -n "$NAMESPACE" port-forward --address 127.0.0.1 svc/garage "$PORT:$PORT" >"$pf_log" 2>&1 &
pf_pid=$!

forward_alive() { kill -0 "$pf_pid" 2>/dev/null; }
forward_error() { tail -n 1 "$pf_log" 2>/dev/null || true; }

deadline=$((SECONDS + WAIT_SECONDS))
until port_answers; do
  forward_alive || die "the forward exited before it was ready: $(forward_error)"
  (( SECONDS < deadline )) || die "127.0.0.1:$PORT did not answer within ${WAIT_SECONDS}s"
  sleep 0.5
done

if (( $# == 0 )); then
  printf '==> Garage S3 API on http://127.0.0.1:%s; Ctrl-C to stop\n' "$PORT"
  # wait returns only when the forward ends on its own.
  wait "$pf_pid" || true
  pf_pid=""
  die "the forward dropped: $(forward_error)"
fi

set +e
"$@"
status=$?
set -e
if ! forward_alive; then
  pf_pid=""
  die "the forward dropped while the command ran (exit $status): $(forward_error). Run it again."
fi
exit "$status"
