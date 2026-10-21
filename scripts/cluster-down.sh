#!/usr/bin/env bash
# Delete the local StormSafe kind cluster (spec 0003). Secrets created by hand go with it;
# docs/cluster.md lists what to recreate after the next scripts/cluster-up.sh.
# Human-only (CLAUDE.md): the owner runs this; agents only edit it.
set -euo pipefail

CLUSTER="stormsafe"

command -v kind >/dev/null 2>&1 || { echo "error: kind is not installed" >&2; exit 1; }

if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  kind delete cluster --name "$CLUSTER"
else
  echo "==> no kind cluster named '$CLUSTER'; nothing to delete"
fi
