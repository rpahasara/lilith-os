"""15B2b-B1b-3e M-B12 PR-B2: OS_DENIAL, SECRET_HYGIENE and PRESERVATION_SET producers (TEST-ONLY, synthetic).

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb2-proof-producers.md. No live system: `systemctl`, the journal,
the host files and root are fakes or temporary directories; no producer is run on DEV. Synthetic transcripts are
admitted by the PR-B1 builder only under a TEST trust that stands in for merged owner-record pins; the DEV pins stay
empty.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, HERE, ROOT / "services/authority-dev", ROOT / "services/authority-dev/tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mb12_os_denial_proof as OS  # noqa: E402
import mb12_preservation_set_proof as PS  # noqa: E402
import mb12_readiness_inputs as RI  # noqa: E402
import mb12_secret_hygiene_proof as SH  # noqa: E402
import test_b1b3e_mb12_prb1_prerequisites as T1  # noqa: E402
from lilith_owner_memory import pr1_acceptance as PA  # noqa: E402

POSIX = os.name == "posix"
H = T1.H
SHOW_OK = {"Id": OS.UNIT, "LoadState": "loaded", "NeedDaemonReload": "no", "FragmentPath": OS.FRAGMENT,
           "DropInPaths": "", "User": OS.USER, "InaccessiblePaths": " ".join(OS.INACCESSIBLE)}
UNIT_BYTES = (ROOT / "services/authority-dev/deploy/lilith-authority-dev.service").read_bytes()
DROPIN_BYTES = (TOOLS / "mb11_restart_boundary_dropins/lilith-authority-dev.service.d/10-no-implicit-restart.conf")


def capture(fn, *args, **kwargs):
    lines: list[str] = []
    ok = fn(*args, say=lines.append, **kwargs)
    return ok, ("\n".join(lines) + "\n").encode("ascii")


# ---------------------------------------------------------------- OS_DENIAL ---

def os_run(**overrides):
    show = {**SHOW_OK, **overrides}
    text = "".join(f"{key}={value}\n" for key, value in show.items())
    return lambda argv: (0, text)


def os_read(**overrides):
    files = {OS.FRAGMENT: UNIT_BYTES, OS.RELEASE_ASSET: UNIT_BYTES, **overrides}
    return lambda path: files.get(path)


class OsDenialTests(unittest.TestCase):
    def prove(self, run=None, read=None, euid=0, phase="UNIT"):
        return capture(OS.prove, phase, run=run or os_run(), read=read or os_read(), euid=lambda: euid)

    def test_the_release_fragment_is_the_accepted_one(self):
        self.assertEqual(hashlib.sha256(UNIT_BYTES).hexdigest(), OS.FRAGMENT_SHA256)
        declared = next(line for line in UNIT_BYTES.decode().splitlines() if line.startswith("InaccessiblePaths="))
        self.assertEqual(tuple(declared.split("=", 1)[1].split(" ")), OS.INACCESSIBLE)
        import mb11_restart_boundary as B
        import mb11_restart_boundary_install as BI
        self.assertEqual(B.DROPINS[OS.UNIT][1], OS.P1B10R_DROPIN_SHA256)
        self.assertEqual(BI.FRAGMENTS[OS.UNIT], OS.FRAGMENT_SHA256)
        self.assertTrue(OS.P1B10R_DROPIN.endswith("/" + B.DROPINS[OS.UNIT][0]))

    def test_pass_is_exactly_the_expected_transcript(self):
        ok, raw = self.prove()
        self.assertTrue(ok)
        self.assertEqual(raw, OS.expected_pass(OS.DROPINS_NONE))
        dropin = DROPIN_BYTES.read_bytes() if DROPIN_BYTES.is_file() else None
        if dropin is not None:
            ok, raw = self.prove(run=os_run(DropInPaths=OS.P1B10R_DROPIN), read=os_read(**{OS.P1B10R_DROPIN: dropin}))
            self.assertTrue(ok)
            self.assertEqual(raw, OS.expected_pass(OS.DROPINS_P1B10R))

    def test_every_deviation_fails_closed(self):
        custody_missing = " ".join(p for p in OS.INACCESSIBLE if p != "/etc/lilith-authority-custody")
        cases = {
            "INACCESSIBLE_PATHS_NOT_EXACT": dict(run=os_run(InaccessiblePaths=custody_missing)),
            "INACCESSIBLE_PATHS_NOT_EXACT ": dict(run=os_run(InaccessiblePaths="")),
            "UNIT_NOT_EXACT": dict(run=os_run(NeedDaemonReload="yes")),
            "UNIT_NOT_EXACT ": dict(run=os_run(User="root")),
            "DROPINS_NOT_ADMITTED": dict(run=os_run(DropInPaths="/etc/systemd/system/x.d/override.conf")),
            "DROPINS_NOT_ADMITTED ": dict(run=os_run(DropInPaths=OS.P1B10R_DROPIN),
                                          read=os_read(**{OS.P1B10R_DROPIN: b"[Service]\nRestart=always\n"})),
            "FRAGMENT_NOT_RELEASE_ASSET": dict(read=os_read(**{OS.FRAGMENT: UNIT_BYTES + b"\n"})),
            "FRAGMENT_NOT_RELEASE_ASSET ": dict(read=os_read(**{OS.RELEASE_ASSET: b"other"})),
            "FRAGMENT_UNOBSERVED": dict(read=os_read(**{OS.FRAGMENT: None})),
            "UNIT_PROPERTIES_UNOBSERVED": dict(run=lambda argv: (1, "")),
        }
        for label, kwargs in cases.items():
            with self.subTest(label=label):
                ok, raw = self.prove(**kwargs)
                lines = raw.decode().splitlines()
                self.assertFalse(ok)
                self.assertIn("FAIL: " + label.strip(), lines)
                self.assertEqual(lines[-1], OS.final_line(False))

    def test_missing_privilege_and_wrong_phase(self):
        ok, raw = self.prove(euid=1000)
        self.assertEqual((ok, raw), (False, (OS.final_line(False, "NOT_ROOT") + "\n").encode()))
        ok, raw = self.prove(phase="P1B-12")
        self.assertEqual((ok, raw), (False, (OS.final_line(False, "USAGE") + "\n").encode()))

    def test_show_parser_is_exact(self):
        good = "".join(f"{k}={v}\n" for k, v in SHOW_OK.items())
        self.assertEqual(OS.parse_show(good), SHOW_OK)
        self.assertIsNone(OS.parse_show(good + "Extra=1\n"))
        self.assertIsNone(OS.parse_show(good + "User=x\n"))
        self.assertIsNone(OS.parse_show("garbage\n"))


# ----------------------------------------------------------- SECRET_HYGIENE ---

def pkcs8_der() -> bytes:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))       # TEST_ONLY fixed seed
    return key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())


def journal(entries=2, first_us=SH.JOURNAL_COVERAGE_NOT_AFTER_US - 1, extra=b""):
    body = b"".join(b"__CURSOR=s=%d\n__REALTIME_TIMESTAMP=%d\nMESSAGE=hello\n\n" % (i, first_us + i)
                    for i in range(entries))
    return body + extra


class SecretScannerTests(unittest.TestCase):
    def test_every_marker_class_is_found_in_real_private_material(self):
        der = pkcs8_der()
        samples = {
            "ED25519_PKCS8_DER": der,
            "ED25519_PKCS8_HEX": der.hex().encode(),
            "ED25519_PKCS8_BASE64": base64.b64encode(der),
            "PEM_PRIVATE_KEY": b"-----" + b"BEGIN " + b"PRIVATE" + b" KEY-----\n",
            "OPENSSH_PRIVATE_KEY": b"-----" + b"BEGIN OPENSSH" + b" PRIVATE KEY-----\n",
        }
        for name, data in samples.items():
            with self.subTest(name=name):
                self.assertIn(name, dict(SH.scan_bytes(b"noise " + data + b" noise").hits()))
        self.assertIn("ED25519_PKCS8_HEX", dict(SH.scan_bytes(der.hex().upper().encode()).hits()))
        self.assertIn("ED25519_PKCS8_BASE64", dict(SH.scan_bytes(base64.urlsafe_b64encode(der)).hits()))
        self.assertEqual(SH.scan_bytes(b"public material only " * 100).hits(), [])

    def test_markers_split_across_chunks_are_counted_once(self):
        der = pkcs8_der()
        for cut in range(1, len(der)):
            scanner = SH.Scanner()
            scanner.feed(b"x" * 7 + der[:cut])
            scanner.feed(der[cut:] + b"y")
            self.assertEqual(dict(scanner.hits()).get("ED25519_PKCS8_DER"), 1, cut)

    def test_coverage_bound_is_the_m_b2_window_start(self):
        from datetime import datetime, timezone
        start = datetime(2026, 10, 6, 8, 59, 59, tzinfo=timezone.utc)          # M-B2 completion record window
        self.assertEqual(SH.JOURNAL_COVERAGE_NOT_AFTER_US, int(start.timestamp()) * 1_000_000)
        self.assertIn("08:59:59Z", (ROOT / "docs/architecture/current-architecture-acceptance-ledger-v0.1.md")
                      .read_text(encoding="utf-8"))

    def test_this_source_contains_no_marker(self):
        self.assertEqual(SH.scan_bytes((TOOLS / "mb12_secret_hygiene_proof.py").read_bytes()).hits(), [])


class JournalScanTests(unittest.TestCase):
    def scan(self, data, euid=0, chunk=13):
        stream = lambda: (data[i:i + chunk] for i in range(0, len(data), chunk))  # noqa: E731
        return capture(SH.journal_scan, stream=stream, euid=lambda: euid)

    def test_clean_covered_journal_passes(self):
        ok, raw = self.scan(journal(entries=5))
        lines = raw.decode().splitlines()
        self.assertTrue(ok)
        self.assertTrue(lines[0].startswith("JOURNAL: entries=5 bytes="))
        self.assertEqual(lines[-1], f"JOURNAL_SECRET_SCAN=PASS coverageFromUs={SH.JOURNAL_COVERAGE_NOT_AFTER_US - 1}")
        self.assertTrue(SH.journal_transcript_ok(raw))

    def test_leak_rotation_empty_and_privilege_fail(self):
        der = pkcs8_der()
        ok, raw = self.scan(journal(extra=b"MESSAGE=" + der.hex().encode() + b"\n"))
        self.assertFalse(ok)
        self.assertIn(b"FAIL: PRIVATE_MATERIAL_MARKER class=ED25519_PKCS8_HEX count=1", raw)
        self.assertNotIn(der.hex().encode(), raw)
        self.assertNotIn(der[16:].hex().encode(), raw)
        self.assertFalse(SH.journal_transcript_ok(raw))
        ok, raw = self.scan(journal(first_us=SH.JOURNAL_COVERAGE_NOT_AFTER_US + 1))
        self.assertFalse(ok)
        self.assertIn(b"FAIL: JOURNAL_COVERAGE_INCOMPLETE", raw)
        ok, raw = self.scan(b"")
        self.assertIn(b"FAIL: JOURNAL_EMPTY", raw)
        ok, raw = self.scan(journal(), euid=1000)
        self.assertEqual(raw, b"JOURNAL_SECRET_SCAN=FAIL reason=NOT_ROOT\n")

    def test_unreadable_journal_fails(self):
        def broken():
            yield b"__CURSOR=x\n"
            raise OSError("journalctl failed")
        ok, raw = capture(SH.journal_scan, stream=broken, euid=lambda: 0)
        self.assertFalse(ok)
        self.assertIn(b"JOURNAL_SECRET_SCAN=FAIL reason=JOURNAL_UNREADABLE", raw)


class SecretScopeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        ok, self.journal_raw = capture(SH.journal_scan, stream=lambda: iter([journal()]), euid=lambda: 0)
        assert ok

    def tearDown(self):
        self.directory.cleanup()

    def file(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}

    def scope(self, *, drop=None, publication=b'{"publicKey":"AAAA"}\n', journal_raw=None):
        ceremonies = []
        for name, roles in SH.PR1B_CREDENTIAL_CEREMONIES.items():
            items = [{"role": role, **self.file(f"{name}-{role}", b"TEST_ONLY " + name.encode() + b" " +
                                                (publication if role == "PUBLICATION" else b"transcript\n"))}
                     for role in roles if (name, role) != drop]
            ceremonies.append({"ceremony": name, "items": items})
        document = {"scopeType": SH.SCOPE_TYPE, "schemaVersion": 1, "environment": "dev", "ceremonies": ceremonies,
                    "journalScan": self.file("journal-scan", journal_raw or self.journal_raw)}
        return json.dumps(document).encode()

    def test_complete_clean_scope_passes_without_printing_paths(self):
        raw_scope = self.scope()
        ok, raw = capture(SH.prove, raw_scope)
        self.assertTrue(ok, raw)
        self.assertNotIn(str(self.root).encode(), raw)
        self.assertEqual(raw.decode().splitlines()[-1], f"SECRET_HYGIENE_PROOF=PASS scope={SH.scope_digest(raw_scope)}")

    def test_incomplete_scope_and_bad_items_fail(self):
        ok, raw = capture(SH.prove, self.scope(drop=("M-B2", "PUBLICATION")))
        self.assertEqual(raw, b"SECRET_HYGIENE_PROOF=FAIL reason=SCOPE_ROLE_MISSING\n")
        doc = json.loads(self.scope())
        doc["ceremonies"] = doc["ceremonies"][:2]
        ok, raw = capture(SH.prove, json.dumps(doc).encode())
        self.assertEqual(raw, b"SECRET_HYGIENE_PROOF=FAIL reason=SCOPE_CEREMONIES_NOT_EXACT\n")
        doc = json.loads(self.scope())
        doc["ceremonies"][0]["items"][0]["sha256"] = H("other")
        ok, raw = capture(SH.prove, json.dumps(doc).encode())
        self.assertFalse(ok)
        self.assertIn(b"FAIL: ITEM_UNREADABLE_OR_DIGEST_MISMATCH M-B1 TRANSCRIPT", raw)
        ok, raw = capture(SH.prove, b'{"scopeType": 1, "scopeType": 2}')
        self.assertEqual(raw, b"SECRET_HYGIENE_PROOF=FAIL reason=SCOPE_DUPLICATE_KEY\n")

    def test_a_leak_or_a_failed_journal_scan_fails(self):
        der = pkcs8_der()
        ok, raw = capture(SH.prove, self.scope(publication=base64.b64encode(der)))
        self.assertFalse(ok)
        self.assertIn(b"class=ED25519_PKCS8_BASE64", raw)
        self.assertNotIn(base64.b64encode(der), raw)
        _ok, failed = capture(SH.journal_scan, stream=lambda: iter([journal(first_us=SH.JOURNAL_COVERAGE_NOT_AFTER_US
                                                                            + 5)]), euid=lambda: 0)
        ok, raw = capture(SH.prove, self.scope(journal_raw=failed))
        self.assertFalse(ok)
        self.assertIn(b"FAIL: JOURNAL_SCAN_NOT_PASS", raw)
        forged = b"JOURNAL_SECRET_SCAN=PASS coverageFromUs=1\n"           # no JOURNAL line
        ok, raw = capture(SH.prove, self.scope(journal_raw=forged))
        self.assertIn(b"FAIL: JOURNAL_SCAN_NOT_PASS", raw)


# --------------------------------------------------------- PRESERVATION_SET ---

def observation(at="2026-10-12T10:00:00Z", **changes):
    members = []
    for name, path, form in PS.MEMBERS:
        observed = {"kind": "REGULAR", "uid": 0, "gid": 0, "mode": "0644", "size": 1, "sha256": H(name)}
        observed.update(changes.get(name, {}))
        members.append({"name": name, "path": path, "form": form, "observed": observed})
    return PS.canonical({"observationType": PS.OBSERVATION_TYPE, "schemaVersion": 1, "environment": "dev",
                         "observedAt": at, "members": members})


BASELINE = observation()
LATER = observation(at="2026-10-12T12:00:00Z")
ACCEPTED = {hashlib.sha256(BASELINE).hexdigest(): H("owner baseline record")}


class PreservationSetTests(unittest.TestCase):
    def test_members_are_exactly_the_b1b3d_set_and_exclude_custody(self):
        self.assertEqual(len({path for _n, path, _f in PS.MEMBERS}), len(PS.MEMBERS))
        for _name, path, _form in PS.MEMBERS:
            self.assertFalse(path.startswith(PS.EXCLUDED_PREFIXES), path)
        broker = (ROOT / "scripts/verify_broker_dev_current_incarnation.py").read_text(encoding="utf-8")
        for name, path, _form in PS.MEMBERS:
            if name.startswith(("STAGE3_", "BROKER_")) and name not in ("STAGE3_VAULT",):
                leaf = path.rsplit("/", 1)[1]
                self.assertIn(leaf, broker, name)
        installer = (ROOT / "scripts/dev_deployer/install_dev_deployer_boundary.sh").read_text(encoding="utf-8")
        for name in ("B1C_HELPER", "B1C_LIBRARY", "B1C_VERIFIER", "B1C_SUDOERS", "API_UNIT"):
            self.assertIn(dict((n, p) for n, p, _f in PS.MEMBERS)[name], installer, name)
        self.assertEqual(dict(PS.ACCEPTED_BASELINES), {})

    def test_compare_refuses_an_unaccepted_baseline(self):
        ok, raw = capture(PS.compare, BASELINE, LATER)
        self.assertFalse(ok)
        self.assertEqual(raw.decode().strip(), "PRESERVATION_SET_PROOF=FAIL reason=BASELINE_NOT_ESTABLISHED "
                                               f"baseline={hashlib.sha256(BASELINE).hexdigest()}")

    def test_equal_against_an_accepted_baseline_is_the_exact_pass(self):
        ok, raw = capture(PS.compare, BASELINE, LATER, accepted=ACCEPTED)
        self.assertTrue(ok)
        self.assertEqual(raw, PS.expected_pass(hashlib.sha256(BASELINE).hexdigest(), "2026-10-12T10:00:00Z",
                                               hashlib.sha256(LATER).hexdigest(), "2026-10-12T12:00:00Z"))
        self.assertIn(PS.NONCLAIM.encode(), raw)

    def test_changes_gaps_order_and_malformed_inputs_fail(self):
        changed = observation(at="2026-10-12T12:00:00Z", API_UNIT={"sha256": H("edited")})
        ok, raw = capture(PS.compare, BASELINE, changed, accepted=ACCEPTED)
        self.assertFalse(ok)
        self.assertIn(b"FAIL: CHANGED_OR_INCOMPLETE API_UNIT", raw)
        gap = {"B1C_HELPER": {"sha256": None}}
        gap_baseline = observation(**gap)
        ok, raw = capture(PS.compare, gap_baseline, observation(at="2026-10-12T12:00:00Z", **gap),
                          accepted={hashlib.sha256(gap_baseline).hexdigest(): H("r")})
        self.assertIn(b"FAIL: CHANGED_OR_INCOMPLETE B1C_HELPER", raw)
        ok, raw = capture(PS.compare, BASELINE, observation(at="2026-10-12T09:00:00Z"), accepted=ACCEPTED)
        self.assertEqual(raw, b"PRESERVATION_SET_PROOF=FAIL reason=OBSERVATION_NOT_AFTER_BASELINE\n")
        doc = json.loads(LATER)
        doc["members"] = doc["members"][:-1]
        ok, raw = capture(PS.compare, BASELINE, PS.canonical(doc), accepted=ACCEPTED)
        self.assertEqual(raw, b"PRESERVATION_SET_PROOF=FAIL reason=OBSERVATION_MEMBERS_NOT_EXACT\n")
        ok, raw = capture(PS.compare, BASELINE, LATER.replace(b"\n", b" \n"), accepted=ACCEPTED)
        self.assertEqual(raw, b"PRESERVATION_SET_PROOF=FAIL reason=OBSERVATION_MALFORMED\n")

    def test_observe_requires_root_and_records_every_form(self):
        with self.assertRaises(PermissionError):
            PS.observe(euid=lambda: 1000)
        raw = PS.observe(member=lambda path, form: {"kind": "ABSENT"}, euid=lambda: 0, now=lambda: "2026-10-12T10:00:00Z")
        self.assertEqual([m["name"] for m in PS.parse_observation(raw)["members"]], [n for n, _p, _f in PS.MEMBERS])

    @unittest.skipUnless(POSIX, "lstat ownership and symlinks are POSIX")
    def test_observe_member_reads_without_following_links(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "tree/sub").mkdir(parents=True)
            (base / "tree/a").write_bytes(b"a")
            (base / "tree/sub/b").write_bytes(b"b")
            (base / "file").write_bytes(b"secret-free")
            os.symlink("/etc/passwd", base / "link")
            self.assertEqual(PS.observe_member(str(base / "file"), PS.FILE)["sha256"],
                             hashlib.sha256(b"secret-free").hexdigest())
            self.assertEqual(PS.observe_member(str(base / "link"), PS.LINK), {
                **PS.observe_member(str(base / "link"), PS.LINK), "kind": "SYMLINK", "target": "/etc/passwd"})
            self.assertNotIn("sha256", PS.observe_member(str(base / "link"), PS.FILE))
            tree = PS.observe_member(str(base / "tree"), PS.TREE)
            self.assertEqual([name for name, _ in tree["entries"]], ["a", "sub", "sub/b"])
            self.assertEqual(set(PS.observe_member(str(base / "file"), PS.METADATA)), {"kind", "uid", "gid", "mode"})
            self.assertEqual(PS.observe_member(str(base / "absent"), PS.FILE), {"kind": "ABSENT"})
            self.assertEqual(PS.observe_member(str(base / "tree"), PS.LISTING)["names"], ["a", "sub"])


# --------------------------------------------------- PR-B1 builder admission ---

def item(raw, exit_code):
    return T1.proof_item(raw, exit_code)


class BuilderAdmissionTests(unittest.TestCase):
    """The PR-B1 builder admits PR-B2 transcripts only under the exact contracts and a provenance pin."""

    def trust(self, accepted):
        return RI.ReadinessTrustV1(dict(RI.DEV_PINS), T1.T0, accepted, None, None)

    def admit(self, name, raw, exit_code, *, pinned=True):
        accepted = {name: frozenset({hashlib.sha256(raw).hexdigest()})} if pinned else {}
        return RI.admit_proof(name, item(raw, exit_code), self.trust(accepted))

    def refused(self, reason, name, raw, exit_code, **kwargs):
        with self.assertRaises(RI.Refused) as caught:
            self.admit(name, raw, exit_code, **kwargs)
        self.assertEqual(caught.exception.reason, reason, caught.exception.detail)

    def secret_transcript(self):
        test = SecretScopeTests("test_complete_clean_scope_passes_without_printing_paths")
        test.setUp()
        try:
            return capture(SH.prove, test.scope())[1]
        finally:
            test.tearDown()

    def test_mapping_and_pins(self):
        self.assertEqual({n for n, p in RI.PROPOSED_PROOF_PRODUCERS.items() if p is None}, set())
        for name, producer in (("OS_DENIAL", RI.OS_DENIAL_UNIT), ("SECRET_HYGIENE", RI.SECRET_HYGIENE_SCOPE),
                               ("PRESERVATION_SET", RI.PRESERVATION_SET_COMPARE)):
            self.assertEqual(RI.PROPOSED_PROOF_PRODUCERS[name], producer)
            relative = producer.split(":")[0]
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
                             RI.PRODUCER_SCRIPT_SHA256[relative])
        self.assertEqual(dict(RI.DEV_ACCEPTED_PROOF_TRANSCRIPTS), {})

    def test_os_denial_admission(self):
        good = OS.expected_pass(OS.DROPINS_NONE)
        self.assertEqual(self.admit("OS_DENIAL", good, 0)["result"], PA.PASS)
        self.refused("PROOF_PROVENANCE_NOT_ESTABLISHED", "OS_DENIAL", good, 0, pinned=False)
        self.refused("TRANSCRIPT_CONTRACT", "OS_DENIAL", good.replace(b"/etc/lilith-os-dev\n", b""), 0)   # forged
        self.refused("TRANSCRIPT_CONTRACT", "OS_DENIAL", good, 1)                                      # wrong exit
        not_root = (OS.final_line(False, "NOT_ROOT") + "\n").encode()
        self.refused("TRANSCRIPT_CONTRACT", "OS_DENIAL", not_root, 1)                                  # no privilege
        custody = RI.expected_custody_denial_pass("P1B-12")
        self.refused("TRANSCRIPT_CONTRACT", "OS_DENIAL", custody, 0)                                   # wrong producer
        _ok, failed = capture(OS.prove, "UNIT", run=os_run(InaccessiblePaths=""), read=os_read(), euid=lambda: 0)
        self.assertEqual(self.admit("OS_DENIAL", failed, 1)["result"], PA.FAIL)

    def test_secret_hygiene_admission(self):
        good = self.secret_transcript()
        self.assertEqual(self.admit("SECRET_HYGIENE", good, 0)["result"], PA.PASS)
        self.refused("PROOF_PROVENANCE_NOT_ESTABLISHED", "SECRET_HYGIENE", good, 0, pinned=False)
        lines = good.decode().splitlines()
        incomplete = ("\n".join(line for line in lines if " M-B2 " not in line) + "\n").encode()
        self.refused("TRANSCRIPT_CONTRACT", "SECRET_HYGIENE", incomplete, 0)                           # scope gap
        wrong_scope = good.replace(lines[-1].encode(), f"SECRET_HYGIENE_PROOF=PASS scope={H('x')}".encode())
        self.refused("TRANSCRIPT_CONTRACT", "SECRET_HYGIENE", wrong_scope, 0)                          # digest
        self.refused("TRANSCRIPT_CONTRACT", "SECRET_HYGIENE", b"SECRET_HYGIENE_PROOF=PASS scope=" +
                     H("x").encode() + b"\n", 0)                                                      # hand-written
        self.refused("TRANSCRIPT_CONTRACT", "SECRET_HYGIENE", b"SECRET_HYGIENE_PROOF=FAIL reason=USAGE\n", 1)

    def test_preservation_set_admission(self):
        _ok, good = capture(PS.compare, BASELINE, LATER, accepted=ACCEPTED)
        self.refused("TRANSCRIPT_CONTRACT", "PRESERVATION_SET", good, 0)        # the pinned baseline set is EMPTY
        real = RI._producer_module

        def patched(relative):
            module = real(relative)
            if relative.endswith("mb12_preservation_set_proof.py"):
                module.ACCEPTED_BASELINES = ACCEPTED
            return module
        with mock.patch.object(RI, "_producer_module", side_effect=patched):
            self.assertEqual(self.admit("PRESERVATION_SET", good, 0)["result"], PA.PASS)
            self.refused("PROOF_PROVENANCE_NOT_ESTABLISHED", "PRESERVATION_SET", good, 0, pinned=False)
            forged = good.replace(b"EQUAL: API_UNIT", b"EQUAL: API_UNIT ", 1)
            self.refused("TRANSCRIPT_CONTRACT", "PRESERVATION_SET", forged, 0)
            _ok, changed = capture(PS.compare, BASELINE, observation(at="2026-10-12T12:00:00Z",
                                                                     API_UNIT={"mode": "0666"}), accepted=ACCEPTED)
            self.assertEqual(self.admit("PRESERVATION_SET", changed, 1)["result"], PA.FAIL)
            _ok, unaccepted = capture(PS.compare, LATER, LATER)
            self.refused("TRANSCRIPT_CONTRACT", "PRESERVATION_SET", unaccepted, 1)

    def test_producer_script_tamper_invalidates_every_contract(self):
        with mock.patch.dict(RI.PRODUCER_SCRIPT_SHA256,
                             {"services/owner-memory-control/tools/mb12_os_denial_proof.py": H("other")}):
            self.refused("PRODUCER_SCRIPT_NOT_PINNED", "OS_DENIAL", OS.expected_pass(OS.DROPINS_NONE), 0)


@unittest.skipUnless(POSIX, "the synthetic PR-1 host needs POSIX ownership and modes")
class EndToEndTests(unittest.TestCase):
    def test_all_seven_producers_leave_only_the_e19_release_defect(self):
        names = ("OS_DENIAL", "SECRET_HYGIENE", "PRESERVATION_SET")
        transcripts = dict(T1.transcripts())
        transcripts["OS_DENIAL"] = (OS.expected_pass(OS.DROPINS_NONE), 0)
        transcripts["SECRET_HYGIENE"] = (BuilderAdmissionTests().secret_transcript(), 0)
        transcripts["PRESERVATION_SET"] = (capture(PS.compare, BASELINE, LATER, accepted=ACCEPTED)[1], 0)
        real = RI._producer_module

        def patched(relative):
            module = real(relative)
            if relative.endswith("mb12_preservation_set_proof.py"):
                module.ACCEPTED_BASELINES = ACCEPTED
            return module
        with T1.synthetic_host() as (X, host, manifest_sha), \
                mock.patch.object(RI, "_producer_module", side_effect=patched):
            case = T1.ReadinessInputTests("test_build_is_deterministic_and_the_release_parser_accepts_it")
            case.X, case.host, case.manifest_sha = X, host, manifest_sha
            case.pins = T1.fixture_pins(X, host, manifest_sha)
            pr2, pr3, t2, t3 = case.pr2_pr3()
            accepted = {name: frozenset({hashlib.sha256(raw).hexdigest()}) for name, (raw, _e) in transcripts.items()}
            trust = RI.ReadinessTrustV1(case.pins, T1.T0, accepted, t2, t3)
            proofs = {name: item(raw, exit_code) for name, (raw, exit_code) in transcripts.items()}
            raw, report = RI.build(T1.build_inputs(X, host, manifest_sha, proofs=proofs, pr2=pr2, pr3=pr3),
                                   environment="test", trust=trust)
            result = case.evaluate(case.roundtrip(raw))
            failing = {n: o.reason for n, o in result.checks.items() if o.status != "PASS"}
            self.assertEqual(failing, {"E19_ACTIVATION_DARK": "ACTIVATION_NOT_DARK"})
            self.assertEqual(result.status, "NOT_READY")
            self.assertEqual(report["expectedNotReady"], ["E19_ACTIVATION_DARK:ACTIVATION_NOT_DARK"])
            for name in names:
                self.assertEqual(case.roundtrip(raw)["proofs"][name]["result"], PA.PASS)


class SourceGuardTests(unittest.TestCase):
    PRODUCERS = ("mb12_os_denial_proof.py", "mb12_secret_hygiene_proof.py", "mb12_preservation_set_proof.py")

    def test_producers_are_read_only_stdlib_tools(self):
        for name in self.PRODUCERS:
            source = (TOOLS / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                for needle in ("import lilith", "from lilith", "write_bytes", "write_text", "os.remove", "unlink(",
                               "shutil", "\"start\"", "\"restart\"", "daemon-reload", "plink", "gcloud", "socket.",
                               "--now"):
                    self.assertFalse(needle in source, needle)
        self.assertNotIn("open(", (TOOLS / "mb12_os_denial_proof.py").read_text(encoding="utf-8").replace(
            "os.open(", ""))

    def test_release_tree_and_pins_untouched(self):
        import release_file_set
        for name in self.PRODUCERS:
            self.assertFalse(any(name in key for key in release_file_set.SHARED_HASHES), name)
        path = "services/owner-memory-control/lilith_owner_memory/pr1_acceptance.py"
        self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), release_file_set.SHARED_HASHES[path])


if __name__ == "__main__":
    unittest.main()
