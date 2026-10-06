"""15B2b-B1b-3e M-B4/M-B5: installer P1B-4/P1B-5 stages, the read-only content verifier and the
bounded remove-before-M-B6 tool, on a synthetic host tree (TEST-ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md (G-3, G-4, G-6).

The host is the PR-1S installer test `FakeHost` under a TEMPORARY root,
brought to `status --expect P1B-2` with a stand-in K-WIT blob (never a
credential). The anchors and registry are the TEST world's derived
representations (throwaway TEST keys). The installer is the unchanged
reviewed `install_authority_dev.py`. Nothing here touches `/`, DEV, the S25
or any real key. Failure messages redact every 64-hex value.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", TOOLS,
           ROOT / "services/authority-dev", ROOT / "services/authority-dev/ceremony",
           ROOT / "services/authority-dev/tests", ROOT / "services/recovery-witness", Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

POSIX = os.name == "posix"
HAVE_CRYPTO = all(importlib.util.find_spec(m) is not None for m in ("cryptography", "rfc8785", "fido2"))

if HAVE_CRYPTO and POSIX:
    import install_authority_dev as I
    import mb4_mb5_installable_inputs as D
    import mb4_mb5_remove_before_mb6 as RM
    import mb4_mb5_trust_install_verifier as V
    import test_pr1s_installer_upgrade as U
    from test_b1b3e_mb4_mb5_installable_inputs import P, TestSources
    from test_custody_preparation import build_archive, fake_wheels

NEW_STANDIN_BLOB = b"TEST_ONLY stand-in K-WIT ciphertext (never a credential)"


def _r(text: str) -> str:
    import re
    return re.sub(r"[0-9a-f]{64}", "<redacted>", str(text))


class RedactedFailures:
    def _formatMessage(self, msg, standardMsg):
        return _r(super()._formatMessage(msg, standardMsg))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree(root: Path) -> dict[str, tuple]:
    """Every path under the host root with its type, mode, inode and content hash."""
    out = {}
    for directory, dirs, files in os.walk(root):
        for name in dirs + files:
            path = Path(directory) / name
            meta = os.lstat(path)
            digest = sha(path.read_bytes()) if stat.S_ISREG(meta.st_mode) else None
            out[str(path.relative_to(root))] = (stat.S_IFMT(meta.st_mode), stat.S_IMODE(meta.st_mode), meta.st_ino,
                                                digest)
    return out


@unittest.skipUnless(HAVE_CRYPTO and POSIX, "POSIX owner/mode semantics and cryptography, rfc8785, fido2 required")
class InstallStageTests(RedactedFailures, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        world = Path(cls._tmp.name) / "world"
        world.mkdir()
        cls.src = TestSources(world)
        cls.files = dict(D.derive_from_members(cls.src.members, cls.src.pins).files)
        other = Path(cls._tmp.name) / "other"
        other.mkdir()
        cls.other = TestSources(other)
        cls.other_files = dict(D.derive_from_members(cls.other.members, cls.other.pins).files)
        w = cls.src.world.accepted
        cls.pins = V.TrustInstallPinsV1(
            root_anchor_sha256=sha(cls.files["registry-root.json"]),
            witness_anchor_sha256=sha(cls.files["witness-anchor.json"]),
            registry_sha256=sha(cls.files["authority-registry.v1.json"]), registry_digest=cls.src.pins.registry_digest,
            kroot_public_key_sha256=w.kroot_public_key_sha256, root_key_id=P.L.ROOT_KEY_ID,
            kwit_public_key_sha256=w.kwit_public_key_sha256, kwit_key_id=w.kwit_key_id,
            kact_public_key_sha256=w.kact_public_key_sha256, kact_key_id=w.kact_key_id, epoch_random=P.EPOCH,
            policy_version=P.L.POLICY_VERSION)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        out = self.stack.enter_context(tempfile.TemporaryDirectory())
        wheels = self.stack.enter_context(fake_wheels())
        self.stack.enter_context(U.accepted_current())
        self.host, self.system = U.old_host(directory)
        archive, attestation, _ = build_archive(Path(out), wheels)
        baseline = I.parse_baseline(U.baseline_file(out, self.system), U.OLD)
        U.full_upgrade(self.host, self.system, baseline, archive, attestation)
        for stage in (I.stage_custody, I.stage_witness_account, I.stage_witness_units):
            self.assertEqual(stage(self.system, U.NEW)["result"], "PASS")
        self.host.daemon_reload()
        self.assertEqual(I.stage_skeleton(self.system, U.NEW)["result"], "PASS")
        blob = self.host.root / I.WITNESS_BLOB.lstrip("/")
        blob.write_bytes(NEW_STANDIN_BLOB)                     # M-B2's effect on the tree (stand-in bytes)
        os.chmod(blob, 0o600)
        self.assertEqual(self.status("P1B-2")["result"], "PASS", self.status("P1B-2")["failures"])
        self.inputs = Path(out) / "inputs"
        self.inputs.mkdir()
        self.uid, self.gid = os.getuid(), os.getgid()

    # ---------------------------------------------------------------------------------------------- helpers ---

    def status(self, stage):
        return I.status(self.system, stage, U.NEW)

    def doc(self, name: str, data: bytes) -> Path:
        path = self.inputs / name
        path.write_bytes(data)
        return path

    def anchors(self, root=None, witness=None):
        return I.stage_install_anchors(self.system, U.NEW, self.doc("r.json", root or self.files["registry-root.json"]),
                                       self.doc("w.json", witness or self.files["witness-anchor.json"]))

    def registry(self, data=None):
        return I.stage_install_registry(self.system, U.NEW,
                                        self.doc("g.json", data or self.files["authority-registry.v1.json"]))

    def verify(self):
        return V.evaluate(root=self.host.root, owner_uid=self.uid, owner_gid=self.gid, pins=self.pins)

    def refused(self, reason_prefix, fn, *args):
        with self.assertRaises(I.InstallError) as caught:
            fn(*args)
        self.assertTrue(caught.exception.reason.startswith(reason_prefix), caught.exception.reason)

    def target(self, absolute):
        return self.host.root / absolute.lstrip("/")

    def remover(self, **kw):
        value = dict(root=self.host.root, owner_uid=self.uid, owner_gid=self.gid, euid=lambda: 0,
                     hostname=lambda: "lilith-dev-01")
        value.update(kw)
        return RM.Host(**value)

    # ------------------------------------------------------------------------------------------------ G-3 ---

    def test_p1b4_p1b5_ladder_with_content_verification(self):
        before = self.verify()
        self.assertEqual(before["phase"], V.W0_PRE_INSTALL)
        self.assertEqual(before["evidence"], dict.fromkeys(V.EVIDENCE, False))
        self.refused("PRECONDITION_FAILED", self.registry)          # M-B5 never precedes M-B4
        # M-B4
        report = self.anchors()
        self.assertEqual(report["result"], "PASS", report["failures"])
        self.assertEqual(self.status("P1B-4")["result"], "PASS")
        for name, path in (("registry-root.json", I.REGISTRY_ROOT_ANCHOR), ("witness-anchor.json", I.WITNESS_ANCHOR)):
            meta = os.lstat(self.target(path))
            self.assertEqual(self.target(path).read_bytes(), self.files[name])   # exactly the derived bytes
            self.assertEqual((stat.S_IMODE(meta.st_mode), stat.S_ISREG(meta.st_mode)), (0o644, True))
        mid = self.verify()
        self.assertEqual(mid["phase"], V.W3_ANCHORS_INSTALLED)
        self.assertEqual(mid["evidence"], {"anchorsEqualOwnerCopies": True, "witnessAnchorNamesKWit": True,
                                           "registryVerifiesOnHost": False})
        self.refused("PRECONDITION_FAILED", self.anchors)           # write-once: no re-run over installed anchors
        # M-B5
        report = self.registry()
        self.assertEqual(report["result"], "PASS", report["failures"])
        self.assertEqual(self.status("P1B-5")["result"], "PASS")
        self.assertEqual(self.status("P1B-4")["result"], "FAIL")    # stage-exact: the registry dir is no longer empty
        self.assertEqual(self.target(I.REGISTRY_DIR + "/authority-registry.v1.json").read_bytes(),
                         self.files["authority-registry.v1.json"])
        after = self.verify()
        self.assertEqual(after["phase"], V.W5_INSTALLED_CONTENT_VERIFIED, after["failures"])
        self.assertEqual(after["evidence"], dict.fromkeys(V.EVIDENCE, True))
        self.assertEqual(after["registryDigest"], self.src.pins.registry_digest)
        self.assertEqual(set(after["hostInputReasons"]), V.EXPECTED_AFTER_MB5)
        self.assertEqual((after["trustInstalledCandidate"], after["registryEffective"], after["authorityGranted"]),
                         (True, False, False))
        self.refused("PRECONDITION_FAILED", self.registry)          # write-once
        for later in ("P1B-6", "P1B-8"):
            self.assertEqual(self.status(later)["result"], "FAIL")  # nothing beyond M-B5 exists

    def test_canonical_byte_and_shape_rejection_writes_nothing(self):
        f = self.files
        self.refused("INPUT_DOCUMENT_NOT_CANONICAL", self.anchors, f["registry-root.json"] + b"\n")
        self.refused("INPUT_DOCUMENT_NOT_CANONICAL", self.anchors, None, f["witness-anchor.json"] + b"\n")
        self.refused("INPUT_DOCUMENT_MALFORMED", self.anchors, self.src.world.root_raw)          # the E-21 wrapper
        self.refused("ANCHOR_SHAPE", self.anchors, f["witness-anchor.json"], f["registry-root.json"])  # swapped
        self.refused("INPUT_DOCUMENT_MALFORMED", self.anchors,
                     json.dumps(dict(json.loads(f["registry-root.json"]), environment="prod"),
                                sort_keys=True, separators=(",", ":")).encode())
        self.assertEqual(self.status("P1B-2")["result"], "PASS")    # nothing was written by any refusal
        self.assertEqual(self.anchors()["result"], "PASS")
        self.refused("INPUT_DOCUMENT_NOT_CANONICAL", self.registry, self.src.transport)        # the signed transport file
        self.refused("REGISTRY_SHAPE", self.registry, f["registry-root.json"])
        self.assertEqual(self.status("P1B-4")["result"], "PASS")
        self.assertEqual(self.registry()["result"], "PASS")

    def test_pre_existing_file_refusal(self):
        planted = self.target(I.REGISTRY_ROOT_ANCHOR)
        planted.write_bytes(self.files["registry-root.json"])
        os.chmod(planted, 0o644)
        self.refused("PRECONDITION_FAILED", self.anchors)           # P1B-2 listing no longer empty
        self.assertEqual(self.verify()["phase"], V.W2_WITNESS_ANCHOR_INCOMPLETE)   # root complete, witness absent
        self.target(I.REGISTRY_ROOT_ANCHOR).unlink()
        reg = self.target(I.REGISTRY_DIR + "/authority-registry.v1.json")
        reg.write_bytes(self.files["authority-registry.v1.json"])
        os.chmod(reg, 0o644)
        self.refused("PRECONDITION_FAILED", self.anchors)
        self.assertEqual(self.verify()["phase"], V.UNEXPECTED)      # a registry without anchors is never an install order

    # ------------------------------------------------------------------------------------------------ G-4 ---

    def test_shape_pass_is_not_content_verification(self):
        report = self.anchors(self.other_files["registry-root.json"], self.other_files["witness-anchor.json"])
        self.assertEqual(report["result"], "PASS")                  # the installer judges shape only
        result = self.verify()
        self.assertFalse(result["evidence"]["anchorsEqualOwnerCopies"])
        self.assertFalse(result["evidence"]["witnessAnchorNamesKWit"])
        self.assertEqual(result["phase"], V.UNEXPECTED)
        self.assertFalse(result["trustInstalledCandidate"])

    def test_wrong_registry_under_correct_anchors_is_not_verified(self):
        self.assertEqual(self.anchors()["result"], "PASS")
        self.assertEqual(self.registry(self.other_files["authority-registry.v1.json"])["result"], "PASS")
        result = self.verify()
        self.assertEqual(result["phase"], V.W4_REGISTRY_INCOMPLETE)
        self.assertFalse(result["evidence"]["registryVerifiesOnHost"])
        # even if the byte pin were (wrongly) the foreign registry's, the K-ROOT signature fails under the installed E-21
        foreign = dataclasses.replace(self.pins, registry_sha256=sha(self.other_files["authority-registry.v1.json"]))
        again = V.evaluate(root=self.host.root, owner_uid=self.uid, owner_gid=self.gid, pins=foreign)
        self.assertFalse(again["evidence"]["registryVerifiesOnHost"])
        self.assertEqual(again["phase"], V.W5_INSTALLED_CONTENT_NOT_VERIFIED)

    def test_wrong_kwit_identity_and_mode_are_not_verified(self):
        self.assertEqual(self.anchors()["result"], "PASS")
        self.assertEqual(self.registry()["result"], "PASS")
        for change in ({"kwit_key_id": "test-only.witness.other"}, {"kwit_public_key_sha256": "1" * 64}):
            result = V.evaluate(root=self.host.root, owner_uid=self.uid, owner_gid=self.gid,
                                pins=dataclasses.replace(self.pins, **change))
            self.assertFalse(result["evidence"]["witnessAnchorNamesKWit"], change)
        os.chmod(self.target(I.WITNESS_ANCHOR), 0o664)
        result = self.verify()
        self.assertFalse(result["evidence"]["anchorsEqualOwnerCopies"])
        self.assertNotEqual(result["phase"], V.W5_INSTALLED_CONTENT_VERIFIED)

    def test_verifier_is_read_only_and_post_ledger_is_out_of_scope(self):
        self.assertEqual(self.anchors()["result"], "PASS")
        self.assertEqual(self.registry()["result"], "PASS")
        snapshot = tree(self.host.root)
        self.verify()
        self.assertEqual(tree(self.host.root), snapshot)
        self.target("/var/lib/lilith-authority-dev").mkdir()
        self.assertEqual(self.verify()["phase"], V.POST_LEDGER)
        source = (TOOLS / "mb4_mb5_trust_install_verifier.py").read_text(encoding="utf-8")
        code = source.split('"""', 2)[2]
        for forbidden in ("os.unlink", "os.remove", "os.rename", "os.chmod", "os.mkdir", "O_WRONLY", "O_CREAT",
                          "subprocess", "socket", "credstore", "credential.secret", "witness.cred", ".write_bytes",
                          "systemctl", "shutil"):
            self.assertNotIn(forbidden, code, forbidden)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(V.main(["observe"]), 2)                # this test host is not DEV (or not root)
            self.assertEqual(V.main(["observe", "/"]), 2)           # no path argument exists
        self.assertIn("REFUSED", err.getvalue())

    # ------------------------------------------------------------------------------------------------ G-6 ---

    def _partial(self, absolute, data):
        path = self.target(absolute)
        path.write_bytes(data)
        os.chmod(path, 0o644)

    def test_w1_w2_w4_classified_and_bounded_removal_restores_p1b2(self):
        f = self.files
        cases = (
            (V.W1_ROOT_ANCHOR_INCOMPLETE, {I.REGISTRY_ROOT_ANCHOR: f["registry-root.json"][:17]}),
            (V.W2_WITNESS_ANCHOR_INCOMPLETE, {I.REGISTRY_ROOT_ANCHOR: f["registry-root.json"],
                                              I.WITNESS_ANCHOR: b""}),
            (V.W4_REGISTRY_INCOMPLETE, {I.REGISTRY_ROOT_ANCHOR: f["registry-root.json"],
                                        I.WITNESS_ANCHOR: f["witness-anchor.json"],
                                        I.REGISTRY_DIR + "/authority-registry.v1.json": f["authority-registry.v1.json"][:99]}),
        )
        for phase, partial in cases:
            with self.subTest(phase):
                for absolute, data in partial.items():
                    self._partial(absolute, data)
                self.assertEqual(self.verify()["phase"], phase)
                self.refused("PRECONDITION_FAILED", self.anchors)   # a partial file blocks every re-run
                outside = {k: v for k, v in tree(self.host.root).items()
                           if k not in {p.lstrip("/") for p in RM.REMOVAL_ORDER}}
                host = self.remover()
                plan = RM.plan(host)
                self.assertEqual(sorted(plan["remove"]), sorted(partial))
                with self.assertRaises(RM.Refused) as caught:
                    RM.remove(host, "0" * 64)
                self.assertEqual(caught.exception.reason, "PLAN_CHANGED")
                result = RM.remove(host, plan["planDigest"])
                self.assertEqual(result["result"], "PRE_INSTALL_RESTORED")
                self.assertEqual(self.status("P1B-2")["result"], "PASS")
                self.assertEqual(self.verify()["phase"], V.W0_PRE_INSTALL)
                after = tree(self.host.root)
                self.assertEqual({k: v for k, v in after.items() if k in outside}, outside)  # nothing else touched
        self.assertEqual(self.anchors()["result"], "PASS")          # the ladder can be re-run after removal
        self.assertEqual(self.registry()["result"], "PASS")
        self.assertEqual(self.verify()["phase"], V.W5_INSTALLED_CONTENT_VERIFIED)

    def test_removal_plan_binds_the_reviewed_state(self):
        self._partial(I.REGISTRY_ROOT_ANCHOR, self.files["registry-root.json"][:5])
        host = self.remover()
        plan = RM.plan(host)
        self._partial(I.REGISTRY_ROOT_ANCHOR, self.files["registry-root.json"][:6])     # changed after review
        with self.assertRaises(RM.Refused) as caught:
            RM.remove(host, plan["planDigest"])
        self.assertEqual(caught.exception.reason, "PLAN_CHANGED")
        self.assertTrue(self.target(I.REGISTRY_ROOT_ANCHOR).exists())

    def test_removal_refuses_outside_its_bound(self):
        host = self.remover()
        with self.assertRaises(RM.Refused) as caught:
            RM.remove(host, RM.plan(host)["planDigest"])
        self.assertEqual(caught.exception.reason, "NOTHING_TO_REMOVE")
        self.assertEqual(self.anchors()["result"], "PASS")
        refusals = []
        for name, setup, undo in (
            ("ledger", lambda: self.target("/var/lib/lilith-authority-dev").mkdir(),
             lambda: self.target("/var/lib/lilith-authority-dev").rmdir()),
            ("witness state", lambda: self.target("/var/lib/lilith-recovery-witness").mkdir(),
             lambda: self.target("/var/lib/lilith-recovery-witness").rmdir()),
            ("owner input", lambda: self._partial(I.GENESIS_PIN_COPY, b"{}"),
             lambda: self.target(I.GENESIS_PIN_COPY).unlink()),
            ("extra trust entry", lambda: self._partial(I.TRUST_DIR + "/other.json", b"{}"),
             lambda: self.target(I.TRUST_DIR + "/other.json").unlink()),
        ):
            setup()
            with self.assertRaises(RM.Refused) as caught:
                RM.plan(host)
            refusals.append((name, caught.exception.reason.split(":")[0]))
            undo()
        self.assertEqual(refusals, [("ledger", "NOT_PRE_LEDGER"), ("witness state", "NOT_PRE_LEDGER"),
                                    ("owner input", "NOT_PRE_LEDGER"), ("extra trust entry", "TRUST_DIRECTORY_UNEXPECTED")])
        registry = self.target(I.REGISTRY_DIR + "/authority-registry.v1.json")
        os.symlink("/etc/passwd", registry)
        with self.assertRaises(RM.Refused) as caught:
            RM.plan(host)
        self.assertTrue(caught.exception.reason.startswith("FILE_UNEXPECTED"))
        registry.unlink()
        for bad, reason in ((self.remover(euid=lambda: 1000), "NOT_ROOT"),
                            (self.remover(hostname=lambda: "lilith-prod-01"), "NOT_DEV_HOST")):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(RM.main(["plan"], bad), 2)
            self.assertIn(reason, err.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(RM.main(["remove"], host), 2)          # USAGE: the digest is required
            self.assertEqual(RM.main(["remove", "/etc", "x"], host), 2)
        self.assertEqual(self.status("P1B-4")["result"], "PASS")    # every refusal left the anchors in place
        source = (TOOLS / "mb4_mb5_remove_before_mb6.py").read_text(encoding="utf-8").split('"""', 2)[2]
        for forbidden in ("rmdir", "shutil", "subprocess", "rename", "chmod", "O_WRONLY", "O_CREAT", "credstore",
                          "systemctl", "witness.cred"):
            self.assertNotIn(forbidden, source, forbidden)
        self.assertEqual(source.count("os.unlink("), 1)


if __name__ == "__main__":
    unittest.main()
