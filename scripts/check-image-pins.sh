#!/usr/bin/env bash
# CI check (spec 0003): every pinned image must be a multi-arch index that includes linux/arm64,
# so it runs on the owner's Apple Silicon machine. Reads image references from stdin, one per
# line, as name:tag@sha256:digest. Fails when a digest is missing, not an index, or lacks arm64.
# Warns, with the tag's current digest, when the tag now points somewhere else.
set -euo pipefail

command -v crane >/dev/null 2>&1 || { echo "error: crane is required" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "error: jq is required" >&2; exit 1; }

# In GitHub Actions, findings also become annotations on the PR.
annotate() { [[ -n "${GITHUB_ACTIONS:-}" ]] && echo "::$1::$2"; return 0; }
fail() { echo "FAIL $1"; annotate error "$1"; failures=$((failures + 1)); }
warn() { echo "WARN $1"; annotate warning "$1"; }

failures=0
checked=0
while read -r ref; do
  [[ -z "$ref" ]] && continue
  checked=$((checked + 1))
  if [[ ! "$ref" =~ ^([^@]+):([^:@/]+)@(sha256:[0-9a-f]{64})$ ]]; then
    fail "$ref: expected name:tag@sha256:<digest>"
    continue
  fi
  name="${BASH_REMATCH[1]}"
  tag="${BASH_REMATCH[2]}"
  digest="${BASH_REMATCH[3]}"

  current="$(crane digest "$name:$tag" 2>/dev/null || echo "unresolved")"
  if [[ "$current" != "$digest" ]]; then
    warn "$name:$tag now resolves to $current (pinned $digest)"
  fi

  # Anonymous pulls can be rate limited (public.ecr.aws answers TOOMANYREQUESTS). Retry once,
  # then read Docker official images from Docker Hub, which serves the same digest.
  for source in "$name" "$name" "${name/#public.ecr.aws\/docker\//docker.io/}"; do
    if manifest="$(crane manifest "$source@$digest" 2>&1)"; then
      [[ "$source" != "$name" ]] && echo "note $name: read $digest from $source (same content address)"
      break
    fi
    grep -q TOOMANYREQUESTS <<<"$manifest" || break
    sleep 10
  done
  if ! jq -e . >/dev/null 2>&1 <<<"$manifest"; then
    fail "$name:$tag: cannot fetch pinned digest $digest: $(tail -n 1 <<<"$manifest")"
    continue
  fi
  media="$(jq -r '.mediaType // empty' <<<"$manifest")"
  case "$media" in
    application/vnd.oci.image.index.v1+json | application/vnd.docker.distribution.manifest.list.v2+json) ;;
    *)
      fail "$name:$tag: $digest is not a multi-arch index ($media)"
      continue
      ;;
  esac
  if jq -e '.manifests[] | select(.platform.os == "linux" and .platform.architecture == "arm64")' \
    <<<"$manifest" >/dev/null; then
    echo "ok   $name:$tag@$digest (multi-arch, linux/arm64)"
  else
    fail "$name:$tag: $digest has no linux/arm64 image"
  fi
done

if (( checked == 0 )); then
  echo "error: no image references on stdin" >&2
  exit 1
fi
echo "$checked image(s) checked, $failures failure(s)"
(( failures == 0 ))
