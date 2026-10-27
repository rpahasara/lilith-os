#!/usr/bin/env python3
"""F9-C: the privileged HERMES_DEV_CONVERSATION erasure executor (root oneshot, path-activated; DEV_SYNTHETIC only).

Trigger: hermes-forget.path sees a request in the spool (/run/hermes-forget/spool/*.req, written by the Core API's
spool client). A request is only {v, owner, authorizationRefId, executionNonce}; it is never authorization by itself.
For each request the executor:

  P0 VALIDATE  parses the request strictly; independently re-validates the Privacy authorization READ-ONLY with the
               hash-pinned Core API modules (owner listed, exact nonce, HMAC, hold ACTIVE, First Interaction scope,
               required-owner floor); verifies the single-principal precondition (lilith_os only, one user, known
               schema) BEFORE anything is changed; writes the durable in-progress marker that keeps the gateway from
               starting (its drop-in ConditionPathExists=!marker).
  P1 STOP      the unit's Conflicts= has stopped the gateway; verifies inactive, no gateway process, port closed.
  P2 SQLITE    whole-store purge of state.db by direct SQL over an allowlisted schema (no Hermes code runs as root),
               FTS rebuild, secure_delete, WAL checkpoint(TRUNCATE), VACUUM; verified counts/integrity/freelist/WAL.
  P3 FILES     empties HERMES_HOME conversation/runtime/log paths without following symlinks; protected files
               (SOUL.md, config, .env, router, plugins, memories, ...) must hash-match the P0 snapshot.
  P4 JOURNAL   rotates and vacuums ONLY the hermes-gateway-dev journald namespace; no entry older than P4 may remain.
  P5 BACKUPS   writes a content-free tombstone first, then removes conversation-bearing artefacts from
               /var/backups/hermes-gateway-dev (HERMES_HOME copies, state.db*, namespace journal copies, tar members).
  P6 EPOCH     appends a monotonic erasure epoch to the root-only append-only epoch log (restore guard input).
  P7 RECEIPT   writes the content-free receipt (Slice 2 contract) atomically WHILE THE GATEWAY STAYS BLOCKED.
  P8 RELEASE   only when Privacy itself shows this authorization COMPLETED with Hermes COMPLETE (immutable,
               HMAC-bound completion rows; read-only) is the journal released and, once no journal is unreleased,
               the marker removed. A bounded in-run wait covers the normal path; ``--reconcile`` (timer, never
               destructive) covers crashes and late completion. An undelivered or lost receipt never unblocks.

Every phase is idempotent and recorded in a per-authorization journal (fsync'd); a crash or reboot resumes. Any
failure leaves the Privacy hold ACTIVE (no receipt), the marker in place (gateway stays stopped) and the request
renamed *.failed (no trigger loop); the Core API adapter's retry submits again and the executor resumes. A request
whose authorization does not verify gets NO receipt (a forged request cannot poison a real authorization's receipt).
Claims: LOGICAL_ERASURE_VERIFIED only; provider erasure ATTESTED_ZDR_NOT_VERIFIED. Never physical destruction.

Hold-first (F9-C Track A). ``--hold`` (hermes-forget-hold.path, when the Core API records the durable FORGET intent in
the sticky intent directory) validates the intent and takes ownership of it (root:<reader group> 0640: the Core API can
no longer remove it); its unit's Conflicts= has stopped the gateway, whose drop-in refuses to start while any intent
exists. The reconcile pass removes the intent only when Privacy proves the First Interaction FORGET COMPLETED with the
Hermes owner (``identity_forget_completed``: HMAC-verified receipt, no ACTIVE hold) and no journal is unreleased.
``--cancel-intent --confirm-owner-approved`` (operator, root) removes it only while no authorization is in flight.

Relationship origin (owner-provided canonical memory): a second closed intent, ``relationship-origin.intent`` with the
label RELATIONSHIP_ORIGIN, is held the same way. Its release needs Privacy's proof that the origin FORGET COMPLETED with
L18_V2 (Hermes is an owner of it only where the Privacy floor provisions that). Each intent name admits exactly its own
label; any other name stays in place, unheld and blocking. The executor's erasure scope is unchanged.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import importlib
import json
import os
import re
import socket
import sqlite3
import stat
import subprocess
import sys
import tarfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

CONFIG_PATH = Path("/etc/hermes-forget/executor.json")
OWNER = "HERMES_DEV_CONVERSATION"
DEV_SYNTHETIC = "DEV_SYNTHETIC"
REQUEST_FIELDS = frozenset({"v", "owner", "authorizationRefId", "executionNonce"})
REF_RE = re.compile(r"^erase\.[0-9a-f]{32}$")
NONCE_RE = re.compile(r"^execution\.[0-9a-f]{32}$")
MAX_REQUEST_BYTES = 1024
SCOPE = "WHOLE_STORE_SINGLE_PRINCIPAL"
CLAIM = "LOGICAL_ERASURE_VERIFIED"
PROVIDER_ERASURE = "ATTESTED_ZDR_NOT_VERIFIED"
PHASES = ("VALIDATE", "STOP", "SQLITE", "FILES", "JOURNAL", "BACKUPS", "EPOCH")
CHECKS = ("single_principal", "sessions_zero", "messages_zero", "fts_zero", "wal_truncated", "integrity_ok",
          "files_purged", "journal_vacuumed", "backups_conversation_free", "protected_files_unchanged")
CORE_API_MODULES = ("__init__.py", "canonical_contracts.py", "memory_action_v2.py", "canonical_authority.py",
                    "privacy_governance.py")

# Hermes state.db: every table must be known. PURGE = conversation content or linkage; KEEP = schema bookkeeping.
# delivery_obligations: outbound reply text, created lazily in state.db by gateway/delivery_ledger.py (found by the
# Track A drill on the real gateway: the executor refused it as UNKNOWN_HERMES_SCHEMA, fail closed).
PURGE_ORDER = ("messages", "session_model_usage", "async_delegations", "compression_locks", "session_turn_leases",
               "gateway_hygiene_state", "gateway_routing", "telegram_dm_topic_bindings", "telegram_dm_topic_mode",
               "delivery_obligations", "sessions", "system_prompts")
KEEP_TABLES = frozenset({"schema_version", "state_meta", "sqlite_sequence", "sqlite_stat1", "sqlite_stat4"})
FTS_TABLES = ("messages_fts", "messages_fts_trigram", "messages_fts_cjk")
FTS_SHADOW_SUFFIXES = ("_data", "_idx", "_docsize", "_config", "_content")

# HERMES_HOME paths emptied (directory kept) / removed. Everything else (code, config, SOUL.md, memories, .env,
# router, plugins, skills, cron/jobs.json) is kept and must be byte-identical afterwards.
PURGE_DIRS = ("logs", "sessions", "pending_messages", "runtime", "state", "gateway", "cache", "audio_cache",
              "image_cache")
PURGE_FILES = ("channel_directory.json", "gateway_state.json", "cron/executions.db", "cron/executions.db-wal",
               "cron/executions.db-shm", "cron/executions.db-journal", "state.db-journal")
PROTECTED = ("SOUL.md", "config.yaml", ".env", "lilith_router", "plugins", "memories", "skills", "cron/jobs.json",
             "router.yaml")
STATE_DB_FILES = ("state.db", "state.db-wal", "state.db-shm", "state.db-journal")
HOME_ROOT_NAMES = (".hermes-dev", "hermes-dev")
ALLOWED_ENV_KEYS = frozenset({"LILITH_OS_PORT", "LILITH_OS_TOKEN"})
JOURNAL_DIR_SUFFIX = ".hermes-gateway-dev"
INTENT_DIR = Path("/var/lib/hermes-forget/intent")
INTENT_NAME = "first-interaction.intent"
# Closed: intent file name -> (label, memory_action_v2 identity attribute, the owner whose COMPLETE releases it).
INTENT_IDENTITIES = {
    INTENT_NAME: ("FIRST_INTERACTION", "FIRST_INTERACTION_IDENTITY", "HERMES_DEV_CONVERSATION"),
    "relationship-origin.intent": ("RELATIONSHIP_ORIGIN", "RELATIONSHIP_ORIGIN_IDENTITY", "L18_V2"),
}
INTENT_FIELDS = frozenset({"v", "identity", "intentRefId", "actorRefId", "recordedAt"})
INTENT_REF_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
MAX_INTENT_BYTES = 1024


class ExecutorError(RuntimeError):
    """Stable, content-free failure code. ``precondition`` marks a refusal before anything was changed."""

    def __init__(self, code: str, *, precondition: bool = False):
        super().__init__(code)
        self.code = code
        self.precondition = precondition


def _require(condition: bool, code: str, *, precondition: bool = False) -> None:
    if not condition:
        raise ExecutorError(code, precondition=precondition)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write(path: Path, data: bytes, *, mode: int = 0o600, gid: Optional[int] = None) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.write(fd, data)
        os.fsync(fd)
        if gid is not None:
            os.fchown(fd, 0, gid)
        os.fchmod(fd, mode)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def receipt_digest(receipt: Mapping[str, Any]) -> str:
    """Identical to the Core API adapter's ``hermes_erasure_owner.receipt_digest``."""
    body = {k: v for k, v in receipt.items() if k != "receiptDigest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                          .encode("ascii")).hexdigest()


# ------------------------------------------------------------------------------------------------ configuration ---

@dataclass(frozen=True)
class Config:
    deployment_environment: str
    hermes_home: Path
    spool_dir: Path
    state_dir: Path
    receipt_dir: Path
    receipt_gid: int
    epoch_log: Path
    marker: Path
    backup_root: Path
    journal_namespace: str
    journal_dir: Path
    gateway_unit: str
    gateway_ports: Tuple[int, ...]
    requester_uid: int
    privacy_db: Path
    privacy_secret: Path
    core_api_dir: Path
    core_api_sha256: Mapping[str, str]
    release_wait_seconds: float = 120.0
    intent_dir: Path = INTENT_DIR

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        st = os.lstat(path)
        _require(stat.S_ISREG(st.st_mode) and st.st_uid == 0 and not st.st_mode & 0o022, "CONFIG_UNTRUSTED")
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        pins = raw["coreApiSha256"]
        _require(isinstance(pins, dict) and set(pins) == set(CORE_API_MODULES)
                 and all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) for v in pins.values()),
                 "CONFIG_PINS_INVALID")
        cfg = cls(
            deployment_environment=str(raw["deploymentEnvironment"]), hermes_home=Path(raw["hermesHome"]),
            spool_dir=Path(raw["spoolDir"]), state_dir=Path(raw["stateDir"]), receipt_dir=Path(raw["receiptDir"]),
            receipt_gid=int(raw["receiptGid"]), epoch_log=Path(raw["epochLog"]), marker=Path(raw["inProgressMarker"]),
            backup_root=Path(raw["backupRoot"]),
            journal_namespace=str(raw["journalNamespace"]), journal_dir=Path(raw["journalDir"]),
            gateway_unit=str(raw["gatewayUnit"]), gateway_ports=tuple(int(p) for p in raw["gatewayPorts"]),
            requester_uid=int(raw["requesterUid"]), privacy_db=Path(raw["privacyDb"]),
            privacy_secret=Path(raw["privacySecret"]), core_api_dir=Path(raw["coreApiDir"]),
            core_api_sha256=dict(pins),
            release_wait_seconds=float(raw.get("releaseWaitSeconds", 120.0)),
            intent_dir=Path(raw.get("intentDir", str(INTENT_DIR))))
        _require(0 <= cfg.release_wait_seconds <= 600, "CONFIG_RELEASE_WAIT_INVALID")
        _require(cfg.deployment_environment == DEV_SYNTHETIC, "INTERIM_V1_PATH_DEV_SYNTHETIC_ONLY")
        return cfg


# ----------------------------------------------------------------------------------- host adapters (injectable) ---

class Host:
    """systemd, journald and process/port observation. Tests substitute a fake; the unit runs the real one."""

    def unit_active(self, unit: str) -> bool:
        out = subprocess.run(["systemctl", "show", unit, "-p", "ActiveState", "--value"], capture_output=True,
                             text=True, timeout=30)
        return out.stdout.strip() in {"active", "activating", "reloading", "deactivating"}

    def stop_unit(self, unit: str) -> None:
        subprocess.run(["systemctl", "stop", unit], capture_output=True, timeout=120)

    def gateway_process_present(self, hermes_home: Path) -> bool:
        """Any Hermes gateway process on the host (cmdline is world-readable; environ is not, without ptrace)."""
        del hermes_home
        for pid in filter(str.isdigit, os.listdir("/proc")):
            try:
                cmd = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            except OSError:
                continue
            if b"hermes_cli.main" in cmd and b"gateway" in cmd:
                return True
        return False

    def port_open(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex(("127.0.0.1", port)) == 0

    def journal(self, namespace: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["journalctl", f"--namespace={namespace}", *args], capture_output=True, timeout=300)

    def journal_entries_until(self, namespace: str, until_usec: int) -> int:
        out = subprocess.run(["journalctl", f"--namespace={namespace}", f"--until=@{until_usec / 1e6:.6f}",
                              "-q", "-o", "export", "--no-pager"], capture_output=True, timeout=300)
        if out.returncode not in (0, 1):
            raise ExecutorError("JOURNAL_UNREADABLE")
        return out.stdout.count(b"\n__CURSOR=") + out.stdout.startswith(b"__CURSOR=")


# ------------------------------------------------------------------------------------ Privacy (read-only, V1) ---

def load_privacy(cfg: Config):
    """Import the deployed Core API Privacy modules read-only after checking every file against the pinned hashes,
    and return a read-only Privacy store. No other Core API module may be loaded."""
    package = cfg.core_api_dir
    for name in CORE_API_MODULES:
        path = package / name
        _require(path.is_file() and not path.is_symlink() and _sha256_file(path) == cfg.core_api_sha256[name],
                 "CORE_API_MODULES_UNPINNED", precondition=True)
    parent = str(package.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    P = importlib.import_module(f"{package.name}.privacy_governance")
    MA = importlib.import_module(f"{package.name}.memory_action_v2")
    loaded = {Path(m.__file__).name for n, m in list(sys.modules.items())
              if (n == package.name or n.startswith(package.name + ".")) and getattr(m, "__file__", None)}
    _require(loaded <= set(CORE_API_MODULES), "CORE_API_MODULES_UNPINNED", precondition=True)
    for name in loaded:
        _require(_sha256_file(package / name) == cfg.core_api_sha256[name], "CORE_API_MODULES_UNPINNED",
                 precondition=True)

    class ReadOnlyPrivacy(P.PrivacyGovernanceStore):
        def _connect(self):
            if not self.path.is_file():
                raise P.PrivacyError("privacy governance database is unavailable")
            if stat.S_IMODE(self.path.stat().st_mode) != 0o600:
                raise P.PrivacyError("privacy governance database must be mode 0600")
            # Never writable. With no WAL content the main file is the whole database, so it is opened immutable (no
            # -shm needed inside the read-only sandbox); with WAL content a normal read-only open reads the WAL.
            wal = Path(str(self.path) + "-wal")
            flags = "mode=ro" if wal.exists() and wal.stat().st_size > 0 else "mode=ro&immutable=1"
            conn = sqlite3.connect(f"{self.path.resolve().as_uri()}?{flags}", uri=True, timeout=5.0)
            conn.row_factory = sqlite3.Row
            existing = {str(r[0]) for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if not P.PRIVACY_TABLES.issubset(existing):
                conn.close()
                raise P.PrivacyError("privacy governance schema is unavailable")
            conn.set_authorizer(P._authorizer)
            return conn

    secret = cfg.privacy_secret.read_bytes()
    return ReadOnlyPrivacy(cfg.privacy_db, secret, None), P, MA


def verify_authorization(cfg: Config, ref: str, nonce: str):
    try:
        store, P, MA = load_privacy(cfg)
        authorization = store.resolve_erasure_authorization(ref, owner=OWNER, execution_nonce=nonce)
        floor = store.required_owners(MA.FIRST_INTERACTION_IDENTITY[0], MA.FIRST_INTERACTION_IDENTITY[1])
    except ExecutorError:
        raise
    except Exception as exc:
        raise ExecutorError("PRIVACY_UNAVAILABLE", precondition=True) from exc
    _require(authorization is not None, "AUTHORIZATION_NOT_VERIFIED", precondition=True)
    _require(authorization.identity == MA.FIRST_INTERACTION_IDENTITY, "AUTHORIZATION_OUT_OF_SCOPE",
             precondition=True)
    _require(OWNER in authorization.resource_owners and OWNER in floor, "OWNER_SCOPE_NOT_PROVISIONED",
             precondition=True)
    return authorization


# ---------------------------------------------------------------------------------------------- the request ---

def read_request(cfg: Config, path: Path) -> Dict[str, str]:
    st = os.lstat(path)
    _require(stat.S_ISREG(st.st_mode) and st.st_uid == cfg.requester_uid and st.st_size <= MAX_REQUEST_BYTES
             and not st.st_mode & 0o002 and st.st_nlink == 1, "REQUEST_REJECTED", precondition=True)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        data = os.read(fd, MAX_REQUEST_BYTES + 1)
    finally:
        os.close(fd)
    try:
        request = json.loads(data.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ExecutorError("REQUEST_REJECTED", precondition=True) from exc
    _require(isinstance(request, dict) and set(request) == REQUEST_FIELDS and request["v"] == 1
             and request["owner"] == OWNER and isinstance(request["authorizationRefId"], str)
             and isinstance(request["executionNonce"], str) and bool(REF_RE.fullmatch(request["authorizationRefId"]))
             and bool(NONCE_RE.fullmatch(request["executionNonce"])), "REQUEST_REJECTED", precondition=True)
    return request


# --------------------------------------------------------------------------------- single-principal precondition ---

def _env_keys(path: Path) -> set:
    keys = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                keys.add(line.split("=", 1)[0].strip().removeprefix("export ").strip())
    return keys


def _enabled_plugins(config_text: str) -> Optional[List[str]]:
    """``plugins: enabled: [- x]`` from Hermes' config.yaml (indentation-based; anything unexpected -> None)."""
    lines = config_text.splitlines()
    for i, line in enumerate(lines):
        if line.rstrip() == "plugins:" and i + 1 < len(lines) and lines[i + 1].rstrip() == "  enabled:":
            out = []
            for item in lines[i + 2:]:
                if item.startswith("    - "):
                    out.append(item[6:].strip())
                elif item.strip() == "" or item.lstrip().startswith("#"):
                    continue
                else:
                    break
            return out
    return None


def check_single_principal(cfg: Config) -> None:
    home = cfg.hermes_home
    _require(home.is_dir() and not home.is_symlink(), "HERMES_HOME_UNAVAILABLE", precondition=True)
    _require(_env_keys(home / ".env") <= ALLOWED_ENV_KEYS, "MULTI_PRINCIPAL_STORE", precondition=True)
    text = (home / "config.yaml").read_text(encoding="utf-8") if (home / "config.yaml").is_file() else ""
    _require(_enabled_plugins(text) == ["lilith_os"], "MULTI_PRINCIPAL_STORE", precondition=True)
    _require(not re.search(r"^platforms:", text, re.M), "MULTI_PRINCIPAL_STORE", precondition=True)
    db = home / "state.db"
    if db.is_file():
        conn = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True, timeout=2.0)
        try:
            check_schema(conn)
            sources = {r[0] for r in conn.execute("SELECT DISTINCT source FROM sessions")}
            users = {r[0] for r in conn.execute("SELECT DISTINCT user_id FROM sessions WHERE user_id IS NOT NULL")}
        except sqlite3.OperationalError as exc:
            raise ExecutorError("STATE_DB_LOCKED" if "locked" in str(exc) else "STATE_DB_UNREADABLE",
                                precondition=True) from exc
        finally:
            conn.close()
        _require(sources <= {"lilith_os"}, "UNRECOGNIZED_SESSION", precondition=True)
        _require(len(users) <= 1, "AMBIGUOUS_OWNERSHIP", precondition=True)


def check_schema(conn: sqlite3.Connection) -> List[str]:
    """The tables present must all be known; returns the FTS tables present."""
    names = [str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    fts = [n for n in FTS_TABLES if n in names]
    shadows = {f + s for f in fts for s in FTS_SHADOW_SUFFIXES}
    unknown = set(names) - set(PURGE_ORDER) - KEEP_TABLES - set(fts) - shadows
    _require(not unknown, "UNKNOWN_HERMES_SCHEMA", precondition=True)
    return fts


# ---------------------------------------------------------------------------------------------------- phases ---

class Executor:
    def __init__(self, cfg: Config, host: Optional[Host] = None, *,
                 fault: Optional[Callable[[str], None]] = None):
        self.cfg = cfg
        self.host = host or Host()
        self.fault = fault or (lambda point: None)

    # journal ---------------------------------------------------------------------------------------------------
    def _journal_path(self, ref: str) -> Path:
        return self.cfg.state_dir / f"{_digest(ref)}.json"

    def _load_journal(self, ref: str, nonce: str) -> Dict[str, Any]:
        path = self._journal_path(ref)
        if path.is_file():
            journal = json.loads(path.read_text(encoding="utf-8"))
            _require(journal.get("nonceDigest") == _digest(nonce), "JOURNAL_NONCE_MISMATCH")
            return journal
        return {"v": 1, "authDigest": _digest(ref), "nonceDigest": _digest(nonce), "startedAt": _utc(),
                "phases": {}, "checks": {}}

    def _save_journal(self, ref: str, journal: Mapping[str, Any]) -> None:
        _atomic_write(self._journal_path(ref), json.dumps(journal, sort_keys=True).encode("utf-8"))

    def _done(self, ref: str, journal: Dict[str, Any], phase: str, **checks: bool) -> None:
        journal["phases"][phase] = "COMPLETE"
        journal["checks"].update(checks)
        self._save_journal(ref, journal)
        self.fault(f"after:{phase}")

    # protected snapshot ----------------------------------------------------------------------------------------
    def _protected_snapshot(self) -> Dict[str, str]:
        home, out = self.cfg.hermes_home, {}
        for rel in PROTECTED:
            top = home / rel
            if top.is_symlink():
                out[rel] = "symlink:" + os.readlink(top)
            elif top.is_file():
                out[rel] = _sha256_file(top)
            elif top.is_dir():
                for root, dirs, files in os.walk(top, followlinks=False):
                    for name in sorted(files):
                        p = Path(root) / name
                        out[str(p.relative_to(home))] = ("symlink:" + os.readlink(p)) if p.is_symlink() \
                            else _sha256_file(p)
        return out

    # P1 ------------------------------------------------------------------------------------------------------
    def phase_stop(self) -> None:
        if self.host.unit_active(self.cfg.gateway_unit):
            self.host.stop_unit(self.cfg.gateway_unit)
        _require(not self.host.unit_active(self.cfg.gateway_unit), "GATEWAY_NOT_STOPPED")
        _require(not self.host.gateway_process_present(self.cfg.hermes_home), "GATEWAY_PROCESS_PRESENT")
        _require(not any(self.host.port_open(p) for p in self.cfg.gateway_ports), "GATEWAY_STILL_LISTENING")

    # P2 ------------------------------------------------------------------------------------------------------
    def phase_sqlite(self) -> Dict[str, bool]:
        home = self.cfg.hermes_home
        db = home / "state.db"
        if not db.exists():
            _require(not any((home / n).exists() for n in STATE_DB_FILES[1:]), "STATE_DB_ORPHAN_SIDECAR")
            return {"sessions_zero": True, "messages_zero": True, "fts_zero": True, "wal_truncated": True,
                    "integrity_ok": True}
        _require(db.is_file() and not db.is_symlink(), "STATE_DB_UNSAFE")
        conn = sqlite3.connect(str(db), timeout=2.0, isolation_level=None)
        try:
            conn.execute("PRAGMA secure_delete=ON")
            conn.execute("PRAGMA foreign_keys=OFF")
            try:
                conn.execute("BEGIN EXCLUSIVE")          # replays/locks the WAL; fails while anyone holds the db
            except sqlite3.OperationalError as exc:
                raise ExecutorError("STATE_DB_LOCKED") from exc
            try:
                fts = check_schema(conn)
                present = {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                for table in PURGE_ORDER:
                    if table in present:
                        conn.execute(f'DELETE FROM "{table}"')
                for table in fts:
                    conn.execute(f'INSERT INTO "{table}"("{table}") VALUES(\'rebuild\')')
                self.fault("sqlite:before-commit")
                conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            self.fault("sqlite:after-commit")
            busy = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            _require(busy is None or busy[0] == 0, "STATE_DB_CHECKPOINT_BUSY")
            try:
                self.fault("sqlite:vacuum")
                conn.execute("VACUUM")
            except sqlite3.OperationalError as exc:
                raise ExecutorError("STATE_DB_VACUUM_FAILED") from exc
            busy = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            _require(busy is None or busy[0] == 0, "STATE_DB_CHECKPOINT_BUSY")
            counts = {t: int(conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])
                      for t in PURGE_ORDER if t in present}
            docs = sum(int(conn.execute(f'SELECT COUNT(*) FROM "{t}_docsize"').fetchone()[0])
                       for t in fts if f"{t}_docsize" in present)
            integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0]) == "ok"
            freelist = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
        finally:
            conn.close()
        wal = home / "state.db-wal"
        checks = {"sessions_zero": counts.get("sessions", 0) == 0, "messages_zero": counts.get("messages", 0) == 0,
                  "fts_zero": docs == 0, "wal_truncated": (not wal.exists()) or wal.stat().st_size == 0,
                  "integrity_ok": integrity and freelist == 0 and not any(counts.values())}
        _require(all(checks.values()), "STATE_DB_VERIFY_FAILED")
        return checks

    # P3 ------------------------------------------------------------------------------------------------------
    def _remove_tree_contents(self, directory: Path) -> None:
        if directory.is_symlink():
            directory.unlink()                       # never follow: the link itself goes, its target is untouched
            return
        if not directory.is_dir():
            return
        dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            purge_fd(dfd)
        finally:
            os.close(dfd)

    def phase_files(self, snapshot: Mapping[str, str]) -> Dict[str, bool]:
        home = self.cfg.hermes_home
        for rel in PURGE_DIRS:
            self._remove_tree_contents(home / rel)
            self.fault(f"files:{rel}")
        for rel in PURGE_FILES:
            p = home / rel
            if p.is_symlink() or p.is_file():
                p.unlink()
        purged = all(not (home / rel).exists() or (home / rel).is_dir() and not any((home / rel).iterdir())
                     for rel in PURGE_DIRS) and not any((home / rel).exists() for rel in PURGE_FILES)
        unchanged = self._protected_snapshot() == dict(snapshot)
        _require(purged, "FILES_VERIFY_FAILED")
        _require(unchanged, "PROTECTED_FILES_CHANGED")
        return {"files_purged": True, "protected_files_unchanged": True}

    # P4 ------------------------------------------------------------------------------------------------------
    def phase_journal(self) -> Dict[str, bool]:
        if not self.cfg.journal_dir.exists():
            return {"journal_vacuumed": True}
        cutoff = int(time.time() * 1e6)
        self.fault("journal:rotate")
        rotated = self.host.journal(self.cfg.journal_namespace, "--rotate")
        _require(rotated.returncode == 0, "JOURNAL_ROTATE_FAILED")
        time.sleep(1.2)                                  # --vacuum-time=1s spares archives younger than 1 s
        vacuumed = self.host.journal(self.cfg.journal_namespace, "--vacuum-time=1s")
        _require(vacuumed.returncode == 0, "JOURNAL_VACUUM_FAILED")
        _require(self.host.journal_entries_until(self.cfg.journal_namespace, cutoff) == 0, "JOURNAL_VERIFY_FAILED")
        return {"journal_vacuumed": True}

    # P5 ------------------------------------------------------------------------------------------------------
    def phase_backups(self, ref: str) -> Dict[str, bool]:
        root = self.cfg.backup_root
        if not root.exists():
            return {"backups_conversation_free": True}
        _require(root.is_dir() and not root.is_symlink(), "BACKUP_ROOT_UNSAFE")
        found = scan_backups(root)
        if found:
            tomb_dir = root / "FORGET-TOMBSTONES"
            tomb_dir.mkdir(mode=0o700, exist_ok=True)
            entries = [{"pathDigest": _digest(str(f.path.relative_to(root)) + ("!" + f.member if f.member else "")),
                        "kind": f.kind, "size": f.size, "sha256Before": f.sha256} for f in found]
            self.fault("backups:before-tombstone")
            _atomic_write(tomb_dir / f"{int(time.time())}-{_digest(ref)[:16]}.json",
                          json.dumps({"v": 1, "authDigest": _digest(ref), "at": _utc(), "removed": entries},
                                     sort_keys=True).encode("utf-8"))
            self.fault("backups:after-tombstone")
            for f in found:
                remove_backup_item(f)
        _require(not scan_backups(root), "BACKUPS_VERIFY_FAILED")
        return {"backups_conversation_free": True}

    # P6 ------------------------------------------------------------------------------------------------------
    def phase_epoch(self, ref: str) -> int:
        log = self.cfg.epoch_log
        auth = _digest(ref)
        lines = read_epochs(log)
        for entry in lines:
            if entry["authDigest"] == auth:
                return int(entry["epoch"])
        epoch = (max((int(e["epoch"]) for e in lines), default=0)) + 1
        fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, (json.dumps({"epoch": epoch, "at": _utc(), "authDigest": auth}, sort_keys=True) + "\n")
                     .encode("ascii"))
            os.fsync(fd)
        finally:
            os.close(fd)
        _fsync_dir(log.parent)
        return epoch

    # receipt ---------------------------------------------------------------------------------------------------
    def _receipt(self, authorization, status: str, phases: Mapping[str, str], checks: Mapping[str, bool],
                 epoch: int) -> Dict[str, Any]:
        receipt = {
            "v": 1, "owner": OWNER, "authorizationRefId": authorization.authorization_ref_id,
            "executionNonce": authorization.execution_nonce,
            "authorizationFingerprint": authorization.authorization_fingerprint, "holdId": authorization.hold_id,
            "identityScope": {"memoryClass": authorization.identity[0], "subjectNamespace": authorization.identity[1],
                              "subjectKey": authorization.identity[2]},
            "scope": SCOPE, "status": status, "phases": {p: phases.get(p, "PENDING") for p in PHASES},
            "checks": {c: bool(checks.get(c, False)) for c in CHECKS}, "erasureEpoch": epoch, "claim": CLAIM,
            "providerErasure": PROVIDER_ERASURE, "completedAt": _utc(),
        }
        receipt["receiptDigest"] = receipt_digest(receipt)
        return receipt

    def _write_receipt(self, receipt: Mapping[str, Any]) -> None:
        _atomic_write(self.cfg.receipt_dir / f"{receipt['authorizationRefId']}.receipt.json",
                      json.dumps(receipt, sort_keys=True).encode("ascii"), mode=0o640, gid=self.cfg.receipt_gid)

    # one request -----------------------------------------------------------------------------------------------
    def process(self, request_path: Path) -> str:
        request = read_request(self.cfg, request_path)
        ref, nonce = request["authorizationRefId"], request["executionNonce"]
        if self._journal_path(ref).is_file():
            journal = self._load_journal(ref, nonce)                             # also binds the exact nonce
            done = journal["phases"]
            # A re-run after the receipt (crash, re-queued request): once Privacy proves completion the authorization
            # no longer resolves, and none is needed: release instead of failing (which would skip the restart).
            if "RELEASED" in done or ("RECEIPT" in done and self._privacy_completed(ref)):
                if "RELEASED" not in done:
                    done["RELEASED"] = "COMPLETE"
                    self._save_journal(ref, journal)
                self.reconcile()
                return "COMPLETE"
        authorization = verify_authorization(self.cfg, ref, nonce)             # independent check #2
        journal = self._load_journal(ref, nonce)
        phases = journal["phases"]
        if "RECEIPT" in phases:                                                  # already finished: idempotent
            if not (self.cfg.receipt_dir / f"{ref}.receipt.json").is_file():
                self._write_receipt(self._receipt(authorization, "COMPLETE", phases, journal["checks"],
                                                  journal["epoch"]))
            return "COMPLETE" if self._await_release(ref, journal) else "AWAITING_PRIVACY_COMPLETION"
        try:
            check_single_principal(self.cfg)
            if "VALIDATE" not in phases:
                journal["protected"] = self._protected_snapshot()
        except ExecutorError as exc:
            if exc.precondition and not phases:                                  # nothing changed yet: REJECTED
                log("REJECTED", code=exc.code)
                self._write_receipt(self._receipt(authorization, "REJECTED", {"VALIDATE": "FAILED"}, {}, 0))
                return "REJECTED"
            raise
        _atomic_write(self.cfg.marker, json.dumps({"authDigest": _digest(ref), "at": _utc()}).encode("ascii"))
        if "VALIDATE" not in phases:
            journal["ref"] = ref                    # root-only state: lets reconcile prove Privacy completion later
            self._done(ref, journal, "VALIDATE", single_principal=True)
        verify_authorization(self.cfg, ref, nonce)                               # hold still ACTIVE
        self.phase_stop()
        if "STOP" not in phases:
            self._done(ref, journal, "STOP")
        # Every destructive phase re-runs its verification even when journalled (a restore may have intervened).
        self._done(ref, journal, "SQLITE", **self.phase_sqlite())
        self._done(ref, journal, "FILES", **self.phase_files(journal["protected"]))
        self._done(ref, journal, "JOURNAL", **self.phase_journal())
        self._done(ref, journal, "BACKUPS", **self.phase_backups(ref))
        journal["epoch"] = self.phase_epoch(ref)
        self._done(ref, journal, "EPOCH")
        verify_authorization(self.cfg, ref, nonce)
        # Finalization. The receipt is written while the gateway is still blocked, and the marker is released only
        # when Privacy itself has COMPLETED this authorization with Hermes COMPLETE (HMAC-bound immutable rows).
        # An undelivered, unrecorded or lost receipt therefore never unblocks anything; a crash anywhere here is
        # healed by the path unit (request still queued), the adapter's retry (receipt re-read or rewritten) and
        # the reconcile pass (marker released once Privacy shows completion).
        self.fault("before:receipt")
        self._write_receipt(self._receipt(authorization, "COMPLETE", phases, journal["checks"], journal["epoch"]))
        self.fault("after:RECEIPT-written")
        journal["phases"]["RECEIPT"] = "COMPLETE"
        self._save_journal(ref, journal)
        self.fault("after:RECEIPT-journalled")
        return "COMPLETE" if self._await_release(ref, journal) else "AWAITING_PRIVACY_COMPLETION"

    # release -----------------------------------------------------------------------------------------------------
    def _privacy_completed(self, ref: str) -> bool:
        try:
            store, _P, _MA = load_privacy(self.cfg)
            return bool(store.owner_completion_recorded(ref, OWNER))
        except Exception:
            return False                                                         # unknown = not completed

    def _await_release(self, ref: str, journal: Dict[str, Any]) -> bool:
        deadline = time.monotonic() + self.cfg.release_wait_seconds
        while True:
            if self._privacy_completed(ref):
                journal["phases"]["RELEASED"] = "COMPLETE"
                self._save_journal(ref, journal)
                self.fault("after:RELEASED")
                self.reconcile()
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(1.0)

    def reconcile(self) -> None:
        """Mark released every journal whose authorization Privacy has completed with Hermes COMPLETE; remove the
        gateway-blocking marker only when no journal remains unreleased. Never erases anything."""
        for path in sorted(self.cfg.state_dir.glob("*.json")):
            try:
                journal = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue                                                         # unreadable: stays blocking
            ref = journal.get("ref")
            if "RELEASED" not in journal.get("phases", {}) and isinstance(ref, str) and self._privacy_completed(ref):
                journal["phases"]["RELEASED"] = "COMPLETE"
                self._save_journal(ref, journal)
                self.fault("after:RELEASED")
        if self.cfg.marker.exists() and not _journals_in_progress(self.cfg.state_dir):
            self.cfg.marker.unlink()
            _fsync_dir(self.cfg.marker.parent)
        for name in INTENT_IDENTITIES:
            intent = self.cfg.intent_dir / name
            if intent.exists() and not _journals_in_progress(self.cfg.state_dir) and _held(intent) \
                    and self._identity_completed(name):
                self.fault("reconcile:before-intent-release")
                intent.unlink()
                _fsync_dir(intent.parent)
                log("INTENT_RELEASED")

    def _identity_completed(self, name: str = INTENT_NAME) -> bool:
        try:
            _label, attribute, owner = INTENT_IDENTITIES[name]
            store, _P, MA = load_privacy(self.cfg)
            return bool(store.identity_forget_completed(getattr(MA, attribute), owner))
        except Exception:
            return False                                                         # unknown = not completed

    # hold-first --------------------------------------------------------------------------------------------------
    def run_hold(self) -> int:
        """Path-unit entry: take ownership of the recorded intent and confirm the gateway is stopped. An invalid intent
        is left in place (still blocking) and reported; nothing here ever removes an intent."""
        try:
            st = os.lstat(self.cfg.intent_dir)
            _require(stat.S_ISDIR(st.st_mode) and st.st_uid == 0 and not st.st_mode & 0o002
                     and bool(st.st_mode & stat.S_ISVTX), "HOLD_INTENT_DIR_UNTRUSTED")
            for name in sorted(os.listdir(self.cfg.intent_dir)):
                if name.startswith("."):
                    continue                                                     # the Core API's own temp files
                if name not in INTENT_IDENTITIES:
                    log("INTENT_INVALID", code="INTENT_NAME_UNEXPECTED")
                    continue
                try:
                    self.fault("hold:before-take")
                    take_intent(self.cfg, self.cfg.intent_dir / name)
                    self.fault("hold:after-take")
                    log("HELD")
                except ExecutorError as exc:
                    log("INTENT_INVALID", code=exc.code)                         # left in place: still blocking
            self.phase_stop()
            log("GATEWAY_STOPPED")
            return 0
        except ExecutorError as exc:
            log("FAILED", code=exc.code)
            return 1

    def run_cancel_intent(self, confirmed: bool) -> int:
        """Operator entry (root, owner-approved): remove a pending intent that never became a Privacy authorization."""
        if not confirmed:
            log("FAILED", code="CANCEL_NOT_CONFIRMED")
            return 2
        self.cfg.state_dir.mkdir(mode=0o700, exist_ok=True)
        lock = os.open(self.cfg.state_dir / ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                store, _P, MA = load_privacy(self.cfg)
                in_flight = [store.in_flight_authorization(getattr(MA, attribute))
                             for _label, attribute, _owner in INTENT_IDENTITIES.values()]
            except Exception:
                log("FAILED", code="CANCEL_REFUSED_PRIVACY_UNAVAILABLE")
                return 2
            if any(ref is not None for ref in in_flight) or _journals_in_progress(self.cfg.state_dir):
                log("FAILED", code="CANCEL_REFUSED_FORGET_IN_FLIGHT")
                return 2
            for name in INTENT_IDENTITIES:
                intent = self.cfg.intent_dir / name
                if intent.exists() or intent.is_symlink():
                    intent.unlink()
                    _fsync_dir(intent.parent)
                    log("INTENT_CANCELLED")
            return 0
        finally:
            os.close(lock)

    def run(self) -> int:
        """Process every pending request; non-zero exit if any failed (so OnSuccess does not restart the gateway)."""
        self.cfg.state_dir.mkdir(mode=0o700, exist_ok=True)
        lock = os.open(self.cfg.state_dir / ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() > deadline:
                        log("FAILED", code="EXECUTOR_BUSY")
                        return 75
                    time.sleep(0.5)
            spool = os.lstat(self.cfg.spool_dir)
            if not (stat.S_ISDIR(spool.st_mode) and spool.st_uid == 0 and not spool.st_mode & 0o002):
                log("FAILED", code="SPOOL_UNTRUSTED")
                return 1
            failed = 0
            for request in sorted(self.cfg.spool_dir.glob("*.req")):
                try:
                    outcome = self.process(request)
                    log(outcome, auth=_digest_of_request(request))
                    request.unlink(missing_ok=True)
                except ExecutorError as exc:
                    failed += 1
                    log("FAILED", code=exc.code)
                    _park(request)
                except Exception as exc:                                         # content-free: type only
                    failed += 1
                    log("FAILED", code="UNEXPECTED_" + type(exc).__name__)
                    _park(request)
            self.reconcile()
            return 1 if failed else 0
        finally:
            os.close(lock)

    def run_reconcile(self) -> int:
        """Timer entry: only the non-destructive release check (no request is processed, nothing is erased)."""
        self.cfg.state_dir.mkdir(mode=0o700, exist_ok=True)
        lock = os.open(self.cfg.state_dir / ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0                                                         # an executor run is in progress
            self.reconcile()
            log("RECONCILED", blocked=self.cfg.marker.exists())
            return 0
        finally:
            os.close(lock)


def purge_fd(dfd: int) -> None:
    """Remove everything below an open directory without following any symlink."""
    for name in os.listdir(dfd):
        st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
        if stat.S_ISDIR(st.st_mode):
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dfd)
            try:
                purge_fd(child)
            finally:
                os.close(child)
            os.rmdir(name, dir_fd=dfd)
        else:
            os.unlink(name, dir_fd=dfd)


def _park(request: Path) -> None:
    try:
        os.replace(request, request.with_suffix(".failed"))
    except OSError:
        pass


def _digest_of_request(request: Path) -> str:
    return _digest(request.name)[:16]


def _held(intent: Path) -> bool:
    st = os.lstat(intent)
    return stat.S_ISREG(st.st_mode) and st.st_uid == 0


def take_intent(cfg: Config, path: Path) -> None:
    """Validate the Core API's intent strictly and make it root-owned (readable by the Core API group)."""
    for _ in range(25):                                    # the recorder's link/unlink window: nlink 2 briefly
        st = os.lstat(path)
        if st.st_nlink == 1:
            break
        time.sleep(0.2)
    _require(stat.S_ISREG(st.st_mode) and st.st_uid in (cfg.requester_uid, 0) and st.st_nlink == 1
             and st.st_size <= MAX_INTENT_BYTES and not st.st_mode & 0o002, "INTENT_REJECTED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        data = os.read(fd, MAX_INTENT_BYTES + 1)
        try:
            intent = json.loads(data.decode("ascii"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ExecutorError("INTENT_REJECTED") from exc
        _require(isinstance(intent, dict) and set(intent) == INTENT_FIELDS and intent.get("v") == 1
                 and path.name in INTENT_IDENTITIES and intent.get("identity") == INTENT_IDENTITIES[path.name][0]
                 and all(isinstance(intent.get(k), str) and bool(INTENT_REF_RE.fullmatch(intent[k]))
                         for k in ("intentRefId", "actorRefId")) and isinstance(intent.get("recordedAt"), str),
                 "INTENT_REJECTED")
        os.fchown(fd, 0, cfg.receipt_gid)
        os.fchmod(fd, 0o640)
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(path.parent)


def _journals_in_progress(state_dir: Path) -> bool:
    for path in state_dir.glob("*.json"):
        try:
            if "RELEASED" not in json.loads(path.read_text(encoding="utf-8")).get("phases", {}):
                return True
        except ValueError:
            return True
    return False


def log(event: str, **fields: Any) -> None:
    print(json.dumps({"event": event, "at": _utc(), **fields}, sort_keys=True), file=sys.stderr, flush=True)


# ----------------------------------------------------------------------------------------- backups and epochs ---

@dataclass(frozen=True)
class BackupItem:
    path: Path
    kind: str
    size: int
    sha256: str
    member: Optional[str] = None


def _conversation_rel(parts: Sequence[str]) -> Optional[str]:
    """Kind of a path (relative parts) inside a backup, if conversation-bearing. HERMES_HOME conversation paths count
    only directly below a HERMES_HOME copy root, so code trees (e.g. src/gateway) are never touched."""
    if parts and parts[-1] in STATE_DB_FILES:
        return "STATE_DB"
    for i, part in enumerate(parts):
        if part.endswith(JOURNAL_DIR_SUFFIX):
            return "JOURNAL_COPY"
        if part in HOME_ROOT_NAMES and i + 1 < len(parts):
            sub = "/".join(parts[i + 1:])
            if parts[i + 1] in PURGE_DIRS or sub in PURGE_FILES:
                return "HERMES_HOME_CONVERSATION"
    return None


def scan_backups(root: Path) -> List[BackupItem]:
    found: List[BackupItem] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = Path(dirpath).relative_to(root).parts
        if rel_dir and rel_dir[0] == "FORGET-TOMBSTONES":
            dirnames[:] = []
            continue
        for name in list(dirnames):                     # os.walk never descends into symlinked directories
            p = Path(dirpath) / name
            if _conversation_rel(rel_dir + (name,)) == "JOURNAL_COPY" and not p.is_symlink():
                found.append(BackupItem(p, "JOURNAL_COPY", 0, _tree_digest(p)))
                dirnames.remove(name)                    # removed as a whole; files below are not listed again
        for name in filenames:
            p = Path(dirpath) / name
            if p.is_symlink():
                continue
            kind = _conversation_rel(rel_dir + (name,))
            if kind:
                found.append(BackupItem(p, kind, p.stat().st_size, _sha256_file(p)))
            elif name.endswith((".tar", ".tar.gz", ".tgz")):
                for member in _tar_conversation_members(p):
                    found.append(BackupItem(p, "TAR_MEMBER", member[1], member[2], member[0]))
    return found


def _tree_digest(path: Path) -> str:
    h = hashlib.sha256()
    for dirpath, _dirs, files in sorted(os.walk(path, followlinks=False)):
        for name in sorted(files):
            p = Path(dirpath) / name
            if not p.is_symlink():
                h.update(str(p.relative_to(path)).encode() + b"\0" + _sha256_file(p).encode())
    return h.hexdigest()


def _tar_conversation_members(path: Path) -> List[Tuple[str, int, str]]:
    out = []
    try:
        with tarfile.open(path, "r:*") as tar:
            for member in tar:
                parts = tuple(p for p in member.name.split("/") if p not in ("", "."))
                if member.isfile() and _conversation_rel(parts):
                    fh = tar.extractfile(member)
                    out.append((member.name, member.size, hashlib.sha256(fh.read() if fh else b"").hexdigest()))
    except tarfile.TarError as exc:
        raise ExecutorError("BACKUP_ARCHIVE_UNREADABLE") from exc
    return out


def remove_backup_item(item: BackupItem) -> None:
    if item.kind == "TAR_MEMBER":
        _rewrite_tar_without_conversation(item.path)
    elif item.path.is_dir() and not item.path.is_symlink():
        dfd = os.open(item.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            purge_fd(dfd)
        finally:
            os.close(dfd)
        os.rmdir(item.path)
    elif item.path.exists() or item.path.is_symlink():
        item.path.unlink()


def _rewrite_tar_without_conversation(path: Path) -> None:
    """Replace the archive by one without its conversation-bearing members (everything else byte-identical in
    content and metadata). Atomic; idempotent (a clean archive is left untouched)."""
    if not _tar_conversation_members(path):
        return
    mode = "w:gz" if path.name.endswith((".gz", ".tgz")) else "w"
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tarfile.open(path, "r:*") as src, tarfile.open(tmp, mode, format=tarfile.PAX_FORMAT) as dst:
        for member in src:
            parts = tuple(p for p in member.name.split("/") if p not in ("", "."))
            if member.isfile() and _conversation_rel(parts):
                continue
            dst.addfile(member, src.extractfile(member) if member.isfile() else None)
    fd = os.open(tmp, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    st = path.stat()
    os.chown(tmp, st.st_uid, st.st_gid)
    os.chmod(tmp, stat.S_IMODE(st.st_mode))
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def read_epochs(log: Path) -> List[Dict[str, Any]]:
    if not log.exists():
        return []
    st = os.lstat(log)
    _require(stat.S_ISREG(st.st_mode) and st.st_uid == 0 and not st.st_mode & 0o077, "EPOCH_LOG_UNTRUSTED")
    entries = []
    for line in log.read_text(encoding="ascii").splitlines():
        entry = json.loads(line)
        _require(isinstance(entry.get("epoch"), int) and isinstance(entry.get("authDigest"), str)
                 and isinstance(entry.get("at"), str), "EPOCH_LOG_CORRUPT")
        entries.append(entry)
    _require([e["epoch"] for e in entries] == list(range(1, len(entries) + 1)), "EPOCH_LOG_CORRUPT")
    return entries


def main(argv: Sequence[str]) -> int:
    args = list(argv[1:])
    modes = [m for m in ("--reconcile", "--hold", "--cancel-intent") if m in args]
    confirmed = "--confirm-owner-approved" in args
    for flag in (*modes, "--confirm-owner-approved"):
        if flag in args:
            args.remove(flag)
    if len(modes) > 1:
        log("FAILED", code="USAGE")
        return 64
    config = Path(args[1]) if len(args) >= 2 and args[0] == "--config" and os.getuid() == 0 else CONFIG_PATH
    try:
        cfg = Config.load(config)
    except ExecutorError as exc:
        log("FAILED", code=exc.code)
        return 78
    except Exception as exc:
        log("FAILED", code="CONFIG_UNREADABLE_" + type(exc).__name__)
        return 78
    executor = Executor(cfg)
    mode = modes[0] if modes else None
    if mode == "--reconcile":
        return executor.run_reconcile()
    if mode == "--hold":
        return executor.run_hold()
    if mode == "--cancel-intent":
        return executor.run_cancel_intent(confirmed)
    return executor.run()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
