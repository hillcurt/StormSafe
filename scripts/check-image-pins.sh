#!/usr/bin/env bash
# CI check (spec 0003): every pinned image must be a multi-arch index that includes linux/arm64,
# so it runs on the owner's Apple Silicon machine. Reads image references from stdin, one per
# line, as name:tag@sha256:digest. Fails when a digest is missing, not an index, or lacks arm64.
# Warns, with the tag's current digest, when the tag now points somewhere else.
set -euo pipefail

command -v crane >/dev/null 2>&1 || { echo "error: crane is required" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "error: jq is required" >&2; exit 1; }

failures=0
checked=0
while read -r ref; do
  [[ -z "$ref" ]] && continue
  checked=$((checked + 1))
  if [[ ! "$ref" =~ ^([^@]+):([^:@/]+)@(sha256:[0-9a-f]{64})$ ]]; then
    echo "FAIL $ref: expected name:tag@sha256:<digest>"
    failures=$((failures + 1))
    continue
  fi
  name="${BASH_REMATCH[1]}"
  tag="${BASH_REMATCH[2]}"
  digest="${BASH_REMATCH[3]}"

  current="$(crane digest "$name:$tag" 2>/dev/null || echo "unresolved")"
  if [[ "$current" != "$digest" ]]; then
    echo "WARN $name:$tag now resolves to $current (pinned $digest)"
  fi

  if ! manifest="$(crane manifest "$name@$digest" 2>/dev/null)"; then
    echo "FAIL $name:$tag: pinned digest $digest not found in the registry"
    failures=$((failures + 1))
    continue
  fi
  media="$(jq -r '.mediaType // empty' <<<"$manifest")"
  case "$media" in
    application/vnd.oci.image.index.v1+json | application/vnd.docker.distribution.manifest.list.v2+json) ;;
    *)
      echo "FAIL $name:$tag: $digest is not a multi-arch index ($media)"
      failures=$((failures + 1))
      continue
      ;;
  esac
  if jq -e '.manifests[] | select(.platform.os == "linux" and .platform.architecture == "arm64")' \
    <<<"$manifest" >/dev/null; then
    echo "ok   $name:$tag@$digest (multi-arch, linux/arm64)"
  else
    echo "FAIL $name:$tag: $digest has no linux/arm64 image"
    failures=$((failures + 1))
  fi
done

if (( checked == 0 )); then
  echo "error: no image references on stdin" >&2
  exit 1
fi
echo "$checked image(s) checked, $failures failure(s)"
(( failures == 0 ))
