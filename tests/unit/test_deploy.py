"""Acceptance tests for spec 0003: the local cluster bootstrap stays pinned, private, and GitOps.

Registry checks (multi-arch, linux/arm64) and rendering need the network, so they run in the
`manifests` CI job instead. These tests read the files only.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
ARGOCD = DEPLOY / "argocd"
CLUSTER_UP = ROOT / "scripts" / "cluster-up.sh"
AGENTS = ROOT / ".claude" / "agents"

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
ARGOCD_IMAGES = (
    "quay.io/argoproj/argocd",
    "ghcr.io/dexidp/dex",
    "public.ecr.aws/docker/library/redis",
)
READ_ONLY_TOOLS = {"Read", "Grep", "Glob"}


def yaml_files(root: Path) -> list[Path]:
    return sorted([*root.rglob("*.yaml"), *root.rglob("*.yml")])


def field(text: str, key: str) -> str:
    """Value of the first `key: value` line, quotes stripped."""
    match = re.search(rf"^\s*{re.escape(key)}:\s*(\S+)\s*$", text, re.MULTILINE)
    assert match, f"no {key!r} field"
    return match.group(1).strip("\"'")


def test_kind_node_image_pinned_by_digest() -> None:
    text = (DEPLOY / "cluster" / "kind-config.yaml").read_text()
    images = re.findall(r"^\s*image:\s*(\S+)", text, re.MULTILINE)
    assert images, "the kind config must name its node image"
    for image in images:
        assert image.startswith("kindest/node:"), image
        assert re.search(rf"@{DIGEST.pattern}$", image), f"pin the node image by digest: {image}"
    assert "extraPortMappings" not in text, "no host ports: reach Argo CD with port-forward"
    assert len(re.findall(r"^\s*- role:", text, re.MULTILINE)) == 1, "single-node cluster"


def test_argocd_manifest_pinned_to_commit() -> None:
    text = (ARGOCD / "kustomization.yaml").read_text()
    urls = re.findall(r"https://\S+", text)
    install = [u for u in urls if "argoproj/argo-cd" in u]
    assert len(install) == 1, "install Argo CD from exactly one upstream manifest"
    ref = re.search(r"argoproj/argo-cd/([^/]+)/manifests/install\.yaml$", install[0])
    assert ref, f"use the non-HA manifests/install.yaml: {install[0]}"
    assert re.fullmatch(r"[0-9a-f]{40}", ref.group(1)), "pin the manifest to a commit SHA"
    assert field(text, "namespace") == "argocd"


def test_argocd_images_pinned_by_digest() -> None:
    text = (ARGOCD / "kustomization.yaml").read_text()
    blocks = re.split(r"^\s*- name:\s*", text.split("images:", 1)[-1], flags=re.MULTILINE)[1:]
    pins = {block.split()[0]: block for block in blocks}
    for image in ARGOCD_IMAGES:
        assert image in pins, f"override {image} by digest"
        assert DIGEST.search(pins[image]), f"{image} needs a sha256 digest"
    for bad in (
        ":stable",
        ":latest",
        "/stable/",
        "/master/",
        "/main/",
        "newTag: stable",
        "newTag: latest",
    ):
        assert bad not in text, f"no floating refs ({bad})"


def test_application_targets_trunk_overlay() -> None:
    text = (ARGOCD / "application.yaml").read_text()
    assert field(text, "kind") == "Application"
    assert field(text, "name") == "stormsafe"
    assert field(text, "repoURL").lower() == "https://github.com/hillcurt/stormsafe.git"
    assert field(text, "targetRevision") == "trunk"
    assert field(text, "path") == "deploy/overlays/local"
    assert field(text, "namespace") == "argocd", "the Application lives with Argo CD"
    destination = text.split("destination:", 1)[1]
    assert field(destination, "namespace") == "stormsafe"
    sync = text.split("automated:", 1)
    assert len(sync) == 2, "use automated sync"
    assert field(sync[1], "prune") == "true"
    assert field(sync[1], "selfHeal") == "true"


def test_base_is_the_namespace_only() -> None:
    kinds = [
        kind
        for path in yaml_files(DEPLOY / "base")
        for kind in re.findall(r"^kind:\s*(\S+)", path.read_text(), re.MULTILINE)
    ]
    assert sorted(kinds) == ["Kustomization", "Namespace"]
    overlay = (DEPLOY / "overlays" / "local" / "kustomization.yaml").read_text()
    assert "../../base" in overlay


def test_no_secrets_under_deploy() -> None:
    """ADR 0004 and 0007: Secrets are created by hand, never committed or synced."""
    for path in yaml_files(DEPLOY):
        text = path.read_text()
        assert not re.search(r"^kind:\s*Secret\b", text, re.MULTILINE), f"Secret in {path}"
        assert "secretGenerator" not in text, f"secretGenerator in {path}"


def test_cluster_up_is_guarded() -> None:
    """A second run must change nothing: create only when missing, apply declaratively."""
    script = CLUSTER_UP.read_text()
    assert script.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in script
    assert "kind get clusters" in script, "check for the cluster before creating it"
    assert "--server-side" in script, "Argo CD CRDs need a server-side apply"
    assert "kubectl create " not in script, "use apply, which is idempotent"
    assert "Synced" in script and "Healthy" in script, "wait for Synced and Healthy"
    down = (ROOT / "scripts" / "cluster-down.sh").read_text()
    assert "kind delete cluster" in down


def test_cluster_up_prints_password_command_only() -> None:
    """The admin password is never read or printed; only the command to read it is shown."""
    script = CLUSTER_UP.read_text()
    secret_lines = [line.strip() for line in script.splitlines() if "initial-admin-secret" in line]
    assert secret_lines, "tell the owner how to read the initial admin password"
    for line in secret_lines:
        assert line.startswith("echo '") and line.endswith("'"), f"print it, don't run it: {line}"
    assert "initial-password" not in script, "never run `argocd admin initial-password`"
    assert "set -x" not in script and "xtrace" not in script, "no tracing of commands"


def test_infra_reviewer_is_read_only() -> None:
    """Same guard as the reviewer: widening its tools is a human-only change (ADR 0003)."""
    text = (AGENTS / "infra-reviewer.md").read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "infra-reviewer has no frontmatter"
    fields = dict(
        (key.strip(), value.strip())
        for key, _, value in (line.partition(":") for line in match.group(1).splitlines())
    )
    assert fields["name"] == "infra-reviewer"
    tools = {t.strip() for t in fields.get("tools", "").split(",") if t.strip()}
    assert tools, "infra-reviewer must declare an explicit tool allowlist"
    assert tools <= READ_ONLY_TOOLS, f"non-read-only tools: {tools - READ_ONLY_TOOLS}"
    body = text.lower()
    for topic in ("adr 0006", "adr 0007", "secret", "digest", "permissions", "advisory"):
        assert topic in body, f"infra-reviewer should cover {topic!r}"


def test_cluster_doc_covers_lifecycle() -> None:
    doc = (ROOT / "docs" / "cluster.md").read_text()
    lower = doc.lower()
    for section in ("prerequisites", "bring up", "argo cd ui", "tear down", "after a rebuild"):
        assert section in lower, f"docs/cluster.md needs a {section!r} section"
    for tool in ("kind", "kubectl"):
        assert re.search(rf"`{tool}`\s*\|\s*v\d", doc), f"list the tested {tool} version"
    assert re.search(r"Docker Desktop\s*\|", doc), "list the tested Docker Desktop version"
    assert "stormsafe-site" in doc, "say which Secrets to recreate after a rebuild"


def test_claude_md_names_digest_file() -> None:
    text = (ROOT / "CLAUDE.md").read_text()
    row = next(line for line in text.splitlines() if line.startswith("| Infra config"))
    assert "deploy/overlays/local/kustomization.yaml" in row


def test_ci_validates_manifests_read_only() -> None:
    wf = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    for step in ("kubectl kustomize", "kubeconform", "shellcheck", "check-image-pins.sh"):
        assert step in wf, f"ci.yml must run {step}"
    assert re.findall(r"^\s+\w[\w-]*: write", wf, re.MULTILINE) == [], "permissions stay read-only"
    for action in re.findall(r"uses:\s*(azure/setup-kubectl@\S+)", wf):
        assert re.search(r"@[0-9a-f]{40}$", action), f"pin {action} by commit"
    downloads = re.findall(r"https://github\.com/\S+/releases/download/\S+", wf)
    assert downloads, "install the CI tools from pinned releases"
    assert wf.count("sha256sum -c") >= len(downloads), "verify every downloaded tool"


SECRETS_CHECK = ROOT / "scripts" / "check-rendered-secrets.sh"
UPSTREAM_STUBS = "argocd-secret,argocd-notifications-secret"


def run_secrets_check(tmp_path: Path, manifest: str, *args: str) -> int:
    rendered = tmp_path / "rendered.yaml"
    rendered.write_text(manifest)
    cmd = ["bash", str(SECRETS_CHECK), *args, str(rendered)]
    return subprocess.run(cmd, capture_output=True, check=False).returncode


def secret(name: str, body: str = "") -> str:
    return f"apiVersion: v1\nkind: Secret\nmetadata:\n  name: {name}\ntype: Opaque\n{body}"


def test_rendered_secrets_check_allows_only_empty_upstream_stubs(tmp_path: Path) -> None:
    """What gets applied, not just what is committed: no Secret values, no StormSafe Secrets."""
    stubs = secret("argocd-secret") + "---\n" + secret("argocd-notifications-secret")
    assert run_secrets_check(tmp_path, stubs, "--allow", UPSTREAM_STUBS) == 0
    filled = secret("argocd-secret", "stringData:\n  admin.password: x\n")
    assert run_secrets_check(tmp_path, filled, "--allow", UPSTREAM_STUBS) != 0
    with_data = secret("argocd-secret", "data:\n  k: eA==\n")
    assert run_secrets_check(tmp_path, with_data, "--allow", UPSTREAM_STUBS) != 0
    assert run_secrets_check(tmp_path, secret("stormsafe-site")) != 0, "Argo CD syncs no Secrets"
    namespace = "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: stormsafe\n"
    assert run_secrets_check(tmp_path, namespace) == 0


def test_ci_checks_rendered_secrets() -> None:
    wf = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert f"check-rendered-secrets.sh --allow {UPSTREAM_STUBS}" in wf, "Argo CD: stubs only"
    synced = re.search(
        r"check-rendered-secrets\.sh[\s\\]+(\S*deploy_base\S*)\s+(\S*deploy_overlays_local\S*)", wf
    )
    assert synced, "check what Argo CD syncs, with nothing allowed"
