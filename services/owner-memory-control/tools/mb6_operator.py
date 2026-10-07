"""15B2b-B1b-3e M-B6 PROVISION_LEDGER: the reviewed owner-laptop operator.

Record: docs/architecture/slice-15b2b-b1b3e-mb6-ledger-remediation.md §7.
SOURCE PREPARED / NOT AUTHORIZED: no form below is authorized by this
repository; each live use needs its own explicit owner authorization. The
go template binds the owner-ACCEPTED continuity (record §8, decision R-1):
`MB6_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_GO`.

Every form is closed: no free path, command or principal argument reaches
DEV. Forms:

| Form | Effect |
| --- | --- |
| `pins <repo>` | local, read-only: clean checkout; control = `HEAD`; every pinned tool hashes to its pin |
| `expected <repo> <authority-registry.v1.json> <registry-root.json> <workdir>` | local: the owner-computed expected ledger head (computed twice), written once to a NEW `<workdir>/expected` |
| `cloud <evidence-dir> <since>` | read-only GCP: the 11 JSON captures + bucket list + Admin Activity since `<since>` |
| `host <repo> <workdir> <evidence-dir> <PRE\\|POST>` | read-only DEV: identity, custody, release readiness (38 modules incl. the `provision` CLI path, and the CLI wrapper), installer `status` (P1B-5 / P1B-6), broker preservation, observer, W5 verifier, M-B6 verifier |
| `denial <repo> <evidence-dir>` | read-only DEV: the root denial proof, existing phase `P1B-5` (unchanged tool) |
| `ledger-denial <repo> <evidence-dir>` | read-only DEV: the separate M-B6 ledger denial proof, phase `P1B-6` (after a verified `LEDGER_COMMITTED_EXACT`) |
| `mb6 <repo> <workdir> <go-file>` | **mutation, one attempt**: a read-only pre-state check, the `O_EXCL` marker, then exactly ONE `lilith-authority-ledger-dev provision 1` |
| `post <repo> <workdir>` | read-only DEV: the `host POST` reads into `<workdir>/post`, the W6 sequence class; on W6-5 + all PASS, the `POST_VERIFIED` record (W6-6). Never continues to M-B7 |
| `classify <repo> <workdir> <evidence-dir>` | read-only DEV: the M-B6 verifier and installer `status`, combined with this sequence's records into one W6 phase |
| `recovery-plan <repo> <workdir> <evidence-dir>` | read-only DEV: the bounded recovery plan and its digest |
| `recovery <repo> <workdir> <plan-evidence-dir> <authorization-file>` | **mutation**: the bounded recovery of exactly that plan (needs a separate owner authorization) |

A go file is the owner's verbatim go statement; the tool refuses unless it
contains every binding line of the template with the exact values, and it
writes the local one-attempt marker (`O_EXCL`) BEFORE the remote
invocation. A marker that exists is a STOP. A refusal before the marker
consumes nothing. Whatever happens after the marker (exit 0, REFUSED,
traceback, ssh failure, timeout) the attempt is consumed: there is no
automatic retry and no second invocation path. A partial
outcome is classified by `post` / `classify`, and only `recovery` (a
separate authorization, a reviewed plan digest) may act on it.

    tool / pin / marker / go-file check != authorization
    one go = exactly one `provision 1`; no retry; M-B6 POST != M-B7

It never opens, loads, decrypts or copies K-ROOT, K-WIT or K-ACT, never runs
a keygen, `systemd-creds`, a unit start/stop/reload/enable, the signer or
the witness, and never runs a genesis, pin, owner-input, hold or witness
form.
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
RELEASE_SHA = "aee323e94412accbe321bc84eae78c5b8cf95afc"
RELEASE_PYTHON = "/opt/lilith-authority-dev/current/venv/bin/python"
SYSTEM_PYTHON = "/usr/bin/python3"
LEDGER_CLI = "/usr/local/sbin/lilith-authority-ledger-dev"
PROVISION = f"sudo -n {LEDGER_CLI} provision 1"       # the ONE M-B6 mutation command
KACT_PUBLICATION = "/root/b1b3d-l2b-publication.json"
ATTEMPT_DIR = "attempts"
MB6_ATTEMPT = "mb6"

TOOL_PINS = {
    "services/authority-dev/ceremony/install_authority_dev.py":
        "fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487",
    "services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py":
        "78f57c01811e20a03ebb06bc114847bad440c7435e85ceb0249a488c659b2361",
    "services/owner-memory-control/tools/mb6_ledger_verifier.py": "6449d6ac88313da177665ab9ae7ee9beb86a3a03a22e2a02c2aecf99a79767b5",
    "services/owner-memory-control/tools/mb6_ledger_recovery.py": "8c2db24970a1e97f19e98574d712459ccfbe185ea669755235dc0b24ba71c612",
    "services/owner-memory-control/tools/mb6_expected_ledger_head.py": "5ecaaaaeba57c8a1afe0d76d0fa0ecaa4ef6bff35d291dc84e0fe7a205a019c8",
    "services/authority-dev/ceremony/observe_authority_dev_host.py":
        "a2f21b45e57a153f099c79a734ab05a575ac5c50f7cbc0527e562e94dd6908bf",
    "scripts/verify_broker_dev_current_incarnation.py":
        "2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba",
    "scripts/authority_custody_denial_proof.py":
        "f4e39c81c24a01be5702f6a65a581fcd08f97e1c5ad4a07326883b605fef1455",
    "services/owner-memory-control/tools/mb6_ledger_denial_proof.py": "470cb27231a0acc3cc5e0ffedb691c1e0a72c313ae80205aa928cff248b9f3c0",
    "services/owner-memory-control/tools/mb6_dr5_target.py": "9978e3a791a829d6beace81ca0e4c6db9b1c154fbc56091f6312385d02632656",
}
INSTALLER = "services/authority-dev/ceremony/install_authority_dev.py"
W5_VERIFIER = "services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py"
VERIFIER = "services/owner-memory-control/tools/mb6_ledger_verifier.py"
RECOVERY = "services/owner-memory-control/tools/mb6_ledger_recovery.py"
EXPECTED = "services/owner-memory-control/tools/mb6_expected_ledger_head.py"
OBSERVER = "services/authority-dev/ceremony/observe_authority_dev_host.py"
BROKER = "scripts/verify_broker_dev_current_incarnation.py"
DENIAL = "scripts/authority_custody_denial_proof.py"
LEDGER_DENIAL = "services/owner-memory-control/tools/mb6_ledger_denial_proof.py"
DR5_TARGET = "services/owner-memory-control/tools/mb6_dr5_target.py"
OPERATOR = "services/owner-memory-control/tools/mb6_operator.py"

REGISTRY_DIGEST = "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc"

# The release modules the M-B6 bundle imports, and their aee323e SHA-256 (unchanged at control).
RELEASE_MODULES = {
    "lilith_authority_dev/__init__.py": "e2810f0aed810c0ca1bdc7a14d60b7394cb892fb8220aeb01a59df598660206b",
    "lilith_authority_dev/ledger.py": "2853f2d73f8db1173207fd034d9d40cc317472bf429e85b1638e45c16d542f1a",
    "lilith_authority_dev/profile.py": "cf291af50ff5738ff7fdc3acc50eaf95dfb4c3c7128589b8f1927fb32652710a",
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
    "lilith_owner_memory/authority_ledger_journal.py":
        "f0d554c53948723c80f5cfbfd638d60855e92ddb562137370d12f9c7eeec49ce",
    "lilith_owner_memory/authority_verifier.py": "3c808267e56e9abc1ea1e848881cefd20a56fde51d9e803ac90f7f0c7517e83a",
    "lilith_owner_memory/recovery_contracts.py": "f4a14cff094d167a2a7925622031352955291c18244545e95c0003fb9231b95e",
    "lilith_owner_memory/rotation_contracts.py": "8f9df8dcd3e8a1b0cd8f03169bf7a51d4b6726cbb708cadfb3025586211996b0",
    "lilith_owner_memory/witness_readiness.py": "129d4479a7c86a6ef33acfb27da4f5cd6c6a6947b89184863a50117091fe3cbd",
}
# The further release modules the ONE mutation command loads: `lilith-authority-ledger-dev` imports
# `lilith_authority_root.cli`, and that import loads exactly these (ceremony package §2.2). aee323e SHA-256,
# unchanged at control. The readiness probe imports the CLI module (definitions only; `main` is not called).
PROVISION_MODULES = {
    "lilith_authority_dev/protocol.py": "4cd1154b4d36b4ff29083e597b77a50ecfd653bc1cc4519fb7dcc6b09353a25a",
    "lilith_authority_root/__init__.py": "b17f2c9dd955128b5028225c5444301548fd3e86fdcacb28d38c053dc5d0a33d",
    "lilith_authority_root/cli.py": "7175577c0bdbf52b7ad6fd56d8e5818a144d955c386ac452b768b4e5000cf10a",
    "lilith_authority_root/clients.py": "f6840254b0ef4abc7150077ab58612e8652472fac9caa71e778eecde3e4c328f",
    "lilith_authority_root/genesis.py": "fa2affd9017f275f62b6b2d9aa8eb8e17d9558d389188f09f0d778f8e4489823",
    "lilith_authority_root/hold_store.py": "8e62b92dd85f84df2b5e0c289260a81a0a20bb52e142e421e359c2b39e5d46ce",
    "lilith_authority_root/ledger_tool.py": "86b21c233012a1d03ca252b1d9a92b0cc0d60c5bc59296be55943e45e75c6fcd",
    "lilith_authority_root/observers.py": "5447eb67b96b5bb93f750fa6a71e63f246266e8d9bbaf6bd3ce9cdab34a349ed",
    "lilith_authority_root/verifier.py": "b60bf348f0e8fec9c76fc2ee2f9cde28e3033f8227acacd294ab51995740ba80",
    "lilith_owner_memory/pr1_acceptance.py": "e0928854e1fcf4107458939ba9ebf1903cf7a4d0ab6808f7e89108db1444bbff",
    "lilith_owner_memory/pr1_bootstrap.py": "9a09a4726bb473067e84e7664dca49d51b90ced1e012564526bae07656d3d5fd",
    "lilith_owner_memory/successor_custody.py": "29e99a7b179d58dd4f8e9cd576ed544f207145f25f89c92e97ca0e6efa65cb72",
    "lilith_owner_memory/successor_readiness.py": "842176d06954607aed39d8988764fc253fa8bd4c41ca49fcd5e2a4532c5ecc16",
    "lilith_recovery_witness/__init__.py": "8c7a3dc1d15115616323a9ee652afde6b4a5f14afc2371dfd92ff3f845b6b3e1",
    "lilith_recovery_witness/core.py": "e4dcbc4bf0bae588fb1486e28ce37047faeb2755c46383ee04ed9ce9c9d5a3fd",
    "lilith_recovery_witness/credential.py": "7a394b561df072f5ec5ed933ab04deca450cfd84bf23f3fcf166b0c068916c18",
    "lilith_recovery_witness/profile.py": "7c28c05f82d399cf460bfd47b35d03985f71d8b1b423c7f6ff12f2e1874bea1d",
    "lilith_recovery_witness/protocol.py": "1b3f54c5a6c9298e5da08be6a8453b11e25002e396af2453f58f9ac07ed5f2e5",
    "lilith_recovery_witness/storage.py": "26ff45042fd90edc80c62402d39b68e2251b0725ee6579633ee2cee54f2b7898",
    "lilith_recovery_witness/writer.py": "ea9b619b4c867a2519f83a2c6c341a8e15d105ad5198dc38ec0609b1ae69bdca",
}
# The installed fixed wrapper `/usr/local/sbin/lilith-authority-ledger-dev` (release member
# `cli/lilith-authority-ledger-dev` = `services/authority-dev/bin/lilith-authority-ledger-dev`).
LEDGER_CLI_SHA256 = "fda779cd0dcecdc26e371082078306978f97e4f7097acae780fa6f38180fc45b"
READINESS_PROBE = (
    "import hashlib,json,sys;R='/opt/lilith-authority-dev/current';sys.path.insert(0,R);"
    "import lilith_authority_host.inputs,lilith_authority_host.paths,lilith_authority_host.store_observer;"
    "import lilith_authority_dev.ledger,lilith_owner_memory.authority_ledger_journal;"
    "import lilith_owner_memory.authority_contracts,lilith_owner_memory.authority_verifier;"
    "import lilith_owner_memory.rotation_contracts,lilith_owner_memory.recovery_contracts;"
    "import lilith_owner_memory.witness_readiness,lilith_authority_root.cli,rfc8785,cryptography,sqlite3;"
    "m={n:getattr(sys.modules[n],'__file__',None) for n in sorted(sys.modules) "
    "if n.split('.')[0] in ('lilith_authority_host','lilith_owner_memory','lilith_memory','lilith_authority_dev',"
    "'lilith_authority_root','lilith_recovery_witness')};"
    "print(json.dumps({'interpreter':sys.executable,'release':R,'modules':{n:[f[len(R)+1:] if f and f.startswith(R+'/') "
    "else f,hashlib.sha256(open(f,'rb').read()).hexdigest() if f else None] for n,f in m.items()},"
    f"'ledgerCli':hashlib.sha256(open('{LEDGER_CLI}','rb').read()).hexdigest(),"
    "'deserialize':hasattr(sqlite3.Connection,'deserialize'),'sqlite':sqlite3.sqlite_version,"
    "'rfc8785':getattr(rfc8785,'__version__',None),'cryptography':cryptography.__version__},sort_keys=True))"
)

# The in-memory bundle loader. It reads a gzip'd JSON {module: source} from stdin, refuses (exit 96)
# unless every module's SHA-256 equals the pin passed in argv[1] (`name=sha,...`), registers each in
# `sys.modules` BEFORE executing it, and runs `main(argv[3:])` of the module named in argv[2]. It
# writes nothing: no temporary file holds a tool.
BOOT = """import gzip,hashlib,json,sys,types
b=json.loads(gzip.decompress(sys.stdin.buffer.read()).decode('utf-8'))
p=dict(x.split('=',1) for x in sys.argv[1].split(','))
if sorted(b)!=sorted(p) or any(hashlib.sha256(s.encode('utf-8')).hexdigest()!=p[n] for n,s in b.items()):
    sys.exit(96)
sys.path.insert(0,'/opt/lilith-authority-dev/current')
for n,s in b.items():
    m=types.ModuleType(n);m.__file__='<mb6-bundle:'+n+'>';sys.modules[n]=m
    exec(compile(s,'<mb6-bundle:'+n+'>','exec'),m.__dict__)
sys.exit(sys.modules[sys.argv[2]].main(sys.argv[3:]))
"""
VERIFIER_BUNDLE = (W5_VERIFIER, VERIFIER)
RECOVERY_BUNDLE = (W5_VERIFIER, VERIFIER, RECOVERY)

INSTALLER_STAGE = {"PRE": "P1B-5", "POST": "P1B-6"}
W5_PHASE = {"PRE": "W5_INSTALLED_CONTENT_VERIFIED", "POST": "OUT_OF_SCOPE_POST_LEDGER"}
MB6_PHASE = {"PRE": "W6_0_NO_MB6_MUTATION", "POST": "LEDGER_COMMITTED_EXACT"}
PRE_STATES = {"W6_0_NO_MB6_MUTATION": "CREATED", "W6_2_STATE_DIRECTORY_EXACT_EMPTY": "ADOPTED_NO_MUTATION"}

# The binding lines of the M-B6 go template for the owner-ACCEPTED continuity (record §8, decision R-1;
# ceremony package §8). `{control}`, `{operator}`, `{head}`, `{pre}` are bound; the tool pins are static.
MB6_GO_LINES = (
    "I authorize M-B6 / PROVISION_LEDGER now for exactly one attempt within this current DEV_SYNTHETIC M-B6 "
    "sequence.",
    "Continuity: MB6_CONTINUITY = OWNER_ATTENDED_EVENT_BOUNDED_SINGLE_SEQUENCE_ONE_GO.",
    "The deploy freeze holds from the start of this live preparation sequence through technical POST and owner "
    "acceptance or sequence termination.",
    "Control commit: {control}.",
    "Operator: " + OPERATOR + " SHA-256 {operator}.",
    "Verifier: " + VERIFIER + " SHA-256 " + TOOL_PINS[VERIFIER] + ".",
    "Recovery: " + RECOVERY + " SHA-256 " + TOOL_PINS[RECOVERY] + ".",
    "Ledger denial proof: " + LEDGER_DENIAL + " SHA-256 " + TOOL_PINS[LEDGER_DENIAL] + ".",
    f"Release: {RELEASE_SHA}.",
    f"Command: {LEDGER_CLI} provision 1, exactly one invocation.",
    "Pre-state: {pre}.",
    "Owner-computed expected ledger head: {head} (ledger sequence 1).",
    f"Registry V1 digest: {REGISTRY_DIGEST}.",
    "OWNER_REGISTER = KNOWN_EMPTY was freshly established in this sequence from Replica A and Replica B.",
    "AUTHORIZATION_REGISTER_COPY_MISSING and GENESIS_PIN_COPY_MISSING remain; M-B6 does not install either copy.",
    "This go does not accept LEDGER_PROVISIONED, and does not authorize M-B7, M-B8, genesis, record 1, First "
    "Memory or PROD.",
    "Any REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output, or other STOP after the attempt marker "
    "consumes this go and ends the sequence. There is no automatic retry.",
    "A partial state enters only the reviewed W6 classifier and the separately authorized recovery or adoption path.",
)
RECOVERY_LINES = (
    "I authorize the bounded M-B6 ledger recovery for exactly one invocation.",
    "Plan digest: {plan}.",
    "Classified host phase: {phase}. Action: {action}.",
    "I acknowledge: this recovery is not a retry of M-B6; a new M-B6 attempt needs a new owner go and a fresh "
    "re-proof.",
    "I acknowledge: it changes no trust, registry, owner-freshness, witness, hold or later state, and reopens no "
    "burn or point-of-no-return decision.",
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


def load_tool(repo: Path, path: str, name: str):
    """Load a pinned tool from `<repo>`: hash-gated, registered in `sys.modules` before execution."""
    source = Path(repo) / path
    _need(sha256_hex(source.read_bytes()) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
    spec = importlib.util.spec_from_file_location(name, source)
    _need(spec is not None and spec.loader is not None, "TOOL_LOAD_FAILED:" + path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        if sys.modules.get(name) is module:
            del sys.modules[name]
        raise Stop("TOOL_LOAD_FAILED:" + path) from exc
    return module


Runner = Callable[[Sequence[str]], "subprocess.CompletedProcess[bytes]"]


def _default_run(argv: Sequence[str]) -> "subprocess.CompletedProcess[bytes]":
    return subprocess.run(list(argv), stdin=subprocess.DEVNULL, capture_output=True, timeout=900, check=False)


def _gcloud_prefix() -> tuple[str, ...]:
    """The Cloud SDK argv prefix. On Windows set `LILITH_MB6_GCLOUD` to a JSON list (the bundled-python recipe)."""
    value = os.environ.get("LILITH_MB6_GCLOUD")
    if not value:
        return ("gcloud",)
    parsed = json.loads(value)
    _need(isinstance(parsed, list) and bool(parsed) and all(isinstance(p, str) and p for p in parsed),
          "GCLOUD_PREFIX")
    return tuple(parsed)


@dataclass
class Operator:
    """`run`, `gcloud` and `now` are TEST seams."""

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
        """Hash-gated single-file stream (the M-B4/M-B5 pattern)."""
        data = self.tool_bytes(repo, path)
        blob = base64.b64encode(gzip.compress(data, mtime=0)).decode("ascii")
        return (f"B={blob}; printf %s \"$B\" | base64 -d | gunzip | sha256sum | cut -c1-64 | grep -qx "
                f"'{TOOL_PINS[path]}' || exit 96; printf %s \"$B\" | base64 -d | gunzip | sudo -n {interpreter} "
                f"-I -B - {args}")

    def bundled(self, repo: Path, paths: Sequence[str], args: str) -> str:
        """Hash-gated in-memory bundle under the release interpreter; the last module is the entry point."""
        sources = {Path(path).stem: self.tool_bytes(repo, path).decode("utf-8") for path in paths}
        blob = base64.b64encode(gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0)).decode("ascii")
        pins = ",".join(f"{Path(path).stem}={TOOL_PINS[path]}" for path in paths)
        boot = base64.b64encode(BOOT.encode("ascii")).decode("ascii")
        loader = f"import base64;exec(base64.b64decode('{boot}'))"
        return (f"B={blob}; printf %s \"$B\" | base64 -d | sudo -n {RELEASE_PYTHON} -I -B -c \"{loader}\" "
                f"{pins} {Path(paths[-1]).stem} {args}")

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

    @staticmethod
    def expected_head(workdir: Path) -> str:
        path = Path(workdir) / "expected" / "expected-ledger.json"
        _need(path.is_file(), "EXPECTED_HEAD_ABSENT")
        value = json.loads(path.read_text(encoding="utf-8"))
        head = value.get("ledgerHead")
        _need(value.get("derivation") == "OWNER_COMPUTED_FROM_REGISTRY_V1" and value.get("ledgerSequence") == 1
              and isinstance(head, str) and _HEX64.fullmatch(head) is not None
              and head == value.get("independentLedgerHead") == value.get("pinDerivedLedgerHead"),
              "EXPECTED_HEAD_INVALID")
        return head

    # ------------------------------------------------------------ local forms ---

    def pins(self, repo: Path) -> dict:
        status = self._git(repo, "status", "--porcelain", "--untracked-files=no")
        _need(status.strip() == b"", "CONTROL_CHECKOUT_NOT_CLEAN")
        control = self.control(repo)
        for path in TOOL_PINS:
            self.tool_bytes(repo, path)
        return {"control": control, "tools": dict(TOOL_PINS), "result": "MB6_TOOL_PINS_EXACT"}

    def expected(self, repo: Path, registry: Path, root_anchor: Path, workdir: Path, tool=None) -> dict:
        """Owner workstation: the expected position from the owner's own files (needs the pinned wheels)."""
        tool = tool or load_tool(Path(repo), EXPECTED, "mb6_expected_ledger_head_operator")
        first = tool.derive(Path(registry).read_bytes(), Path(root_anchor).read_bytes())
        second = tool.derive(Path(registry).read_bytes(), Path(root_anchor).read_bytes())
        _need(first == second, "EXPECTED_NOT_DETERMINISTIC")
        out = self._new_dir(Path(workdir) / "expected")
        (out / "expected-ledger.json").write_text(json.dumps(first, sort_keys=True, indent=2) + "\n",
                                                  encoding="utf-8", newline="\n")
        _need(self.expected_head(workdir) == first["ledgerHead"], "EXPECTED_REREAD_MISMATCH")
        return {"ledgerSequence": 1, "ledgerHead": first["ledgerHead"], "accepted": False,
                "result": "MB6_EXPECTED_HEAD_COMPUTED_FOR_OWNER_DECISION"}

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
        codes = {name: self._save(out, name, self.run([*self.gcloud, *query, f"--project={PROJECT}",
                                                         "--format=json"])) for name, query in queries.items()}
        codes["buckets"] = self._save(out, "buckets", self.run([*self.gcloud, "storage", "buckets", "list",
                                                                f"--project={PROJECT}", "--format=value(name)"]))
        log = f'logName="projects/{PROJECT}/logs/cloudaudit.googleapis.com%2Factivity" AND timestamp>="{since}"'
        codes["audit"] = self._save(out, "audit", self.run([
            *self.gcloud, "logging", "read", log, f"--project={PROJECT}", "--freshness=400d",
            "--format=value(timestamp,protoPayload.authenticationInfo.principalEmail,protoPayload.serviceName,"
            "protoPayload.methodName,protoPayload.resourceName)"]))
        _need(all(code == 0 for code in codes.values()), "CLOUD_CAPTURE_FAILED")
        return {"captures": sorted(codes), "result": "MB6_CLOUD_CAPTURED"}

    def _host_reads(self, repo: Path, out: Path, phase: str, head: str) -> dict[str, int]:
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
            "/etc/lilith-authority-dev/owner /var/lib/lilith-authority-custody/holds; "
            "for p in /var/lib/lilith-authority-dev /var/lib/lilith-recovery-witness; do "
            "if sudo -n test -e $p; then echo \"STATE $p PRESENT\"; else echo \"STATE $p ABSENT\"; fi; done")
        readiness = (f"readlink /opt/lilith-authority-dev/current; sudo -n test -x {RELEASE_PYTHON} "
                     f"&& echo RELEASE_PYTHON=executable; sudo -n {RELEASE_PYTHON} -I -B -c \"{READINESS_PROBE}\"")
        return {
            "identity": self._save(out, "identity", self.ssh(identity)),
            "custody": self._save(out, "custody", self.ssh(custody)),
            "readiness": self._save(out, "readiness", self.ssh(readiness)),
            "status": self._save(out, "status", self.ssh(self.streamed(
                repo, INSTALLER, SYSTEM_PYTHON, f"status --expect {INSTALLER_STAGE[phase]} {RELEASE_SHA}"))),
            "preservation": self._save(out, "preservation", self.ssh(self.streamed(
                repo, BROKER, SYSTEM_PYTHON, "preservation"))),
            "observer": self._save(out, "observer", self.ssh(self.streamed(repo, OBSERVER, SYSTEM_PYTHON, "observe"))),
            "w5verifier": self._save(out, "w5verifier", self.ssh(self.streamed(
                repo, W5_VERIFIER, RELEASE_PYTHON, f"expect {W5_PHASE[phase]}"))),
            "mb6verifier": self._save(out, "mb6verifier", self.ssh(self.bundled(
                repo, VERIFIER_BUNDLE, f"expect {MB6_PHASE[phase]} {head}"))),
        }

    def host(self, repo: Path, workdir: Path, evidence: Path, phase: str) -> dict:
        _need(phase in INSTALLER_STAGE, "PHASE_INVALID")
        head = self.expected_head(workdir)
        out = self._new_dir(Path(evidence))
        codes = self._host_reads(repo, out, phase, head)
        readiness_ok = codes["readiness"] == 0 and self.readiness_ok((out / "readiness.out").read_bytes())
        result = "MB6_HOST_" + phase + ("_PASS" if all(c == 0 for c in codes.values()) and readiness_ok
                                        else "_NOT_PASS")
        return {"codes": codes, "readinessExact": readiness_ok, "result": result,
                "note": "PASS requires every code 0 and the owner's comparison of the recorded facts"}

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
        return (modules == {**RELEASE_MODULES, **PROVISION_MODULES} and probe.get("ledgerCli") == LEDGER_CLI_SHA256
                and probe.get("release") == "/opt/lilith-authority-dev/current" and probe.get("deserialize") is True)

    def denial(self, repo: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code = self._save(out, "denial", self.ssh(self.streamed(repo, DENIAL, SYSTEM_PYTHON, "P1B-5")))
        return {"code": code, "result": "MB6_DENIAL_P1B5_" + ("PASS" if code == 0 else "NOT_PASS")}

    def ledger_denial(self, repo: Path, evidence: Path) -> dict:
        out = self._new_dir(Path(evidence))
        code = self._save(out, "ledger-denial", self.ssh(self.streamed(repo, LEDGER_DENIAL, SYSTEM_PYTHON, "P1B-6")))
        return {"code": code, "transcriptSha256": sha256_hex((out / "ledger-denial.out").read_bytes()),
                "result": "MB6_LEDGER_DENIAL_P1B6_" + ("PASS" if code == 0 else "NOT_PASS")}

    # -------------------------------------------------------------- mutation ---

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

    def _verifier(self, repo: Path, phase_args: str) -> tuple[int, dict | None, "subprocess.CompletedProcess[bytes]"]:
        result = self.ssh(self.bundled(repo, VERIFIER_BUNDLE, phase_args))
        try:
            report = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            report = None
        return result.returncode, report, result

    def mb6(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        control = self.pins(repo)["control"]
        head = self.expected_head(workdir)
        raw = Path(go_file).read_bytes()
        text = raw.decode("utf-8")
        pre = next((state for state in PRE_STATES if f"Pre-state: {state}." in " ".join(text.split())), None)
        _need(pre is not None, "GO_PRE_STATE_MISSING")
        operator = sha256_hex(self._git(repo, "show", f"HEAD:{OPERATOR}"))
        _need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")
        self.check_go(text, MB6_GO_LINES, control=control, operator=operator, head=head, pre=pre)
        _need(not (Path(workdir) / ATTEMPT_DIR / f"{MB6_ATTEMPT}.json").exists(), "ATTEMPT_ALREADY_CONSUMED:mb6")
        verifier = load_tool(Path(repo), VERIFIER, "mb6_ledger_verifier_operator_classify")   # before any write
        code, report, _ = self._verifier(repo, f"expect {pre} {head}")      # read-only, before the marker
        _need(code == 0 and isinstance(report, dict) and report.get("phase") == pre, "PRE_STATE_NOT_AS_GO")
        directory = self._one_attempt(workdir, MB6_ATTEMPT, raw)
        (directory / "mb6-pre-state.json").write_text(json.dumps({"preState": pre, "expectedLedgerHead": head,
                                                                  "control": control}, sort_keys=True) + "\n",
                                                      encoding="ascii", newline="\n")
        try:
            result = self.ssh(PROVISION)                                    # the ONE mutation
        except subprocess.TimeoutExpired as exc:
            result = subprocess.CompletedProcess(exc.cmd, None, exc.output or b"", exc.stderr or b"")
        except OSError as exc:
            result = subprocess.CompletedProcess([], None, b"", f"LOCAL_{type(exc).__name__}".encode("ascii"))
        self._save(directory, "mb6-provision", result)
        transcript, detail = verifier.classify_transcript(result.returncode, result.stdout or b"", result.stderr or b"",
                                                          expected_head=head, state_directory=PRE_STATES[pre])
        (directory / "mb6-transcript.json").write_text(json.dumps({"class": transcript, "detail": detail},
                                                                  sort_keys=True) + "\n", encoding="ascii", newline="\n")
        return {"code": result.returncode, "attempt": "CONSUMED", "transcript": transcript, "detail": detail,
                "next": "M-B6 POST (`post`), then HARD STOP for owner review; never M-B7",
                "result": "MB6_INVOKED_ONCE" if transcript == verifier.CLI_SUCCESS_EXACT else "MB6_STOP"}

    # ------------------------------------------------------- classification ---

    def _records(self, workdir: Path) -> tuple[bool, str, bool]:
        directory = Path(workdir) / ATTEMPT_DIR
        consumed = (directory / f"{MB6_ATTEMPT}.json").is_file()
        transcript = "NOT_INVOKED"
        if (directory / "mb6-transcript.json").is_file():
            transcript = json.loads((directory / "mb6-transcript.json").read_text(encoding="ascii"))["class"]
        elif consumed:
            transcript = "CLI_FAILED_UNCLASSIFIED"     # marker without a recorded transcript: the laptop died
        post = Path(workdir) / "post" / "POST_VERIFIED.json"
        return consumed, transcript, post.is_file()

    def classify(self, repo: Path, workdir: Path, evidence: Path) -> dict:
        head = self.expected_head(workdir)
        out = self._new_dir(Path(evidence))
        code, report, result = self._verifier(repo, f"observe {head}")
        self._save(out, "mb6verifier", result)
        _need(code == 0 and isinstance(report, dict), "VERIFIER_FAILED")
        verifier = load_tool(Path(repo), VERIFIER, "mb6_ledger_verifier_operator_classify")
        consumed, transcript, post = self._records(workdir)
        phase = verifier.classify_sequence(host_phase=report["phase"], ledger_clean=report["ledgerClean"],
                                           attempt_consumed=consumed, transcript=transcript, post_verified=post)
        return {"hostPhase": report["phase"], "sequencePhase": phase, "attemptConsumed": consumed,
                "transcript": transcript, "postVerified": post, "result": "MB6_CLASSIFIED"}

    def post(self, repo: Path, workdir: Path) -> dict:
        head = self.expected_head(workdir)
        consumed, transcript, post = self._records(workdir)
        _need(consumed, "MB6_NOT_IN_THIS_SEQUENCE")
        _need(not post, "POST_ALREADY_VERIFIED")
        out = self._new_dir(Path(workdir) / "post")
        codes = self._host_reads(repo, out, "POST", head)
        readiness_ok = codes["readiness"] == 0 and self.readiness_ok((out / "readiness.out").read_bytes())
        try:
            report = json.loads((out / "mb6verifier.out").read_bytes().decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            report = {"phase": "UNCLASSIFIED_STOP", "ledgerClean": False, "evidence": {}}
        verifier = load_tool(Path(repo), VERIFIER, "mb6_ledger_verifier_operator_classify")
        phase = verifier.classify_sequence(host_phase=report.get("phase", "UNCLASSIFIED_STOP"),
                                           ledger_clean=report.get("ledgerClean") is True, attempt_consumed=True,
                                           transcript=transcript, post_verified=False)
        evidence = report.get("evidence", {})
        verified = (phase == verifier.W6_5 and all(c == 0 for c in codes.values()) and readiness_ok
                    and all(evidence.get(name) is True for name in verifier.EVIDENCE)
                    and report.get("registryEffective") is False and report.get("authorityGranted") is False)
        if verified:
            fd = os.open(out / "POST_VERIFIED.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.write(fd, json.dumps({"expectedLedgerHead": head, "evidence": evidence,
                                         "phase": verifier.W6_6, "ownerAccepted": False}, sort_keys=True)
                         .encode("ascii") + b"\n")
                os.fsync(fd)
            finally:
                os.close(fd)
        return {"codes": codes, "readinessExact": readiness_ok, "sequencePhase": verifier.W6_6 if verified else phase,
                "evidence": evidence, "result": "MB6_POST_VERIFIED" if verified else "MB6_POST_NOT_VERIFIED",
                "next": "HARD STOP: owner acceptance of LEDGER_PROVISIONED (separate); M-B7 is not authorized"
                if verified else "STOP: owner review; `recovery-plan` only under a separate authorization"}

    # -------------------------------------------------------------- recovery ---

    def recovery_plan(self, repo: Path, workdir: Path, evidence: Path) -> dict:
        head = self.expected_head(workdir)
        out = self._new_dir(Path(evidence))
        result = self.ssh(self.bundled(repo, RECOVERY_BUNDLE, f"plan {head}"))
        code = self._save(out, "recovery-plan", result)
        return {"code": code, "result": "MB6_RECOVERY_PLAN_RECORDED" if code == 0 else "MB6_RECOVERY_PLAN_REFUSED",
                "authorityGranted": False}

    def recovery(self, repo: Path, workdir: Path, plan_evidence: Path, authorization: Path) -> dict:
        self.pins(repo)
        head = self.expected_head(workdir)
        plan = json.loads((Path(plan_evidence) / "recovery-plan.out").read_text(encoding="utf-8"))
        digest, phase, action = plan.get("planDigest"), plan.get("phase"), plan.get("action")
        _need(isinstance(digest, str) and _HEX64.fullmatch(digest) is not None and plan.get("mutating") is True
              and plan.get("expectedLedgerHead") == head, "PLAN_NOT_ACTIONABLE")
        raw = Path(authorization).read_bytes()
        self.check_go(raw.decode("utf-8"), RECOVERY_LINES, plan=digest, phase=phase, action=action)
        directory = self._one_attempt(workdir, "recovery-" + digest[:16], raw)
        code = self._save(directory, "recovery", self.ssh(self.bundled(repo, RECOVERY_BUNDLE,
                                                                        f"recover {head} {digest}")))
        return {"code": code, "result": "MB6_RECOVERY_INVOKED_ONCE" if code == 0 else "MB6_RECOVERY_STOP",
                "next": "classify; a new M-B6 attempt needs a new owner go and a fresh re-proof"}


USAGE = __doc__.split("| Form |", 1)[1].split("\n\n", 1)[0]


def main(argv: list[str], operator: Operator | None = None) -> int:
    operator = operator or Operator()
    forms: dict[tuple[str, int], Callable[..., dict]] = {
        ("pins", 1): lambda a: operator.pins(Path(a[0])),
        ("expected", 4): lambda a: operator.expected(Path(a[0]), Path(a[1]), Path(a[2]), Path(a[3])),
        ("cloud", 2): lambda a: operator.cloud(Path(a[0]), a[1]),
        ("host", 4): lambda a: operator.host(Path(a[0]), Path(a[1]), Path(a[2]), a[3]),
        ("denial", 2): lambda a: operator.denial(Path(a[0]), Path(a[1])),
        ("ledger-denial", 2): lambda a: operator.ledger_denial(Path(a[0]), Path(a[1])),
        ("mb6", 3): lambda a: operator.mb6(Path(a[0]), Path(a[1]), Path(a[2])),
        ("post", 2): lambda a: operator.post(Path(a[0]), Path(a[1])),
        ("classify", 3): lambda a: operator.classify(Path(a[0]), Path(a[1]), Path(a[2])),
        ("recovery-plan", 3): lambda a: operator.recovery_plan(Path(a[0]), Path(a[1]), Path(a[2])),
        ("recovery", 4): lambda a: operator.recovery(Path(a[0]), Path(a[1]), Path(a[2]), Path(a[3])),
    }
    form = forms.get((argv[0], len(argv) - 1)) if argv else None
    if form is None:
        print("mb6_operator: USAGE" + USAGE, file=sys.stderr)
        return 2
    try:
        result = form(argv[1:])
    except Stop as stop:
        print(f"mb6_operator: STOP {stop.code}", file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(dict(result, authorityGranted=False), sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
