"""15B2b-B1b-3e M-B4/M-B5: the reviewed owner-laptop operator for the INSTALL_TRUST_AND_REGISTRY ceremony.

Records:
- docs/architecture/slice-15b2b-b1b3e-mb4-mb5-continuity-owner-decision.md (the accepted model);
- docs/architecture/slice-15b2b-b1b3e-mb4-mb5-ceremony-package.md (the procedure; every form below).

It replaces owner scratch scripts with one reviewed tool. Every form is
closed: no free path, command or principal argument reaches DEV.

| Form | Effect |
| --- | --- |
| `pins <repo>` | local, read-only: clean checkout at the control commit; every pinned tool hashes to its pin |
| `derive <repo> <export.tar> <workdir>` | local: derive the three representations into a NEW `<workdir>/derived`, re-derive and compare, independently re-hash, write `SHA256SUMS` |
| `cloud <evidence-dir> <since>` | read-only GCP: the 11 JSON captures + bucket list + Admin Activity since `<since>` |
| `host <repo> <evidence-dir> <W0\\|W3\\|W5>` | read-only DEV: identity, K-ACT / K-WIT / host block, release readiness probe, installer `status`, broker preservation, observer, content verifier `expect` |
| `stage <workdir>` | DEV operator home only: create the 0700 stage directory, copy the four files, re-hash them there |
| `mb4 <repo> <workdir> <go-file>` | **mutation, one attempt**: the hash-gated installer `install-anchors` (needs the owner's M-B4 go) |
| `mb5 <repo> <workdir> <go-file>` | **mutation, one attempt**: the hash-gated installer `install-registry` (needs the owner's M-B5 go) |
| `denial <repo> <evidence-dir>` | read-only DEV: the root denial proof, phase `P1B-5` |
| `removal-plan <repo> <evidence-dir>` | read-only DEV: the bounded removal plan |
| `removal <repo> <workdir> <planDigest> <authorization-file>` | **mutation**: the bounded removal (needs a separate owner authorization) |
| `cleanup <workdir>` | DEV operator home only: remove the four staged files and the stage directory |

A go file is the owner's verbatim go statement. The tool refuses unless it
contains every binding line of the reviewed template (package §7 / §9) with
the exact pins, and it writes a local one-attempt marker (`O_EXCL`) BEFORE
the remote invocation. A marker that exists is a STOP: there is no retry,
whatever the outcome.

    tool / flag / marker / go-file check != authorization
    one go = exactly one installer invocation; no retry

It never opens, loads, decrypts or copies K-ROOT or K-WIT, never runs a
keygen, `systemd-creds`, a unit start/stop/reload/enable, the signer or the
witness, and never runs a ledger, genesis, pin or hold form.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

PROJECT = "lilith-agent-260823-27389"
ZONE = "asia-southeast1-b"
DEV = "lilith-dev-01"
OPERATOR_HOME = "/home/ravindupahasara2_gmail_com"
STAGE_DIR = OPERATOR_HOME + "/lilith-mb4-mb5-stage"
RELEASE_SHA = "aee323e94412accbe321bc84eae78c5b8cf95afc"
RELEASE_PYTHON = "/opt/lilith-authority-dev/current/venv/bin/python"
SYSTEM_PYTHON = "/usr/bin/python3"
KACT_PUBLICATION = "/root/b1b3d-l2b-publication.json"
ATTEMPT_DIR = "attempts"

# Package §1: every executable the ceremony runs, by repository path, and its SHA-256.
TOOL_PINS = {
    "services/authority-dev/ceremony/install_authority_dev.py":
        "fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487",
    "services/owner-memory-control/tools/mb4_mb5_installable_inputs.py":
        "dbe94a2d3a38fa838d4fd7eeb9016274c85c684221ddb770e8e993cc15b18d61",
    "services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py":
        "78f57c01811e20a03ebb06bc114847bad440c7435e85ceb0249a488c659b2361",
    "services/owner-memory-control/tools/mb4_mb5_remove_before_mb6.py":
        "db0629a6a5f39ca65e23010aeeccc565978b7d8990f38d6b8bb6c361046ee104",
    "services/owner-memory-control/tools/mb3_registry_ceremony.py":
        "c77b651ca2ae9d5f6c5526f958469a01c0d42e6ebdf189fc206ac2132af61320",
    "services/owner-memory-control/tools/verify_mb3_registry.py":
        "e710cfa623d494e243ab4a1fbaefe28e8d079e58398368f9dcabd645e06b5507",
    "services/authority-dev/ceremony/observe_authority_dev_host.py":
        "a2f21b45e57a153f099c79a734ab05a575ac5c50f7cbc0527e562e94dd6908bf",
    "scripts/verify_broker_dev_current_incarnation.py":
        "2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba",
    "scripts/authority_custody_denial_proof.py":
        "f4e39c81c24a01be5702f6a65a581fcd08f97e1c5ad4a07326883b605fef1455",
}
INSTALLER = "services/authority-dev/ceremony/install_authority_dev.py"
VERIFIER = "services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py"
REMOVER = "services/owner-memory-control/tools/mb4_mb5_remove_before_mb6.py"
OBSERVER = "services/authority-dev/ceremony/observe_authority_dev_host.py"
BROKER = "scripts/verify_broker_dev_current_incarnation.py"
DENIAL = "scripts/authority_custody_denial_proof.py"
DERIVATION = "services/owner-memory-control/tools/mb4_mb5_installable_inputs.py"

# The accepted installable representation pins (continuity decision §3).
DERIVED = {
    "registry-root.json": "bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687",
    "witness-anchor.json": "be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a",
    "authority-registry.v1.json": "46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e",
}
EXPORT_SHA256 = "c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8"
REGISTRY_DIGEST = "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc"
TRANSPORT_SHA256 = "3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156"
E21 = "cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf"
KWIT = "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf"
STAGED = tuple(DERIVED) + ("SHA256SUMS",)

# Package §6.3: the release modules the content verifier imports, and their aee323e SHA-256.
RELEASE_MODULES = {
    "lilith_authority_host/__init__.py": "27a314ec79fc0083f18eb70be215de10b9dc6c39119be505c5cfa690cbb7ac3a",
    "lilith_authority_host/inputs.py": "775d521a197372f252cd718877f74e7902b8e9f7fee79bdd843115131a0ea299",
    "lilith_authority_host/paths.py": "d95171b91c126da983a3ec2cc864b1875dd333b0b0d638eacf8645e93d52c55e",
    "lilith_authority_host/store_observer.py": "e22414fa594c5eddc139f62e2bdabe379f9e78cc78adf339ad60276990d1c27a",
    "lilith_memory/__init__.py": "2bbebd95846f1073a0b4e2ec3a2aa24378c56be4ecbb5470e5c1f1d359037e21",
    "lilith_memory/canonical_contracts.py": "f93d26d8a7e01d78d25f1f1d9540577cf2a55dfd4d52c4b64c87bef93ad887e0",
    "lilith_memory/owner_proof.py": "3a3eb7147d1e276ac261457a2340e045a0c43f6bc63eeb1a78bfc9864f80ac08",
    "lilith_owner_memory/__init__.py": "d1f1bf65a24315005ca4b597971dec6efa0212d4ab5836832e2a5a80fb9e62b4",
    "lilith_owner_memory/contracts.py": "ff5075f1131f84348bdbc5d3fbd3410e53c7da39e265476a0b57ace6ff8ef5c7",
    "lilith_owner_memory/authority_contracts.py": "fabd8fd24f45febe83f8fd67c3fc39f277278e9145df9c55d5e03e5e8598e74f",
    "lilith_owner_memory/authority_verifier.py": "3c808267e56e9abc1ea1e848881cefd20a56fde51d9e803ac90f7f0c7517e83a",
    "lilith_owner_memory/recovery_contracts.py": "f4a14cff094d167a2a7925622031352955291c18244545e95c0003fb9231b95e",
    "lilith_owner_memory/rotation_contracts.py": "8f9df8dcd3e8a1b0cd8f03169bf7a51d4b6726cbb708cadfb3025586211996b0",
    "lilith_owner_memory/witness_readiness.py": "129d4479a7c86a6ef33acfb27da4f5cd6c6a6947b89184863a50117091fe3cbd",
}
# Read-only: import what the verifier imports, then hash the exact release files it loaded.
READINESS_PROBE = (
    "import hashlib,json,sys;R='/opt/lilith-authority-dev/current';sys.path.insert(0,R);"
    "import lilith_authority_host.inputs,lilith_authority_host.paths,lilith_authority_host.store_observer;"
    "import lilith_owner_memory.authority_contracts,lilith_owner_memory.authority_verifier;"
    "import lilith_owner_memory.rotation_contracts,lilith_owner_memory.recovery_contracts;"
    "import lilith_owner_memory.witness_readiness,rfc8785,cryptography;"
    "m={n:getattr(sys.modules[n],'__file__',None) for n in sorted(sys.modules) "
    "if n.split('.')[0] in ('lilith_authority_host','lilith_owner_memory','lilith_memory')};"
    "print(json.dumps({'interpreter':sys.executable,'release':R,'modules':{n:[f[len(R)+1:] if f and f.startswith(R+'/') "
    "else f,hashlib.sha256(open(f,'rb').read()).hexdigest() if f else None] for n,f in m.items()},"
    "'rfc8785':getattr(rfc8785,'__version__',None),'cryptography':cryptography.__version__},sort_keys=True))"
)
VERIFIER_PHASE = {"W0": "W0_PRE_INSTALL", "W3": "W3_ANCHORS_INSTALLED_REGISTRY_ABSENT",
                  "W5": "W5_INSTALLED_CONTENT_VERIFIED"}
INSTALLER_STAGE = {"W0": "P1B-2", "W3": "P1B-4", "W5": "P1B-5"}

# The binding lines of the go templates (package §7, §9). `{control}` is the control commit.
MB4_GO_LINES = (
    "I authorize M-B4 / install-anchors now for exactly one attempt within this current DEV_SYNTHETIC "
    "M-B4/M-B5 sequence.",
    "Continuity: MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO.",
    "Control commit: {control}.",
    f"Release: {RELEASE_SHA}.",
    f"Installer SHA-256: {TOOL_PINS[INSTALLER]}.",
    f"registry-root.json SHA-256: {DERIVED['registry-root.json']}.",
    f"witness-anchor.json SHA-256: {DERIVED['witness-anchor.json']}.",
    f"E-21 K-ROOT fingerprint: publicKeySha256={E21}.",
    f"K-WIT fingerprint: publicKeySha256={KWIT}.",
    "I acknowledge: M-B4 closes the K-WIT burn/regenerate option. That option does not reopen merely because "
    "installed files are later removed before M-B6.",
    "This go does not authorize M-B5, and M-B4 success does not mean TRUST_INSTALLED.",
    "Any REFUSED, FAILED, unexpected output, or other STOP consumes this go and ends the sequence. There is no retry.",
)
MB5_GO_LINES = (
    "I authorize M-B5 / install-registry now for exactly one attempt within this current DEV_SYNTHETIC "
    "M-B4/M-B5 sequence.",
    "Continuity: MB4_MB5_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_TWO_GO.",
    "Control commit: {control}.",
    f"Release: {RELEASE_SHA}.",
    f"Installer SHA-256: {TOOL_PINS[INSTALLER]}.",
    f"authority-registry.v1.json SHA-256: {DERIVED['authority-registry.v1.json']}.",
    f"Registry V1 digest: {REGISTRY_DIGEST}.",
    "M-B4 POST verifier phase: W3_ANCHORS_INSTALLED_REGISTRY_ABSENT, with anchorsEqualOwnerCopies and "
    "witnessAnchorNamesKWit true.",
    "The inter-stage continuity check K-1 … K-8 passed in this sequence after the M-B4 POST.",
    "This go does not accept TRUST_INSTALLED, and does not authorize M-B6, genesis, record 1, First Memory or PROD.",
    "Any REFUSED, FAILED, unexpected output, or other STOP consumes this go and ends the sequence. There is no retry.",
)
REMOVAL_LINES = (
    "I authorize the bounded M-B4/M-B5 removal before M-B6 for exactly one invocation.",
    "Plan digest: {plan}.",
    "I acknowledge: this removal does not reopen the K-WIT burn/regenerate option, and any consumed M-B4/M-B5 go "
    "stays consumed.",
)
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class Stop(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise Stop(code)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


DERIVATION_MODULE = "mb4_mb5_installable_inputs_operator"


def load_derivation(repo: Path):
    """Load the pinned derivation module from `<repo>`: a fresh module on every call, fail closed.

    The module is registered in `sys.modules` BEFORE `exec_module`: its
    dataclasses use postponed annotations, and `dataclasses` resolves them
    through `sys.modules[cls.__module__]` while the module executes (the
    `verify_mb3_registry._load` pattern). Any earlier entry under the name is
    replaced, never reused. On a load failure the half-executed module is
    removed again and the operator STOPs; nothing has been written yet."""
    path = Path(repo) / DERIVATION
    _need(sha256_hex(path.read_bytes()) == TOOL_PINS[DERIVATION], "TOOL_PIN_MISMATCH:" + DERIVATION)
    spec = importlib.util.spec_from_file_location(DERIVATION_MODULE, path)
    _need(spec is not None and spec.loader is not None, "DERIVATION_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[DERIVATION_MODULE] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        if sys.modules.get(DERIVATION_MODULE) is module:
            del sys.modules[DERIVATION_MODULE]
        raise Stop("DERIVATION_LOAD_FAILED") from exc
    return module


Runner = Callable[[Sequence[str]], "subprocess.CompletedProcess[bytes]"]


def _default_run(argv: Sequence[str]) -> "subprocess.CompletedProcess[bytes]":
    return subprocess.run(list(argv), stdin=subprocess.DEVNULL, capture_output=True, timeout=900, check=False)


def _gcloud_prefix() -> tuple[str, ...]:
    """The Cloud SDK argv prefix. On Windows set `LILITH_MB4_MB5_GCLOUD` to a JSON list such as
    `["<SDK>/platform/bundledpython/python.exe", "<SDK>/lib/gcloud.py"]` (the reviewed bundled-python recipe)."""
    value = os.environ.get("LILITH_MB4_MB5_GCLOUD")
    if not value:
        return ("gcloud",)
    parsed = json.loads(value)
    _need(isinstance(parsed, list) and bool(parsed) and all(isinstance(p, str) and p for p in parsed),
          "GCLOUD_PREFIX")
    return tuple(parsed)


@dataclass
class Operator:
    """`run` and `gcloud` are TEST seams; `gcloud` is the argv prefix that runs the Cloud SDK."""

    gcloud: tuple[str, ...] = field(default_factory=_gcloud_prefix)
    run: Runner = field(default=_default_run)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc))

    # ---------------------------------------------------------------- helpers ---

    def _git(self, repo: Path, *args: str) -> bytes:
        result = self.run(["git", "-C", str(repo), *args])
        _need(result.returncode == 0, "GIT_FAILED")
        return result.stdout

    def control(self, repo: Path) -> str:
        sha = self._git(repo, "rev-parse", "HEAD").decode("ascii").strip()
        _need(_SHA40.fullmatch(sha) is not None, "CONTROL_INVALID")
        return sha

    def tool_bytes(self, repo: Path, path: str) -> bytes:
        data = self._git(repo, "show", f"HEAD:{path}")
        _need(sha256_hex(data) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return data

    def ssh(self, command: str) -> "subprocess.CompletedProcess[bytes]":
        guarded = f'test "$(hostname)" = {DEV} || exit 97; {command}'
        return self.run([*self.gcloud, "compute", "ssh", DEV, f"--zone={ZONE}", f"--project={PROJECT}",
                         "--tunnel-through-iap", f"--command={guarded}"])

    def streamed(self, repo: Path, path: str, interpreter: str, args: str) -> str:
        """Hash-gated stream: the host re-hashes the decoded tool and runs it only on an exact pin match."""
        data = self.tool_bytes(repo, path)
        blob = base64.b64encode(gzip.compress(data, mtime=0)).decode("ascii")
        pin = TOOL_PINS[path]
        return (f"B={blob}; printf %s \"$B\" | base64 -d | gunzip | sha256sum | cut -c1-64 | grep -qx '{pin}' "
                f"|| exit 96; printf %s \"$B\" | base64 -d | gunzip | sudo -n {interpreter} -I -B - {args}")

    @staticmethod
    def _save(directory: Path, name: str, result: "subprocess.CompletedProcess[bytes]") -> int:
        (directory / f"{name}.out").write_bytes(result.stdout or b"")
        (directory / f"{name}.err").write_bytes(result.stderr or b"")
        (directory / f"{name}.rc").write_text(f"{result.returncode}\n", encoding="ascii")
        return result.returncode

    @staticmethod
    def _new_dir(path: Path) -> Path:
        _need(not path.exists() and not path.is_symlink(), "DIRECTORY_EXISTS:" + path.name)
        path.mkdir(mode=0o700, parents=False)
        return path

    # ------------------------------------------------------------ local forms ---

    def pins(self, repo: Path) -> dict:
        status = self._git(repo, "status", "--porcelain", "--untracked-files=no")
        _need(status.strip() == b"", "CONTROL_CHECKOUT_NOT_CLEAN")
        control = self.control(repo)
        for path in TOOL_PINS:
            self.tool_bytes(repo, path)
        return {"control": control, "tools": dict(TOOL_PINS), "result": "MB4_MB5_TOOL_PINS_EXACT"}

    def derive(self, repo: Path, export: Path, workdir: Path, derivation=None) -> dict:
        """Owner-held export -> the three pinned files. The export itself is never modified.

        Runs where the pinned wheels are (WSL); it needs no git. The two
        derivation sources must hash to their pins, and the output must equal
        the owner-accepted representation pins, which is the decisive check."""
        for path in (DERIVATION, "services/owner-memory-control/tools/mb3_registry_ceremony.py"):
            _need(sha256_hex((Path(repo) / path).read_bytes()) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        _need(sha256_hex(Path(export).read_bytes()) == EXPORT_SHA256, "EXPORT_SHA256_MISMATCH")
        if derivation is None:
            derivation = load_derivation(Path(repo))   # before any write: a load failure leaves no output
        sources = derivation.ACCEPTED_SOURCES
        before = sha256_hex(Path(export).read_bytes())
        first = derivation.derive_from_members(derivation.read_export(Path(export), sources), sources)
        second = derivation.derive_from_members(derivation.read_export(Path(export), sources), sources)
        _need(dict(first.files) == dict(second.files), "DERIVATION_NOT_DETERMINISTIC")
        derivation.check_pins(first, DERIVED)
        out = self._new_dir(Path(workdir) / "derived")
        derivation._write_outputs(out / "files", first)
        rehash = {name: sha256_hex((out / "files" / name).read_bytes()) for name in DERIVED}   # independent re-read
        _need(rehash == DERIVED, "STAGED_REHASH_MISMATCH")
        sums = "".join(f"{DERIVED[name]}  {name}\n" for name in DERIVED)
        (out / "files" / "SHA256SUMS").write_text(sums, encoding="ascii", newline="\n")
        _need(sha256_hex(Path(export).read_bytes()) == before == EXPORT_SHA256, "EXPORT_CHANGED")
        return {"derived": rehash, "exportSha256": before, "exportUnchanged": True, "result": "MB4_MB5_DERIVED_PINNED"}

    # --------------------------------------------------------- read-only remote ---

    def cloud(self, evidence: Path, since: str) -> dict:
        _need(_INSTANT.fullmatch(since) is not None, "SINCE_INVALID")
        out = self._new_dir(Path(evidence))
        queries = {
            "instance": ("compute", "instances", "describe", DEV, f"--zone={ZONE}"),
            "instances": ("compute", "instances", "list"),
            "disks": ("compute", "disks", "list"),
            "snapshots": ("compute", "snapshots", "list"),
            "instant-snapshots": ("compute", "instant-snapshots", "list"),
            "resource-policies": ("compute", "resource-policies", "list"),
            "machine-images": ("compute", "machine-images", "list"),
            "custom-images": ("compute", "images", "list", "--no-standard-images"),
            "project-iam": ("projects", "get-iam-policy", PROJECT),
            "instance-iam": ("compute", "instances", "get-iam-policy", DEV, f"--zone={ZONE}"),
            "disk-iam": ("compute", "disks", "get-iam-policy", DEV, f"--zone={ZONE}"),
        }
        codes = {}
        for name, query in queries.items():
            codes[name] = self._save(out, name, self.run([*self.gcloud, *query, f"--project={PROJECT}",
                                                          "--format=json"]))
        codes["buckets"] = self._save(out, "buckets", self.run([*self.gcloud, "storage", "buckets", "list",
                                                                f"--project={PROJECT}", "--format=value(name)"]))
        log = f'logName="projects/{PROJECT}/logs/cloudaudit.googleapis.com%2Factivity" AND timestamp>="{since}"'
        codes["audit"] = self._save(out, "audit", self.run([
            *self.gcloud, "logging", "read", log, f"--project={PROJECT}", "--freshness=400d",
            "--format=value(timestamp,protoPayload.authenticationInfo.principalEmail,protoPayload.serviceName,"
            "protoPayload.methodName,protoPayload.resourceName)"]))
        _need(all(code == 0 for code in codes.values()), "CLOUD_CAPTURE_FAILED")
        return {"captures": sorted(codes), "result": "MB4_MB5_CLOUD_CAPTURED", "compare": "byte-identical to the last "
                "accepted window, except the audit read (only iam.serviceAccounts.actAs entries allowed)"}

    def host(self, repo: Path, evidence: Path, phase: str) -> dict:
        _need(phase in VERIFIER_PHASE, "PHASE_INVALID")
        out = self._new_dir(Path(evidence))
        identity = ("date -u +%FT%TZ; hostname; cat /etc/machine-id; cat /proc/sys/kernel/random/boot_id; "
                    "uname -r; [ -e /var/run/reboot-required ] && echo REBOOT_REQUIRED=present "
                    "|| echo REBOOT_REQUIRED=absent")
        custody = (
            "sudo -n /usr/bin/ls -A1 /etc/credstore.encrypted; "
            "sudo -n /usr/bin/stat -c '%n %U:%G %a %s %d %i %Y %Z' "
            "/etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred; "
            "sudo -n /usr/bin/sha256sum /etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred; "
            "sudo -n /usr/bin/ls -A1 /etc/lilith-recovery-witness/credentials; "
            "sudo -n /usr/bin/stat -c '%n %U:%G %a %s %d %i %Y %Z' "
            "/etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred; "
            "sudo -n /usr/bin/sha256sum /etc/lilith-recovery-witness/credentials/lilith-recovery-witness.witness.cred; "
            f"sudo -n /usr/bin/sha256sum {KACT_PUBLICATION}; "
            "systemctl show -p Id,ActiveState,UnitFileState,MainPID,NRestarts,InvocationID lilith-memory-broker.service "
            "lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service "
            "lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket --no-pager; "
            "sudo -n /usr/local/sbin/lilith-activation-verify; echo activation_rc=$?; "
            "sudo -n /usr/bin/ls -A1 /etc/lilith-authority-dev/trust /etc/lilith-authority-dev/registry "
            "/etc/lilith-authority-dev/owner; "
            "for p in /var/lib/lilith-authority-dev /var/lib/lilith-recovery-witness; do "
            "if sudo -n test -e $p; then echo \"LATER_STATE $p PRESENT\"; else echo \"LATER_STATE $p ABSENT\"; fi; "
            "done")
        readiness = (f"readlink /opt/lilith-authority-dev/current; sudo -n test -x {RELEASE_PYTHON} "
                     f"&& echo RELEASE_PYTHON=executable; sudo -n {RELEASE_PYTHON} -I -B -c \"{READINESS_PROBE}\"")
        codes = {
            "identity": self._save(out, "identity", self.ssh(identity)),
            "custody": self._save(out, "custody", self.ssh(custody)),
            "readiness": self._save(out, "readiness", self.ssh(readiness)),
            "status": self._save(out, "status", self.ssh(self.streamed(
                repo, INSTALLER, SYSTEM_PYTHON, f"status --expect {INSTALLER_STAGE[phase]} {RELEASE_SHA}"))),
            "preservation": self._save(out, "preservation", self.ssh(self.streamed(
                repo, BROKER, SYSTEM_PYTHON, "preservation"))),
            "observer": self._save(out, "observer", self.ssh(self.streamed(repo, OBSERVER, SYSTEM_PYTHON, "observe"))),
            "verifier": self._save(out, "verifier", self.ssh(self.streamed(
                repo, VERIFIER, RELEASE_PYTHON, f"expect {VERIFIER_PHASE[phase]}"))),
        }
        readiness_ok = codes["readiness"] == 0 and self.readiness_ok((out / "readiness.out").read_bytes())
        result = "MB4_MB5_HOST_" + phase + ("_PASS" if all(c == 0 for c in codes.values()) and readiness_ok
                                            else "_NOT_PASS")
        return {"codes": codes, "readinessExact": readiness_ok, "result": result,
                "note": "PASS requires every code 0 and the owner's comparison of the recorded facts (package §4)"}

    @staticmethod
    def readiness_ok(raw: bytes) -> bool:
        lines = raw.decode("utf-8", "replace").splitlines()
        if len(lines) != 3 or lines[0] != f"releases/{RELEASE_SHA}" or lines[1] != "RELEASE_PYTHON=executable":
            return False
        try:
            probe = json.loads(lines[2])
        except ValueError:
            return False
        modules = {file: digest for file, digest in probe.get("modules", {}).values()}
        return modules == RELEASE_MODULES and probe.get("release") == "/opt/lilith-authority-dev/current"

    def denial(self, repo: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code = self._save(out, "denial", self.ssh(self.streamed(repo, DENIAL, SYSTEM_PYTHON, "P1B-5")))
        return {"code": code, "result": "MB4_MB5_DENIAL_P1B5_" + ("PASS" if code == 0 else "NOT_PASS")}

    def removal_plan(self, repo: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code = self._save(out, "removal-plan", self.ssh(self.streamed(repo, REMOVER, SYSTEM_PYTHON, "plan")))
        return {"code": code, "result": "MB4_MB5_REMOVAL_PLAN_RECORDED", "authorityGranted": False}

    # ------------------------------------------------------ operator-home forms ---

    def stage(self, workdir: Path) -> dict:
        files = Path(workdir) / "derived" / "files"
        for name in DERIVED:
            _need(sha256_hex((files / name).read_bytes()) == DERIVED[name], "LOCAL_STAGE_REHASH:" + name)
        created = self.ssh(f"test ! -e {STAGE_DIR} && mkdir -m 0700 {STAGE_DIR} && echo STAGE_CREATED")
        _need(created.returncode == 0 and created.stdout.strip() == b"STAGE_CREATED", "STAGE_DIRECTORY")
        copied = self.run([*self.gcloud, "compute", "scp", *[str(files / name) for name in STAGED],
                           f"{DEV}:{STAGE_DIR}/", f"--zone={ZONE}", f"--project={PROJECT}", "--tunnel-through-iap"])
        _need(copied.returncode == 0, "STAGE_COPY_FAILED")
        return self.staged_check()

    def staged_check(self) -> dict:
        listing = " ".join(sorted(STAGED))
        check = self.ssh(f"cd {STAGE_DIR} && test \"$(ls -A | LC_ALL=C sort | tr '\\n' ' ')\" = '{listing} ' "
                         f"&& test -z \"$(find . -mindepth 1 ! -type f)\" && sha256sum -c --strict SHA256SUMS")
        _need(check.returncode == 0, "STAGED_FILES_NOT_PINNED")
        return {"stage": STAGE_DIR, "files": dict(DERIVED), "result": "MB4_MB5_STAGED_FILES_PINNED_ON_HOST"}

    def cleanup(self, workdir: Path) -> dict:
        self.staged_check()
        names = " ".join(f"{STAGE_DIR}/{name}" for name in STAGED)
        done = self.ssh(f"rm -f {names} && rmdir {STAGE_DIR} && test ! -e {STAGE_DIR} && echo STAGE_DIR_ABSENT")
        _need(done.returncode == 0 and done.stdout.strip() == b"STAGE_DIR_ABSENT", "CLEANUP_FAILED")
        return {"result": "MB4_MB5_STAGE_CLEANED"}

    # -------------------------------------------------------------- mutations ---

    @staticmethod
    def check_go(text: str, lines: Sequence[str], **values: str) -> None:
        flat = " ".join(text.replace(">", " ").split())
        for line in lines:
            _need(" ".join(line.format(**values).split()) in flat, "GO_LINE_MISSING")

    def _one_attempt(self, workdir: Path, name: str, go: bytes) -> Path:
        directory = Path(workdir) / ATTEMPT_DIR
        directory.mkdir(mode=0o700, exist_ok=True)
        marker = directory / f"{name}.json"
        try:
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError as exc:
            raise Stop("ATTEMPT_ALREADY_CONSUMED:" + name) from exc
        try:
            os.write(fd, json.dumps({"attempt": name, "startedAt": self.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                                     "goSha256": sha256_hex(go), "invocationsPermitted": 1},
                                    sort_keys=True).encode("ascii") + b"\n")
            os.fsync(fd)
        finally:
            os.close(fd)
        return directory

    def mb4(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        control = self.pins(repo)["control"]
        raw = Path(go_file).read_bytes()
        self.check_go(raw.decode("utf-8"), MB4_GO_LINES, control=control)
        self.staged_check()
        directory = self._one_attempt(workdir, "mb4", raw)
        args = (f"install-anchors {RELEASE_SHA} {STAGE_DIR}/registry-root.json {STAGE_DIR}/witness-anchor.json")
        code = self._save(directory, "mb4-install-anchors", self.ssh(self.streamed(repo, INSTALLER, SYSTEM_PYTHON,
                                                                                    args)))
        return {"code": code, "attempt": "CONSUMED", "next": "M-B4 POST: host W3, then HARD STOP",
                "result": "MB4_INVOKED_ONCE" if code == 0 else "MB4_STOP"}

    def mb5(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        control = self.pins(repo)["control"]
        _need((Path(workdir) / ATTEMPT_DIR / "mb4.json").is_file(), "MB4_NOT_IN_THIS_SEQUENCE")
        raw = Path(go_file).read_bytes()
        self.check_go(raw.decode("utf-8"), MB5_GO_LINES, control=control)
        self.staged_check()
        directory = self._one_attempt(workdir, "mb5", raw)
        args = f"install-registry {RELEASE_SHA} {STAGE_DIR}/authority-registry.v1.json"
        code = self._save(directory, "mb5-install-registry", self.ssh(self.streamed(repo, INSTALLER, SYSTEM_PYTHON,
                                                                                     args)))
        return {"code": code, "attempt": "CONSUMED", "next": "M-B5 POST: host W5, then STOP for owner acceptance",
                "result": "MB5_INVOKED_ONCE" if code == 0 else "MB5_STOP"}

    def removal(self, repo: Path, workdir: Path, plan_digest: str, authorization: Path) -> dict:
        self.pins(repo)
        _need(_HEX64.fullmatch(plan_digest) is not None, "PLAN_DIGEST_INVALID")
        raw = Path(authorization).read_bytes()
        self.check_go(raw.decode("utf-8"), REMOVAL_LINES, plan=plan_digest)
        directory = self._one_attempt(workdir, "removal-" + plan_digest[:16], raw)
        code = self._save(directory, "removal", self.ssh(self.streamed(repo, REMOVER, SYSTEM_PYTHON,
                                                                        f"remove {plan_digest}")))
        return {"code": code, "result": "REMOVAL_INVOKED_ONCE" if code == 0 else "REMOVAL_STOP",
                "next": "host W0 and installer status --expect P1B-2"}


USAGE = __doc__.split("| Form |", 1)[1].split("\n\n", 1)[0]


def main(argv: list[str], operator: Operator | None = None) -> int:
    operator = operator or Operator()
    forms: dict[tuple[str, int], Callable[..., dict]] = {
        ("pins", 1): lambda a: operator.pins(Path(a[0])),
        ("derive", 3): lambda a: operator.derive(Path(a[0]), Path(a[1]), Path(a[2])),
        ("cloud", 2): lambda a: operator.cloud(Path(a[0]), a[1]),
        ("host", 3): lambda a: operator.host(Path(a[0]), Path(a[1]), a[2]),
        ("stage", 1): lambda a: operator.stage(Path(a[0])),
        ("mb4", 3): lambda a: operator.mb4(Path(a[0]), Path(a[1]), Path(a[2])),
        ("mb5", 3): lambda a: operator.mb5(Path(a[0]), Path(a[1]), Path(a[2])),
        ("denial", 2): lambda a: operator.denial(Path(a[0]), Path(a[1])),
        ("removal-plan", 2): lambda a: operator.removal_plan(Path(a[0]), Path(a[1])),
        ("removal", 4): lambda a: operator.removal(Path(a[0]), Path(a[1]), a[2], Path(a[3])),
        ("cleanup", 1): lambda a: operator.cleanup(Path(a[0])),
    }
    form = forms.get((argv[0], len(argv) - 1)) if argv else None
    if form is None:
        print("mb4_mb5_operator: USAGE" + USAGE, file=sys.stderr)
        return 2
    try:
        result = form(argv[1:])
    except Stop as stop:
        print(f"mb4_mb5_operator: STOP {stop.code}", file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
