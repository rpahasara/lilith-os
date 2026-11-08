"""R3b stages 2-5 OFFLINE: the OWNER_PROD inert install on a PROD-shaped synthetic host, end to end with returns.

Record: docs/architecture/canonical-memory-prod-integration-plan.md R3b. The host mirrors audit run 2 (gid 995 taken,
LILITH's live files present); stage 1 (foundation) runs first with OS-allocated ids. The release is this tree's payload
built into a layout-v3 archive with stand-in wheels (only the manifest pin is patched, as in the P3 transition tests);
the host tree is a synthetic tar (its pins patched; a separate test checks the real 88a1168 pins from git). `python -m
venv` / `pip` are simulated. Nothing is started, enabled or reloaded: the runner refuses any systemctl call.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _p in (ROOT / "services/owner-memory-control/tools", HERE, ROOT / "services/authority-dev/ceremony"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

LINUX = hasattr(os, "O_NOATIME")
if LINUX:
    import owner_prod_inert_stages as ST  # noqa: E402
    import test_owner_prod_inert_install as TF  # noqa: E402  (stage-1 fakes: PROD-shaped accounts, runner)
    import test_owner_prod_p3_transition as TT  # noqa: E402  (stand-in wheels, payload build, layout v3)

CONTEXT_DIR = ROOT / "services/owner-memory-control/tools/hermes_context"


def done(code=0):
    return subprocess.CompletedProcess([], code, b"", b"")


def tree(root: Path) -> dict:
    return TF.tree(root)


def other_gid(path: Path):
    """A group the test may legitimately give a file it owns (any gid as root, else a supplementary group), or None."""
    current = os.lstat(path).st_gid
    if os.geteuid() == 0:
        return 54321
    return next((g for g in os.getgroups() if g != current), None)


def edit_journal(journal: Path, edit) -> None:
    lines = [json.loads(line) for line in journal.read_text(encoding="ascii").splitlines() if line.strip()]
    journal.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in edit(lines)), encoding="ascii")


@unittest.skipUnless(LINUX, "O_NOATIME, modes and symlinks need Linux")
class StagesTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        house = stack.enter_context(TT.T19.stand_in_wheels())
        self.tmp = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.root = self.tmp / "host"
        self.root.mkdir()
        for relative in ST.F1.LIVE:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"live " + relative.encode())
        (self.root / "etc/systemd/system").mkdir(parents=True)
        (self.root / "etc/tmpfiles.d").mkdir()
        (self.root / "etc/machine-id").write_text("0123456789abcdef0123456789abcdef\n", encoding="ascii")
        (self.root / "var/lib").mkdir(parents=True)
        (self.root / "usr/local/lib").mkdir(parents=True)
        (self.root / "opt").mkdir()
        self.before = tree(self.root)
        # stage 1, the foundation
        self.accounts = TF.FakeAccounts()
        f1 = ST.F1.Foundation(self.root, run=TF.FakeRunner(self.accounts), hostname="lilith-01", euid=0,
                              accounts=self.accounts, chown=False)
        f1.install(f1.approval())
        self.f1 = f1
        # the release archive (this tree's payload, layout v3) and its pinned manifest
        payloads = TT.build_new(ROOT, house)
        out = self.tmp / "release"
        out.mkdir()
        with TT.S.layout_v3():
            self.archive, self.stamp, manifest = TT.T19.archive_for(out, ST.RELEASE, payloads)
        stack.enter_context(mock.patch.object(ST.P3, "NEW_MANIFEST_SHA256", manifest))
        # a synthetic host tree, pins patched to it
        self.tar = self.tmp / "tree.tar"
        files = {"current/services/owner-memory-control/tools/first_memory_dev_host.py": b"host tool",
                 "current/services/core-api/lilith_memory/canonical_store.py": b"store"}
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for d in ("current", "current/services", "current/services/owner-memory-control",
                      "current/services/owner-memory-control/tools", "current/services/core-api",
                      "current/services/core-api/lilith_memory"):
                info = tarfile.TarInfo(d)
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        self.tar.write_bytes(buf.getvalue())
        manifest_text = "".join(f"{hashlib.sha256(b).hexdigest()}  {n}\n" for n, b in sorted(files.items())).encode()
        for name, value in (("HOST_TREE_TAR_SHA256", hashlib.sha256(buf.getvalue()).hexdigest()),
                            ("HOST_TREE_MANIFEST_SHA256", hashlib.sha256(manifest_text).hexdigest()),
                            ("HOST_TREE_FILES", len(files))):
            stack.enter_context(mock.patch.object(ST, name, value))
        self.calls: list[list[str]] = []
        self.venv_fail = False
        self.pip_fail = False

    def run_cmd(self, argv):
        argv = list(argv)
        self.calls.append(argv)
        assert "systemctl" not in " ".join(argv), argv                    # nothing is ever reloaded or started
        if argv[1:3] == ["-m", "venv"]:
            venv = Path(argv[3])
            (venv / "bin").mkdir(parents=True)
            (venv / "pyvenv.cfg").write_bytes(b"home = /usr/bin\ninclude-system-site-packages = false\n")
            os.symlink("/usr/bin/python3", venv / "bin/python")            # absolute, outside the host root
            os.symlink("python", venv / "bin/python3")
            (venv / "lib/python3.12/site-packages").mkdir(parents=True)
            os.symlink("lib", venv / "lib64")
            return done(1 if self.venv_fail else 0)
        if argv[1:4] == ["-m", "pip", "install"]:
            pkg = Path(argv[0]).parents[1] / "lib/python3.12/site-packages/cryptography"
            pkg.mkdir()
            (pkg / "__init__.py").write_bytes(b"# wheel payload\n")
            if self.pip_fail:                                              # pip died half-way through the install
                return done(1)
            (pkg / "hazmat.so").write_bytes(b"\x7fELF wheel payload")
            os.chmod(pkg / "hazmat.so", 0o755)
            return done(0)
        raise AssertionError(argv)

    def stages(self, **kw) -> "ST.Stages":
        args = dict(run=self.run_cmd, hostname="lilith-01", euid=0, chown=False)
        args.update(kw)
        s = ST.Stages(self.root, **args)
        s.f1 = ST.F1.Foundation(self.root, run=self.f1.run, hostname=args["hostname"], euid=args["euid"],
                                accounts=self.accounts, chown=False)       # the same synthetic accounts
        return s

    def inputs(self, stage):
        return {"release": [self.archive, self.stamp], "units": [], "hosttree": [self.tar],
                "context": [CONTEXT_DIR / "canonical_context_service.py", CONTEXT_DIR / "lilith-first-memory-context.socket",
                            CONTEXT_DIR / "lilith-first-memory-context@.service"]}[stage]

    def install(self, stage, s=None):
        s = s or self.stages()
        return s.install(stage, s.approval(stage), self.inputs(stage))

    def stop(self, reason, fn):
        with self.assertRaises(ST.F1.Stop) as caught:
            fn()
        self.assertTrue(caught.exception.reason.startswith(reason), caught.exception.reason)

    def live(self):
        return {r: tree(self.root)[r] for r in ST.F1.LIVE}

    # ------------------------------------------------------------------ install ---
    def test_all_four_stages_install_inert_and_leave_lilith_untouched(self):
        live = self.live()
        for stage in ST.STAGES:
            self.assertEqual(self.install(stage)["result"], f"STAGE_{stage.upper()}_INSTALLED")
        self.assertEqual(self.live(), live)
        r = self.root
        self.assertEqual(os.readlink(r / ST.CURRENT), f"releases/{ST.RELEASE}")
        for unit in ("lilith-authority-dev.service", "lilith-recovery-witness.service",
                     "lilith-first-memory-context@.service"):
            self.assertIn(b"Environment=LILITH_ENV=prod", (r / ST.UNIT_DIR / f"{unit}.d" / ST.DROPIN_NAME).read_bytes())
        self.assertEqual((r / ST.CANONICAL_CONFIG).read_bytes(), ST.CANONICAL_CONFIG_DISABLED)   # recall + creation off
        for never in ST.NEVER:
            self.assertFalse(os.path.lexists(r / never), never)                                    # no grant, no router flag
        self.assertEqual((r / ST.F1.DEPLOYMENT).read_bytes(), ST.F1.DEPLOYMENT_BYTES)
        self.assertEqual([c[1:3] for c in self.calls], [["-m", "venv"], ["-m", "pip"]])             # the only commands
        self.assertFalse(os.listdir(r / ST.F1.CANONICAL))                                          # the store stays empty

    def test_every_witness_unit_is_the_e23_new_bytes(self):
        self.install("release")
        self.install("units")
        for member, target in ST.I.WITNESS_UNIT_TARGETS.items():
            if member in ST.E23.PAYLOAD_DELTA:
                self.assertEqual(hashlib.sha256((self.root / target.lstrip("/")).read_bytes()).hexdigest(),
                                 ST.E23.PAYLOAD_DELTA[member][1], member)

    # ------------------------------------------------------------------- stops ---
    def test_order_single_use_and_separation_stops_change_nothing(self):
        cases = (
            ("units before release", "units", lambda: None, {}, "EARLIER_STAGE_NOT_INSTALLED:release"),
            ("wrong host", "release", lambda: None, {"hostname": "lilith-dev-01"}, "WRONG_HOST"),
            ("dev deployment", "release",
             lambda: (self.root / ST.F1.DEPLOYMENT).write_bytes(b'{"environment":"dev"}'), {}, "DEPLOYMENT_NOT_OWNER_PROD"),
            ("a grant already present", "release",
             lambda: ((self.root / ST.FM_CONFIG_DIR).mkdir(parents=True), (self.root / ST.GRANT).write_bytes(b"{}")),
             {}, "PRESENT:/" + ST.GRANT),
            ("a pre-existing symlink", "release",
             lambda: (self.root / ST.OPT).symlink_to(self.tmp), {}, "PRESENT:/" + ST.OPT),
            ("a pre-existing unit file", "units",
             lambda: (self.install("release"), (self.root / ST.UNIT_DIR / "lilith-authority-dev.service").write_bytes(b"x")),
             {}, "PRESENT:/etc/systemd/system/lilith-authority-dev.service"),
        )
        for label, stage, prepare, kw, reason in cases:
            with self.subTest(label):
                self.setUp()
                prepare()
                before = tree(self.root)
                s = self.stages(**kw)
                self.stop(reason, lambda: s.install(stage, s.approval(stage), self.inputs(stage)))
                self.assertEqual(tree(self.root), before)

    def test_a_second_install_and_a_wrong_approval_are_refused(self):
        s = self.stages()
        self.stop("APPROVAL_NOT_THIS_PLAN", lambda: s.install("release", "0" * 16, self.inputs("release")))
        self.install("release")
        self.stop("PRESENT:/", lambda: self.install("release"))

    def test_missing_or_mismatched_release_files_are_refused(self):
        with mock.patch.object(ST.P3, "NEW_MANIFEST_SHA256", "0" * 64):
            self.stop("MANIFEST_NOT_THE_P3_PIN", lambda: self.install("release"))
        bad = self.tmp / "bad.tar.gz"
        bad.write_bytes(self.archive.read_bytes()[:-40])
        s = self.stages()
        self.stop("RELEASE_ARCHIVE_REFUSED", lambda: s.install("release", s.approval("release"), [bad, self.stamp]))
        self.stop("RELEASE_ARCHIVE_REFUSED:ARCHIVE_MISSING",
                  lambda: s.install("release", s.approval("release"), [self.tmp / "absent", self.stamp]))
        self.assertFalse(os.path.lexists(self.root / ST.OPT))
        self.install("release")
        (self.root / ST.RELEASE_DIR / "lilith_authority_dev/server.py").write_bytes(b"tampered")
        self.stop("INSTALLED_RELEASE_FILE_CHANGED", lambda: self.install("units"))   # later stages re-verify the release

    def test_a_missing_parent_directory_is_a_stop(self):
        self.install("release")
        (self.root / "etc/tmpfiles.d").rmdir()
        self.stop("PARENT_MISSING:/etc/tmpfiles.d", lambda: self.install("units"))

    def test_the_host_tree_tar_must_be_the_pinned_one(self):
        self.install("release")
        self.install("units")
        other = self.tmp / "other.tar"
        other.write_bytes(self.tar.read_bytes() + b"\0" * 512)
        s = self.stages()
        self.stop("HOST_TREE_TAR_NOT_PINNED", lambda: s.install("hosttree", s.approval("hosttree"), [other]))

    # ----------------------------------------------------------------- returns ---
    def test_an_interrupted_venv_is_never_deleted_unverified(self):
        """A venv whose creation or pip install did not complete has no recorded manifest: its contents are unknown,
        so the return STOPS before removing anything (owner adjudication), instead of deleting it recursively."""
        for flag, reason in (("venv_fail", "VENV_FAILED"), ("pip_fail", "PIP_FAILED")):
            with self.subTest(flag):
                self.setUp()
                setattr(self, flag, True)
                self.stop(reason, lambda: self.install("release"))
                self.assertTrue((self.root / ST.RELEASE_DIR / "venv").exists())             # half-made
                s = self.stages()
                before = tree(self.root)
                self.stop("VENV_UNVERIFIED:" + ST.RELEASE_DIR + "/venv", lambda: s.return_("release", s.approval("release")))
                self.assertEqual(tree(self.root), before)                                   # nothing removed

    def test_an_interrupted_release_before_the_venv_exists_returns_cleanly(self):
        """An interruption before the venv directory exists leaves nothing unverified: the return removes exactly
        the verified items created so far."""
        real = self.run_cmd

        def die_before_venv(argv):
            if argv[1:3] == ["-m", "venv"]:
                raise OSError("power lost")
            return real(argv)

        s = self.stages(run=die_before_venv)
        with self.assertRaises(OSError):
            s.install("release", s.approval("release"), self.inputs("release"))
        self.assertFalse(os.path.lexists(self.root / ST.RELEASE_DIR / "venv"))
        s = self.stages()
        self.assertEqual(s.return_("release", s.approval("release"))["result"], "STAGE_RELEASE_RETURNED")
        self.assertFalse(os.path.lexists(self.root / ST.OPT))

    def test_a_correct_venv_returns_cleanly_without_following_its_links(self):
        outside = self.root / "usr/bin"
        outside.mkdir(parents=True)
        (outside / "python3").write_bytes(b"the system interpreter")                       # the link's real target
        self.install("release")
        s = self.stages()
        self.assertEqual(s.return_("release", s.approval("release"))["result"], "STAGE_RELEASE_RETURNED")
        self.assertFalse(os.path.lexists(self.root / ST.OPT))
        self.assertEqual((outside / "python3").read_bytes(), b"the system interpreter")    # never followed

    def test_a_changed_venv_stops_the_return_before_anything_is_removed(self):
        venv = lambda *p: self.root / ST.RELEASE_DIR / "venv" / Path(*p)  # noqa: E731
        site = ("lib", "python3.12", "site-packages", "cryptography")
        def swap_dir_for_link():
            elsewhere = self.elsewhere
            elsewhere.mkdir()
            (elsewhere / "keep.txt").write_bytes(b"not part of the venv")
            target = venv(*site)
            for child in target.iterdir():
                child.unlink()
            target.rmdir()
            os.symlink(str(elsewhere), target)

        cases = {
            "file content": (lambda: venv(*site, "__init__.py").write_bytes(b"# tampered\n"), "VENV_CHANGED"),
            "file mode": (lambda: os.chmod(venv(*site, "hazmat.so"), 0o777), "VENV_CHANGED"),
            "unexpected file": (lambda: venv(*site, "backdoor.py").write_bytes(b"x"), "VENV_CHANGED"),
            "unexpected dir": (lambda: venv("include").mkdir(), "VENV_CHANGED"),
            "missing file": (lambda: venv("pyvenv.cfg").unlink(), "VENV_CHANGED"),
            "link retargeted": (lambda: (venv("bin/python").unlink(), os.symlink("/tmp/evil", venv("bin/python"))),
                                "VENV_CHANGED"),
            "unexpected link": (lambda: os.symlink("/etc", venv("etc")), "VENV_CHANGED"),
            "dir replaced by a link": (swap_dir_for_link, "VENV_CHANGED"),
            "file replaced by a fifo": (lambda: (venv("pyvenv.cfg").unlink(), os.mkfifo(venv("pyvenv.cfg"))),
                                        "VENV_ENTRY_TYPE"),
            "venv root replaced by a link": (lambda: (self._move_venv_away(self.elsewhere),
                                                      os.symlink(str(self.elsewhere), venv())), "ITEM_CHANGED"),
        }
        for label, (tamper, reason) in cases.items():
            with self.subTest(label):
                self.setUp()
                self.elsewhere = self.tmp / "elsewhere"
                self.install("release")
                tamper()
                s = self.stages()
                before = tree(self.root)
                self.stop(reason, lambda: s.return_("release", s.approval("release")))
                self.assertEqual(tree(self.root), before)                                   # nothing removed
                if self.elsewhere.exists():
                    self.assertTrue(any(self.elsewhere.iterdir()))                          # never followed

    def _move_venv_away(self, elsewhere):
        os.rename(self.root / ST.RELEASE_DIR / "venv", elsewhere)

    def test_a_tampered_venv_manifest_in_the_journal_stops_the_return(self):
        self.install("release")
        journal = self.root / ST.STATE / "release.journal"
        text = journal.read_text(encoding="ascii")
        self.assertIn('"step": "venv"', text)
        journal.write_text(text.replace("pyvenv.cfg", "pyvenv.cfX"), encoding="ascii")
        s = self.stages()
        before = tree(self.root)
        self.stop("VENV_MANIFEST_INVALID", lambda: s.return_("release", s.approval("release")))
        self.assertEqual(tree(self.root), before)

    def test_each_stage_returns_newest_first_and_everything_returns_to_the_start(self):
        for stage in ST.STAGES:
            self.install(stage)
        s = self.stages()
        self.stop("LATER_STAGE_PRESENT:units", lambda: s.return_("release", s.approval("release")))
        self.stop("LATER_STAGE_PRESENT:release", lambda: self.f1.return_(self.f1.approval()))
        for stage in reversed(ST.STAGES):
            self.assertEqual(s.return_(stage, s.approval(stage))["result"], f"STAGE_{stage.upper()}_RETURNED")
        self.f1.return_(self.f1.approval())
        after = tree(self.root)
        kept = lambda k: not k.startswith(ST.STATE) and k != "var/lib"
        self.assertEqual({k: v for k, v in after.items() if kept(k)}, {k: v for k, v in self.before.items() if kept(k)})
        self.assertNotIn("lilith-authority-dev", self.accounts.users)

    def test_a_refused_return_changes_nothing(self):
        for stage in ST.STAGES:
            self.install(stage)
        cases = {
            "a changed host-tree file": (lambda: (self.root / ST.HOST_TREE_CURRENT / "services/core-api/lilith_memory"
                                                  / "canonical_store.py").write_bytes(b"edited"), "hosttree", "ITEM_CHANGED"),
            "an unexpected file": (lambda: (self.root / ST.CONTEXT_LIB / "extra.py").write_bytes(b"x"), "context",
                                   "UNEXPECTED_ENTRY"),
            "a changed drop-in": (lambda: (self.root / ST.UNIT_DIR / "lilith-authority-dev.service.d" / ST.DROPIN_NAME)
                                  .write_bytes(b"[Service]\n"), "units", "ITEM_CHANGED"),
        }
        for label, (prepare, stage, reason) in cases.items():
            with self.subTest(label):
                self.setUp()
                for each in ST.STAGES:
                    self.install(each)
                s = self.stages()
                for later in reversed(ST.STAGES[ST.STAGES.index(stage) + 1:]):
                    s.return_(later, s.approval(later))
                prepare()
                before = tree(self.root)
                self.stop(reason, lambda: s.return_(stage, s.approval(stage)))
                self.assertEqual(tree(self.root), before)

    def test_a_live_file_change_during_a_stage_stops_it(self):
        """Each stage baselines LILITH's live files at its own start (lilith.db is legitimately written between
        windows) and requires them unchanged through the stage."""
        real = self.run_cmd

        def edit_during(argv):
            result = real(argv)
            if argv[1:3] == ["-m", "venv"]:
                (self.root / ST.F1.LIVE[0]).write_bytes(b"someone edited SOUL mid-window")
            return result

        s = self.stages(run=edit_during)
        self.stop("LIVE_FILES_CHANGED", lambda: s.install("release", s.approval("release"), self.inputs("release")))


    # ------------------------------------------------------------------ H-1 / H-2 ---
    def journal_items(self, stage):
        return {path: kind for kind, path, _d in self.stages().journal(stage)[0]["items"]}

    def returned_up_to(self, stage):
        """All stages installed, every stage after `stage` returned: `stage` is next to return."""
        for each in ST.STAGES:
            self.install(each)
        s = self.stages()
        for later in reversed(ST.STAGES[ST.STAGES.index(stage) + 1:]):
            s.return_(later, s.approval(later))
        return s

    def test_h1_a_changed_mode_or_owner_of_any_item_kind_stops_the_return(self):
        dropin_dir = f"{ST.UNIT_DIR}/lilith-authority-dev.service.d"
        cases = {
            "file mode (unit drop-in)": ("units", lambda: os.chmod(self.root / dropin_dir / ST.DROPIN_NAME, 0o600),
                                         "ITEM_CHANGED:" + dropin_dir + "/" + ST.DROPIN_NAME),
            "directory mode (drop-in dir)": ("units", lambda: os.chmod(self.root / dropin_dir, 0o700),
                                             "ITEM_CHANGED:" + dropin_dir),
            "directory mode (host tree)": ("hosttree", lambda: os.chmod(self.root / ST.HOST_TREE_CURRENT, 0o777),
                                           "ITEM_CHANGED:" + ST.HOST_TREE_CURRENT),
            "file mode (release manifest)": ("release", lambda: os.chmod(self.root / ST.RELEASE_DIR / ST.I.MANIFEST, 0o600),
                                             "ITEM_CHANGED:" + ST.RELEASE_DIR + "/" + ST.I.MANIFEST),
        }
        gid = other_gid(self.root / "etc/machine-id")
        if gid is not None:
            cases["file group (context service)"] = ("context", lambda: os.chown(self.root / ST.CONTEXT_SERVICE, -1, gid),
                                                     "ITEM_CHANGED:" + ST.CONTEXT_SERVICE)
            cases["link owner (current)"] = ("release", lambda: os.chown(self.root / ST.CURRENT, -1, gid,
                                                                          follow_symlinks=False), "ITEM_CHANGED:" + ST.CURRENT)
        for label, (stage, tamper, reason) in cases.items():
            with self.subTest(label):
                self.setUp()
                s = self.returned_up_to(stage)
                tamper()
                before = tree(self.root)
                self.stop(reason, lambda: s.return_(stage, s.approval(stage)))
                self.assertEqual(tree(self.root), before)

    def test_h1_a_legacy_or_incomplete_stage_journal_is_refused(self):
        cases = {
            "no schema": (lambda lines: [dict(lines[0], schema=1)] + lines[1:], "JOURNAL_LEGACY"),
            "a done item without its meta": (lambda lines: [{k: v for k, v in e.items() if k != "meta"}
                                                            if e.get("path") == ST.CONTEXT_SERVICE else e for e in lines],
                                             "JOURNAL_INCOMPLETE:" + ST.CONTEXT_SERVICE),
        }
        for label, (edit, reason) in cases.items():
            with self.subTest(label):
                self.setUp()
                s = self.returned_up_to("context")
                edit_journal(s.journal_path("context"), edit)
                before = tree(self.root)
                self.stop(reason, lambda: s.return_("context", s.approval("context")))
                self.assertEqual(tree(self.root), before)

    def test_h2_an_interrupted_item_that_exists_needs_owner_adjudication(self):
        s = self.returned_up_to("context")
        edit_journal(s.journal_path("context"), lambda lines: [
            e for e in lines if not (e.get("phase") == "done" and e.get("path") == ST.CONTEXT_SERVICE)
            and e.get("result") != "INSTALLED"])
        before = tree(self.root)
        self.stop("ITEM_INTERRUPTED:" + ST.CONTEXT_SERVICE, lambda: s.return_("context", s.approval("context")))
        self.assertEqual(tree(self.root), before)

    def test_h2_a_change_after_verification_stops_that_removal_and_is_never_resumed(self):
        rel = lambda *p: "/".join((ST.RELEASE_DIR,) + p)  # noqa: E731
        manifest = rel(ST.I.MANIFEST)
        venv_cfg = rel("venv", "pyvenv.cfg")
        site = rel("venv", "lib", "python3.12", "site-packages", "cryptography")
        decoy = lambda: self.tmp / "decoy"  # noqa: E731

        def swap_venv_parent(path):
            if path == rel("venv", "lib", "python3.12", "site-packages", "cryptography", "hazmat.so"):
                d = decoy()
                d.mkdir()
                (d / "hazmat.so").write_bytes(b"\x7fELF wheel payload")
                os.rename(self.root / site, self.tmp / "moved")
                os.symlink(str(d), self.root / site)

        cases = {
            "the current link retargeted": (lambda p: p == ST.CURRENT and (
                (self.root / ST.CURRENT).unlink(), os.symlink("releases/elsewhere", self.root / ST.CURRENT)),
                "CHANGED_DURING_RETURN:" + ST.CURRENT),
            "a venv file rewritten": (lambda p: p == venv_cfg and (self.root / venv_cfg).write_bytes(b"home = /evil\n"),
                                      "CHANGED_DURING_RETURN:" + venv_cfg),
            "a venv directory swapped for a link": (swap_venv_parent, "PATH_NOT_A_REAL_DIRECTORY"),
            "the manifest file rewritten": (lambda p: p == manifest and (self.root / manifest).write_bytes(
                (self.root / manifest).read_bytes()), "CHANGED_DURING_RETURN:" + manifest),
            "a file appears in a release directory": (
                lambda p: p == rel("lilith_authority_dev") and (self.root / rel("lilith_authority_dev", "late.py"))
                .write_bytes(b"x"), "REMOVE_REFUSED:" + rel("lilith_authority_dev")),
        }
        for label, (hook, reason) in cases.items():
            with self.subTest(label):
                self.setUp()
                s = self.returned_up_to("release")
                s.before_remove = hook
                self.stop(reason, lambda: s.return_("release", s.approval("release")))
                journal = s.journal("release")
                started = [e["path"] for e in journal if e.get("step") == "remove" and e["phase"] == "intent"]
                finished = [e["path"] for e in journal if e.get("step") == "remove" and e["phase"] == "done"]
                self.assertEqual(len(started), len(finished) + 1)        # the stopped removal is journaled as begun
                if decoy().exists():
                    self.assertEqual((decoy() / "hazmat.so").read_bytes(), b"\x7fELF wheel payload")   # never followed
                s.before_remove = None
                before = tree(self.root)
                self.stop("RETURN_PARTIAL", lambda: s.return_("release", s.approval("release")))
                self.assertEqual(tree(self.root), before)

    def test_h2_the_host_lock_is_shared_by_every_stage_install_and_return(self):
        self.install("release")
        s = self.stages()
        with ST.SF.HostLock(self.root, ST.STATE):
            before = tree(self.root)
            self.stop("LOCKED_BY_ANOTHER_PROCESS", lambda: s.return_("release", s.approval("release")))
            self.stop("LOCKED_BY_ANOTHER_PROCESS", lambda: self.install("units"))
            self.stop("LOCKED_BY_ANOTHER_PROCESS", lambda: self.f1.return_(self.f1.approval()))
            self.assertEqual(tree(self.root), before)
        self.assertEqual(self.install("units")["result"], "STAGE_UNITS_INSTALLED")     # free again afterwards


class PinTests(unittest.TestCase):
    def test_the_release_and_host_tree_pins(self):
        if not LINUX:
            self.skipTest("module imports POSIX-only helpers")
        self.assertEqual(ST.RELEASE, "88a1168bd41797109772ffce7df7352c1ae40e4c")
        self.assertEqual((ST.HOST_TREE_FILES, ST.HOST_TREE_MANIFEST_SHA256[:8], ST.HOST_TREE_TAR_SHA256[:8]),
                         (96, "af8140a8", "2b8d28e2"))
        self.assertEqual(ST.CANONICAL_CONFIG_DISABLED, b'{"activeCapabilities":[],"canonicalLtmEnabled":false,"schemaVersion":1}')

    def test_the_real_host_tree_reproduces_its_pins_from_git(self):
        if not LINUX:
            self.skipTest("module imports POSIX-only helpers")
        check = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", ST.RELEASE + "^{commit}"], capture_output=True)
        if check.returncode != 0:
            self.skipTest("shallow clone without the release commit")
        packages = ("services/authority-dev/lilith_authority_dev", "services/authority-dev/lilith_authority_host",
                    "services/authority-dev/lilith_authority_root", "services/core-api/lilith_memory",
                    "services/owner-memory-control/lilith_owner_memory", "services/recovery-witness/lilith_recovery_witness")
        tools = ("first_memory_dev_host.py", "first_memory_l04_migration.py", "relationship_origin_l04_migration.py",
                 "relationship_origin_forget_dev.py")
        names = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", ST.RELEASE, "--", *packages],
                               capture_output=True, text=True, check=True).stdout.split()
        files = sorted([n for n in names if n.endswith(".py")] + ["services/owner-memory-control/tools/" + t for t in tools])
        lines = "".join(f"{hashlib.sha256(subprocess.run(['git', '-C', str(ROOT), 'show', f'{ST.RELEASE}:{f}'], capture_output=True, check=True).stdout).hexdigest()}  current/{f}\n" for f in files)
        self.assertEqual((len(files), hashlib.sha256(lines.encode()).hexdigest()),
                         (ST.HOST_TREE_FILES, ST.HOST_TREE_MANIFEST_SHA256))


if __name__ == "__main__":
    unittest.main()
