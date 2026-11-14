"""Acceptance tests for spec 0004: the local Garage object store stays pinned, private, and small.

Registry checks (multi-arch, linux/arm64), rendering, schema validation, and `shellcheck` need the
network or extra tools, so they run in the `manifests` CI job. These tests read the files, and run
`cluster-up.sh` against stub `docker`, `kind`, and `kubectl` commands, so no cluster is touched.
"""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
GARAGE = DEPLOY / "base" / "garage"
ARGOCD = DEPLOY / "argocd"
SCRIPTS = ROOT / "scripts"
CLUSTER_UP = SCRIPTS / "cluster-up.sh"
STORE_INIT = SCRIPTS / "store-init.sh"
STORE_FORWARD = SCRIPTS / "store-forward.sh"
KIND_CONFIG = DEPLOY / "cluster" / "kind-config.yaml"

PLACEHOLDER = "__STORMSAFE_STORE_HOST_DIR__"
NODE_PATH = "/var/lib/stormsafe/store"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def garage_text() -> str:
    return "\n---\n".join(p.read_text() for p in sorted(GARAGE.glob("*.yaml")))


def documents(text: str) -> list[str]:
    return [doc for doc in re.split(r"^---\s*$", text, flags=re.MULTILINE) if doc.strip()]


def kinds(text: str) -> list[str]:
    return re.findall(r"^kind:\s*(\S+)", text, re.MULTILINE)


def doc_of_kind(kind: str) -> str:
    found = [d for d in documents(garage_text()) if re.search(rf"^kind:\s*{kind}\s*$", d, re.M)]
    assert len(found) == 1, f"expected exactly one {kind} under deploy/base/garage/"
    return found[0]


def values(text: str, key: str) -> list[str]:
    return [
        v.strip().strip("\"'")
        for v in re.findall(rf"^\s*-?\s*{re.escape(key)}:\s*(.+?)\s*$", text, re.MULTILINE)
    ]


# --- manifests ---------------------------------------------------------------------------------


def test_base_includes_garage() -> None:
    base = (DEPLOY / "base" / "kustomization.yaml").read_text()
    assert re.search(r"^\s*-\s*garage/?\s*$", base, re.MULTILINE), "base must include garage/"
    listed = (GARAGE / "kustomization.yaml").read_text()
    for path in GARAGE.glob("*.yaml"):
        if path.name != "kustomization.yaml":
            assert path.name in listed, f"{path.name} is not listed in garage/kustomization.yaml"


def test_garage_image_pinned_by_digest() -> None:
    images = values(doc_of_kind("StatefulSet"), "image")
    assert len(images) == 1, "one container, one image"
    image = images[0]
    assert re.fullmatch(rf"dxflrs/garage:v2\.\d+\.\d+@{DIGEST.pattern}", image), (
        f"pin a stable v2 Garage release by digest: {image}"
    )


def test_garage_runs_non_root_single_replica() -> None:
    sts = doc_of_kind("StatefulSet")
    assert values(sts, "replicas") == ["1"]
    assert "runAsNonRoot: true" in sts
    uids = values(sts, "runAsUser")
    assert uids and all(int(uid) > 0 for uid in uids), "run as a non-zero UID"
    assert "allowPrivilegeEscalation: false" in sts
    assert "readOnlyRootFilesystem: true" in sts
    assert re.search(r"drop:\s*\n\s*-\s*ALL", sts), "drop all capabilities"
    assert "automountServiceAccountToken: false" in sts, "Garage never talks to the API server"
    assert "privileged: true" not in sts
    assert "hostNetwork" not in sts and "hostPort" not in sts, "no host networking"


def test_garage_readiness_is_tcp_on_admin_port() -> None:
    """Owner's call (plan.md): /health is 503 until store-init.sh assigns the layout."""
    sts = doc_of_kind("StatefulSet")
    probe = sts.split("readinessProbe:", 1)
    assert len(probe) == 2, "Garage needs a readiness probe"
    assert re.match(r"\s*\n\s*tcpSocket:\s*\n\s*port:\s*(3903|admin)\s*\n", probe[1]), (
        "readiness is a TCP check on the admin API port"
    )


def test_garage_secrets_come_from_secret_refs() -> None:
    sts = doc_of_kind("StatefulSet")
    for env in ("GARAGE_RPC_SECRET", "GARAGE_ADMIN_TOKEN"):
        block = sts.split(f"name: {env}", 1)
        assert len(block) == 2, f"set {env}"
        assert re.match(r"\s*\n\s*valueFrom:\s*\n\s*secretKeyRef:", block[1]), (
            f"{env} comes from a Secret"
        )
    assert values(sts, "value") == [], "no literal env values"


def test_garage_config_has_no_secret_values() -> None:
    cm = doc_of_kind("ConfigMap")
    toml = cm.split("garage.toml: |", 1)
    assert len(toml) == 2, "the ConfigMap holds garage.toml"
    config = toml[1]
    for key in ("rpc_secret", "admin_token", "metrics_token"):
        assert not re.search(rf"^\s*{key}\s*=", config, re.MULTILINE), f"no {key} in garage.toml"
    assert re.search(r"^\s*replication_factor\s*=\s*1\s*$", config, re.MULTILINE)
    assert re.search(r'^\s*db_engine\s*=\s*"sqlite"', config, re.MULTILINE)
    for key in ("metadata_dir", "data_dir"):
        match = re.search(rf'^\s*{key}\s*=\s*"([^"]+)"', config, re.MULTILINE)
        assert match and match.group(1).startswith("/var/lib/garage/"), f"{key} on the volume"
    s3 = config.split("[s3_api]", 1)
    admin = config.split("[admin]", 1)
    assert len(s3) == 2 and re.search(r'api_bind_addr\s*=\s*"[^"]*:3900"', s3[1].split("[")[0])
    assert len(admin) == 2 and re.search(r'api_bind_addr\s*=\s*"[^"]*:3903"', admin[1])
    assert "[s3_web]" not in config, "no web endpoint (out of scope)"


def test_garage_service_is_s3_clusterip_only() -> None:
    text = garage_text()
    assert kinds(text).count("Service") == 1, "exactly one Service"
    svc = doc_of_kind("Service")
    assert values(svc, "type") in ([], ["ClusterIP"]), "ClusterIP only"
    assert values(svc, "port") == ["3900"], "the S3 API port only"
    assert "clusterIP: None" not in svc
    for path in DEPLOY.rglob("*.yaml"):
        body = path.read_text()
        for bad in ("NodePort", "LoadBalancer", "nodePort:"):
            assert bad not in body, f"{bad} in {path.relative_to(ROOT)}"


def test_garage_volume_is_the_node_mount() -> None:
    pv = doc_of_kind("PersistentVolume")
    pvc = doc_of_kind("PersistentVolumeClaim")
    assert values(pv, "path") == [NODE_PATH], "the PV is the kind node's mount path"
    assert values(pv, "persistentVolumeReclaimPolicy") == ["Retain"]
    assert "claimRef:" in pv, "bind the PV to its claim"
    claim = values(pvc, "name")[0]
    assert claim in values(pv.split("claimRef:", 1)[1], "name")
    for doc in (pv, pvc):
        assert re.search(r'^\s*storageClassName:\s*""\s*$', doc, re.MULTILINE), (
            "empty storage class, so kind's default provisioner never takes the claim"
        )
    assert f"claimName: {claim}" in doc_of_kind("StatefulSet")
    assert "volumeClaimTemplates" not in garage_text(), "one PV and one PVC, as the spec says"


# --- kind config -------------------------------------------------------------------------------


def test_kind_config_mounts_placeholder_only() -> None:
    text = KIND_CONFIG.read_text()
    assert values(text, "hostPath") == [PLACEHOLDER], "commit the placeholder, never a real path"
    assert values(text, "containerPath") == [NODE_PATH]
    assert "/Users/" not in text and "/home/" not in text


# --- Argo CD project ---------------------------------------------------------------------------


def test_application_uses_stormsafe_project() -> None:
    text = (ARGOCD / "application.yaml").read_text()
    assert values(text, "project") == ["stormsafe"]


def test_appproject_is_least_privilege() -> None:
    text = (ARGOCD / "appproject.yaml").read_text()
    assert values(text, "kind") == ["AppProject"]
    assert values(text, "namespace") == ["argocd", "stormsafe"], "lives with Argo CD"
    repos = text.split("sourceRepos:", 1)[1].split(":", 1)[0]
    assert re.findall(r"^\s*-\s*(\S+)", repos, re.MULTILINE) == [
        "https://github.com/hillcurt/StormSafe.git"
    ], "this repo is the only source"
    dest = text.split("destinations:", 1)[1].split("clusterResourceWhitelist:", 1)[0]
    assert values(dest, "namespace") == ["stormsafe"], "stormsafe is the only destination"
    assert values(dest, "server") == ["https://kubernetes.default.svc"]
    allowed = text.split("clusterResourceWhitelist:", 1)[1]
    assert sorted(values(allowed, "kind")) == ["Namespace", "PersistentVolume"]
    assert values(allowed, "group") == ["", ""], "core API group only"
    assert "*" not in text, "no wildcards"


def test_appproject_applied_with_the_application() -> None:
    """A CR can't go in the same apply as its CRD, so it is not in the Argo CD kustomization."""
    assert "appproject" not in (ARGOCD / "kustomization.yaml").read_text()
    script = CLUSTER_UP.read_text()
    assert "deploy/argocd/appproject.yaml" in script


def test_ci_validates_appproject() -> None:
    wf = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    call = wf.split("kubeconform -strict", 1)[1].split("\n\n", 1)[0]
    assert "deploy/argocd/appproject.yaml" in call, "validate the AppProject against its CRD"


# --- scripts: static checks --------------------------------------------------------------------


def lines_with(script: str, needle: str) -> list[str]:
    return [line.strip() for line in script.splitlines() if needle in line]


def test_new_scripts_are_strict_bash() -> None:
    for path in (STORE_INIT, STORE_FORWARD):
        script = path.read_text()
        assert script.startswith("#!/usr/bin/env bash\n"), path.name
        assert "set -euo pipefail" in script, path.name
        assert "set -x" not in script and "xtrace" not in script, f"no tracing in {path.name}"
        assert os.access(path, os.X_OK), f"{path.name} must be executable"


def test_store_forward_binds_loopback_and_cleans_up() -> None:
    script = STORE_FORWARD.read_text()
    forwards = lines_with(script, "port-forward")
    calls = [line for line in forwards if not line.startswith("#")]
    assert calls, "open a kubectl port-forward"
    for line in calls:
        if "kubectl" in line or line.startswith("kc "):
            assert "--address 127.0.0.1" in line, f"bind 127.0.0.1 only: {line}"
            assert "svc/garage" in line and "3900:3900" in line
    assert "0.0.0.0" not in script and "--address localhost" not in script
    assert re.search(r"trap\s+\S+\s+EXIT", script), "close the forward on every exit"
    assert re.search(r"trap\s+.+\s+INT", script), "Ctrl-C closes the forward"
    assert "kill" in script, "stop the forward"
    assert "in use" in script, "fail clearly when 3900 is taken"
    assert "dropped" in script, "say when the forward dropped"


def test_store_init_prints_key_commands_only() -> None:
    script = STORE_INIT.read_text()
    key_lines = lines_with(script, "key create")
    assert len(key_lines) >= 2, "print the key create command for both keys"
    for line in key_lines:
        assert line.startswith("echo '") and line.endswith("'"), f"print it, don't run it: {line}"
    for line in lines_with(script, "bucket allow"):
        assert line.startswith("echo '") and line.endswith("'"), f"print it, don't run it: {line}"
    assert "key info" not in script and "--show-secret" not in script, "never read a key"
    assert "secret garage" not in script and "admin-token" not in script, "never read the token"
    assert "get secret" not in script


def test_store_init_is_guarded() -> None:
    """A second run changes nothing: layout only at version 0, buckets only when missing."""
    script = STORE_INIT.read_text()
    assert "kubectl" in script and "exec" in script, "run garage through kubectl exec"
    assert "Current cluster layout version" in script
    assert "layout apply" in script and "layout assign" in script
    assert "bucket info" in script, "check a bucket exists before creating it"
    for bucket in ("dvc", "mlflow"):
        assert re.search(rf"\b{bucket}\b", script), f"create the {bucket} bucket"
    assert "/proxy/health" in script, "wait for /health after the layout"


def test_cluster_up_creates_garage_secret_once() -> None:
    script = CLUSTER_UP.read_text()
    assert "STORMSAFE_STORE_HOST_DIR" in script
    assert "openssl rand" in script, "generate the values"
    assert "get secret garage" in script, "create only when missing"
    creates = [line for line in lines_with(script, "create -f -") if not line.startswith("#")]
    assert len(creates) == 1, "one create, from stdin"
    assert "--from-literal" not in script, "values never go in a process's arguments"
    assert script.count("kc apply") == 2, "one apply for Argo CD, one for project + Application"


# --- scripts: cluster-up.sh against stubs ------------------------------------------------------

STUBS = {
    "docker": """#!/usr/bin/env bash
case "$1" in
  info) exit 0 ;;
  inspect) [[ "$*" == *Mounts* ]] && echo "$STUB_MOUNTS"; exit 0 ;;
esac
exit 0
""",
    "kind": """#!/usr/bin/env bash
echo "kind $*" >> "$STUB_LOG/kind.log"
if [[ "$1 $2" == "get clusters" ]]; then cat "$STUB_LOG/clusters" 2>/dev/null; exit 0; fi
if [[ "$1 $2" == "create cluster" ]]; then
  while (( $# )); do [[ "$1" == --config ]] && cp "$2" "$STUB_LOG/kind-config.yaml"; shift; done
  echo stormsafe > "$STUB_LOG/clusters"
fi
exit 0
""",
    "kubectl": """#!/usr/bin/env bash
echo "kubectl $*" >> "$STUB_LOG/kubectl.log"
case "$*" in
  *"get secret garage"*) exit "$STUB_SECRET_MISSING" ;;
  *"create -f -"*) cat > "$STUB_LOG/secret.yaml"; exit 0 ;;
  *jsonpath*) echo "Synced Healthy"; exit 0 ;;
  *" -f -"*) cat > /dev/null; exit 0 ;;
esac
exit 0
""",
}


def stub_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    for rel in (
        "scripts/cluster-up.sh",
        "deploy/cluster/kind-config.yaml",
        "deploy/argocd/application.yaml",
        "deploy/argocd/appproject.yaml",
    ):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, repo / rel)
    return repo


def run_cluster_up(
    tmp_path: Path,
    store_dir: str | None,
    *,
    secret_missing: bool = True,
    running_without_mount: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    repo = stub_repo(tmp_path)
    bin_dir = tmp_path / "bin"
    log = tmp_path / "log"
    bin_dir.mkdir()
    log.mkdir()
    for name, body in STUBS.items():
        path = bin_dir / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    if running_without_mount:
        (log / "clusters").write_text("stormsafe\n")
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "STUB_LOG": str(log),
        "STUB_SECRET_MISSING": "1" if secret_missing else "0",
        "STUB_MOUNTS": "" if running_without_mount else NODE_PATH,
    }
    if store_dir is not None:
        env["STORMSAFE_STORE_HOST_DIR"] = store_dir
    proc = subprocess.run(
        ["bash", str(repo / "scripts" / "cluster-up.sh")],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    return proc, log


def kind_created(log: Path) -> bool:
    kind_log = log / "kind.log"
    return kind_log.exists() and "create cluster" in kind_log.read_text()


needs_openssl = pytest.mark.skipif(not shutil.which("openssl"), reason="needs openssl")


def test_cluster_up_refuses_without_store_dir(tmp_path: Path) -> None:
    proc, log = run_cluster_up(tmp_path, None)
    assert proc.returncode != 0
    assert "STORMSAFE_STORE_HOST_DIR" in proc.stderr
    assert not kind_created(log), "refuse before creating anything"


@pytest.mark.parametrize("bad", ["inside-repo", "relative/store"])
def test_cluster_up_refuses_bad_store_dir(tmp_path: Path, bad: str) -> None:
    store = str(tmp_path / "repo" / "data") if bad == "inside-repo" else bad
    proc, log = run_cluster_up(tmp_path, store)
    assert proc.returncode != 0, f"must refuse {store}"
    assert "STORMSAFE_STORE_HOST_DIR" in proc.stderr
    assert not kind_created(log)


@needs_openssl
def test_cluster_up_renders_mount_and_secret(tmp_path: Path) -> None:
    store = tmp_path / "store"
    proc, log = run_cluster_up(tmp_path, str(store))
    assert proc.returncode == 0, proc.stderr
    assert store.is_dir(), "create the host folder if it is missing"
    rendered = (log / "kind-config.yaml").read_text()
    assert values(rendered, "hostPath") == [str(store)]
    assert PLACEHOLDER not in rendered
    committed = (tmp_path / "repo" / "deploy" / "cluster" / "kind-config.yaml").read_text()
    assert PLACEHOLDER in committed, "render to a temporary file, never the committed one"

    secret = (log / "secret.yaml").read_text()
    assert values(secret, "kind") == ["Secret"]
    assert "name: garage" in secret and "namespace: stormsafe" in secret
    rpc = re.search(r"^\s*rpc-secret:\s*(\S+)", secret, re.MULTILINE)
    token = re.search(r"^\s*admin-token:\s*(\S+)", secret, re.MULTILINE)
    assert rpc and token, "both keys in the Secret"
    rpc_value, token_value = rpc.group(1).strip("\"'"), token.group(1).strip("\"'")
    assert re.fullmatch(r"[0-9a-f]{64}", rpc_value), "32 random bytes, hex"
    assert len(token_value) >= 32
    output = proc.stdout + proc.stderr
    calls = (log / "kubectl.log").read_text()
    for value in (rpc_value, token_value):
        assert value not in output, "never print a generated value"
        assert value not in calls, "never pass a value as an argument"


@needs_openssl
def test_cluster_up_keeps_an_existing_secret(tmp_path: Path) -> None:
    proc, log = run_cluster_up(tmp_path, str(tmp_path / "store"), secret_missing=False)
    assert proc.returncode == 0, proc.stderr
    assert not (log / "secret.yaml").exists(), "leave an existing Secret as it is"
    assert "create -f -" not in (log / "kubectl.log").read_text()


def test_cluster_up_warns_when_running_cluster_lacks_mount(tmp_path: Path) -> None:
    proc, log = run_cluster_up(
        tmp_path, str(tmp_path / "store"), secret_missing=False, running_without_mount=True
    )
    assert not kind_created(log), "never recreate a running cluster"
    assert "cluster-down.sh" in proc.stderr, "say how to rebuild"
    assert NODE_PATH in proc.stderr


# --- config and docs ---------------------------------------------------------------------------


def test_env_example_has_blank_store_dir() -> None:
    lines = (ROOT / ".env.example").read_text().splitlines()
    assert "STORMSAFE_STORE_HOST_DIR=" in lines, "list it, blank"


def test_cluster_doc_covers_store() -> None:
    doc = (ROOT / "docs" / "cluster.md").read_text()
    lower = doc.lower()
    for needle in (
        "store-init.sh",
        "store-forward.sh",
        "stormsafe_store_host_dir",
        "file sharing",
        "rebuild",
        "garage key create",
        "aws_region=garage",
    ):
        assert needle in lower, f"docs/cluster.md should cover {needle!r}"
    after = lower.split("after a rebuild", 1)[1]
    assert "garage" in after, "say what happens to Garage's Secret after a rebuild"
