"""R3b/R3g OFFLINE: the OWNER_PROD inert install foundation on a PROD-shaped synthetic host.

Record: docs/architecture/canonical-memory-prod-integration-plan.md R3b, R3g. The host mirrors audit run 2: system ids
996-999 taken and gid 995 taken (as on lilith-01), LILITH's live identity, router, stores and 15B2a keys present.
`useradd` / `userdel` are simulated against synthetic account tables; nothing touches a real host.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location("owner_prod_inert_install",
                                              ROOT / "services/owner-memory-control/tools/owner_prod_inert_install.py")
INST = importlib.util.module_from_spec(spec)
spec.loader.exec_module(INST)
LINUX = hasattr(os, "O_NOATIME")


def done(code=0):
    return subprocess.CompletedProcess([], code, b"", b"")


class FakeAccounts(INST.Accounts):
    """PROD-shaped: system uids 996-999 and gid 995 are already taken (audit run 2: gid 995 in use)."""

    def __init__(self):
        self.users = {"systemd-a": (999, 999), "systemd-b": (998, 998), "chrony": (997, 997), "tss": (996, 996)}
        self.groups = {"systemd-a": 999, "systemd-b": 998, "chrony": 997, "tss": 996, "taken-995": 995}

    def user(self, name):
        return self.users.get(name)

    def group(self, name):
        return self.groups.get(name)


class FakeRunner:
    def __init__(self, accounts: FakeAccounts, fail_on: str | None = None, during=None):
        self.accounts, self.fail_on, self.during, self.calls = accounts, fail_on, during, []

    def __call__(self, argv):
        argv = list(argv)
        self.calls.append(argv)
        name = argv[-1]
        if argv[:len(INST.USERADD)] == list(INST.USERADD):
            if name == self.fail_on:
                return done(1)
            used = {u for u, _g in self.accounts.users.values()} | set(self.accounts.groups.values())
            n = next(i for i in range(999, 100, -1) if i not in used)       # the highest free system id, as useradd
            self.accounts.users[name], self.accounts.groups[name] = (n, n), n
            if self.during:
                self.during()
            return done(0)
        if argv[0] == INST.USERDEL:
            self.accounts.users.pop(name, None)
            self.accounts.groups.pop(name, None)
            return done(0)
        raise AssertionError(argv)


def tree(root: Path) -> dict:
    out, stack = {}, [root]
    while stack:
        top = stack.pop()
        with os.scandir(top) as it:
            for e in it:
                st = os.lstat(e.path)
                key = os.path.relpath(e.path, root)
                if e.is_dir(follow_symlinks=False):
                    out[key] = ("dir", st.st_mode, sorted(os.listdir(e.path)))
                    stack.append(Path(e.path))
                elif e.is_symlink():
                    out[key] = ("link", st.st_mode, os.readlink(e.path))
                else:
                    out[key] = (st.st_mode, st.st_size, st.st_mtime_ns, hashlib.sha256(Path(e.path).read_bytes()).hexdigest())
    return out


@unittest.skipUnless(LINUX, "O_NOATIME needs Linux")
class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for relative in INST.LIVE:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"live " + relative.encode())
        (self.root / "etc").mkdir(exist_ok=True)
        (self.root / "etc/machine-id").write_text("0123456789abcdef0123456789abcdef\n", encoding="ascii")
        (self.root / "var/lib").mkdir(parents=True)
        self.accounts = FakeAccounts()
        self.run = FakeRunner(self.accounts)

    def f(self, **kw) -> INST.Foundation:
        args = dict(run=self.run, hostname="lilith-01.asia-southeast1-b.c.p.internal", euid=0, accounts=self.accounts,
                    chown=False)
        args.update(kw)
        return INST.Foundation(self.root, **args)

    def live(self) -> dict:
        return {r: tree(self.root)[r] for r in INST.LIVE}

    def test_install_creates_exactly_the_four_items_with_collision_free_ids(self):
        before, before_tree = self.live(), tree(self.root)
        f = self.f()
        result = f.install(f.approval())
        self.assertEqual(result["result"], "FOUNDATION_INSTALLED")
        ids = result["principals"]
        self.assertEqual(ids, {"lilith-authority-dev": (994, 994), "lilith-recovery-witness": (993, 993)})
        self.assertNotIn(995, {g for _u, g in ids.values()})                  # PROD's occupied gid is never used
        self.assertNotEqual(ids["lilith-authority-dev"], (995, 985))           # DEV's numbers are never assumed
        self.assertEqual(self.live(), before)                                  # LILITH's files byte- and mtime-equal
        self.assertEqual((self.root / INST.DEPLOYMENT).read_bytes(), INST.DEPLOYMENT_BYTES)
        canonical = self.root / INST.CANONICAL
        self.assertEqual((os.listdir(canonical), oct(os.stat(canonical).st_mode & 0o777)), ([], "0o700"))
        self.assertEqual([c[-1] for c in self.run.calls], list(INST.PRINCIPALS))
        sys.path.insert(0, str(ROOT / "services/authority-dev"))
        from lilith_authority_host import inputs as HI
        self.assertEqual(HI.read_deployment(root=self.root, owner_uid=os.getuid()), HI.PROD_DEPLOYMENT)
        after_tree = tree(self.root)
        self.assertEqual(set(after_tree) - set(before_tree),
                         {INST.CANONICAL, INST.AUTHORITY_CONFIG, INST.DEPLOYMENT, INST.STATE, INST.JOURNAL})
        changed = {k for k in before_tree if after_tree.get(k) != before_tree[k]}
        # only the parents that gained exactly one of those entries changed their listing
        self.assertEqual(changed, {"etc", "var/lib", "home/lilith/.hermes/lilith-os"})

    def test_every_preflight_stop_changes_nothing(self):
        cases = {
            "wrong host": (dict(hostname="lilith-dev-01"), None, "WRONG_HOST"),
            "not root": (dict(euid=1000), None, "NOT_ROOT"),
            "dev machine": ({}, lambda: (self.root / "etc/machine-id").write_bytes(b"ae929170e6fa4c8ab9cc7b9547238d9d\n"),
                            "DEV_MACHINE"),
            "principal exists": ({}, lambda: self.accounts.users.__setitem__("lilith-recovery-witness", (990, 990)),
                                 "PRINCIPAL_EXISTS:lilith-recovery-witness"),
            "canonical exists": ({}, lambda: (self.root / INST.CANONICAL).mkdir(), "PRESENT:/" + INST.CANONICAL),
            "deployment exists": ({}, lambda: ((self.root / INST.AUTHORITY_CONFIG).mkdir(parents=True),
                                               (self.root / INST.DEPLOYMENT).write_text("{}")), "PRESENT:/" + INST.DEPLOYMENT),
            "live file missing": ({}, lambda: (self.root / INST.LIVE[0]).unlink(), "LIVE_FILE_MISSING"),
        }
        for label, (kw, prepare, reason) in cases.items():
            with self.subTest(label):
                self.setUp()
                if prepare:
                    prepare()
                before, accounts = tree(self.root), dict(self.accounts.users)
                f = self.f(**kw)
                with self.assertRaises(INST.Stop) as caught:
                    f.install(f.approval())
                self.assertEqual(caught.exception.reason, reason)
                self.assertEqual(tree(self.root), before)
                self.assertEqual(self.accounts.users, accounts)
                self.assertEqual(self.run.calls, [])

    def test_a_wrong_approval_and_a_second_install_are_refused(self):
        f = self.f()
        with self.assertRaises(INST.Stop) as caught:
            f.install("0" * 16)
        self.assertEqual(caught.exception.reason, "APPROVAL_NOT_THIS_PLAN")
        f.install(f.approval())
        with self.assertRaises(INST.Stop) as caught:
            f.install(f.approval())
        self.assertTrue(caught.exception.reason.startswith("PRINCIPAL_EXISTS"))

    def test_a_mid_install_failure_stops_and_the_return_removes_exactly_what_exists(self):
        before = self.live()
        self.run.fail_on = "lilith-recovery-witness"
        f = self.f()
        with self.assertRaises(INST.Stop) as caught:
            f.install(f.approval())
        self.assertEqual(caught.exception.reason, "USERADD_FAILED:lilith-recovery-witness")
        self.assertIn("lilith-authority-dev", self.accounts.users)
        self.assertFalse((self.root / INST.CANONICAL).exists())
        self.assertFalse((self.root / INST.DEPLOYMENT).exists())
        self.run.fail_on = None
        result = f.return_(f.approval())
        self.assertEqual(result["removed"], ["principal:lilith-authority-dev"])
        self.assertNotIn("lilith-authority-dev", self.accounts.users)
        self.assertEqual(self.live(), before)
        self.assertTrue((self.root / INST.STATE / "foundation.journal.returned").exists())

    def test_a_live_file_changing_during_install_is_a_stop(self):
        target = self.root / INST.LIVE[0]
        self.run.during = lambda: target.write_bytes(b"changed by someone else")
        f = self.f()
        with self.assertRaises(INST.Stop) as caught:
            f.install(f.approval())
        self.assertEqual(caught.exception.reason, "LIVE_FILES_CHANGED")

    def test_the_full_return_restores_the_pre_install_state(self):
        before, accounts = tree(self.root), dict(self.accounts.users)
        f = self.f()
        f.install(f.approval())
        result = f.return_(f.approval())
        self.assertEqual(result["removed"], ["file:deployment", "dir:authority-config", "dir:canonical",
                                             "principal:lilith-recovery-witness", "principal:lilith-authority-dev"])
        after = tree(self.root)
        kept = lambda k: not k.startswith(INST.STATE) and k != "var/lib"     # the returned journal stays as evidence
        self.assertEqual({k: v for k, v in after.items() if kept(k)}, {k: v for k, v in before.items() if kept(k)})
        self.assertEqual(after["var/lib"][2], ["lilith-owner-prod-install"])
        self.assertEqual(sorted(os.listdir(self.root / INST.STATE)), ["foundation.journal.returned"])
        self.assertEqual(self.accounts.users, accounts)

    def test_a_refused_return_changes_nothing(self):
        f = self.f()
        f.install(f.approval())
        cases = {
            "store directory used": (lambda: (self.root / INST.CANONICAL / "cognitive_memory.db").write_bytes(b"x"),
                                     "CANONICAL_NOT_EMPTY"),
            "principal recreated": (lambda: self.accounts.users.__setitem__("lilith-authority-dev", (950, 950)),
                                    "PRINCIPAL_CHANGED:lilith-authority-dev"),
            "deployment edited": (lambda: (self.root / INST.DEPLOYMENT).write_bytes(b"{}"), "DEPLOYMENT_CHANGED"),
        }
        for label, (prepare, reason) in cases.items():
            with self.subTest(label):
                self.setUp()
                f = self.f()
                f.install(f.approval())
                prepare()
                before, accounts, calls = tree(self.root), dict(self.accounts.users), len(self.run.calls)
                with self.assertRaises(INST.Stop) as caught:
                    f.return_(f.approval())
                self.assertEqual(caught.exception.reason, reason)
                self.assertEqual(tree(self.root), before)
                self.assertEqual(self.accounts.users, accounts)
                self.assertEqual(len(self.run.calls), calls)                    # no userdel ran


class StaticTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "services/owner-memory-control/tools/owner_prod_inert_install.py").read_text(encoding="utf-8")

    def test_principals_are_the_installers_names_created_by_name(self):
        installer = (ROOT / "services/authority-dev/ceremony/install_authority_dev.py").read_text(encoding="utf-8")
        self.assertIn('SERVICE_USER = "lilith-authority-dev"', installer)
        self.assertIn('WITNESS_USER = "lilith-recovery-witness"', installer)
        self.assertEqual(INST.PRINCIPALS, ("lilith-authority-dev", "lilith-recovery-witness"))
        self.assertIn('"--system", "--user-group"', self.source)
        code = self.source.split('"""', 2)[2]                                # the code, not the docstring
        self.assertNotRegex(code, r"--(uid|gid)\b|\b(985|995)\b")             # no numeric id is ever requested

    def test_the_only_commands_are_useradd_and_userdel(self):
        self.assertEqual(self.source.count("self.run(["), 2)
        self.assertIn("self.run([*USERADD, name])", self.source)
        self.assertIn("self.run([USERDEL, name])", self.source)
        self.assertEqual((INST.USERADD[0], INST.USERDEL), ("/usr/sbin/useradd", "/usr/sbin/userdel"))

    def test_the_isolated_store_and_deployment_match_the_host_and_p2(self):
        self.assertEqual("/" + INST.CANONICAL, "/home/lilith/.hermes/lilith-os/canonical")
        host = (ROOT / "services/owner-memory-control/tools/first_memory_dev_host.py").read_text(encoding="utf-8")
        self.assertIn('PROD_CANONICAL = Path("/home/lilith/.hermes/lilith-os/canonical")', host)
        self.assertEqual(INST.DEPLOYMENT_BYTES, b'{"environment":"prod","profile":"OWNER_PROD","schemaVersion":1}')

    def test_live_files_are_only_read(self):
        for relative in INST.LIVE:
            self.assertFalse(relative.startswith(INST.CANONICAL))
        self.assertNotIn("LIVE).write", self.source)
        self.assertIn("os.O_RDONLY | os.O_NOATIME | os.O_NOFOLLOW", self.source)


if __name__ == "__main__":
    unittest.main()
