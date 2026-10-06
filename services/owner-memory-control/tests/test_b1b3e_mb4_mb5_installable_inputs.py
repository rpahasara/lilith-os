"""15B2b-B1b-3e M-B4/M-B5: governed derivation of the installable representations (TEST-ONLY).

Records: docs/architecture/slice-15b2b-b1b3e-mb4-mb5-installable-representation-owner-decision.md,
docs/architecture/slice-15b2b-b1b3e-mb4-mb5-trust-install-remediation.md.

Every key here is a throwaway TEST key (the M-B3 package test `World`), and
the "accepted" sources are that world's bytes. Nothing is installed, nothing
contacts anything. The real accepted export is public but stays outside the
repository: `RealExportTests` runs only when `LILITH_MB3_EXPORT` names it,
and then proves the pinned derived SHA-256 values. Failure messages redact
every 64-hex value.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
CEREMONY = ROOT / "services/authority-dev/ceremony"
for _p in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", TOOLS, CEREMONY,
           Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

HAVE_CRYPTO = all(importlib.util.find_spec(m) is not None for m in ("cryptography", "rfc8785", "fido2"))
REAL_EXPORT = os.environ.get("LILITH_MB3_EXPORT")

REAL = {
    "export": "c4ea3d66fdef3f6b30c63a1f7f4903a3d2d5427f0419c6e1bd7aadd12c9564d8",
    "transport": "3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156",
    "manifest": "9ce94816a28cac159b768f998d072c829b4a7fdd36d1dba3b88c2e57572aa319",
    "wrapper": "300a57dc01690868f7e6fa5dede4f7ca7278505e95b4fbbf0a2d505a18ffdb3f",
    "kact": "d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032",
    "kwit": "9e9dd0787b3d6df8d40730c6abab728cacbe5136269ca4421160da830bb23472",
    "digest": "fa66272131a3ef076036616b07766a377de4fdc1e4fef4cb8a054726f05c14fc",
    "root_anchor": "bc5f00a76b518c4f11b6804d35844c036db75eaa730d56c35f97f430558ff687",
    "witness_anchor": "be360da2324880d725aea509bb0f41500f51ecfc3c2995dd3057824bb471ab5a",
    "registry": "46b0bfc558ec3a19467206ada3dc53c18e8a6a4cd0782711b4800cfe099f8b1e",
}

if HAVE_CRYPTO:
    import test_b1b3e_mb3_registry_package as P  # the TEST world (keys, publications, manifest)
    import install_authority_dev as I
    import mb4_mb5_installable_inputs as D
    import mb4_mb5_trust_install_verifier as V
    from lilith_owner_memory import witness_readiness as WR

    L = P.L


def _r(text: str) -> str:
    import re
    return re.sub(r"[0-9a-f]{64}", "<redacted>", str(text))


class RedactedFailures:
    def _formatMessage(self, msg, standardMsg):
        return _r(super()._formatMessage(msg, standardMsg))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestSources:
    """A signed TEST Registry V1 and its M-B3-shaped inputs, plus matching TEST pins."""

    def __init__(self, directory: Path):
        self.world = P.World(directory)
        kact_value = json.loads(self.world.kact_raw)
        candidate = L.capture_candidate(P.OWNER.registry_v1, kact_value, epoch_random=P.EPOCH,
                                        policy_version=L.POLICY_VERSION, issued_at=P.ISSUED)
        signed = P.OWNER.registry_v1(self.world.root_key(), kact_value, epoch_random=P.EPOCH,
                                     policy_version=L.POLICY_VERSION, issued_at=P.ISSUED)
        self.transport = L.canonical_bytes(signed)
        self.manifest = L.canonical_bytes(P._manifest_for(self.world, candidate))
        self.members = {"registry": self.transport, "manifest": self.manifest, "root": self.world.root_raw,
                        "kact": self.world.kact_raw, "kwit": self.world.kwit_raw}
        self.pins = D.SourcePinsV1(
            export_sha256="0" * 64, registry_transport_sha256=sha(self.transport), manifest_sha256=sha(self.manifest),
            root_wrapper_sha256=sha(self.world.root_raw), kact_publication_sha256=self.world.kact_sha,
            kwit_publication_sha256=sha(self.world.kwit_raw), registry_digest=candidate.registry_digest,
            accepted=self.world.accepted)

    def with_pins(self, **changes):
        import dataclasses
        return dataclasses.replace(self.pins, **changes)


@unittest.skipUnless(HAVE_CRYPTO, "cryptography, rfc8785 and fido2 are required")
class DerivationTests(RedactedFailures, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.src = TestSources(Path(cls.tmp.name))
        cls.derivation = D.derive_from_members(cls.src.members, cls.src.pins)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def refused(self, code, fn, *args, **kw):
        with self.assertRaises(D.DerivationRefusal) as caught:
            fn(*args, **kw)
        self.assertEqual(caught.exception.code, code)

    # ---- the accepted pins in code equal the records -------------------------------------------------------------

    def test_accepted_source_and_derived_pins(self):
        s = D.ACCEPTED_SOURCES
        self.assertEqual((s.export_sha256, s.registry_transport_sha256, s.manifest_sha256, s.root_wrapper_sha256,
                          s.kact_publication_sha256, s.kwit_publication_sha256, s.registry_digest),
                         (REAL["export"], REAL["transport"], REAL["manifest"], REAL["wrapper"], REAL["kact"],
                          REAL["kwit"], REAL["digest"]))
        import dataclasses
        self.assertEqual(dataclasses.astuple(s.accepted), dataclasses.astuple(L.ACCEPTED))
        self.assertEqual(D.DERIVED_SHA256, {"registry-root.json": REAL["root_anchor"],
                                            "witness-anchor.json": REAL["witness_anchor"],
                                            "authority-registry.v1.json": REAL["registry"]})
        self.assertEqual(D.INSTALL_TARGETS, {"registry-root.json": I.REGISTRY_ROOT_ANCHOR,
                                             "witness-anchor.json": I.WITNESS_ANCHOR,
                                             "authority-registry.v1.json": I.REGISTRY_DIR + "/authority-registry.v1.json"})
        p = V.ACCEPTED_PINS
        self.assertEqual((p.root_anchor_sha256, p.witness_anchor_sha256, p.registry_sha256, p.registry_digest),
                         (REAL["root_anchor"], REAL["witness_anchor"], REAL["registry"], REAL["digest"]))
        a = L.ACCEPTED
        self.assertEqual((p.kroot_public_key_sha256, p.kwit_public_key_sha256, p.kwit_key_id, p.kact_public_key_sha256,
                          p.kact_key_id, p.root_key_id, p.policy_version),
                         (a.kroot_public_key_sha256, a.kwit_public_key_sha256, a.kwit_key_id, a.kact_public_key_sha256,
                          a.kact_key_id, L.ROOT_KEY_ID, L.POLICY_VERSION))
        self.assertEqual(p.epoch_random, "11f184889f333dece054f3b91a301632")

    # ---- positive: the three representations ---------------------------------------------------------------------

    def test_registry_is_transport_minus_exactly_one_lf_and_identity_unchanged(self):
        registry = self.derivation.files["authority-registry.v1.json"]
        self.assertEqual(registry + b"\n", self.src.transport)
        self.assertEqual(L._canonical(json.loads(registry)), registry)
        self.assertEqual(L.RC.registry_digest(json.loads(registry)), self.src.pins.registry_digest)
        self.assertEqual(json.loads(registry), json.loads(self.src.transport))   # no semantic change

    def test_root_anchor_is_only_the_registry_root_object(self):
        root = self.derivation.files["registry-root.json"]
        wrapper = json.loads(self.src.world.root_raw)
        self.assertEqual(json.loads(root), wrapper["registryRoot"])
        self.assertEqual(set(json.loads(root)), {"schemaVersion", "rootKeyId", "environment", "algorithm", "publicKey"})
        self.assertEqual(json.loads(root)["algorithm"], "Ed25519")
        key = D.A.TrustedRegistryRootV1.from_dict(json.loads(root)).public_key
        self.assertEqual(sha(key), self.src.world.accepted.kroot_public_key_sha256)
        self.assertNotIn(b"publicKeySha256", root)

    def test_witness_anchor_names_kwit(self):
        anchor = json.loads(self.derivation.files["witness-anchor.json"])
        self.assertEqual(set(anchor), {"schemaVersion", "witnessKeyId", "environment", "algorithm", "publicKey"})
        self.assertEqual(anchor["witnessKeyId"], self.src.world.accepted.kwit_key_id)
        self.assertEqual(sha(D.A._public_key(anchor["publicKey"])), self.src.world.accepted.kwit_public_key_sha256)

    def test_outputs_have_no_newline_and_pass_the_unchanged_installer_and_runtime_parsers(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, data in self.derivation.files.items():
                self.assertFalse(data.endswith(b"\n"), name)
                self.assertEqual(WR.parse_document_bytes(data), json.loads(data))
                path = Path(directory) / name
                path.write_bytes(data)
                self.assertEqual(I._canonical_document(path), data, name)
                path.write_bytes(data + b"\n")                    # the transport form is refused unchanged
                with self.assertRaises(I.InstallError) as caught:
                    I._canonical_document(path)
                self.assertEqual(caught.exception.reason, "INPUT_DOCUMENT_NOT_CANONICAL")
                with self.assertRaises(Exception):
                    WR.parse_document_bytes(data + b"\n")

    def test_deterministic_twice_byte_equal(self):
        again = D.derive_from_members(dict(self.src.members), self.src.pins)
        self.assertEqual(dict(again.files), dict(self.derivation.files))
        with tempfile.TemporaryDirectory() as other:
            fresh = TestSources(Path(other))          # a different world derives different bytes
            self.assertNotEqual(D.derive_from_members(fresh.members, fresh.pins).sha256(), self.derivation.sha256())

    # ---- fail closed: sources, LF, normalization, identity -------------------------------------------------------

    def test_wrong_source_pins_stop(self):
        m, p = self.src.members, self.src.pins
        self.refused("ROOT_WRAPPER_SHA256_MISMATCH", D.derive_root_anchor, m["root"], p.__class__(
            **{**p.__dict__, "root_wrapper_sha256": "1" * 64}))
        self.refused("KWIT_PUBLICATION_SHA256_MISMATCH", D.derive_witness_anchor, m["kwit"],
                     self.src.with_pins(kwit_publication_sha256="1" * 64))
        for field_, code in (("registry_transport_sha256", "REGISTRY_TRANSPORT_SHA256_MISMATCH"),
                             ("manifest_sha256", "MANIFEST_SHA256_MISMATCH"),
                             ("kact_publication_sha256", "KACT_PUBLICATION_SHA256_MISMATCH")):
            self.refused(code, D.derive_registry, m["registry"], manifest_raw=m["manifest"], root_wrapper_raw=m["root"],
                         kact_raw=m["kact"], kwit_raw=m["kwit"], pins=self.src.with_pins(**{field_: "1" * 64}))
        self.refused("REGISTRY_DIGEST_NOT_ACCEPTED", D.derive_registry, m["registry"], manifest_raw=m["manifest"],
                     root_wrapper_raw=m["root"], kact_raw=m["kact"], kwit_raw=m["kwit"],
                     pins=self.src.with_pins(registry_digest="1" * 64))

    def _registry_with(self, transport: bytes):
        return D.derive_registry(transport, manifest_raw=self.src.members["manifest"],
                                 root_wrapper_raw=self.src.members["root"], kact_raw=self.src.members["kact"],
                                 kwit_raw=self.src.members["kwit"],
                                 pins=self.src.with_pins(registry_transport_sha256=sha(transport)))

    def test_registry_lf_and_normalization_rules(self):
        base = self.src.transport[:-1]
        for bad, reason in ((base, "no LF"), (base + b"\n\n", "two LFs"), (base + b"\r\n", "CRLF"),
                            (base + b" \n", "trailing space"), (base.replace(b",", b", ", 1) + b"\n", "inner space")):
            with self.subTest(reason):
                with self.assertRaises(D.DerivationRefusal):
                    self._registry_with(bad)

    def test_registry_field_or_signature_change_stops(self):
        value = json.loads(self.src.transport)
        changed = dict(value, issuedAt="2026-10-06T12:00:01Z")
        with self.assertRaises(D.DerivationRefusal):
            self._registry_with(L.canonical_bytes(changed))
        forged = dict(value, signature=value["signature"][:-2] + ("AA" if value["signature"][-2:] != "AA" else "AB"))
        with self.assertRaises(D.DerivationRefusal):
            self._registry_with(L.canonical_bytes(forged))

    def test_root_wrapper_identity_and_shape_stop(self):
        wrapper = json.loads(self.src.world.root_raw)
        other = dict(wrapper, publicKeySha256="1" * 64)                       # check value inconsistent
        extra = dict(wrapper, note="x")                                       # wrapper field set
        inner = dict(wrapper, registryRoot=dict(wrapper["registryRoot"], rootKeyId="test-only.other.root"))
        env = dict(wrapper, registryRoot=dict(wrapper["registryRoot"], environment="prod"))
        for value in (other, extra, inner, env):
            raw = L.canonical_bytes(value)
            with self.subTest(value=sorted(value)):
                with self.assertRaises(D.DerivationRefusal):
                    D.derive_root_anchor(raw, self.src.with_pins(root_wrapper_sha256=sha(raw)))
        raw = self.src.world.root_raw.rstrip(b"\n")                          # not the accepted wrapper form
        with self.assertRaises(D.DerivationRefusal):
            D.derive_root_anchor(raw, self.src.with_pins(root_wrapper_sha256=sha(raw)))
        with tempfile.TemporaryDirectory() as other_dir:                     # a different K-ROOT is not E-21
            stranger = P.World(Path(other_dir)).root_raw
            with self.assertRaises(D.DerivationRefusal):
                D.derive_root_anchor(stranger, self.src.with_pins(root_wrapper_sha256=sha(stranger)))

    def test_kwit_identity_stops(self):
        import dataclasses
        wrong_key = dataclasses.replace(self.src.world.accepted, kwit_public_key_sha256="1" * 64)
        self.refused("KWIT_PUBLICATION_KWIT_FINGERPRINT_NOT_ACCEPTED", D.derive_witness_anchor,
                     self.src.members["kwit"], self.src.with_pins(accepted=wrong_key))
        wrong_id = dataclasses.replace(self.src.world.accepted, kwit_key_id="test-only.witness.other")
        self.refused("KWIT_PUBLICATION_KWIT_KEY_ID_NOT_ACCEPTED", D.derive_witness_anchor,
                     self.src.members["kwit"], self.src.with_pins(accepted=wrong_id))
        anchor_file = self.src.members["kwit"].replace(b"\n", b"")         # an arbitrary export is not the source
        with self.assertRaises(D.DerivationRefusal):
            D.derive_witness_anchor(anchor_file, self.src.with_pins(kwit_publication_sha256=sha(anchor_file)))

    def test_strict_parse(self):
        for raw, code in ((b'{"a":1,"a":2}', "X_MALFORMED"), (b'{"a":1.5}', "X_MALFORMED"), (b'{"a":NaN}', "X_MALFORMED"),
                          ('{"a":"é"}'.encode("utf-8"), "X_NOT_ASCII"), (b"[1]", "X_MALFORMED")):
            self.refused(code, D.strict_object, raw, "X")

    def test_staged_files_check_and_cli_never_installs(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "out"
            D._write_outputs(out, self.derivation)
            self.assertEqual(sorted(os.listdir(out)), sorted(D.DERIVED_NAMES))
            self.assertEqual(D.check_files(out, self.derivation.sha256()), self.derivation.sha256())
            with self.assertRaises(D.DerivationRefusal):
                D.check_files(out)                                         # TEST bytes are not the real pins
            with self.assertRaises(D.DerivationRefusal):
                D._write_outputs(out, self.derivation)                     # never overwrites
            (out / "extra").write_bytes(b"x")
            with self.assertRaises(D.DerivationRefusal):
                D.check_files(out, self.derivation.sha256())
        report = D.report(self.derivation, self.src.pins)
        self.assertEqual((report["installed"], report["effective"], report["authorityGranted"]), (False, False, False))
        source = (TOOLS / "mb4_mb5_installable_inputs.py").read_text(encoding="utf-8")
        for forbidden in ("subprocess", "socket", "_root_key", "getpass", "Ed25519PrivateKey", "/etc/credstore",
                          "systemctl", "install-anchors", "install-registry"):
            self.assertNotIn(forbidden, source)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(D.main(["install"]), 2)


@unittest.skipUnless(HAVE_CRYPTO and REAL_EXPORT, "set LILITH_MB3_EXPORT to the accepted M-B3 export (public)")
class RealExportTests(RedactedFailures, unittest.TestCase):
    """The pinned values, re-derived from the real accepted export (public bytes only)."""

    def test_real_derivation_equals_the_pins(self):
        members = D.read_export(Path(REAL_EXPORT))
        derivation = D.derive_from_members(members)
        D.check_pins(derivation)
        self.assertEqual(derivation.sha256(), D.DERIVED_SHA256)
        self.assertEqual(sha(members["registry"]), REAL["transport"])
        self.assertEqual(derivation.files["authority-registry.v1.json"] + b"\n", members["registry"])
        self.assertEqual(L.RC.registry_digest(json.loads(derivation.files["authority-registry.v1.json"])),
                         REAL["digest"])
        root = D.A.TrustedRegistryRootV1.from_dict(json.loads(derivation.files["registry-root.json"]))
        self.assertEqual(sha(root.public_key), "cb36daf176d813359b8bd0fe6361f549fd3334a52d0cd1f85cc5247cb26592cf")
        witness = json.loads(derivation.files["witness-anchor.json"])
        self.assertEqual(sha(D.A._public_key(witness["publicKey"])),
                         "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf")
        with tempfile.TemporaryDirectory() as directory:
            for name, data in derivation.files.items():
                path = Path(directory) / name
                path.write_bytes(data)
                self.assertEqual(I._canonical_document(path), data)
        with tarfile.open(REAL_EXPORT) as archive:            # the transport file itself is never changed
            self.assertEqual(sha(archive.extractfile(D.EXPORT_MEMBERS["registry"]).read()), REAL["transport"])


if __name__ == "__main__":
    unittest.main()
