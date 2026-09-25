"""Deterministic tests for trusted B1b-1 CI/DEV validation controls."""

from __future__ import annotations

import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import build_core_api_bundle as api_bundle
from scripts import memory_broker_validation as broker


SHA = "a" * 40


class BrokerControlTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.archive = self.root / "validation.tar.gz"
        self.attestation = self.root / "validation.json"

    def populate(self) -> None:
        for name in broker.FILES:
            path = self.candidate / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# synthetic control-test placeholder\n")

    def built(self) -> dict:
        with mock.patch.object(broker, "assert_candidate_sha"):
            return broker.build(self.candidate, self.archive, self.attestation, SHA)

    def rewrite_attested_archive(self, changes: dict[str, bytes]) -> None:
        with tarfile.open(self.archive, "r:gz") as tar:
            payloads = {member.name: tar.extractfile(member).read() for member in tar.getmembers()}
        payloads.update(changes)
        with tarfile.open(self.archive, "w:gz") as tar:
            for name, data in payloads.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        value = json.loads(self.attestation.read_text())
        value["archiveByteSize"] = self.archive.stat().st_size
        value["archiveSha256"] = broker._digest(self.archive.read_bytes())
        self.attestation.write_bytes(broker._canonical(value))

    def test_absent_is_not_applicable(self) -> None:
        self.assertFalse(broker.component_present(self.candidate))
        self.assertIsNone(broker.component_files(self.candidate))
        self.assertIsNone(self.built())

    def test_present_requires_exact_surface(self) -> None:
        (self.candidate / broker.BROKER_ROOT).mkdir(parents=True)
        with self.assertRaisesRegex(broker.ValidationError, "BROKER_FILE_SET_MISMATCH"):
            broker.component_files(self.candidate)
        self.populate()
        self.assertEqual(set(broker.component_files(self.candidate)), broker.FILES)
        (self.candidate / next(iter(broker.BROKER_FILES))).unlink()
        with self.assertRaisesRegex(broker.ValidationError, "BROKER_FILE_SET_MISMATCH"):
            broker.component_files(self.candidate)

    def test_extra_executable_and_symlink_rejected(self) -> None:
        self.populate()
        extra = self.candidate / broker.BROKER_ROOT / "lilith_memory_broker" / "unreviewed.py"
        extra.write_text("pass\n")
        with self.assertRaisesRegex(broker.ValidationError, "BROKER_FILE_SET_MISMATCH"):
            broker.component_files(self.candidate)
        extra.unlink()
        link = self.candidate / broker.BROKER_ROOT / "link.py"
        try:
            link.symlink_to(self.candidate / next(iter(broker.BROKER_FILES)))
        except OSError:
            self.skipTest("symlink creation is unavailable")
        with self.assertRaisesRegex(broker.ValidationError, "SYMLINK"):
            broker.component_files(self.candidate)

    def test_oversize_and_private_material_rejected(self) -> None:
        self.populate()
        selected = self.candidate / sorted(broker.BROKER_FILES)[0]
        selected.write_bytes(b"x" * (broker.MAX_FILE + 1))
        with self.assertRaisesRegex(broker.ValidationError, "OVERSIZED"):
            broker.component_files(self.candidate)
        selected.write_bytes(b"-----BEGIN PRIVATE KEY-----")
        with self.assertRaisesRegex(broker.ValidationError, "PRIVATE_MATERIAL"):
            broker.component_files(self.candidate)

    def test_exact_manifest_and_archive_roundtrip(self) -> None:
        self.populate()
        result = self.built()
        self.assertEqual(result["candidateSha"], SHA)
        self.assertEqual(result["artifactRole"], broker.ROLE)
        self.assertEqual({item["path"] for item in result["files"]}, broker.FILES)
        destination = self.root / "extracted"
        self.assertEqual(broker.verify_extract(self.archive, self.attestation, destination, SHA), result)
        self.assertEqual((destination / next(iter(broker.BROKER_FILES))).read_bytes(), b"# synthetic control-test placeholder\n")

    def test_candidate_sha_mismatch_and_archive_tampering(self) -> None:
        self.populate()
        self.built()
        with self.assertRaisesRegex(broker.ValidationError, "ATTESTATION_IDENTITY_MISMATCH"):
            broker.verify_extract(self.archive, self.attestation, self.root / "wrong", "b" * 40)
        self.archive.write_bytes(self.archive.read_bytes() + b"tampered")
        with self.assertRaisesRegex(broker.ValidationError, "ARTIFACT_DIGEST_MISMATCH"):
            broker.verify_extract(self.archive, self.attestation, self.root / "tampered", SHA)

    def test_oversized_archive_rejected_before_extraction(self) -> None:
        self.populate()
        self.built()
        with self.archive.open("ab") as stream:
            stream.write(b"x" * (broker.MAX_ARCHIVE + 1))
        with self.assertRaisesRegex(broker.ValidationError, "ARTIFACT_MISSING_OR_OVERSIZED"):
            broker.verify_extract(self.archive, self.attestation, self.root / "oversized", SHA)

    def test_file_digest_and_manifest_mismatch(self) -> None:
        self.populate()
        self.built()
        self.rewrite_attested_archive({next(iter(broker.BROKER_FILES)): b"changed"})
        with self.assertRaisesRegex(broker.ValidationError, "FILE_DIGEST_MISMATCH"):
            broker.verify_extract(self.archive, self.attestation, self.root / "changed", SHA)
        self.built()
        self.rewrite_attested_archive({broker.MANIFEST_NAME: b"{}"})
        with self.assertRaisesRegex(broker.ValidationError, "EMBEDDED_MANIFEST_MISMATCH"):
            broker.verify_extract(self.archive, self.attestation, self.root / "manifest", SHA)

    def test_traversal_and_link_member_rejected(self) -> None:
        self.populate()
        self.built()
        self.rewrite_attested_archive({"../escape.py": b"unsafe"})
        with self.assertRaisesRegex(broker.ValidationError, "ARCHIVE_MEMBER_SET_MISMATCH"):
            broker.verify_extract(self.archive, self.attestation, self.root / "traversal", SHA)
        self.built()
        with tarfile.open(self.archive, "r:gz") as tar:
            payloads = {member.name: tar.extractfile(member).read() for member in tar.getmembers()}
        with tarfile.open(self.archive, "w:gz") as tar:
            for name, data in payloads.items():
                info = tarfile.TarInfo(name)
                if name == next(iter(broker.BROKER_FILES)):
                    info.type = tarfile.SYMTYPE
                    info.linkname = "../escape"
                else:
                    info.size = len(data)
                tar.addfile(info, None if info.issym() else io.BytesIO(data))
        value = json.loads(self.attestation.read_text())
        value["archiveByteSize"] = self.archive.stat().st_size
        value["archiveSha256"] = broker._digest(self.archive.read_bytes())
        self.attestation.write_bytes(broker._canonical(value))
        with self.assertRaisesRegex(broker.ValidationError, "UNSAFE_ARCHIVE_MEMBER"):
            broker.verify_extract(self.archive, self.attestation, self.root / "link", SHA)

    def test_compile_and_test_failures_propagate(self) -> None:
        self.populate()
        for failure_call in (1, 3):
            with self.subTest(failure_call=failure_call):
                calls = 0
                def fail(argv, root, env):
                    nonlocal calls
                    calls += 1
                    if calls == failure_call:
                        raise subprocess.CalledProcessError(1, argv)
                with mock.patch.object(broker, "_run", side_effect=fail):
                    with self.assertRaises(subprocess.CalledProcessError):
                        broker.execute(self.candidate)

    def test_empty_test_surface_fails_closed(self) -> None:
        self.populate()
        with mock.patch.object(broker, "_run", wraps=broker._run) as invoked:
            with self.assertRaises(subprocess.CalledProcessError):
                broker.execute(self.candidate)
        self.assertEqual(invoked.call_count, 3)
        self.assertEqual(invoked.call_args_list[2].args[0][-1], "14")

    def test_cleanup_after_success_and_failure(self) -> None:
        self.populate()
        self.built()
        seen = []
        def observe(root, python):
            seen.append(root)
            self.assertTrue(root.exists())
        with mock.patch.object(broker, "execute", side_effect=observe):
            self.assertEqual(broker.run_transient(self.archive, self.attestation, SHA)["status"], "VALIDATED")
        self.assertFalse(seen[-1].exists())
        with mock.patch.object(broker, "execute", side_effect=lambda root, python: (seen.append(root), (_ for _ in ()).throw(RuntimeError("test failed")))):
            with self.assertRaisesRegex(RuntimeError, "test failed"):
                broker.run_transient(self.archive, self.attestation, SHA)
        self.assertFalse(seen[-1].exists())

    def test_candidate_sha_checked_against_checkout(self) -> None:
        with mock.patch.object(broker.subprocess, "run", side_effect=[
            mock.Mock(stdout="b" * 40 + "\n"),
        ]):
            with self.assertRaisesRegex(broker.ValidationError, "CANDIDATE_SHA_MISMATCH"):
                broker.assert_candidate_sha(self.candidate, SHA)

    def test_private_fixture_not_in_api_release(self) -> None:
        names = {name for name, _ in api_bundle._sources(Path(__file__).resolve().parents[1])}
        self.assertFalse(any("memory-broker" in name or "test_owner_proof" in name for name in names))
        self.assertIn("services/core-api/tests/test_owner_proof.py", broker.SHARED_FILES)

    def test_dev_wiring_is_additive_and_proves_cleanup_and_stage_i_state(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/deploy-dev.yml").read_text()
        runner = (root / "scripts/run_memory_broker_dev_validation.sh").read_text()
        self.assertIn("Check out trusted deployment controls", workflow)
        self.assertIn("Check out the exact commit validated by CI", workflow)
        self.assertIn("Build deterministic exact-SHA Core API bundle", workflow)
        self.assertIn("Build separate exact-SHA broker validation artifact", workflow)
        # 15B2b-B1c: broker validation runs on the runner before any cloud
        # authentication; routine DEV deployment has no broker or PROD reach.
        step = "Validate broker candidate transiently before any cloud authentication"
        self.assertIn(step, workflow)
        self.assertLess(workflow.index(step), workflow.index("uses: google-github-actions/auth@v3"))
        self.assertIn("memory_broker_validation.py verify-run", workflow)
        self.assertNotIn("Audit production darkness", workflow)
        self.assertNotIn("/runner.sh", workflow)
        self.assertIn("Publish successful DEV deployment status", workflow)
        self.assertIn('"$SYSTEM_PYTHON" -m venv "$VENV_DIR"', runner)
        self.assertIn("'fido2==2.2.1' 'rfc8785==0.1.4'", runner)
        self.assertIn('rm -rf -- "$VENV_DIR"', runner)
        for marker in ("trap cleanup EXIT", "rmdir -- \"$WORKSPACE\"", "lifecycle.py", "cognitive_memory.dev.db", "privacy_governance.dev.db", 'test "$BEFORE_LIFECYCLE" = "$AFTER_LIFECYCLE"', 'test "$BEFORE_CUSTODY" = "$AFTER_CUSTODY"'):
            self.assertIn(marker, runner)

    def test_ci_requires_broker_in_existing_context(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        self.assertIn("name: Core API tests", workflow)
        self.assertIn("python scripts/memory_broker_validation.py ci --source-root .", workflow)
        self.assertIn("python -m unittest discover -s services/core-api/tests", workflow)
        self.assertIn("python scripts/run_cognitive_regressions.py", workflow)


if __name__ == "__main__":
    unittest.main()
