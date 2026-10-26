"""The fixed root ceremony CLIs of the reviewed release (PR-1S, S-9, S-11).

Installed by the upgrade `cli` stage as `/usr/local/sbin/<name>` (`root:root
0755`); each is a thin wrapper that calls `main(<name>, argv)`. Closed argument
forms only; no path, environment, key, or JSON-to-write argument, except the
one closed owner input document the verifier and the release read. Every
command prints one JSON object on stdout; a refusal prints
`<name>: REFUSED <reason>` on stderr and exits 2.

| CLI | forms |
| --- | --- |
| `lilith-authority-ledger-dev` | `provision <registryVersion>`, `observe` (root); `provision-as-signer <registryVersion>` (signer uid, via runuser); `first-memory <remember\\|recall> <session>` (root; the First Memory bridge below) |
| `lilith-authority-hold-dev` | `observe`, `create-initial-held`, `release-initial <approvedPackageDigest> <inputs.json>`, `create-successor-held <ROTATION\\|KEY_COMPROMISE_RECOVERY> <N>`, `create-maintenance-held <authorizationId> <targetRegistryVersion>`, `create-custody-debt-held <N>`, `release-ceremony <ceremonyId> <approvedReadinessDigest> <successor-inputs.json>` |
| `lilith-authority-verify-dev` | `eligibility <inputs.json>`, `full <inputs.json>`, `genesis-candidate <registryVersion> <updatedAt>` |
| `lilith-recovery-witness-owner-dev` | `health`, `read`, `bootstrap <registryVersion> <updatedAt>`, `execute-head-advance <authorization.json> <targetRegistryVersion>`, `execute-epoch-advance <authorization.json> <targetRegistryVersion>` |
| `lilith-authority-recovery-dev` | `advance-epoch <authorization.json>`, `void-challenges`, `quarantine-uses` |

Nothing here starts, enables, or reloads a unit, and nothing here signs.

First Memory bridge (`first-memory`): the one root boundary between the unprivileged First Memory conversation host
and the root-only signer owner socket. Root code runs only from this root-owned release tree. It refuses unless the
fixed host tree (`FIRST_MEMORY_TREE`) is entirely root-owned and not group/other-writable, forks the host and drops
it PERMANENTLY to `lilith` (real, effective and saved uid/gid; no supplementary groups) before exec, and never imports
host code. Over one inherited socket pair it forwards only `ISSUE_OWNER_EVIDENCE` and the evidence-use operations;
it rejects any caller `holdStore` and adds the complete hold-store snapshot it reads itself. No listener, no path,
command or file argument, no other operation.
"""

from __future__ import annotations

import json
import os
import re
import socket
import stat
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from lilith_authority_dev import protocol as AP
from lilith_authority_host import inputs as HI
from lilith_authority_host import paths as P
from lilith_authority_host.store_observer import observe_witness_state, read_regular
from lilith_owner_memory import authority_ledger_journal as J
from lilith_owner_memory import successor_custody as SC
from lilith_owner_memory import successor_readiness as SR
from lilith_owner_memory import witness_readiness as WR
from lilith_recovery_witness import protocol as WP

from . import clients, genesis, ledger_tool, verifier
from .hold_store import HoldStoreError, HoldStoreV1

ENVIRONMENT = "dev"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
MAX_INPUT = 256 * 1024
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[1-9][0-9]{0,15}\Z")
_ORDINAL = re.compile(r"[1-9][0-9]{0,3}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_AUTHORIZATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_CEREMONY_ID = _AUTHORIZATION_ID


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _no_duplicates(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise Refused("INPUT_DUPLICATE_KEY")
        value[key] = item
    return value


def _document(path: str) -> Any:
    try:
        raw = read_regular(path, limit=MAX_INPUT)
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise Refused("INPUT_DOCUMENT_UNREADABLE") from exc


def _arg(pattern: re.Pattern[str], value: str, reason: str) -> str:
    if not isinstance(value, str) or not value.isascii() or pattern.fullmatch(value) is None:
        raise Refused(reason)
    return value


def _require_root(euid: int) -> None:
    if euid != 0:
        raise Refused("NOT_ROOT")


def _host_view() -> tuple[HI.HostInputsV1, WR.WitnessStoreObservationV1, WR.WitnessStoreContextV1]:
    inputs = HI.read_host_inputs(environment=ENVIRONMENT)
    if inputs.registry_root is None or inputs.witness_anchor is None:
        raise Refused("HOST_INPUTS_INCOMPLETE:" + ",".join(inputs.reasons))
    context = inputs.store_context(authority_public_keys=HI.authority_public_keys(inputs))
    return inputs, observe_witness_state(P.WITNESS_STATE), context


def _signer_ids() -> tuple[int, int]:
    import pwd

    entry = pwd.getpwnam(P.AUTHORITY_USER)
    return entry.pw_uid, entry.pw_gid


# ------------------------------------------------------------- commands ---

def _ledger(argv: list[str], euid: int) -> dict[str, Any]:
    if argv[:1] == ["provision-as-signer"] and len(argv) == 2:
        uid, _gid = _signer_ids()
        observed = ledger_tool.provision_as_signer(environment=ENVIRONMENT,
                                                   registry_version=int(_arg(_VERSION, argv[1], "VERSION_INVALID")),
                                                   euid=euid, signer_uid=uid)
        return {"ledgerSequence": observed.sequence, "ledgerHead": observed.head, "authorityGranted": False}
    _require_root(euid)
    if argv[:1] == ["first-memory"] and len(argv) == 3:
        return run_first_memory(argv[1], argv[2])
    if argv[:1] == ["provision"] and len(argv) == 2:
        version = int(_arg(_VERSION, argv[1], "VERSION_INVALID"))
        uid, gid = _signer_ids()

        def run_as_signer(registry_version: int) -> int:
            return subprocess.run(["/usr/sbin/runuser", "-u", P.AUTHORITY_USER, "--", P.LEDGER_CLI,
                                   "provision-as-signer", str(registry_version)], env=FIXED_ENV, check=False,
                                  timeout=120).returncode

        return ledger_tool.provision(environment=ENVIRONMENT, registry_version=version, euid=euid, signer_uid=uid,
                                     signer_gid=gid, run_as_signer=run_as_signer)
    if argv == ["observe"]:
        from lilith_authority_dev.ledger import observe_copy

        observed = observe_copy(P.AUTHORITY_LEDGER, environment=ENVIRONMENT)
        return {"ledgerSequence": observed.sequence, "ledgerHead": observed.head,
                "registryView": observed.registry_view, "rowsConsistent": observed.rows_consistent,
                "terminalReopened": observed.terminal_reopened, "authorityGranted": False}
    raise Refused("USAGE")


def _verify_run(mode: str, path: str, hold=None) -> Any:
    owner = verifier.parse_verifier_inputs(_document(path))
    return verifier.evaluate(mode, owner, health=clients.signer_health, hold=hold)


def _hold(argv: list[str], euid: int) -> dict[str, Any]:
    _require_root(euid)
    store = HoldStoreV1(environment=ENVIRONMENT)
    if argv == ["observe"]:
        observed = store.observe()
        return {"listingDigest": observed.listing_digest, "snapshot": dict(observed.snapshot),
                "authorityGranted": False}
    inputs, witness_store, context = _host_view()
    if argv == ["create-initial-held"]:
        return {"record": store.create_initial_held(witness_store=witness_store, context=context)}
    if argv[:1] == ["release-initial"] and len(argv) == 3:
        approved = _arg(_DIGEST, argv[1], "APPROVED_DIGEST_INVALID")
        record = store.release_initial(
            approved_package_digest=approved,
            rerun=lambda held: _verify_run(SR.HOLD_RELEASE_ELIGIBILITY, argv[2], hold=held),
            witness_store=witness_store, context=context)
        return {"record": record}
    if argv[:1] == ["create-successor-held"] and len(argv) == 3:
        if argv[1] not in (SC.ROTATION, SC.KEY_COMPROMISE_RECOVERY):
            raise Refused("KIND_INVALID")
        return {"record": store.create_successor_held(kind=argv[1],
                                                      ordinal=int(_arg(_ORDINAL, argv[2], "ORDINAL_INVALID")),
                                                      witness_store=witness_store, context=context,
                                                      registries=inputs.registries)}
    if argv[:1] == ["create-maintenance-held"] and len(argv) == 3:
        version = int(_arg(_VERSION, argv[2], "VERSION_INVALID"))
        target = next((r for r in inputs.registries if r.get("registryVersion") == version), None)
        if target is None:
            raise Refused("REGISTRY_NOT_INSTALLED")
        return {"record": store.create_maintenance_held(
            authorization_id=_arg(_AUTHORIZATION_ID, argv[1], "AUTHORIZATION_ID_INVALID"), target_registry=target,
            witness_store=witness_store, context=context, registries=inputs.registries)}
    if argv[:1] == ["create-custody-debt-held"] and len(argv) == 2:
        return {"record": store.create_custody_debt_held(ordinal=int(_arg(_ORDINAL, argv[1], "ORDINAL_INVALID")),
                                                         witness_store=witness_store, context=context)}
    if argv[:1] == ["release-ceremony"] and len(argv) == 4:
        ceremony = _arg(_CEREMONY_ID, argv[1], "CEREMONY_ID_INVALID")
        approved = _arg(_DIGEST, argv[2], "APPROVED_DIGEST_INVALID")
        document = _document(argv[3])
        record = store.release_with_readiness(
            ceremony_id=ceremony, approved_readiness_digest=approved,
            rerun=lambda held: verifier.successor_readiness(document, hold=held, health=clients.signer_health),
            witness_store=witness_store, context=context)
        return {"record": record}
    raise Refused("USAGE")


def _verify(argv: list[str], euid: int) -> dict[str, Any]:
    _require_root(euid)
    if argv[:1] in (["eligibility"], ["full"]) and len(argv) == 2:
        mode = SR.HOLD_RELEASE_ELIGIBILITY if argv[0] == "eligibility" else SR.FULL_READINESS
        return verifier.report(_verify_run(mode, argv[1]))
    if argv[:1] == ["genesis-candidate"] and len(argv) == 3:
        built, _inputs, _ledger = genesis.candidate(environment=ENVIRONMENT,
                                                    registry_version=int(_arg(_VERSION, argv[1], "VERSION_INVALID")),
                                                    updated_at=_arg(_INSTANT, argv[2], "UPDATED_AT_INVALID"))
        return genesis.candidate_report(built)
    raise Refused("USAGE")


def _witness(argv: list[str], euid: int) -> dict[str, Any]:
    _require_root(euid)
    if argv == ["health"]:
        return dict(clients.witness_owner(WP.HEALTH, {}))
    if argv == ["read"]:
        return dict(clients.witness_owner(WP.READ_WITNESS, {}))
    if argv[:1] == ["bootstrap"] and len(argv) == 3:
        return genesis.bootstrap(environment=ENVIRONMENT,
                                 registry_version=int(_arg(_VERSION, argv[1], "VERSION_INVALID")),
                                 updated_at=_arg(_INSTANT, argv[2], "UPDATED_AT_INVALID"),
                                 witness_owner=clients.witness_owner)
    if argv[:1] in (["execute-head-advance"], ["execute-epoch-advance"]) and len(argv) == 3:
        authorization = _document(argv[1])
        version = int(_arg(_VERSION, argv[2], "VERSION_INVALID"))
        snapshot = dict(HoldStoreV1(environment=ENVIRONMENT).observe().snapshot)
        if argv[0] == "execute-head-advance":
            return dict(clients.witness_owner(WP.EXECUTE_REGISTRY_HEAD_ADVANCE, {
                "authorization": authorization, "targetRegistryVersion": version, "holdStore": snapshot}))
        from lilith_authority_dev.ledger import journal_copy, observe_copy

        observed = observe_copy(P.AUTHORITY_LEDGER, environment=ENVIRONMENT)
        journal = journal_copy(P.AUTHORITY_LEDGER, environment=ENVIRONMENT)
        adoption = journal[-1] if journal else None
        if not isinstance(adoption, dict) or adoption.get("op") != J.ADVANCE_EPOCH:
            raise Refused("ADOPTION_NOT_JOURNALLED")
        return dict(clients.witness_owner(WP.EXECUTE_EPOCH_ADVANCE, {
            "authorization": authorization, "targetRegistryVersion": version, "adoptionRecord": adoption,
            "ledgerSequence": observed.sequence, "ledgerHead": observed.head, "holdStore": snapshot}))
    raise Refused("USAGE")


# ---------------------------------------------------------------- First Memory bridge ---

FIRST_MEMORY_TREE = "/opt/lilith-first-memory-dev/current"
FIRST_MEMORY_ENTRY = FIRST_MEMORY_TREE + "/services/owner-memory-control/tools/first_memory_dev_host.py"
FIRST_MEMORY_PYTHON = P.CURRENT_RELEASE + "/venv/bin/python"
FIRST_MEMORY_USER = "lilith"
FIRST_MEMORY_FORMS = ("remember", "recall")
BRIDGE_FD = 3
BRIDGE_MAX_REQUESTS = 64
BRIDGE_OPERATIONS = frozenset({AP.ISSUE_OWNER_EVIDENCE}) | AP.USE_OPERATIONS
_SESSION = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")
BRIDGE_REFUSAL = {"status": "REFUSED", "reason": "BRIDGE_REQUEST_INVALID", "authorityGranted": False}


def bridge_request(raw: bytes, *, hold_snapshot: Callable[[], dict[str, Any]],
                   exchange: Callable[[bytes], dict[str, Any]]) -> dict[str, Any]:
    """One host request -> one signer frame, or a refusal. The caller names an allowed operation and its owner
    artifacts only; the hold snapshot is always root's own read."""
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
        if not isinstance(value, dict) or set(value) != {"operation", "payload"}:
            raise Refused("BRIDGE_REQUEST_INVALID")
        operation, payload = value["operation"], value["payload"]
        if operation not in BRIDGE_OPERATIONS or not isinstance(payload, dict) or "holdStore" in payload:
            raise Refused("BRIDGE_REQUEST_INVALID")
        if operation != AP.LOOKUP_EVIDENCE_USE:
            payload = {**payload, "holdStore": dict(hold_snapshot())}
        if operation == AP.ISSUE_OWNER_EVIDENCE and set(payload) != AP.GOVERNED_ISSUE_FIELDS:
            raise Refused("BRIDGE_REQUEST_INVALID")
        frame = AP.encode_frame(operation, payload)       # the signer's own strict parser, before anything is sent
    except (Refused, AP.ProtocolError, UnicodeDecodeError, ValueError, TypeError):
        return dict(BRIDGE_REFUSAL)
    return dict(exchange(frame))


def _recv_exact(conn: socket.socket, size: int) -> bytes | None:
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def serve_bridge(conn: socket.socket, *, hold_snapshot: Callable[[], dict[str, Any]],
                 exchange: Callable[[bytes], dict[str, Any]], max_requests: int = BRIDGE_MAX_REQUESTS) -> int:
    """Serve length-prefixed JSON requests until EOF; a malformed frame ends the bridge. Returns requests served."""
    served = 0
    while served < max_requests:
        header = _recv_exact(conn, 4)
        if header is None:
            break
        length = struct.unpack(">I", header)[0]
        if not 0 < length <= AP.MAX_FRAME_BYTES:
            break
        raw = _recv_exact(conn, length)
        if raw is None:
            break
        try:
            response = bridge_request(raw, hold_snapshot=hold_snapshot, exchange=exchange)
        except (OSError, ValueError) as exc:
            response = {"status": "REFUSED", "reason": "SIGNER_UNREACHABLE:" + type(exc).__name__,
                        "authorityGranted": False}
        body = json.dumps(response, sort_keys=True, separators=(",", ":")).encode("utf-8")
        conn.sendall(struct.pack(">I", len(body)) + body)
        served += 1
    return served


def trusted_tree_failures(tree: str, *, owner_uid: int = 0) -> list[str]:
    """Every path that would let a non-root principal change code run for root's bridge: the tree and its parents
    must be root-owned, never group/other-writable, never a symlink."""
    failures: list[str] = []
    root = Path(tree)

    def check(path: Path) -> None:
        try:
            meta = os.lstat(path)
        except OSError:
            failures.append("MISSING:" + str(path))
            return
        if stat.S_ISLNK(meta.st_mode) or meta.st_uid != owner_uid or meta.st_mode & 0o022:
            failures.append("UNTRUSTED:" + str(path))

    for parent in reversed(root.parents):
        check(parent)
    check(root)
    if root.is_dir() and not root.is_symlink():
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            for name in dirnames + filenames:
                check(Path(dirpath) / name)
    return failures


def drop_privileges(user: str) -> tuple[int, int]:
    """Permanently become `user`: no supplementary groups, real = effective = saved uid/gid. Verified, then proven
    irreversible (regaining uid 0 must fail)."""
    import pwd

    entry = pwd.getpwnam(user)
    uid, gid = entry.pw_uid, entry.pw_gid
    if uid == 0 or gid == 0:
        raise Refused("FIRST_MEMORY_USER_IS_ROOT")
    os.setgroups([])
    os.setresgid(gid, gid, gid)
    os.setresuid(uid, uid, uid)
    if os.getresuid() != (uid, uid, uid) or os.getresgid() != (gid, gid, gid) or os.getgroups():
        raise Refused("PRIVILEGE_DROP_INCOMPLETE")
    try:
        os.setuid(0)
    except PermissionError:
        return uid, gid
    raise Refused("PRIVILEGE_DROP_REVERSIBLE")


def run_first_memory(form: str, session: str, *, tree: str = FIRST_MEMORY_TREE, entry: str = FIRST_MEMORY_ENTRY,
                     python: str = FIRST_MEMORY_PYTHON, user: str = FIRST_MEMORY_USER,
                     hold_snapshot: Callable[[], dict[str, Any]] | None = None,
                     exchange: Callable[[bytes], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Fork the host as `user` (permanently) and serve its bridge. Keyword arguments are TEST seams; the CLI passes
    none."""
    if form not in FIRST_MEMORY_FORMS:
        raise Refused("USAGE")
    _arg(_SESSION, session, "SESSION_INVALID")
    failures = trusted_tree_failures(tree)
    if failures or not Path(entry).is_relative_to(tree):
        raise Refused("FIRST_MEMORY_HOST_UNTRUSTED:" + ",".join(failures[:4]))
    if hold_snapshot is None:
        hold_snapshot = lambda: dict(HoldStoreV1(environment=ENVIRONMENT).observe().snapshot)  # noqa: E731
    if exchange is None:
        exchange = lambda frame: clients._authority_response(  # noqa: E731
            clients._exchange(P.AUTHORITY_OWNER_SOCKET, frame, limit=AP.MAX_FRAME_BYTES))
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    pid = os.fork()
    if pid == 0:                                                   # child: never returns into root code
        try:
            parent.close()
            os.dup2(child.fileno(), BRIDGE_FD, inheritable=True)
            os.chdir("/")
            drop_privileges(user)
            os.execve(python, [python, "-I", "-B", entry, form, session], dict(FIXED_ENV))
        except BaseException:
            pass
        os._exit(127)
    child.close()
    try:
        served = serve_bridge(parent, hold_snapshot=hold_snapshot, exchange=exchange)
    finally:
        parent.close()
    _pid, status = os.waitpid(pid, 0)
    return {"hostExit": os.waitstatus_to_exitcode(status), "bridgeRequests": served, "authorityGranted": False}


def _recovery(argv: list[str], euid: int) -> dict[str, Any]:
    _require_root(euid)
    snapshot = dict(HoldStoreV1(environment=ENVIRONMENT).observe().snapshot)
    if argv[:1] == ["advance-epoch"] and len(argv) == 2:
        return dict(clients.signer_recovery(AP.RECOVERY_ADVANCE_EPOCH, hold_snapshot=snapshot,
                                            epoch_authorization=_document(argv[1])))
    if argv == ["void-challenges"]:
        return dict(clients.signer_recovery(AP.RECOVERY_VOID_CHALLENGE, hold_snapshot=snapshot))
    if argv == ["quarantine-uses"]:
        return dict(clients.signer_recovery(AP.RECOVERY_QUARANTINE_USE, hold_snapshot=snapshot))
    raise Refused("USAGE")


COMMANDS: dict[str, Callable[[list[str], int], dict[str, Any]]] = {
    "lilith-authority-ledger-dev": _ledger,
    "lilith-authority-hold-dev": _hold,
    "lilith-authority-verify-dev": _verify,
    "lilith-recovery-witness-owner-dev": _witness,
    "lilith-authority-recovery-dev": _recovery,
}


def main(name: str, argv: list[str], *, euid: int | None = None) -> int:
    handler = COMMANDS.get(name)
    if handler is None:
        print(f"{name}: REFUSED UNKNOWN_CLI", file=sys.stderr)
        return 2
    try:
        result = handler(list(argv), os.geteuid() if euid is None else euid)
    except Refused as exc:
        print(f"{name}: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except (HoldStoreError, ledger_tool.LedgerToolError, genesis.GenesisToolError) as exc:
        print(f"{name}: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except (verifier.VerifierInputError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"{name}: REFUSED {type(exc).__name__}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0
