#!/usr/bin/env python3
"""OWNER_PROD inert install, stage 1 of R3b: the foundation (SOURCE ONLY; PREPARED, NOT RUN).

Record: docs/architecture/canonical-memory-prod-integration-plan.md R3b/R3g. Root on `lilith-01` only, under a separate
owner-approved window; nothing here is authorized by the repository.

Stage 1 creates exactly four things, none of which LILITH reads, and nothing else:
1. the two service principals, by NAME, with ids the OS allocates (`useradd --system --user-group`, the accepted DEV
   installer's own rule): `lilith-authority-dev` and `lilith-recovery-witness`. DEV's numeric ids are never assumed
   (gid 995 is already taken on PROD); the allocated ids are recorded and every later stage pins them;
2. the empty isolated canonical store directory (D-7) `/home/lilith/.hermes/lilith-os/canonical` (root:root, 0700);
3. `/etc/lilith-authority-dev/` (root, 0755) when absent;
4. `/etc/lilith-authority-dev/deployment.json` = the OWNER_PROD selection (root, 0644).

No service, unit, key, credential, registration, grant, store file or router file is created or changed. LILITH's
live files (identity, router, stores, the two 15B2a keys) are digested before and after (streamed, O_NOATIME) and must
be equal. Later stages (authority release staging, units with `LILITH_ENV=prod`, witness, host tree, context units with
no grant) are separate and not in this file.

Every step is appended to a journal BEFORE its effect; a failure stops at once (no retry, no repair) and leaves the
journal naming exactly what exists. `return` removes exactly the journal's items, in reverse, each re-verified first
(a principal whose ids changed, a non-empty store directory or a changed `deployment.json` stops the return).

H-1/H-2 (plan §13, `owner_prod_safe_fs`): the journal (schema 2) records each created path's observed mode, owner
and integrity; the return refuses a legacy or incomplete journal, an interrupted item that exists, or any item whose
mode, owner, content or type differs. It removes each entry through descriptors (never following a link), only if
its inode is unchanged since verification, journals every removal, and refuses to resume a partial return. Install
and return hold the installer's exclusive host lock.

    python owner_prod_inert_install.py plan              the exact text; its SHA-256 prefix is the approval
    python owner_prod_inert_install.py install <approval>
    python owner_prod_inert_install.py return  <approval>

    stage 1 != an installed authority;  a principal != a running service;  deployment.json != an activated profile
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import owner_prod_safe_fs as SF  # noqa: E402  (H-1/H-2: descriptor-relative verify-then-remove, the host lock)

PROD_HOST = "lilith-01"
DEV_MACHINE_ID_SHA256 = hashlib.sha256(b"ae929170e6fa4c8ab9cc7b9547238d9d\n").hexdigest()
PRINCIPALS = ("lilith-authority-dev", "lilith-recovery-witness")    # install_authority_dev SERVICE_USER / WITNESS_USER
USERADD = ("/usr/sbin/useradd", "--system", "--user-group", "--no-create-home", "--home-dir", "/nonexistent",
           "--shell", "/usr/sbin/nologin")
USERDEL = "/usr/sbin/userdel"
CANONICAL = "home/lilith/.hermes/lilith-os/canonical"
AUTHORITY_CONFIG = "etc/lilith-authority-dev"
DEPLOYMENT = AUTHORITY_CONFIG + "/deployment.json"
DEPLOYMENT_BYTES = json.dumps({"environment": "prod", "profile": "OWNER_PROD", "schemaVersion": 1},
                              sort_keys=True, separators=(",", ":")).encode("ascii")
STATE = "var/lib/lilith-owner-prod-install"
JOURNAL = STATE + "/foundation.journal"
LATER_STAGES = ("release", "units", "hosttree", "context")
HERMES = "home/lilith/.hermes"
LIVE = tuple(f"{HERMES}/{p}" for p in (
    "SOUL.md", "memories/USER.md", "memories/MEMORY.md", "config.yaml", "lilith_router/router.yaml",
    "lilith_router/gateway_integration.py", "lilith-os/api/app.py", "lilith-os/data/cognitive_memory.db",
    "lilith-os/data/privacy_governance.db", "lilith-os/data/lilith.db", "lilith-os/data/actor_authority.key",
    "lilith-os/data/privacy_authority.key"))
STEPS = ("principal:lilith-authority-dev", "principal:lilith-recovery-witness", "dir:canonical", "dir:authority-config",
         "file:deployment")
JOURNAL_SCHEMA = 2
FS_STEPS = {"dir:canonical": (CANONICAL, "dir", 0o700), "dir:authority-config": (AUTHORITY_CONFIG, "dir", 0o755),
            "file:deployment": (DEPLOYMENT, "file", 0o644)}

Stop = SF.Stop
_need = SF.need


def _sha_stream(path: Path) -> str:
    digest = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | os.O_NOATIME | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)
    finally:
        os.close(fd)


class Accounts:
    """Name -> (uid, gid) lookups (real: pwd/grp). TEST passes a synthetic one."""

    def user(self, name: str) -> Optional[tuple[int, int]]:
        import pwd
        try:
            entry = pwd.getpwnam(name)
        except KeyError:
            return None
        return entry.pw_uid, entry.pw_gid

    def group(self, name: str) -> Optional[int]:
        import grp
        try:
            return grp.getgrnam(name).gr_gid
        except KeyError:
            return None


class Foundation:
    def __init__(self, root: Path, *, run: Callable[[Sequence[str]], subprocess.CompletedProcess], hostname: str,
                 euid: int, accounts: Accounts, chown: bool = True):
        self.root, self.run, self.hostname, self.euid, self.accounts, self.chown = root, run, hostname, euid, accounts, chown
        self.before_remove: Optional[Callable[[str], None]] = None     # TEST seam: runs after verification, per removal

    def p(self, relative: str) -> Path:
        return self.root / relative

    # ------------------------------------------------------------------ checks ---
    def host_guard(self) -> None:
        _need(self.euid == 0, "NOT_ROOT")
        _need(self.hostname.split(".", 1)[0] == PROD_HOST, "WRONG_HOST")
        _need(_sha_stream(self.p("etc/machine-id")) != DEV_MACHINE_ID_SHA256, "DEV_MACHINE")

    def live_digests(self) -> dict[str, str]:
        out = {}
        for relative in LIVE:
            path = self.p(relative)
            _need(stat.S_ISREG(os.lstat(path).st_mode), "LIVE_FILE_NOT_REGULAR:" + relative)
            out[relative] = _sha_stream(path)
        return out

    def preflight(self) -> dict[str, Any]:
        """Read-only. Every item this stage would create must be absent, and every live file present."""
        self.host_guard()
        for name in PRINCIPALS:
            _need(self.accounts.user(name) is None and self.accounts.group(name) is None, "PRINCIPAL_EXISTS:" + name)
        for relative in (CANONICAL, DEPLOYMENT, STATE):
            _need(not os.path.lexists(self.p(relative)), "PRESENT:/" + relative)
        try:
            live = self.live_digests()
        except FileNotFoundError as exc:
            raise Stop("LIVE_FILE_MISSING") from exc
        return {"live": live, "authorityConfigExists": os.path.lexists(self.p(AUTHORITY_CONFIG))}

    def plan_text(self) -> str:
        return ("OWNER_PROD inert install, stage 1 (foundation), lilith-01 only. Creates, in order, each journaled first:\n"
                + "".join(f"  {s}\n" for s in STEPS)
                + "Principals by name with OS-allocated ids (useradd --system --user-group); DEV ids never assumed.\n"
                  "Nothing else: no unit, service, key, credential, registration, grant, store file or router file.\n"
                  "LILITH's live files digested before and after; any difference, failure or surprise is a STOP.\n")

    def approval(self) -> str:
        return hashlib.sha256(self.plan_text().encode("ascii")).hexdigest()[:16]

    # ----------------------------------------------------------------- journal ---
    def _journal(self, entry: dict[str, Any]) -> None:
        path = self.p(JOURNAL)
        with open(path, "a", encoding="ascii") as f:          # appended BEFORE the effect it names
            f.write(json.dumps(entry, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def journal(self) -> list[dict[str, Any]]:
        path = self.p(JOURNAL)
        if not os.path.lexists(path):
            return []
        return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines() if line.strip()]

    # ----------------------------------------------------------------- install ---
    def install(self, approval: str) -> dict[str, Any]:
        _need(approval == self.approval(), "APPROVAL_NOT_THIS_PLAN")
        facts = self.preflight()
        state = self.p(STATE)
        try:
            state.mkdir(mode=0o700, parents=True)
        except FileExistsError as exc:                          # another process got here between preflight and now
            raise Stop("LOCKED_BY_ANOTHER_PROCESS") from exc
        with SF.HostLock(self.root, STATE):
            return self._install_locked(facts)

    def _install_locked(self, facts: dict[str, Any]) -> dict[str, Any]:
        fd = os.open(self.p(JOURNAL), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)    # one install, ever
        os.close(fd)
        self._journal({"step": "begin", "live": facts["live"], "schema": JOURNAL_SCHEMA})
        for name in PRINCIPALS:
            self._journal({"step": "principal:" + name, "phase": "intent"})
            done = self.run([*USERADD, name])
            _need(done.returncode == 0, "USERADD_FAILED:" + name)
            ids = self.accounts.user(name)
            gid = self.accounts.group(name)
            _need(ids is not None and gid is not None and ids[1] == gid and ids[0] < 1000, "PRINCIPAL_SHAPE:" + name)
            self._journal({"step": "principal:" + name, "phase": "done", "uid": ids[0], "gid": gid})
        self._journal({"step": "dir:canonical", "phase": "intent"})
        canonical = self.p(CANONICAL)
        canonical.mkdir(mode=0o700)
        os.chmod(canonical, 0o700)
        self._own(canonical)
        self._journal({"step": "dir:canonical", "phase": "done", "meta": self._created_meta("dir:canonical")})
        self._journal({"step": "dir:authority-config", "phase": "intent", "existed": facts["authorityConfigExists"]})
        done: dict[str, Any] = {"step": "dir:authority-config", "phase": "done", "existed": facts["authorityConfigExists"]}
        if not facts["authorityConfigExists"]:
            self.p(AUTHORITY_CONFIG).mkdir(mode=0o755)
            os.chmod(self.p(AUTHORITY_CONFIG), 0o755)
            self._own(self.p(AUTHORITY_CONFIG))
            done["meta"] = self._created_meta("dir:authority-config")
        self._journal(done)
        self._journal({"step": "file:deployment", "phase": "intent"})
        fd = os.open(self.p(DEPLOYMENT), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        try:
            os.write(fd, DEPLOYMENT_BYTES)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(self.p(DEPLOYMENT), 0o644)
        self._own(self.p(DEPLOYMENT))
        self._journal({"step": "file:deployment", "phase": "done",
                       "sha256": hashlib.sha256(DEPLOYMENT_BYTES).hexdigest(), "meta": self._created_meta("file:deployment")})
        after = self.live_digests()
        _need(after == facts["live"], "LIVE_FILES_CHANGED")
        self._journal({"step": "end", "result": "FOUNDATION_INSTALLED"})
        return {"result": "FOUNDATION_INSTALLED", "principals": self.recorded_principals()}

    def _own(self, path: Path) -> None:
        if self.chown:
            os.lchown(path, 0, 0)

    def _created_meta(self, step: str) -> list:
        """H-1: the Meta just created, checked against what this stage means to create, then journaled."""
        relative, kind, mode = FS_STEPS[step]
        meta, _identity = SF.observe(self.root, relative)
        integrity = hashlib.sha256(DEPLOYMENT_BYTES).hexdigest() if kind == "file" else ""
        _need(meta.kind == kind and meta.mode == mode and meta.integrity == integrity
              and (not self.chown or (meta.uid, meta.gid) == (0, 0)), "ITEM_NOT_AS_INSTALLED:" + step)
        return meta.as_list()

    def recorded_principals(self) -> dict[str, tuple[int, int]]:
        return {e["step"].split(":", 1)[1]: (e["uid"], e["gid"]) for e in self.journal()
                if e["step"].startswith("principal:") and e.get("phase") == "done"}

    # ------------------------------------------------------------------ return ---
    def return_(self, approval: str) -> dict[str, Any]:
        """Remove exactly the journaled items, in reverse. EVERY item is verified before ANY is removed, so a refused
        return changes nothing. Owner-approved, never automatic."""
        _need(approval == self.approval(), "APPROVAL_NOT_THIS_PLAN")
        self.host_guard()
        _need(os.path.isdir(self.p(STATE)) and not os.path.islink(self.p(STATE)), "NO_JOURNAL")
        with SF.HostLock(self.root, STATE):
            return self._return_locked()

    def _return_locked(self) -> dict[str, Any]:
        for stage in LATER_STAGES:                         # stages 2-5 return first (owner_prod_inert_stages)
            _need(not os.path.lexists(self.p(f"{STATE}/{stage}.journal")), "LATER_STAGE_PRESENT:" + stage)
        entries = self.journal()
        _need(bool(entries) and entries[0]["step"] == "begin", "NO_JOURNAL")
        _need(entries[0].get("schema") == JOURNAL_SCHEMA, "JOURNAL_LEGACY")
        _need(not any(e["step"] == "remove" for e in entries), "RETURN_PARTIAL")       # never resumed automatically
        intents = {e["step"] for e in entries if e.get("phase") == "intent"}
        done = {e["step"]: e for e in entries if e.get("phase") == "done"}
        recorded = self.recorded_principals()
        actions: list[tuple[str, Callable[[], None]]] = []
        # 1. verify everything (H-1: kind, mode, owner and integrity of every created path)
        verified: dict[str, tuple] = {}
        for step in ("file:deployment", "dir:authority-config", "dir:canonical"):
            relative, kind, _mode = FS_STEPS[step]
            if step not in intents:
                continue
            if step == "dir:authority-config" and done.get(step, {}).get("existed", True):
                continue                                   # it was there before stage 1: not ours to remove
            if step not in done:                           # interrupted: what exists is unverified, owner adjudication
                _need(not os.path.lexists(self.p(relative)), "ITEM_INTERRUPTED:" + step)
                continue
            expected = SF.Meta.from_journal(done[step].get("meta"), step)
            if kind == "dir":
                listing = SF.list_dir(self.root, relative)
                allowed = {"deployment.json"} if step == "dir:authority-config" else set()
                _need(set(listing) <= allowed, "CANONICAL_NOT_EMPTY" if step == "dir:canonical"
                      else "AUTHORITY_CONFIG_NOT_EMPTY")
            meta, ident = SF.observe(self.root, relative)
            if step == "file:deployment":
                _need(meta.kind == "file" and meta.integrity == hashlib.sha256(DEPLOYMENT_BYTES).hexdigest(),
                      "DEPLOYMENT_CHANGED")
            _need(meta == expected, "ITEM_CHANGED:" + step)
            verified[step] = ident
            actions.append((step, lambda r=relative, i=ident, k=kind: SF.remove_verified(self.root, r, i, k)))
        for name in reversed(PRINCIPALS):
            if "principal:" + name not in intents:
                continue
            ids, gid = self.accounts.user(name), self.accounts.group(name)
            if ids is None and gid is None:
                continue                                   # the intent was journaled, the account never created
            _need(name in recorded and ids == recorded[name] and gid == recorded[name][1], "PRINCIPAL_CHANGED:" + name)

            def delete(name: str = name) -> None:
                done = self.run([USERDEL, name])
                _need(done.returncode == 0 and self.accounts.user(name) is None
                      and self.accounts.group(name) is None, "USERDEL_FAILED:" + name)
            actions.append(("principal:" + name, delete))
        _need(self.live_digests() == entries[0]["live"], "LIVE_FILES_CHANGED")
        # 2. then act, in the verified order; every removal journaled before and after (H-2)
        removed = []
        for label, act in actions:
            if self.before_remove is not None:
                self.before_remove(label)
            self._journal({"step": "remove", "phase": "intent", "item": label})
            act()
            self._journal({"step": "remove", "phase": "done", "item": label})
            removed.append(label)
        _need(self.live_digests() == entries[0]["live"], "LIVE_FILES_CHANGED")
        self.p(JOURNAL).rename(self.p(STATE + "/foundation.journal.returned"))
        return {"result": "FOUNDATION_RETURNED", "removed": removed}


def main(argv: list[str]) -> int:
    def run(args: Sequence[str]) -> subprocess.CompletedProcess:
        return subprocess.run(list(args), capture_output=True, timeout=60, check=False, stdin=subprocess.DEVNULL,
                              env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})

    f = Foundation(Path("/"), run=run, hostname=os.uname().nodename, euid=os.geteuid(), accounts=Accounts())
    try:
        if argv == ["plan"]:
            print(f.plan_text() + f"approval {f.approval()}")
            return 0
        if len(argv) == 2 and argv[0] == "install":
            print(json.dumps(f.install(argv[1]), sort_keys=True))
            return 0
        if len(argv) == 2 and argv[0] == "return":
            print(json.dumps(f.return_(argv[1]), sort_keys=True))
            return 0
        print(__doc__)
        return 2
    except Stop as exc:
        print(f"owner_prod_inert_install: STOP {exc.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
