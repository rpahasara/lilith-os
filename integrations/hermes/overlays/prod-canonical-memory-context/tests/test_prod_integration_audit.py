"""OFFLINE: the prepared PROD integration audit (`prod_integration_audit_ro.py`) is read-only, content-free and fails
closed.

Record: docs/architecture/canonical-memory-prod-integration-plan.md §6. Nothing here contacts PROD. The audit runs
against a synthetic root (with a real WAL-mode SQLite store, live `-wal` / `-shm` files and secrets) through
injected `systemctl`, hostname and euid. Every file's bytes, mode, size, inode, mtime and atime, and every directory
listing, are compared before and after.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prod_integration_audit_ro.py"
ROOT = HERE.parents[4]
PLAN = ROOT / "docs/architecture/canonical-memory-prod-integration-plan.md"
spec = importlib.util.spec_from_file_location("prod_integration_audit_ro", SOURCE)
AUD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AUD)

LINUX = hasattr(os, "O_NOATIME")
TELEGRAM_ID = "987654321012"
SECRET_BYTES = b"S" * 32
OLD = 1_000_000_000                                       # an access time older than every mtime (relatime would bump it)


def done(code=0, out=b""):
    return subprocess.CompletedProcess([], code, out, b"")


# What systemd 255 (DEV, same Ubuntu 24.04 as PROD) prints: only the properties the unit type has. A timer has no
# MainPID or NRestarts, so a service-only schema can never be complete for a timer (the run-1 failure).
SYSTEMD_PROPS = {
    "service": {"LoadState": "loaded", "ActiveState": "active", "SubState": "running", "MainPID": "42",
                "NRestarts": "0", "UnitFileState": "enabled", "Result": "success"},
    "timer": {"LoadState": "loaded", "ActiveState": "active", "SubState": "waiting", "UnitFileState": "enabled",
              "Result": "success"},
}


def systemctl_ok(argv):
    assert argv[0] == AUD.SYSTEMCTL and argv[1] in ("show", "list-units"), argv
    if argv[1] == "show":
        known = SYSTEMD_PROPS[argv[2].rsplit(".", 1)[1]]
        wanted = [a.split("=", 1)[1] for a in argv[3:] if a.startswith("--property=")]
        return done(0, "".join(f"{k}={known[k]}\n" for k in wanted if k in known).encode())
    return done(0, b"lilith-career-watcher.service loaded failed failed Career\n")


def build(root: Path) -> None:
    h = root / AUD.HERMES
    for name in AUD.PINS:
        (h / name).parent.mkdir(parents=True, exist_ok=True)
        (h / name).write_bytes(("pinned " + name).encode())
    (h / "config.yaml").write_text(f"telegram:\n  allowed_users: [{TELEGRAM_ID}]\n", encoding="ascii")
    (h / "plugins/lilith_os").mkdir(parents=True)
    (h / "plugins/lilith_os/adapter.py").write_bytes(b"adapter")
    (h / "hermes-agent/.git").mkdir(parents=True)
    (h / "hermes-agent/.git/HEAD").write_text("f293e7206b4ddd66042329442c6afebc19a8808d\n", encoding="ascii")
    (h / "hermes-agent/venv").mkdir()
    (h / "hermes-agent/venv/pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.11.16\n", encoding="ascii")
    (h / "groq.env").write_text("GROQ_API_KEY=never-read\n", encoding="ascii")
    data = root / AUD.DATA
    data.mkdir(parents=True)
    for name in AUD.SECRETS:
        (data / name).write_bytes(SECRET_BYTES)
        os.chmod(data / name, 0o600)
    for name in AUD.STORES:
        c = sqlite3.connect(data / name)
        c.execute("pragma journal_mode=wal")
        c.execute("create table t(x)")
        c.execute("insert into t values ('private row')")
        c.commit()
        c.close()
    (h / "state.db").write_bytes(b"")
    for d in ("etc", "proc/self"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "etc/machine-id").write_text("0123456789abcdef0123456789abcdef\n", encoding="ascii")
    (root / "usr/lib").mkdir(parents=True)
    (root / "usr/lib/os-release").write_text('ID=ubuntu\nVERSION_ID="24.04"\n', encoding="ascii")
    (root / "etc/os-release").symlink_to("../usr/lib/os-release")          # exactly as on Ubuntu 24.04
    (root / "proc/meminfo").write_text("MemTotal: 2000000 kB\nMemAvailable: 900000 kB\n", encoding="ascii")
    (root / "proc/self/mounts").write_text("/dev/sda1 / ext4 rw,relatime 0 0\n", encoding="ascii")


def tree(root: Path) -> dict:
    """Everything a mutation could touch: names, bytes, mode, size, inode, mtime_ns, atime_ns."""
    out = {}
    for path in sorted(root.rglob("*")):
        st = os.lstat(path)
        digest = None
        if path.is_file() and not path.is_symlink():
            fd = os.open(path, os.O_RDONLY | os.O_NOATIME)                # the comparison itself must not bump atime
            try:
                digest = hashlib.sha256(os.read(fd, 1 << 26)).hexdigest()
            finally:
                os.close(fd)
        out[str(path.relative_to(root))] = (st.st_mode, st.st_size, st.st_ino, st.st_mtime_ns, st.st_atime_ns, digest)
    return out


def age_atimes(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            st = os.lstat(path)
            os.utime(path, ns=(OLD * 10**9, st.st_mtime_ns))


@unittest.skipUnless(LINUX, "O_NOATIME needs Linux")
class AuditRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        build(self.root)
        # one store stays busy: an open WAL writer, so its -wal and -shm exist while the audit runs
        self.live = sqlite3.connect(self.root / AUD.DATA / "lilith.db")
        self.live.execute("insert into t values ('live write')")
        self.live.commit()
        self.addCleanup(self.live.close)
        age_atimes(self.root)

    def audit(self, run=systemctl_ok, hostname="lilith-01.asia-southeast1-b.c.project.internal", euid=0, root=None):
        lines: list[str] = []
        a = AUD.Audit(root or self.root, run=run, hostname=hostname, euid=euid, out=lines.append)
        return a, a.execute(), lines

    def test_complete_run_changes_nothing_and_prints_no_content(self):
        before = tree(self.root)
        opened: list[str] = []
        real_open = os.open

        def spy(path, flags, *a, **k):
            opened.append(str(path))
            self.assertTrue(flags & os.O_NOATIME and flags & os.O_NOFOLLOW)
            self.assertFalse(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            return real_open(path, flags, *a, **k)

        with mock.patch.object(AUD.os, "open", spy):
            audit, code, lines = self.audit()
        self.assertEqual(code, 0, "\n".join(l for l in lines if l.startswith("ERR")))
        self.assertEqual(lines[-1], f"PROD_INTEGRATION_AUDIT_COMPLETE observed={audit.expected()}")
        self.assertEqual(tree(self.root), before)                              # bytes, inodes, mtimes and atimes
        text = "\n".join(lines)
        for secret in (TELEGRAM_ID, "private row", "live write", SECRET_BYTES.decode(), "never-read",
                       "0123456789abcdef"):
            self.assertNotIn(secret, text)
        for path in opened:
            self.assertFalse(path.endswith((".key", "-wal", "-shm", "-journal", "state.db", ".env")), path)
        self.assertIn("A channels telegram_allowlist_keys 1", lines)
        for line in lines:
            kind, *rest = line.split(" ")
            self.assertIn(kind, ("A", "AUDIT", "PROD_COMPAT_PASS", "PROD_COMPAT_FAIL", "PROD_INTEGRATION_AUDIT_COMPLETE"))
            self.assertLessEqual(len(rest), 3, line)

    def test_negative_control_the_no_mutation_check_detects_an_atime_change(self):
        """Without O_NOATIME the same reads bump access times on this relatime filesystem, and `tree` sees it."""
        before = tree(self.root)
        with mock.patch.object(os, "O_NOATIME", 0):
            _a, code, _lines = self.audit()
        self.assertEqual(code, 0)
        changed = [k for k, v in tree(self.root).items() if v != before.get(k)]
        if not changed:
            self.skipTest("this filesystem does not update atime on read (noatime); the control is not meaningful")
        self.assertTrue(any(k.endswith("SOUL.md") for k in changed), changed)

    def test_large_files_are_hashed_streaming_without_loading_them(self):
        """A 64 MiB file is hashed correctly while Python's peak allocation stays near one chunk."""
        import tracemalloc

        big = self.root / AUD.DATA / "big.bin"
        size = 64 << 20
        with open(big, "wb") as f:                     # the test's own fixture (sparse); the audit never writes
            f.seek(size - 1)
            f.write(b"\x01")
        want = hashlib.sha256()
        with open(big, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                want.update(block)
        audit = AUD.Audit(self.root, run=systemctl_ok, hostname="lilith-01", euid=0, out=lambda line: None)
        sizes: list[int] = []
        real_read = os.read

        def spy(fd, n):
            sizes.append(n)
            return real_read(fd, n)

        tracemalloc.start()
        try:
            with mock.patch.object(AUD.os, "read", spy):
                got = audit.sha(str(big.relative_to(self.root)))
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(got, want.hexdigest())
        self.assertEqual(set(sizes), {AUD.CHUNK})
        self.assertGreaterEqual(len(sizes), size // AUD.CHUNK)
        self.assertLess(peak, 3 * AUD.CHUNK, f"peak {peak} bytes for a {size}-byte file")

    def test_a_whole_file_read_over_the_limit_fails_closed(self):
        config = self.root / AUD.HERMES / "config.yaml"
        config.write_bytes(b"x" * (AUD.MAX_READ + 1))
        _a, code, lines = self.audit()
        self.fails_closed(lines, code, "channels telegram_allowlist_keys ValueError")
        self.assertTrue(any(l.startswith("A pin config.yaml DIFF:") for l in lines))   # hashing it still streams

    def test_run1_five_failures_reproduced_with_the_old_rules(self):
        """The PROD-shaped fixture under the run-1 rules (os-release read with O_NOFOLLOW, one service-only schema for
        every unit) gives exactly run 1's five errors; the current rules give COMPLETE."""
        def old_os_release(audit):
            fields = dict(line.split("=", 1) for line in audit.read("etc/os-release").decode("ascii").splitlines()
                          if "=" in line)
            return fields["ID"]

        service = AUD.UNIT_PROPS["service"][1:]                            # run 1: no LoadState, no per-type schema
        run1_units = ("hermes-gateway.service", "lilith-os-api.service", "lilith-morning-brief-watcher.timer",
                      "lilith-career-watcher.timer", "lilith-meeting-prep-watcher.timer", "lilith-gmail-watcher.timer",
                      "unattended-upgrades.service")
        with mock.patch.object(AUD.Audit, "os_release", old_os_release), mock.patch.object(AUD, "UNITS", run1_units), \
                mock.patch.dict(AUD.UNIT_PROPS, {"service": service, "timer": service}):
            _a, code, lines = self.audit()
        errors = sorted(l for l in lines if l.startswith("ERR "))
        self.assertEqual(code, 3)
        self.assertEqual(errors, sorted(["ERR host os OSError"] + [
            f"ERR unit {t} ValueError" for t in run1_units if t.endswith(".timer")]))
        self.assertEqual(len(errors), 5)
        _a, code, lines = self.audit()
        self.assertEqual(code, 0, [l for l in lines if l.startswith("ERR")])
        self.assertIn("A host os ubuntu-24.04", lines)
        timers = [l for l in lines if l.startswith("A unit ") and ".timer " in l]
        self.assertEqual(len(timers), 5)
        for line in timers:
            self.assertIn("LoadState=loaded|ActiveState=active|SubState=waiting|UnitFileState=enabled|Result=success",
                          line)
        self.assertTrue(any(l.startswith("A unit hermes-gateway.service LoadState=loaded|") and "MainPID=42" in l
                            for l in lines))

    def test_os_release_follows_only_the_exact_ubuntu_link(self):
        link = self.root / "etc/os-release"
        canonical = self.root / "usr/lib/os-release"
        cases = {
            "absolute link to the canonical file": ("/usr/lib/os-release", None),
            "link to another file": ("../home/lilith/.hermes/SOUL.md", "ValueError"),
            "link climbing above the root": ("../../../usr/lib/os-release", None),   # normpath stays inside the root
            "link to a near miss": ("../usr/lib/os-release.d", "ValueError"),
        }
        for label, (target, error) in cases.items():
            with self.subTest(label):
                link.unlink()
                link.symlink_to(target)
                _a, code, lines = self.audit()
                if error is None:
                    self.assertIn("A host os ubuntu-24.04", lines)
                else:
                    self.fails_closed(lines, code, f"host os {error}")
        link.unlink()
        link.symlink_to("../usr/lib/os-release")
        canonical.rename(self.root / "usr/lib/os-release.real")
        canonical.symlink_to("os-release.real")                           # a chain: the target itself is a link
        _a, code, lines = self.audit()
        self.fails_closed(lines, code, "host os OSError")
        canonical.unlink()
        (self.root / "usr/lib/os-release.real").rename(canonical)
        link.unlink()
        link.mkdir()                                                       # not a file at all
        _a, code, lines = self.audit()
        self.fails_closed(lines, code, "host os ValueError")
        link.rmdir()
        link.write_text('ID=ubuntu\nVERSION_ID="24.04"\n', encoding="ascii")    # a plain regular file is fine
        _a, code, lines = self.audit()
        self.assertEqual(code, 0)

    def test_no_other_symlink_is_followed(self):
        for relative in (AUD.HERMES + "/SOUL.md", AUD.DATA + "/lilith.db", "proc/meminfo"):
            with self.subTest(relative):
                path = self.root / relative
                saved = path.read_bytes()
                path.unlink()
                (self.root / "decoy").write_bytes(saved)
                path.symlink_to(self.root / "decoy")
                _a, code, lines = self.audit()
                self.assertEqual(code, 3)
                self.assertTrue(any(l.startswith("ERR ") and "OSError" in l for l in lines))
                path.unlink()
                path.write_bytes(saved)
                (self.root / "decoy").unlink()

    def test_a_missing_timer_is_visible_not_inactive(self):
        def run(argv):
            if argv[1] == "show" and argv[2] == "lilith-gmail-watcher.timer":
                return done(0, b"LoadState=not-found\nActiveState=inactive\nSubState=dead\nUnitFileState=\n"
                               b"Result=success\n")
            return systemctl_ok(argv)

        _a, code, lines = self.audit(run=run)
        self.assertEqual(code, 0)
        self.assertIn("A unit lilith-gmail-watcher.timer LoadState=not-found|ActiveState=inactive|SubState=dead|"
                      "UnitFileState=-|Result=success", lines)

    def matching_pins(self) -> dict:
        return {name: hashlib.sha256((self.root / AUD.HERMES / name).read_bytes()).hexdigest() for name in AUD.PINS}

    def compat_line(self, lines):
        found = [l for l in lines if l.startswith("PROD_COMPAT_")]
        self.assertEqual(len(found), 1, lines[-3:])
        self.assertEqual(lines.index(found[0]), len(lines) - 2)            # just before the COMPLETE line
        return found[0]

    def test_compat_gate_passes_only_for_the_untouched_pre_window_state(self):
        with mock.patch.dict(AUD.PINS, self.matching_pins()):
            _a, code, lines = self.audit()
        self.assertEqual(code, 0)
        self.assertEqual(self.compat_line(lines), "PROD_COMPAT_PASS")
        _a, code, lines = self.audit()                                     # the fixture's own (drifted) pins
        self.assertEqual(code, 0)
        self.assertTrue(self.compat_line(lines).startswith("PROD_COMPAT_FAIL pin:SOUL.md,"))

    def test_compat_gate_fails_on_each_disqualifying_observation(self):
        canonical = self.root / "home/lilith/.hermes/lilith-os/canonical"

        def gateway_stopped(argv):
            if argv[1] == "show" and argv[2] == "hermes-gateway.service":
                return done(0, b"LoadState=loaded\nActiveState=inactive\nSubState=dead\nMainPID=0\nNRestarts=0\n"
                               b"UnitFileState=enabled\n")
            return systemctl_ok(argv)

        def timer_missing(argv):
            if argv[1] == "show" and argv[2] == "lilith-morning-brief.timer":
                return done(0, b"LoadState=not-found\nActiveState=inactive\nSubState=dead\nUnitFileState=\n"
                               b"Result=success\n")
            return systemctl_ok(argv)

        cases = (("present:/home/lilith/.hermes/lilith-os/canonical", lambda: canonical.mkdir(parents=True), systemctl_ok),
                 ("not_running:hermes-gateway.service", lambda: None, gateway_stopped),
                 ("unit_not_loaded:lilith-morning-brief.timer", lambda: None, timer_missing))
        for reason, prepare, run in cases:
            with self.subTest(reason):
                prepare()
                with mock.patch.dict(AUD.PINS, self.matching_pins()):
                    _a, code, lines = self.audit(run=run)
                self.assertEqual(code, 0)                                 # a gate verdict, never an audit error
                self.assertIn(reason, self.compat_line(lines))
                if canonical.exists():
                    canonical.rmdir()

    def test_no_compat_verdict_on_an_incomplete_run(self):
        (self.root / AUD.HERMES / "SOUL.md").unlink()
        _a, code, lines = self.audit()
        self.assertEqual(code, 3)
        self.assertFalse(any(l.startswith("PROD_COMPAT_") for l in lines))

    def test_live_wal_and_shm_files_are_only_lstat_ed(self):
        data = self.root / AUD.DATA
        self.assertTrue((data / "lilith.db-wal").exists() and (data / "lilith.db-shm").exists())
        keys = [str((data / n).relative_to(self.root)) for n in ("lilith.db-wal", "lilith.db-shm")]
        before = {k: tree(self.root)[k] for k in keys}
        with mock.patch.object(sqlite3, "connect", side_effect=AssertionError("the audit opened SQLite")):
            _a, code, lines = self.audit()
        self.assertEqual(code, 0)
        self.assertEqual({k: tree(self.root)[k] for k in keys}, before)
        self.assertTrue(any(l.startswith("A store_companions lilith.db wal=") and "shm=" in l for l in lines))

    def fails_closed(self, lines, code, needle):
        self.assertEqual(code, 3, lines[-1])
        self.assertTrue(lines[-1].startswith("PROD_INTEGRATION_AUDIT_INCOMPLETE errors="), lines[-1])
        self.assertFalse(any("AUDIT_COMPLETE" in l for l in lines))
        self.assertTrue(any(l.startswith("ERR ") and needle in l for l in lines), [l for l in lines if "ERR" in l])

    def test_a_missing_pinned_file_fails_closed(self):
        (self.root / AUD.HERMES / "SOUL.md").unlink()
        _a, code, lines = self.audit()
        self.fails_closed(lines, code, "pin SOUL.md FileNotFoundError")

    def test_a_permission_error_fails_closed(self):
        real_open = os.open

        def denied(path, *a, **k):
            if str(path).endswith("router.yaml"):
                raise PermissionError(13, "denied")
            return real_open(path, *a, **k)

        with mock.patch.object(AUD.os, "open", denied):
            _a, code, lines = self.audit()
        self.fails_closed(lines, code, "PermissionError")

    def test_a_symlinked_file_is_refused_not_followed(self):
        target = self.root / AUD.HERMES / "memories/USER.md"
        target.unlink()
        target.symlink_to(self.root / AUD.DATA / "actor_authority.key")
        _a, code, lines = self.audit()
        self.fails_closed(lines, code, "pin memories/USER.md OSError")

    def test_failed_empty_or_incomplete_commands_fail_closed(self):
        cases = {
            "rc": lambda argv: done(1),
            "empty": lambda argv: done(0, b""),
            "partial": lambda argv: done(0, b"ActiveState=active\n") if argv[1] == "show" else systemctl_ok(argv),
            "timeout": lambda argv: (_ for _ in ()).throw(subprocess.TimeoutExpired(argv, 30)),
        }
        for label, run in cases.items():
            with self.subTest(label):
                _a, code, lines = self.audit(run=run)
                self.fails_closed(lines, code, "unit")

    def test_unsafe_or_unparseable_values_fail_closed(self):
        (self.root / "etc/os-release").write_text('ID=ubuntu\nVERSION_ID="24.04 LTS; rm -rf"\n', encoding="ascii")
        (self.root / "proc/meminfo").write_text("garbage\n", encoding="ascii")
        _a, code, lines = self.audit()
        self.fails_closed(lines, code, "host os ValueError")
        self.assertTrue(any(l.startswith("ERR host memory") for l in lines))
        self.assertFalse(any("rm -rf" in l for l in lines))

    def test_any_exception_in_an_observation_is_recorded_not_fatal(self):
        with mock.patch.object(AUD.Audit, "hermes_commit", side_effect=RuntimeError("boom")):
            _a, code, lines = self.audit()
        self.fails_closed(lines, code, "hermes commit RuntimeError")
        self.assertTrue(any(l.startswith("A unit failed ") for l in lines))     # later observations still ran

    def test_a_missing_observation_is_incomplete_even_without_an_err(self):
        with mock.patch.object(AUD.Audit, "expected", return_value=10_000):
            _a, code, lines = self.audit()
        self.assertEqual(code, 3)
        self.assertTrue(lines[-1].startswith("PROD_INTEGRATION_AUDIT_INCOMPLETE errors=0"))

    def test_refusals_happen_before_any_other_read(self):
        dev_root = Path(tempfile.mkdtemp(dir=self.tmp.name))
        build(dev_root)
        (dev_root / "etc/machine-id").write_bytes(b"ae929170e6fa4c8ab9cc7b9547238d9d\n")
        for label, kwargs, root in (("dev host name", {"hostname": "lilith-dev-01"}, self.root),
                                    ("dev machine", {"hostname": "lilith-01"}, dev_root),
                                    ("not root", {"euid": 1000}, self.root)):
            with self.subTest(label):
                reads: list[str] = []
                real_open = os.open

                def spy(path, *a, **k):
                    reads.append(str(path))
                    return real_open(path, *a, **k)

                with mock.patch.object(AUD.os, "open", spy):
                    _a, code, lines = self.audit(root=root, **kwargs)
                self.assertEqual(code, 2)
                self.assertEqual(len(lines), 1)
                self.assertTrue(lines[0].startswith("PROD_INTEGRATION_AUDIT_REFUSED"), lines)
                self.assertEqual([r for r in reads if not r.endswith("etc/machine-id")], [])

    def test_pin_match_and_drift_are_findings_not_errors(self):
        target = self.root / AUD.HERMES / "SOUL.md"
        want = hashlib.sha256(target.read_bytes()).hexdigest()
        with mock.patch.dict(AUD.PINS, {"SOUL.md": want}):
            _a, code, lines = self.audit()
        self.assertEqual(code, 0)
        self.assertIn(f"A pin SOUL.md MATCH:{want}", lines)
        self.assertTrue(any(l.startswith("A pin memories/USER.md DIFF:") for l in lines))


class StaticTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text(encoding="utf-8")
        self.code = self.source.split('"""', 2)[2]                            # everything after the module docstring

    def test_no_sqlite_no_write_no_shell_no_network(self):
        allowed = {"open(": self.code.count("os.open("), "replace(": self.code.count('.replace(" ", "-")')}
        for needle in ("sqlite", ".connect(", "open(", "write", "unlink", "rename", "replace(", "mkdir", "chmod",
                       "chown", "remove", "rmtree", "shell=True", "os.system", "popen", "socket", "urllib", "http",
                       "requests", "immutable", "utime", "truncate"):
            self.assertEqual(self.code.count(needle), allowed.get(needle, 0), needle)

    def test_the_only_subprocess_is_systemctl_show_or_list_units(self):
        self.assertEqual(self.code.count("subprocess.run("), 1)
        self.assertEqual(re.findall(r'self\.systemctl\("([a-z-]+)"', self.code), ["show", "list-units"])
        self.assertIn('SYSTEMCTL = "/usr/bin/systemctl"', self.code)

    def test_reads_use_noatime_nofollow_readonly(self):
        self.assertIn("os.O_RDONLY | os.O_NOATIME | os.O_NOFOLLOW", self.code)
        self.assertEqual(self.code.count("os.open("), 1)
        # the one symlink exception: read in os_release only, for exactly the Ubuntu os-release link
        self.assertEqual(self.code.count("os.readlink("), 1)
        body = self.code.split("def os_release", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("os.readlink(self.p(OS_RELEASE))", body)
        self.assertIn('OS_RELEASE, OS_RELEASE_CANONICAL = "etc/os-release", "usr/lib/os-release"', self.code)
        self.assertNotIn("realpath(self.p(OS_RELEASE", self.code)

    def test_timer_names_are_the_preserved_prod_units(self):
        preserved = sorted(p.name for p in (ROOT / "integrations/hermes/history/prod/systemd").glob("*.timer"))
        self.assertEqual(sorted(u for u in AUD.UNITS if u.endswith(".timer")), preserved)
        self.assertNotIn("lilith-morning-brief-watcher.timer", AUD.UNITS)
        self.assertNotIn("lilith-meeting-prep-watcher.timer", AUD.UNITS)
        self.assertFalse((HERE.parent / "prod_compat_ro.sh").exists())  # superseded by the helper's gate (no SQLite)

    def test_unit_schemas_cover_every_audited_unit_type(self):
        self.assertEqual({u.rsplit(".", 1)[1] for u in AUD.UNITS}, set(AUD.UNIT_PROPS))
        self.assertNotIn("MainPID", AUD.UNIT_PROPS["timer"])
        self.assertNotIn("NRestarts", AUD.UNIT_PROPS["timer"])
        for schema in AUD.UNIT_PROPS.values():
            self.assertEqual(schema[0], "LoadState")

    def test_secrets_credentials_and_history_are_never_read(self):
        for name in ("groq.env", "auth.json", '/.env'):
            self.assertNotIn(name, self.code)
        self.assertIn('SECRETS = ("actor_authority.key", "privacy_authority.key")  # lstat only', self.code)
        self.assertIn('STORE_META_ONLY = ("state.db",)', self.code)

    def test_pins_are_full_sha256_and_named_in_the_plan(self):
        plan = PLAN.read_text(encoding="utf-8")
        for name, pin in AUD.PINS.items():
            self.assertRegex(pin, r"\A[0-9a-f]{64}\Z", name)
        for value in (AUD.PINS["lilith_router/gateway_integration.py"], "88a1168bd41797109772ffce7df7352c1ae40e4c",
                      "072001af671feca6564906d3d685f89bfc608f9d595aed58bae0f72a25777684",
                      "53ae457b8b907e12282ed468da0387620b7a376a46ab1c450709b67540b43c07",
                      "99fe90649e316ef992db7c05575c19eafe56e703d505f44f39c5577903fe9587"):
            self.assertIn(value, plan)

    def test_prepared_not_run_and_prod_only(self):
        self.assertIn("PREPARED, NOT RUN", self.source.splitlines()[1])
        self.assertEqual(AUD.PROD_HOST, "lilith-01")


if __name__ == "__main__":
    unittest.main()
