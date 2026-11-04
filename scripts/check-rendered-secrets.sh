#!/usr/bin/env bash
# CI check (spec 0003): no Secret values in what gets applied, and no Secrets Argo CD syncs.
# Reads rendered manifests (`kubectl kustomize` output) and fails on:
#   - any Secret with `data` or `stringData`, always;
#   - any Secret not named in --allow (comma-separated).
# The only allowed Secrets are the two empty stubs Argo CD's upstream install ships and fills in
# at runtime (argocd-secret, argocd-notifications-secret); StormSafe's own overlays allow none.
#
# Usage: check-rendered-secrets.sh [--allow name,name] FILE...
set -euo pipefail

allow=""
if [[ "${1:-}" == "--allow" ]]; then
  allow="${2:?--allow needs a comma-separated list of names}"
  shift 2
fi
(( $# > 0 )) || { echo "usage: $0 [--allow name,name] FILE..." >&2; exit 2; }

# kustomize output is normalized: documents split by `---`, top-level keys at column 0,
# metadata.name indented two spaces.
awk -v allow="$allow" '
  BEGIN { n = split(allow, names, ","); for (i = 1; i <= n; i++) allowed[names[i]] = 1 }
  function finish() {
    if (kind == "Secret") {
      where = docfile ": Secret/" (name == "" ? "<unnamed>" : name)
      if (hasdata) { print "FAIL " where " has data or stringData"; bad++ }
      else if (!(name in allowed)) { print "FAIL " where " is not allowed here"; bad++ }
      else { print "ok   " where " (empty upstream stub, allowed)" }
    }
    kind = ""; name = ""; hasdata = 0; inmeta = 0
  }
  FNR == 1 { if (NR != 1) finish(); docfile = FILENAME }
  /^---/ { finish(); next }
  /^kind:[ \t]*/ { kind = $2 }
  /^metadata:/ { inmeta = 1; next }
  /^[^ \t#]/ { inmeta = 0 }
  inmeta && /^  name:[ \t]*/ { name = $2 }
  /^(data|stringData):/ { hasdata = 1 }
  END { finish(); exit (bad > 0) }
' "$@"
