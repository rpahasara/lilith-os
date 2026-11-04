#!/usr/bin/env python3
"""PROD read-only integration audit for canonical memory (PREPARED, NOT RUN; one separate owner approval). lilith-01 only.

Record: docs/architecture/canonical-memory-prod-integration-plan.md §6. Run as root with the system interpreter, from
stdin, so nothing is written to disk and no bytecode is cached:

    sudo -n /usr/bin/python3 -I -B -        (the operator pipes this file, pinned by its SHA-256)

Guarantees:
- **No SQLite database is opened.** The live stores are judged by byte digest and file metadata only. That includes
  their `-wal` / `-shm` companions, which are only `lstat`ed, so no lock, journal, WAL or shared-memory file can be
  created or changed. Under D-7 (isolated canonical store) their schema is not needed. A schema or row-count reading,
  if ever needed, comes from an isolated copy of an existing snapshot, never from the live files.
- **No access time is changed; hashing streams.** Every file is read with `O_RDONLY | O_NOATIME | O_NOFOLLOW` in
  1 MiB chunks; SHA-256 is streamed (one chunk in memory at a time) and a whole-file read is refused over 4 MiB; without `O_NOATIME`
  the audit refuses. No symlink is ever followed or read (no `readlink`: reading a link bumps the link's own atime,
  which `O_NOATIME` cannot prevent). For Ubuntu's `/etc/os-release` link the audit only `lstat`s it (its size must be
  the length of `../usr/lib/os-release` or `/usr/lib/os-release`) and reads the canonical `/usr/lib/os-release`
  (os-release(5)'s fallback) directly with `O_NOFOLLOW`, so a different link target can never redirect the read.
- **Units by type:** a service is read as LoadState, ActiveState, SubState, MainPID, NRestarts and UnitFileState; a
  timer as LoadState, ActiveState, SubState, UnitFileState and Result. A missing unit shows as `LoadState=not-found`.
- **Nothing is written:** no file, directory, socket or unit change. The only subprocesses are
  `/usr/bin/systemctl show` and `/usr/bin/systemctl list-units`, with fixed arguments.
- **Content-free output:** SHA-256 digests, sizes, modes, counts, versions and states only. Every printed value must
  match `SAFE`; anything else is an error. Secrets are `lstat`ed only; the Telegram allowlist is printed as a count;
  the machine ID as a SHA-256.
- **Fail closed:** a missing file, permission error, empty result, failed command, unparseable value or any
  exception is an `ERR` line. The final line is `PROD_INTEGRATION_AUDIT_COMPLETE` (exit 0) only when there are zero
  errors and every expected observation was made; otherwise it is `PROD_INTEGRATION_AUDIT_INCOMPLETE` (exit 3). A
  wrong host, a non-root run or a missing `O_NOATIME` refuses before anything is read (exit 2).

A `PIN … DIFF` is a finding (PROD drifted from the recorded pin), not an audit error.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

SAFE = re.compile(r"[A-Za-z0-9._:/=,|+@-]{1,240}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PROD_HOST = "lilith-01"
DEV_MACHINE_ID_SHA256 = hashlib.sha256(b"ae929170e6fa4c8ab9cc7b9547238d9d\n").hexdigest()   # refuse the DEV VM
HERMES = "home/lilith/.hermes"
DATA = HERMES + "/lilith-os/data"
SYSTEMCTL = "/usr/bin/systemctl"
CHUNK = 1 << 20                   # bounded read size (1 MiB); hashing streams, never loads a whole file
MAX_READ = 4 << 20                # whole-file reads are only for small text metadata files

# The exact pins recorded by the last accepted PROD windows (Cutover 2 2026-11-03, T4 wording fix 2026-11-04).
PINS = {
    "SOUL.md": "d082db5aa1a8745460c1c3a3edebaf6fcd196336f5e1a5e8ef7108303bda5ccd",
    "memories/USER.md": "6d7804efb32b158105e017e38857abc09ea6c44b5fb6f39636840c290b792d9c",
    "memories/MEMORY.md": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "config.yaml": "26bb4accd8a1578dfa3d80f46805c7af576a4f4b508d4c73d982aee0909137a1",
    "lilith_router/router.yaml": "ff1d5dc722b70d0dd97dd4adc882b9b2a55586b7058c89d951f7de27287c79e9",
    "lilith_router/gateway_integration.py": "4db8bb58da3fbdef80fb550c74709bb3ea62c605afadec56aa96b28d2568ca8b",
    "lilith_router/social_lean.py": "5c4c2d1fb113d53c43f34f7611c635a62209f2b41d74457887c835e540f6e410",
    "lilith_router/social_guard.py": "3a0906b5d6054ffed18b25f2babf315d51cff9a77f9ff68f46e4b9984beb9c98",
    "lilith_router/policy.py": "932971678e1698313b5318bbb5ae9d20c2ef00a7740ea5ab30fbc617672aeb91",
    "lilith_router/config.py": "69e839ad2d48d1de805687a4f3f42fa85d0c24f8e3adaada88ede5087dc6df56",
    "lilith_router/state.py": "8c93b81cfe777e4e9907384c198273722ad4cb5ca5c48b1684a84487185967d6",
    "lilith_router/world_context.py": "91deea9761d41a94c2c5d0f28a5ebccbf9b3cbb04cf721a1daac037d95ac7b00",
    "lilith_router/_prod_world_context.py": "ebe62158fc162319e4c56d19ffec4b5ded9ab3d1e77faf65b3b9e769f5d52f02",
    "lilith_router/ethics.py": "d6a1c20b45557169a4fefa7b5d81907da0e0ae12519f8c63724900ac8ce47dbd",
    "lilith_router/motivation.py": "fd6c11898bce7c40d374713e270c1d3b9a6823e456f3efd70ec3e21d27a2fe42",
    "lilith_router/planning.py": "4c74337d76fdd76947c21fb654b4463f6acd1a39db3670737427cf9fb0647e5b",
    "lilith_router/workspace.py": "d79f67e1c761d6d98e689074d7e101e97fcc3b23cecfeba551cf2aaefd5ec597",
    "hermes-agent/gateway/run.py": "31fef97d1a3f31b34baac87190b5eaad8b4384fcd96bd9f0977eefe77aea1f92",
    "hermes-agent/gateway/session.py": "63559a0380887ac9b48ed5db5223f2a35fb8eaa33dbff613ec36c110b804cb93",
    "hermes-agent/hermes_state.py": "adff66984b57b1bb4843d154996ea77afa85984890fe9845ec9b80d630193173",
    "hermes-agent/run_agent.py": "b6aa4da0b9e1f8248fa403709fe363decfb192bc31b1135ca9012fab8971163f",
    "lilith-os/api/app.py": "53dfae2aed84004c8ef2f24a4a07003b3864d700cba6e7eeaeb2bee8e20f44d2",
}
RECORDED_ONLY = ("plugins/lilith_os/adapter.py",)          # pinned only by prefix in the records (39fa27b9)
STORES = ("cognitive_memory.db", "privacy_governance.db", "lilith.db")     # digest + metadata; never opened by SQLite
STORE_META_ONLY = ("state.db",)                            # Hermes history: metadata only (it changes every turn)
SECRETS = ("actor_authority.key", "privacy_authority.key")  # lstat only
ABSENT = ("etc/lilith-authority-dev", "opt/lilith-authority-dev", "opt/lilith-first-memory-dev",
          "etc/lilith-first-memory-dev", "usr/local/lib/lilith-canonical-context", "var/lib/lilith-authority-dev",
          "run/lilith-privacy-fresh", "run/lilith-first-memory-context.sock", "home/lilith/.hermes/lilith-os/canonical",
          HERMES + "/lilith_router/canonical_memory.py", HERMES + "/lilith_router/canonical_memory.json")
# The installer's real service principals (install_authority_dev.SERVICE_USER / WITNESS_USER; names keep the -dev
# naming debt). Runs 1 and 2 checked guessed names (lilith-authority, -witness, -broker, -forget): not evidence.
PRINCIPALS = ("lilith-authority-dev", "lilith-recovery-witness")
IDS = (985, 995)
# Timer names from the repository's preserved PROD units (integrations/hermes/history/prod/systemd/*.timer); audit
# run 2 showed that the two earlier guesses (`lilith-morning-brief-watcher`, `lilith-meeting-prep-watcher`) do not exist.
UNITS = ("hermes-gateway.service", "lilith-os-api.service", "lilith-agenda-snapshot.timer",
         "lilith-career-watcher.timer", "lilith-gmail-watcher.timer", "lilith-meeting-prep.timer",
         "lilith-morning-brief.timer", "unattended-upgrades.service")
# The pre-window compatibility gate (R3d; replaces prod_compat_ro.sh, which opened SQLite): judged only on a COMPLETE
# run, from the run's own observations. Services that must be running before any canonical-memory window:
GATE_RUNNING = ("hermes-gateway.service", "lilith-os-api.service")
# Per unit type: systemd prints only the properties a unit type has (a timer has no MainPID / NRestarts). LoadState
# makes a missing unit (`not-found`, otherwise shown as inactive) visible.
UNIT_PROPS = {
    "service": ("LoadState", "ActiveState", "SubState", "MainPID", "NRestarts", "UnitFileState"),
    "timer": ("LoadState", "ActiveState", "SubState", "UnitFileState", "Result"),
}
# Ubuntu's /etc/os-release is a link to ../usr/lib/os-release. The audit never follows or reads the link: it lstats it
# (the size of a symlink is the length of its target) and reads the canonical file itself.
OS_RELEASE, OS_RELEASE_CANONICAL = "etc/os-release", "usr/lib/os-release"
OS_RELEASE_LINK_SIZES = (len("../usr/lib/os-release"), len("/usr/lib/os-release"))


class Refused(Exception):
    pass


class Audit:
    def __init__(self, root: Path, *, run: Callable[[Sequence[str]], subprocess.CompletedProcess], hostname: str,
                 euid: int, out: Callable[[str], None] = print):
        self.root, self.run, self.hostname, self.euid, self.out = root, run, hostname, euid, out
        self.errors: list[str] = []
        self.values: dict[tuple[str, str], str] = {}
        self.count = 0

    # ------------------------------------------------------------------ reads ---
    def p(self, relative: str) -> Path:
        return self.root / relative

    def chunks(self, relative: str) -> Iterator[bytes]:
        """The file in bounded chunks (CHUNK bytes), without following a symlink and without changing its access
        time. The single open in this module."""
        fd = os.open(self.p(relative), os.O_RDONLY | os.O_NOATIME | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
        try:
            while True:
                chunk = os.read(fd, CHUNK)
                if not chunk:
                    return
                yield chunk
        finally:
            os.close(fd)

    def read(self, relative: str) -> bytes:
        """A small text file whole (config, os-release, /proc, git and venv metadata); over MAX_READ is an error."""
        parts, size = [], 0
        for chunk in self.chunks(relative):
            size += len(chunk)
            if size > MAX_READ:
                raise ValueError("FILE_TOO_LARGE_TO_READ")
            parts.append(chunk)
        return b"".join(parts)

    def sha(self, relative: str) -> str:
        """Streaming SHA-256: at most one CHUNK is held at a time, whatever the file size."""
        digest = hashlib.sha256()
        for chunk in self.chunks(relative):
            digest.update(chunk)
        return digest.hexdigest()

    # ------------------------------------------------------------- recording ---
    def emit(self, kind: str, section: str, name: str, value: object) -> None:
        text = str(value)
        if not SAFE.fullmatch(text) or not SAFE.fullmatch(section) or not SAFE.fullmatch(name):
            raise ValueError("UNSAFE_VALUE")
        self.out(f"{kind} {section} {name} {text}")

    def obs(self, section: str, name: str, fn: Callable[[], object]) -> None:
        self.count += 1
        try:
            value = fn()
            if value is None or value == "" or value == []:
                raise ValueError("EMPTY")
            self.emit("A", section, name, value)
            self.values[(section, name)] = str(value)
        except Exception as exc:  # noqa: BLE001 - every failure is recorded, never swallowed
            self.errors.append(f"{section}/{name}")
            self.out(f"ERR {section} {name} {type(exc).__name__}")

    def pin(self, name: str, want: str) -> None:
        def check() -> str:
            got = self.sha(f"{HERMES}/{name}")
            return ("MATCH:" if got == want else "DIFF:") + got
        self.obs("pin", name, check)

    # ---------------------------------------------------------------- guards ---
    def guard(self) -> None:
        if self.euid != 0:
            raise Refused("NOT_ROOT")
        if not hasattr(os, "O_NOATIME"):
            raise Refused("NO_O_NOATIME")
        if self.hostname.split(".", 1)[0] != PROD_HOST:
            raise Refused("WRONG_HOST")
        if self.sha("etc/machine-id") == DEV_MACHINE_ID_SHA256:
            raise Refused("DEV_MACHINE")

    # ---------------------------------------------------------------- probes ---
    def systemctl(self, *args: str) -> str:
        result = self.run([SYSTEMCTL, *args])
        if result.returncode != 0:
            raise RuntimeError("SYSTEMCTL_RC")
        return result.stdout.decode("ascii")

    def unit(self, name: str) -> str:
        schema = UNIT_PROPS[name.rsplit(".", 1)[1]]                         # KeyError for any other unit type
        text = self.systemctl("show", name, *(f"--property={p}" for p in schema))
        props = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
        if set(props) != set(schema):
            raise ValueError("UNIT_INCOMPLETE")
        return "|".join(f"{p}={props[p] or '-'}" for p in schema)

    def failed_units(self) -> str:
        text = self.systemctl("list-units", "--state=failed", "--no-legend", "--plain", "--no-pager")
        names = sorted(line.split()[0] for line in text.splitlines() if line.strip())
        return "count=%d%s" % (len(names), "," + ",".join(names) if names else "")

    def meminfo(self) -> str:
        fields = dict(line.split(":", 1) for line in self.read("proc/meminfo").decode("ascii").splitlines() if ":" in line)
        total, available = (int(fields[k].split()[0]) // 1024 for k in ("MemTotal", "MemAvailable"))
        return f"total_mb={total},available_mb={available}"

    def disk(self) -> str:
        st = os.statvfs(self.root)
        return f"total_mb={st.f_blocks * st.f_frsize >> 20},free_mb={st.f_bavail * st.f_frsize >> 20}"

    def mount_atime(self) -> str:
        for line in self.read("proc/self/mounts").decode("ascii", "replace").splitlines():
            parts = line.split()
            if len(parts) > 3 and parts[1] == "/":
                options = [o for o in parts[3].split(",") if o in ("noatime", "relatime", "strictatime", "nodiratime")]
                return ",".join(options) or "default-relatime"
        raise ValueError("ROOT_MOUNT_NOT_FOUND")

    def os_release(self) -> str:
        """`etc/os-release` when it is a regular file; when it is a symlink of exactly the Ubuntu target length, the
        canonical `usr/lib/os-release`, read directly with O_NOFOLLOW (the link is lstat-ed only, never followed or read,
        so its atime is untouched and its target cannot redirect the read). Anything else is an error."""
        relative = OS_RELEASE
        st = os.lstat(self.p(OS_RELEASE))
        if stat.S_ISLNK(st.st_mode):
            if st.st_size not in OS_RELEASE_LINK_SIZES:
                raise ValueError("OS_RELEASE_LINK_UNEXPECTED")
            relative = OS_RELEASE_CANONICAL
        elif not stat.S_ISREG(st.st_mode):
            raise ValueError("OS_RELEASE_NOT_REGULAR")
        fields = dict(line.split("=", 1) for line in self.read(relative).decode("ascii").splitlines()
                      if "=" in line)
        return f"{fields['ID'].strip(chr(34))}-{fields['VERSION_ID'].strip(chr(34))}"

    def hermes_commit(self) -> str:
        base = os.path.realpath(self.p(f"{HERMES}/hermes-agent"))
        rel = os.path.relpath(base, self.root)
        head = self.read(f"{rel}/.git/HEAD").decode("ascii").strip()
        if HEX64.fullmatch(head) or re.fullmatch(r"[0-9a-f]{40}", head):
            return head
        ref = head.split("ref: ", 1)[1]
        try:
            return self.read(f"{rel}/.git/{ref}").decode("ascii").strip()
        except FileNotFoundError:
            packed = self.read(f"{rel}/.git/packed-refs").decode("ascii")
            return next(line.split()[0] for line in packed.splitlines() if line.endswith(" " + ref))

    def venv_version(self) -> str:
        base = os.path.relpath(os.path.realpath(self.p(f"{HERMES}/hermes-agent")), self.root)
        cfg = self.read(f"{base}/venv/pyvenv.cfg").decode("ascii")
        return next(line.split("=", 1)[1].strip() for line in cfg.splitlines()
                    if line.split("=", 1)[0].strip() in ("version", "version_info"))

    def meta(self, relative: str) -> str:
        st = os.lstat(self.p(relative))
        if not stat.S_ISREG(st.st_mode):
            raise ValueError("NOT_REGULAR")
        return f"bytes={st.st_size},mode={stat.S_IMODE(st.st_mode):o},uid={st.st_uid},mtime={int(st.st_mtime)}"

    def companions(self, relative: str) -> str:
        """`-wal` / `-shm` beside a store: lstat only (never opened)."""
        parts = []
        for suffix in ("-wal", "-shm", "-journal"):
            try:
                parts.append(f"{suffix[1:]}={os.lstat(self.p(relative + suffix)).st_size}")
            except FileNotFoundError:
                parts.append(f"{suffix[1:]}=absent")
        return ",".join(parts)

    def absent(self, relative: str) -> str:
        return "PRESENT" if os.path.lexists(self.p(relative)) else "absent"

    def allowlist_count(self) -> int:
        text = self.read(f"{HERMES}/config.yaml").decode("utf-8", "replace")
        return len(re.findall(r"(?m)^\s*(allowed_users|allowed_user_ids|allow_from)\s*:", text)) or 0

    # ----------------------------------------------------------------- audit ---
    def observations(self) -> Iterable[tuple[str, str, Callable[[], object]]]:
        yield "host", "machine_id_sha256", lambda: self.sha("etc/machine-id")
        yield "host", "os", self.os_release
        yield "host", "kernel", lambda: os.uname().release
        yield "host", "system_python", lambda: "%d.%d.%d" % sys.version_info[:3]
        yield "host", "glibc", lambda: os.confstr("CS_GNU_LIBC_VERSION").replace(" ", "-")
        yield "host", "nproc", lambda: os.cpu_count()
        yield "host", "memory", self.meminfo
        yield "host", "disk", self.disk
        yield "host", "root_mount_atime", self.mount_atime
        yield "hermes", "commit", self.hermes_commit
        yield "hermes", "venv_python", self.venv_version
        for name in RECORDED_ONLY:
            yield "recorded", name, lambda name=name: self.sha(f"{HERMES}/{name}")
        for name in STORES:
            yield "store", name, lambda name=name: f"sha256={self.sha(f'{DATA}/{name}')},{self.meta(f'{DATA}/{name}')}"
            yield "store_companions", name, lambda name=name: self.companions(f"{DATA}/{name}")
        for name in STORE_META_ONLY:
            yield "store", name, lambda name=name: self.meta(f"{HERMES}/{name}")
            yield "store_companions", name, lambda name=name: self.companions(f"{HERMES}/{name}")
        for name in SECRETS:
            yield "secret_meta", name, lambda name=name: self.meta(f"{DATA}/{name}")
        for relative in ABSENT:
            yield "absent", "/" + relative, lambda relative=relative: self.absent(relative)
        import grp
        import pwd

        for name in PRINCIPALS:
            yield "principal", name, lambda name=name: "user=%s,group=%s" % (
                _exists(pwd.getpwnam, name), _exists(grp.getgrnam, name))
        for number in IDS:
            yield "id_in_use", str(number), lambda number=number: "uid=%s,gid=%s" % (
                _exists(pwd.getpwuid, number), _exists(grp.getgrgid, number))
        for name in UNITS:
            yield "unit", name, lambda name=name: self.unit(name)
        yield "unit", "failed", self.failed_units
        yield "channels", "telegram_allowlist_keys", self.allowlist_count

    def compat_failures(self) -> list[str]:
        """Why PROD is not in the state a canonical-memory window may start from (empty = PASS). A gate, not an error:
        the audit stays COMPLETE either way."""
        failures = []
        for name in PINS:
            if not self.values.get(("pin", name), "").startswith("MATCH:"):
                failures.append("pin:" + name)
        for relative in ABSENT:
            if self.values.get(("absent", "/" + relative)) != "absent":
                failures.append("present:/" + relative)
        for name in PRINCIPALS:
            if self.values.get(("principal", name)) != "user=no,group=no":
                failures.append("principal:" + name)
        for name in UNITS:
            if not self.values.get(("unit", name), "").startswith("LoadState=loaded|"):
                failures.append("unit_not_loaded:" + name)
        for name in GATE_RUNNING:
            if "|ActiveState=active|SubState=running|" not in self.values.get(("unit", name), ""):
                failures.append("not_running:" + name)
        return failures

    def expected(self) -> int:
        return len(PINS) + sum(1 for _ in self.observations())

    def execute(self) -> int:
        try:
            self.guard()
        except (Refused, OSError) as exc:
            self.out(f"PROD_INTEGRATION_AUDIT_REFUSED {exc.args[0] if exc.args else type(exc).__name__}")
            return 2
        self.out(f"AUDIT host={PROD_HOST} schema=1")
        for name, want in PINS.items():
            self.pin(name, want)
        for section, name, fn in self.observations():
            self.obs(section, name, fn)
        expected = self.expected()
        if self.errors or self.count != expected:
            self.out(f"PROD_INTEGRATION_AUDIT_INCOMPLETE errors={len(self.errors)} observed={self.count} "
                     f"expected={expected}")
            return 3
        failures = self.compat_failures()
        self.out("PROD_COMPAT_PASS" if not failures else "PROD_COMPAT_FAIL " + ",".join(failures))
        self.out(f"PROD_INTEGRATION_AUDIT_COMPLETE observed={self.count}")
        return 0


def _exists(lookup: Callable[[object], object], key: object) -> str:
    try:
        lookup(key)
        return "yes"
    except KeyError:
        return "no"


def _run(argv: Sequence[str]) -> subprocess.CompletedProcess:
    return subprocess.run(list(argv), capture_output=True, timeout=30, check=False, stdin=subprocess.DEVNULL,
                          env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "SYSTEMD_PAGER": "", "SYSTEMD_COLORS": "0"})


def main() -> int:
    return Audit(Path("/"), run=_run, hostname=os.uname().nodename, euid=os.geteuid()).execute()


if __name__ == "__main__":
    sys.exit(main())
