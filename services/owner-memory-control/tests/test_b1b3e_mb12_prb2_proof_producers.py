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


BOOT_A, BOOT_B = "a" * 32, "b" * 32


def entry(realtime_us, boot=BOOT_A, message=b"hello", binary=None):
    out = b"__CURSOR=s=%d\n__REALTIME_TIMESTAMP=%d\n__MONOTONIC_TIMESTAMP=1\n_BOOT_ID=%s\nMESSAGE=%s\n" % (
        realtime_us, realtime_us, boot.encode(), message)
    if binary is not None:
        out += b"BINARY_FIELD\n" + len(binary).to_bytes(8, "little") + binary + b"\n"
    return out + b"\n"


def export(*entries):
    return b"".join(entries)


class _Reader(io.BytesIO):
    def __init__(self, data, *, fail_finish=False):
        super().__init__(data)
        self.fail_finish = fail_finish

    def finish(self):
        if self.fail_finish:
            raise OSError("journalctl failed")


def journal_transcript(*entries, fail_finish=False):
    return capture(SH.journal_scan, stream=lambda: _Reader(export(*entries), fail_finish=fail_finish),
                   euid=lambda: 0)


US = SH.to_us


def covering_journal(**windows):
    """A synthetic journal whose single boot spans every window given (start - 1h ... end + 1h)."""
    low = min(US(w[0]) for w in windows.values()) - 3_600_000_000
    high = max(US(w[1]) for w in windows.values()) + 3_600_000_000
    return journal_transcript(entry(low), entry(high))[1]


# TEST_ONLY ceremony table: the real names and venues, records that exist in this repository, and SYNTHETIC windows
# for the ceremonies whose real window is unrecorded. M-B11 has NOT occurred; its entry here is synthetic.
SYNTHETIC_M_B11 = ("2026-10-12T13:00:00Z", "2026-10-12T13:20:00Z")
TEST_CEREMONIES = {
    **SH.CEREMONIES,
    "M-B9b": SH.CeremonyV1("DEV", "K-WIT signing the V2 genesis", "slice-15b2b-b1b3e-mb9-package-b-completion.md",
                           "GENESIS_CHAIN_1", SH.CEREMONIES["M-B9b"].publication_sha256,
                           ("2026-10-09T04:59:49Z", "2026-10-09T05:10:00Z")),          # synthetic end
    "M-B11": SH.CeremonyV1("DEV", "first K-ACT load (SYNTHETIC)", "slice-15b2b-b1b3e-mb11-signer-start-design.md",
                           None, None, SYNTHETIC_M_B11),
}
DEV_WINDOWS = {n: c.window for n, c in TEST_CEREMONIES.items() if c.venue == "DEV"}


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
        self.assertEqual(SH.scan_bytes(b"public material only " * 100).hits(), [])

    def test_base64_markers_at_every_byte_alignment(self):
        der = pkcs8_der()
        for offset in (0, 1, 2):
            for prefix in (b"", b"\x00\x00", b"\xff\x7f", bytes(range(200, 203))):
                blob = prefix[:offset] + b"\x00" * (offset - len(prefix[:offset])) + der + b"tail"
                for encode in (base64.b64encode, base64.urlsafe_b64encode):
                    with self.subTest(offset=offset, prefix=prefix, encode=encode.__name__):
                        self.assertIn("ED25519_PKCS8_BASE64", dict(SH.scan_bytes(b"x" + encode(blob)).hits()))

    def test_outside_the_contract_is_stated_not_detected(self):
        der = pkcs8_der()
        seed = bytes(range(32))
        for data in (seed, seed.hex().encode(), ":".join(f"{b:02x}" for b in der).encode()):
            self.assertEqual(SH.scan_bytes(data).hits(), [])     # documented nonclaims, never a hidden PASS claim
        source = (TOOLS / "mb12_secret_hygiene_proof.py").read_text(encoding="utf-8")
        for nonclaim in ("never \"no secret ever leaked\"", "Bare 32-byte seeds"):
            self.assertIn(nonclaim, source)

    def test_markers_split_across_chunks_are_counted_once(self):
        der = pkcs8_der()
        for cut in range(1, len(der)):
            scanner = SH.Scanner()
            scanner.feed(b"x" * 7 + der[:cut])
            scanner.feed(der[cut:] + b"y")
            self.assertEqual(dict(scanner.hits()).get("ED25519_PKCS8_DER"), 1, cut)

    def test_this_source_contains_no_marker(self):
        self.assertEqual(SH.scan_bytes((TOOLS / "mb12_secret_hygiene_proof.py").read_bytes()).hits(), [])


class JournalScanTests(unittest.TestCase):
    def test_clean_journal_reports_every_boot(self):
        ok, raw = journal_transcript(entry(10, BOOT_A), entry(20, BOOT_A), entry(30, BOOT_B, binary=b"\x00\x01"))
        lines = raw.decode().splitlines()
        self.assertTrue(ok, raw)
        self.assertEqual(lines[1:3], [f"BOOT: {BOOT_A} firstRealtimeUs=10 lastRealtimeUs=20 entries=2",
                                      f"BOOT: {BOOT_B} firstRealtimeUs=30 lastRealtimeUs=30 entries=1"])
        self.assertEqual(lines[-1], "JOURNAL_SECRET_SCAN=PASS firstRealtimeUs=10 lastRealtimeUs=30")
        self.assertEqual(SH.parse_journal_transcript(raw), [(BOOT_A, 10, 20), (BOOT_B, 30, 30)])

    def test_a_leak_in_a_binary_field_fails_without_echo(self):
        der = pkcs8_der()
        ok, raw = journal_transcript(entry(10, binary=b"pre" + der + b"post"))
        self.assertFalse(ok)
        self.assertIn(b"FAIL: PRIVATE_MATERIAL_MARKER class=ED25519_PKCS8_DER count=1", raw)
        self.assertNotIn(der[16:20].hex().encode(), raw)
        self.assertIsNone(SH.parse_journal_transcript(raw))

    def test_malformed_truncated_oversized_and_unfinished_streams_fail(self):
        cases = {
            "JOURNAL_TRUNCATED": export(entry(10))[:-1],
            "JOURNAL_ENTRY_MALFORMED": b"__CURSOR=x\n__REALTIME_TIMESTAMP=5\nMESSAGE=x\n\n",
            "JOURNAL_MALFORMED": b"\n",
        }
        for reason, data in cases.items():
            with self.subTest(reason=reason):
                ok, raw = capture(SH.journal_scan, stream=lambda d=data: _Reader(d), euid=lambda: 0)
                self.assertFalse(ok)
                self.assertTrue(raw.decode().endswith(f"JOURNAL_SECRET_SCAN=FAIL reason={reason}\n"), raw)
        with mock.patch.object(SH, "MAX_FIELD_BYTES", 16):
            ok, raw = journal_transcript(entry(10, binary=b"x" * 64))
        self.assertIn(b"reason=JOURNAL_FIELD_TOO_LARGE", raw)
        ok, raw = journal_transcript(entry(10), fail_finish=True)                 # journalctl exit != 0
        self.assertIn(b"reason=JOURNAL_UNREADABLE", raw)
        ok, raw = capture(SH.journal_scan, stream=lambda: _Reader(b""), euid=lambda: 0)
        self.assertIn(b"FAIL: JOURNAL_EMPTY", raw)
        ok, raw = capture(SH.journal_scan, stream=lambda: _Reader(export(entry(1))), euid=lambda: 1000)
        self.assertEqual(raw, b"JOURNAL_SECRET_SCAN=FAIL reason=NOT_ROOT\n")

    def test_transcript_parser_rejects_tampering(self):
        _ok, raw = journal_transcript(entry(10, BOOT_A), entry(30, BOOT_B))
        text = raw.decode()
        for forged in (text.replace("entries=2", "entries=3", 1), text.replace("boots=2", "boots=1"),
                       text.replace(f"BOOT: {BOOT_B} firstRealtimeUs=30", f"BOOT: {BOOT_B} firstRealtimeUs=40"),
                       "JOURNAL_SECRET_SCAN=PASS firstRealtimeUs=1 lastRealtimeUs=9\n"):
            self.assertIsNone(SH.parse_journal_transcript(forged.encode()))


class SecretScopeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def file(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}

    def scope(self, *, ceremonies=TEST_CEREMONIES, drop=(), publications=None, journal=None, leak=None):
        entries = []
        for name, spec in ceremonies.items():
            if name in drop:
                continue
            items = [{"role": "TRANSCRIPT", "kind": None, **self.file(f"{name}-t", b"TEST_ONLY transcript " +
                                                                      name.encode() + (leak or b""))}]
            if spec.publication:
                data = (publications or {}).get(name, b"TEST_ONLY publication " + name.encode())
                item = {"role": "PUBLICATION", "kind": spec.publication, **self.file(f"{name}-p", data)}
                if spec.publication_sha256 and name not in (publications or {}):
                    item["sha256"] = spec.publication_sha256      # the recorded pin; bytes stored under it below
                    (self.root / f"{name}-p").write_bytes(b"pinned stand-in")
                entries.append({"ceremony": name, "items": items + [item]})
            else:
                entries.append({"ceremony": name, "items": items})
        journal_raw = journal if journal is not None else covering_journal(**DEV_WINDOWS)
        return json.dumps({"scopeType": SH.SCOPE_TYPE, "schemaVersion": 1, "environment": "dev",
                           "ceremonies": entries, "journalScan": self.file("journal", journal_raw)}).encode()

    def read(self, path, sha256):
        """TEST read: the pinned publications' real bytes are owner-held, so a stand-in is admitted under the pin."""
        data = Path(path).read_bytes()
        if data == b"pinned stand-in":
            return data
        return SH._read_bound(path, sha256)

    def prove(self, raw, **kwargs):
        kwargs.setdefault("ceremonies", TEST_CEREMONIES)
        kwargs.setdefault("unresolved", {})
        return capture(SH.prove, raw, read=self.read, **kwargs)

    def test_closed_synthetic_scope_passes_without_printing_paths(self):
        raw_scope = self.scope()
        ok, raw = self.prove(raw_scope)
        self.assertTrue(ok, raw)
        self.assertNotIn(str(self.root).encode(), raw)
        lines = raw.decode().splitlines()
        self.assertEqual(lines[0], f"SCOPE: sha256={SH.scope_digest(raw_scope)} ceremonies="
                                   "M-B1,M-B2,M-B3,M-B9a,M-B9b,M-B11")
        for name in ("M-B2", "M-B9a", "M-B9b", "M-B11"):
            self.assertTrue(any(line.startswith(f"COVERED: {name} boot=") for line in lines), name)
        for name in ("M-B1", "M-B3"):
            self.assertIn(f"OFFHOST: {name} S25 (no DEV journal)", lines)

    def test_the_real_scope_fails_closed_today(self):
        """M-B11 has not occurred and has no record; M-B9b's end is unrecorded; the K-ACT L2b question is open."""
        ok, raw = capture(SH.prove, self.scope(ceremonies=SH.CEREMONIES), read=self.read)
        self.assertFalse(ok)
        for line in ("FAIL: SCOPE_DECISION_UNRESOLVED B1B3D-L2b", "FAIL: CEREMONY_RECORD_ABSENT M-B11",
                     "FAIL: CEREMONY_WINDOW_NOT_RECORDED M-B9b", "FAIL: CEREMONY_WINDOW_NOT_RECORDED M-B11"):
            self.assertIn(line.encode(), raw)
        self.assertEqual(SH.CEREMONIES["M-B11"].record, None)
        self.assertEqual(SH.CEREMONIES["M-B11"].window, (None, None))

    def test_omitting_m_b3_m_b9a_or_m_b9b_fails(self):
        for name in ("M-B3", "M-B9a", "M-B9b", "M-B1", "M-B2", "M-B11"):
            with self.subTest(name=name):
                ok, raw = self.prove(self.scope(drop=(name,)))
                self.assertEqual(raw, b"SECRET_HYGIENE_PROOF=FAIL reason=SCOPE_CEREMONIES_NOT_EXACT\n")

    def test_publication_rules(self):
        doc = json.loads(self.scope())
        doc["ceremonies"][2]["items"] = doc["ceremonies"][2]["items"][:1]        # M-B3 without SIGNED_REGISTRY_V1
        ok, raw = self.prove(json.dumps(doc).encode())
        self.assertEqual(raw, b"SECRET_HYGIENE_PROOF=FAIL reason=SCOPE_PUBLICATION_NOT_EXACT\n")
        ok, raw = self.prove(self.scope(publications={"M-B3": b"some other registry bytes"}))
        self.assertIn(b"FAIL: PUBLICATION_NOT_THE_RECORDED_ONE M-B3 PUBLICATION:SIGNED_REGISTRY_V1", raw)
        doc = json.loads(self.scope())
        doc["ceremonies"][3]["items"].append({**doc["ceremonies"][3]["items"][0], "role": "PUBLICATION",
                                              "kind": "GENESIS_CHAIN_1"})     # M-B9a publishes nothing
        ok, raw = self.prove(json.dumps(doc).encode())
        self.assertEqual(raw, b"SECRET_HYGIENE_PROOF=FAIL reason=SCOPE_ITEM_NOT_IN_CONTRACT\n")

    def test_journal_newest_entry_before_the_last_ceremony_fails(self):
        early = {name: window for name, window in DEV_WINDOWS.items() if name != "M-B11"}
        ok, raw = self.prove(self.scope(journal=covering_journal(**early)))        # oldest fine, newest too early
        self.assertFalse(ok)
        self.assertIn(b"FAIL: JOURNAL_DOES_NOT_COVER M-B11", raw)

    def test_journal_oldest_entry_after_m_b2_fails(self):
        late = {name: window for name, window in DEV_WINDOWS.items() if name != "M-B2"}
        ok, raw = self.prove(self.scope(journal=covering_journal(**late)))
        self.assertIn(b"FAIL: JOURNAL_DOES_NOT_COVER M-B2", raw)

    def test_endpoints_alone_never_prove_coverage_across_a_boot_gap(self):
        start, end = US(SYNTHETIC_M_B11[0]), US(SYNTHETIC_M_B11[1])
        low = US(DEV_WINDOWS["M-B2"][0]) - 1
        _ok, split = journal_transcript(entry(low, BOOT_A), entry(start + 60_000_000, BOOT_A),
                                        entry(start + 120_000_000, BOOT_B), entry(end + 1, BOOT_B))
        ok, raw = self.prove(self.scope(journal=split))                            # M-B11 spans the boot boundary
        self.assertFalse(ok)
        self.assertIn(b"FAIL: JOURNAL_DOES_NOT_COVER M-B11", raw)

    def test_failed_forged_or_leaking_inputs_fail(self):
        _ok, leaking = journal_transcript(entry(1, binary=pkcs8_der()))
        ok, raw = self.prove(self.scope(journal=leaking))
        self.assertIn(b"FAIL: JOURNAL_SCAN_NOT_PASS", raw)
        ok, raw = self.prove(self.scope(journal=b"JOURNAL_SECRET_SCAN=PASS firstRealtimeUs=1 lastRealtimeUs=9\n"))
        self.assertIn(b"FAIL: JOURNAL_SCAN_NOT_PASS", raw)
        der = pkcs8_der()
        ok, raw = self.prove(self.scope(leak=base64.b64encode(b"x" + der)))
        self.assertIn(b"class=ED25519_PKCS8_BASE64", raw)
        self.assertNotIn(base64.b64encode(b"x" + der), raw)
        doc = json.loads(self.scope())
        doc["ceremonies"][0]["items"][0]["sha256"] = H("other")
        ok, raw = self.prove(json.dumps(doc).encode())
        self.assertIn(b"FAIL: ITEM_UNREADABLE_OR_DIGEST_MISMATCH M-B1 TRANSCRIPT", raw)
        ok, raw = self.prove(b'{"scopeType": 1, "scopeType": 2}')
        self.assertEqual(raw, b"SECRET_HYGIENE_PROOF=FAIL reason=SCOPE_DUPLICATE_KEY\n")

    @unittest.skipUnless(POSIX, "symlinks are POSIX")
    def test_read_bound_is_enforced_while_reading_and_never_follows_links(self):
        big = self.root / "big"
        big.write_bytes(b"x" * 100)
        with mock.patch.object(SH, "MAX_ITEM_BYTES", 10):
            self.assertIsNone(SH._read_bound(str(big), hashlib.sha256(b"x" * 100).hexdigest()))
        os.symlink(big, self.root / "link")
        self.assertIsNone(SH._read_bound(str(self.root / "link"), hashlib.sha256(b"x" * 100).hexdigest()))
        self.assertEqual(SH._read_bound(str(big), hashlib.sha256(b"x" * 100).hexdigest()), b"x" * 100)
        self.assertIsNone(SH._read_bound(str(big), H("other")))

    def test_ceremony_values_are_the_records(self):
        records = ROOT / "docs/architecture"
        for name, spec in SH.CEREMONIES.items():
            with self.subTest(name=name):
                if spec.record:
                    text = (records / spec.record).read_text(encoding="utf-8")
                    if spec.publication_sha256:
                        self.assertIn(spec.publication_sha256, text)
                    for instant in (spec.window or ()):
                        if instant:
                            self.assertIn(instant, text)
        self.assertEqual([n for n, c in SH.CEREMONIES.items() if c.venue == "S25"], ["M-B1", "M-B3"])
        self.assertIn("B1B3D-L2b", SH.UNRESOLVED_SCOPE)


# --------------------------------------------------------- PRESERVATION_SET ---

def observation(at="2026-10-12T10:00:00Z", **changes):
    members = []
    for name, path, form in PS.MEMBERS:
        observed = {"kind": "REGULAR", "uid": 0, "gid": 0, "mode": "0644", "size": 1, "sha256": H(name)}
        observed.update(changes.get(name, {}))
        members.append({"name": name, "path": path, "form": form, "observed": observed})
    return PS.canonical({"observationType": PS.OBSERVATION_TYPE, "schemaVersion": 1, "environment": "dev",
                         "observedAt": at, "limits": dict(PS.LIMITS), "members": members})


BASELINE = observation()
LATER = observation(at="2026-10-12T12:00:00Z")
ACCEPTED = {hashlib.sha256(BASELINE).hexdigest(): H("owner baseline record")}


class PreservationSetTests(unittest.TestCase):
    def test_members_are_exactly_the_b1b3d_set_and_exclude_custody(self):
        self.assertEqual(len(PS.MEMBERS), 22)
        self.assertEqual(len({path for _n, path, _f in PS.MEMBERS}), 22)
        self.assertEqual(dict((n, f) for n, _p, f in PS.MEMBERS)["BROKER_RELEASES"], PS.TREE)
        for _name, path, _form in PS.MEMBERS:
            self.assertFalse(path.startswith(PS.EXCLUDED_PREFIXES), path)
        broker = (ROOT / "scripts/verify_broker_dev_current_incarnation.py").read_text(encoding="utf-8")
        for name, path, _form in PS.MEMBERS:
            if name.startswith(("STAGE3_", "BROKER_")) and name not in ("STAGE3_VAULT",):
                self.assertIn(path.rsplit("/", 1)[1], broker, name)
        installer = (ROOT / "scripts/dev_deployer/install_dev_deployer_boundary.sh").read_text(encoding="utf-8")
        for name in ("B1C_HELPER", "B1C_LIBRARY", "B1C_VERIFIER", "B1C_SUDOERS", "API_UNIT"):
            self.assertIn(dict((n, p) for n, p, _f in PS.MEMBERS)[name], installer, name)
        self.assertEqual(dict(PS.ACCEPTED_BASELINES), {})

    def test_routine_helper_never_writes_the_api_unit(self):
        helper = (ROOT / "scripts/dev_deployer/lilith-dev-deploy").read_text(encoding="utf-8")
        self.assertNotIn("/etc/systemd/system", helper)
        self.assertIn('systemctl restart "${SERVICE_NAME}"', helper)

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

    def test_changes_refusals_order_and_malformed_inputs_fail(self):
        changed = observation(at="2026-10-12T12:00:00Z", API_UNIT={"sha256": H("edited")})
        ok, raw = capture(PS.compare, BASELINE, changed, accepted=ACCEPTED)
        self.assertIn(b"FAIL: CHANGED_OR_INCOMPLETE API_UNIT", raw)
        refused = {"BROKER_RELEASES": {"refused": "TREE_TOO_MANY_ENTRIES"}}
        refused_baseline = observation(**refused)
        ok, raw = capture(PS.compare, refused_baseline, observation(at="2026-10-12T12:00:00Z", **refused),
                          accepted={hashlib.sha256(refused_baseline).hexdigest(): H("r")})
        self.assertIn(b"FAIL: CHANGED_OR_INCOMPLETE BROKER_RELEASES", raw)       # refused == refused is never EQUAL
        ok, raw = capture(PS.compare, BASELINE, observation(at="2026-10-12T09:00:00Z"), accepted=ACCEPTED)
        self.assertEqual(raw, b"PRESERVATION_SET_PROOF=FAIL reason=OBSERVATION_NOT_AFTER_BASELINE\n")
        doc = json.loads(LATER)
        doc["members"] = doc["members"][:-1]
        ok, raw = capture(PS.compare, BASELINE, PS.canonical(doc), accepted=ACCEPTED)
        self.assertEqual(raw, b"PRESERVATION_SET_PROOF=FAIL reason=OBSERVATION_MEMBERS_NOT_EXACT\n")
        doc = json.loads(LATER)
        doc["limits"] = {**doc["limits"], "maxTreeEntries": 10 ** 9}
        ok, raw = capture(PS.compare, BASELINE, PS.canonical(doc), accepted=ACCEPTED)
        self.assertEqual(raw, b"PRESERVATION_SET_PROOF=FAIL reason=OBSERVATION_MALFORMED\n")
        ok, raw = capture(PS.compare, BASELINE, LATER.replace(b"\n", b" \n"), accepted=ACCEPTED)
        self.assertEqual(raw, b"PRESERVATION_SET_PROOF=FAIL reason=OBSERVATION_MALFORMED\n")

    def test_observe_requires_root(self):
        with self.assertRaises(PermissionError):
            PS.observe(euid=lambda: 1000)
        raw = PS.observe(member=lambda path, form: {"kind": "ABSENT"}, euid=lambda: 0, now=lambda: "2026-10-12T10:00:00Z")
        self.assertEqual([m["name"] for m in PS.parse_observation(raw)["members"]], [n for n, _p, _f in PS.MEMBERS])


@unittest.skipUnless(POSIX, "descriptor-relative lstat, symlinks and FIFOs are POSIX")
class PreservationObservationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name)
        release = self.base / "releases/817a83e"
        (release / "venv/lib").mkdir(parents=True)
        (release / "app.py").write_bytes(b"print('broker')\n")
        (release / "venv/lib/mod.py").write_bytes(b"x = 1\n")
        os.symlink("/etc", release / "venv/escape")
        self.releases = str(self.base / "releases")

    def tearDown(self):
        PS._AFTER_LSTAT = None
        self.directory.cleanup()

    def observe(self):
        return PS.observe_member(self.releases, PS.TREE)

    def flat(self, value, prefix=""):
        out = {}
        for name, item in value.get("entries", ()):
            out[prefix + name] = item
            out.update(self.flat(item, prefix + name + "/"))
        return out

    def test_release_contents_are_hashed_and_links_not_followed(self):
        value = self.observe()
        flat = self.flat(value)
        self.assertEqual(flat["817a83e/app.py"]["sha256"], hashlib.sha256(b"print('broker')\n").hexdigest())
        self.assertEqual(flat["817a83e/venv/escape"], {**flat["817a83e/venv/escape"], "kind": "SYMLINK",
                                                       "target": "/etc"})
        self.assertNotIn("entries", flat["817a83e/venv/escape"])
        self.assertTrue(PS.complete(value))

    def test_in_place_modification_addition_and_removal_are_detected(self):
        before = self.observe()
        target = self.base / "releases/817a83e/app.py"
        target.write_bytes(b"print('evil!')\n")                      # same length, in place
        os.utime(target, ns=(1, 1))
        self.assertNotEqual(self.observe(), before)
        target.write_bytes(b"print('broker')\n")
        (self.base / "releases/817a83e/venv/lib/new.py").write_bytes(b"")
        self.assertNotEqual(self.flat(self.observe()).keys(), self.flat(before).keys())
        os.remove(self.base / "releases/817a83e/venv/lib/new.py")
        os.remove(self.base / "releases/817a83e/venv/lib/mod.py")
        self.assertNotIn("817a83e/venv/lib/mod.py", self.flat(self.observe()))
        b, a = observation(), observation(at="2026-10-12T12:00:00Z", BROKER_RELEASES=self.observe())
        ok, raw = capture(PS.compare, observation(BROKER_RELEASES=before), a,
                          accepted={hashlib.sha256(observation(BROKER_RELEASES=before)).hexdigest(): H("r")})
        self.assertIn(b"FAIL: CHANGED_OR_INCOMPLETE BROKER_RELEASES", raw)
        del b

    def test_file_identity_change_during_observation_is_refused(self):
        def swap(dirfd, name):
            if name == "app.py":
                replacement = self.base / "releases/817a83e/app.tmp"
                replacement.write_bytes(b"print('broker')\n")
                os.replace(replacement, self.base / "releases/817a83e/app.py")
        PS._AFTER_LSTAT = swap
        self.assertEqual(self.observe(), {"refused": "IDENTITY_CHANGED"})

    def test_oversized_files_trees_depth_and_unsupported_types_are_refused(self):
        for limit, value, reason in (("maxFileBytes", 4, "FILE_TOO_LARGE"),
                                     ("maxTreeEntries", 3, "TREE_TOO_MANY_ENTRIES"),
                                     ("maxTreeBytes", 10, "TREE_TOO_MANY_BYTES"),
                                     ("maxDepth", 1, "TREE_TOO_DEEP")):
            with self.subTest(limit=limit), mock.patch.dict(PS.LIMITS, {limit: value}):
                self.assertEqual(self.observe(), {"refused": reason})
        os.mkfifo(self.base / "releases/817a83e/pipe")
        self.assertEqual(self.observe(), {"refused": "UNSUPPORTED_TYPE"})

    def test_forms_and_absence(self):
        self.assertEqual(PS.observe_member(str(self.base / "absent"), PS.FILE), {"kind": "ABSENT"})
        self.assertEqual(PS.observe_member(str(self.base / "nodir/x"), PS.FILE), {"kind": "ABSENT"})
        self.assertEqual(PS.observe_member(self.releases, PS.FILE), {"refused": "UNEXPECTED_DIRECTORY",
                                                                     "kind": "DIRECTORY"})
        self.assertEqual(PS.observe_member(str(self.base / "releases/817a83e/app.py"), PS.TREE)["refused"],
                         "NOT_A_DIRECTORY")
        self.assertEqual(set(PS.observe_member(str(self.base / "releases/817a83e/app.py"), PS.METADATA)),
                         {"kind", "uid", "gid", "mode"})
        os.symlink(self.releases, self.base / "current")
        self.assertEqual(PS.observe_member(str(self.base / "current"), PS.LINK)["target"], self.releases)


# --------------------------------------------------- PR-B1 builder admission ---

def item(raw, exit_code):
    return T1.proof_item(raw, exit_code)


def patched_producers(real):
    def patched(relative):
        module = real(relative)
        if relative.endswith("mb12_preservation_set_proof.py"):
            module.ACCEPTED_BASELINES = ACCEPTED
        if relative.endswith("mb12_secret_hygiene_proof.py"):          # TEST_ONLY: a closed scope
            module.CEREMONIES, module.UNRESOLVED_SCOPE = TEST_CEREMONIES, {}
        return module
    return patched


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

    @staticmethod
    def secret_transcript():
        test = SecretScopeTests("test_closed_synthetic_scope_passes_without_printing_paths")
        test.setUp()
        try:
            return test.prove(test.scope())[1]
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
        self.refused("TRANSCRIPT_CONTRACT", "OS_DENIAL", RI.expected_custody_denial_pass("P1B-12"), 0)  # producer
        _ok, failed = capture(OS.prove, "UNIT", run=os_run(InaccessiblePaths=""), read=os_read(), euid=lambda: 0)
        self.assertEqual(self.admit("OS_DENIAL", failed, 1)["result"], PA.FAIL)

    def test_secret_hygiene_is_refused_while_the_real_scope_is_open(self):
        good = self.secret_transcript()
        self.refused("TRANSCRIPT_CONTRACT", "SECRET_HYGIENE", good, 0)            # real producer: scope not closed

    def test_secret_hygiene_admission_under_a_closed_test_scope(self):
        good = self.secret_transcript()
        lines = good.decode().splitlines()
        with mock.patch.object(RI, "_producer_module", side_effect=patched_producers(RI._producer_module)):
            self.assertEqual(self.admit("SECRET_HYGIENE", good, 0)["result"], PA.PASS)
            self.refused("PROOF_PROVENANCE_NOT_ESTABLISHED", "SECRET_HYGIENE", good, 0, pinned=False)
            for label, drop in (("M-B3", " M-B3 "), ("M-B9a", " M-B9a "), ("M-B9b", " M-B9b "),
                                ("coverage", "COVERED: M-B11")):
                forged = ("\n".join(line for line in lines if drop not in line and not line.startswith(drop))
                          + "\n").encode()
                with self.subTest(label=label):
                    self.refused("TRANSCRIPT_CONTRACT", "SECRET_HYGIENE", forged, 0)
            wrong_scope = good.replace(lines[-1].encode(), f"SECRET_HYGIENE_PROOF=PASS scope={H('x')}".encode())
            self.refused("TRANSCRIPT_CONTRACT", "SECRET_HYGIENE", wrong_scope, 0)
            self.refused("TRANSCRIPT_CONTRACT", "SECRET_HYGIENE", b"SECRET_HYGIENE_PROOF=PASS scope=" +
                         H("x").encode() + b"\n", 0)
            self.refused("TRANSCRIPT_CONTRACT", "SECRET_HYGIENE", b"SECRET_HYGIENE_PROOF=FAIL reason=USAGE\n", 1)

    def test_preservation_set_admission(self):
        _ok, good = capture(PS.compare, BASELINE, LATER, accepted=ACCEPTED)
        self.refused("TRANSCRIPT_CONTRACT", "PRESERVATION_SET", good, 0)        # the pinned baseline set is EMPTY
        with mock.patch.object(RI, "_producer_module", side_effect=patched_producers(RI._producer_module)):
            self.assertEqual(self.admit("PRESERVATION_SET", good, 0)["result"], PA.PASS)
            self.refused("PROOF_PROVENANCE_NOT_ESTABLISHED", "PRESERVATION_SET", good, 0, pinned=False)
            self.refused("TRANSCRIPT_CONTRACT", "PRESERVATION_SET", good.replace(b"EQUAL: API_UNIT",
                                                                                 b"EQUAL: API_UNIT ", 1), 0)
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
    def test_all_seven_producers_and_the_corrected_e19_judge_give_synthetic_ready(self):
        """A synthetic TEST result under TEST trust and a closed TEST scope; it says nothing about DEV readiness."""
        transcripts = dict(T1.transcripts())
        transcripts["OS_DENIAL"] = (OS.expected_pass(OS.DROPINS_NONE), 0)
        transcripts["SECRET_HYGIENE"] = (BuilderAdmissionTests.secret_transcript(), 0)
        transcripts["PRESERVATION_SET"] = (capture(PS.compare, BASELINE, LATER, accepted=ACCEPTED)[1], 0)
        with T1.synthetic_host() as (X, host, manifest_sha), \
                mock.patch.object(RI, "_producer_module", side_effect=patched_producers(RI._producer_module)):
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
            # Before the E-19 correction this left exactly E19_ACTIVATION_DARK. TEST trust only: no DEV meaning.
            self.assertEqual(failing, {})
            self.assertEqual(result.status, "READY")
            self.assertEqual(report["expectedNotReady"], [])


class DevFailsClosedTests(unittest.TestCase):
    def test_dev_inputs_still_fail_closed(self):
        with self.assertRaises(RI.Refused) as caught:
            RI.build({}, environment="dev")
        self.assertEqual(caught.exception.reason, "INPUT_MALFORMED")      # OD-M12-3 accepted; still fail-closed
        self.assertEqual(dict(RI.DEV_ACCEPTED_PROOF_TRANSCRIPTS), {})
        self.assertEqual(dict(PS.ACCEPTED_BASELINES), {})
        self.assertTrue(SH.UNRESOLVED_SCOPE)


class SourceGuardTests(unittest.TestCase):
    PRODUCERS = ("mb12_os_denial_proof.py", "mb12_secret_hygiene_proof.py", "mb12_preservation_set_proof.py")

    def test_producers_are_read_only_stdlib_tools(self):
        for name in self.PRODUCERS:
            source = (TOOLS / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                for needle in ("import lilith", "from lilith", "write_bytes", "write_text", "os.remove", "unlink(",
                               "shutil", "\"start\"", "\"restart\"", "daemon-reload", "plink", "gcloud", "socket.",
                               "--now", "O_WRONLY", "O_RDWR", "O_CREAT"):
                    self.assertFalse(needle in source, needle)

    def test_streamed_producers_need_no_file_context(self):
        for name in self.PRODUCERS:
            namespace = {"__name__": "streamed"}
            exec(compile((TOOLS / name).read_text(encoding="utf-8"), "<stdin>", "exec"), namespace)   # no __file__
            self.assertIn("main", namespace, name)

    def test_release_tree_and_pins_untouched(self):
        import release_file_set
        for name in self.PRODUCERS:
            self.assertFalse(any(name in key for key in release_file_set.SHARED_HASHES), name)
        path = "services/owner-memory-control/lilith_owner_memory/pr1_acceptance.py"
        self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), release_file_set.SHARED_HASHES[path])


if __name__ == "__main__":
    unittest.main()
