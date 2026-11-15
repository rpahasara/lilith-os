"""Regression and bypass checks for the protected-main DEV gate classifier."""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import classify_dev_deployment as gate


def changed(path, status="M", old="100644", new="100644"):
    return path, status, old, new


# ---------------------------------------------------------------- Next.js server-boundary guard
# The classifier is path-based. This structural guard (run by CI on every PR, before deploy-dev can run) keeps the
# frontend lane honest: every module that runs or reaches privileged code on the Next.js server must be outside it.
_SPEC = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)["']([^"'\n]+)["']""")  # import/export-from, side-effect, dynamic, require
_NON_LITERAL_LOAD = re.compile(r"""\b(?:import|require)\s*\(\s*(?!["'])""")
_SERVER_DIRECTIVE = re.compile(r"""["']use server["']""")
_SERVER_PACKAGES = ("server-only", "next/headers", "next/cache")  # server-only APIs (next/server types are also used by tests)
_SECRET_ENV = re.compile(r"process\.env\.(?!NEXT_PUBLIC_|NODE_ENV\b)[A-Za-z_]")
_SUFFIXES = ("", ".ts", ".tsx", ".js", ".mjs", "/index.ts", "/index.tsx", "/index.js")


def server_boundary_violations(root):
    """Return (module, reason) pairs for privileged Next.js server modules the frontend lane would admit."""
    src = root / "src"
    files = sorted(p for p in src.rglob("*") if p.is_file() and p.suffix in (".ts", ".tsx", ".js", ".mjs"))
    text = {p: p.read_text(encoding="utf-8") for p in files}
    rel = {p: p.relative_to(root).as_posix() for p in files}

    def resolve(owner, spec):
        if spec.startswith("@/"):
            base = src / spec[2:]
        elif spec.startswith((".", "/")):
            base = owner.parent / spec
        else:
            return None  # package
        for suffix in _SUFFIXES:
            candidate = Path(os.path.normpath(str(base) + suffix))
            if candidate.is_file():
                return candidate
        return "unresolved"

    imports, packages, problems = {}, {}, []
    for path in files:
        imports[path], packages[path] = set(), set()
        for spec in _SPEC.findall(text[path]):
            target = resolve(path, spec)
            if target is None:
                packages[path].add(spec)
            elif target == "unresolved":
                problems.append((rel[path], f"unresolved import {spec!r}"))
            else:
                imports[path].add(target)

    # Code that RUNS on the Next.js server: entry points, server actions, server-only API users.
    server_roots = {
        p for p in files
        if p.name in gate.FRONTEND_SERVER_FILENAMES
        or _SERVER_DIRECTIVE.search(text[p])
        or packages[p].intersection(_SERVER_PACKAGES)
    }
    # Code that TOUCHES privileged material: the listed server modules, secret env readers, and the server roots.
    privileged = server_roots | {p for p in files if rel[p] in gate.FRONTEND_SERVER_PATHS or _SECRET_ENV.search(text[p])}

    server_side = set(server_roots)                 # forward: everything server code loads (static, re-export,
    pending = list(server_roots)                    # side-effect, literal dynamic import, require)
    while pending:
        for target in imports[pending.pop()]:
            if target not in server_side:
                server_side.add(target)
                pending.append(target)
    grew = True                                     # reverse: everything that loads privileged code, transitively
    while grew:
        grew = False
        for path in files:
            if path not in privileged and imports[path] & privileged:
                privileged.add(path)
                grew = True

    for path in sorted(server_side):
        if _NON_LITERAL_LOAD.search(text[path]):
            problems.append((rel[path], "non-literal dynamic import/require in server-side module"))
    for path in sorted(server_side | privileged):
        if gate.is_frontend_only(rel[path], "M", "100644", "100644"):
            problems.append((rel[path], "server-side or privileged module admitted to the frontend lane"))
    return sorted(problems)


class DevGateClassifierTests(unittest.TestCase):
    def classify(self, *entries, blobs=None):
        return gate.classify_entries(list(entries), blobs or {})

    def test_exact_stage_ii_workflow_is_control_only(self):
        self.assertEqual(
            self.classify(changed(".github/workflows/memory-broker-dev-stage2-runtime.yml", "A", "000000")),
            gate.CONTROL_ONLY_NO_DEPLOY,
        )

    def test_exact_stage_ii_harness_test_is_control_only(self):
        self.assertEqual(
            self.classify(changed("scripts/test_memory_broker_stage2_control.py", "A", "000000")),
            gate.CONTROL_ONLY_NO_DEPLOY,
        )

    def test_architecture_and_allowed_control_are_control_only(self):
        self.assertEqual(
            self.classify(
                changed("docs/architecture/slice-15b2b-b1b2b-stage2-runtime-control.md", "A", "000000"),
                changed("scripts/memory_broker_stage2_control.py", "A", "000000"),
            ),
            gate.CONTROL_ONLY_NO_DEPLOY,
        )

    def test_reviewed_installer_revision_only(self):
        for path, pinned in gate.PINNED_CANDIDATE_BLOBS.items():
            self.assertEqual(self.classify(changed(path), blobs={path: pinned}), gate.CONTROL_ONLY_NO_DEPLOY)
            self.assertEqual(self.classify(changed(path), blobs={path: "0" * 40}), gate.DEPLOY_REQUIRED)

    def test_exact_pr_46_control_plane_surface_needs_no_application_deploy(self):
        self.assertEqual(
            self.classify(*(changed(path) for path in (
                ".github/workflows/ci.yml",
                ".github/workflows/deploy-dev.yml",
                "scripts/test_pr_ci_dev_separation.py",
                "scripts/classify_dev_deployment.py",
                "scripts/test_classify_dev_deployment.py",
            ))),
            gate.CONTROL_ONLY_NO_DEPLOY,
        )

    def test_exact_premerge_broker_validation_control_tests_are_control_only(self):
        self.assertEqual(self.classify(*(changed(path) for path in (
            ".github/workflows/deploy-dev.yml",
            "scripts/test_broker_only_dev_workflow.py",
            "scripts/test_pr_ci_dev_separation.py",
            "scripts/classify_dev_deployment.py",
            "scripts/test_classify_dev_deployment.py",
        ))), gate.CONTROL_ONLY_NO_DEPLOY)
        self.assertEqual(self.classify(changed("scripts/unreviewed_broker_workflow.py")),
                         gate.DEPLOY_REQUIRED)

    def test_docs_and_tests_only_need_no_application_deploy(self):
        self.assertEqual(self.classify(
            changed("docs/architecture/slice-15b2b-b1b2b-stage2-runtime-control.md"),
            changed("scripts/test_broker_dev_lifecycle.py"),
        ), gate.CONTROL_ONLY_NO_DEPLOY)

    def test_snapshot_validator_and_tests_use_separate_install_path(self):
        self.assertEqual(self.classify(*(changed(path) for path in (
            "scripts/verify_broker_dev_lifecycle.py",
            "scripts/test_broker_dev_lifecycle.py",
            "scripts/test_trusted_broker_snapshot_linux.py",
            "scripts/test_broker_candidate_dev_snapshot.py",
        ))), gate.CONTROL_ONLY_NO_DEPLOY)

    def test_exact_snapshot_control_plane_is_control_only(self):
        installer = "scripts/trusted_broker_snapshot_installer.py"
        snapshot = "scripts/broker_candidate_dev_snapshot.py"
        for path in (installer, snapshot):
            with self.subTest(path=path):
                self.assertEqual(self.classify(changed(path)), gate.CONTROL_ONLY_NO_DEPLOY)
        self.assertEqual(self.classify(*(changed(path) for path in (
            installer, snapshot,
            "scripts/test_trusted_broker_snapshot.py",
            "scripts/test_broker_candidate_dev_snapshot.py",
            "docs/architecture/slice15b2b-trusted-snapshot-install-acceptance-contract.md",
        ))), gate.CONTROL_ONLY_NO_DEPLOY)
        self.assertEqual(self.classify(
            changed("scripts/classify_dev_deployment.py"),
            changed("scripts/test_classify_dev_deployment.py"),
        ), gate.CONTROL_ONLY_NO_DEPLOY)
        for runtime in (
            "services/memory-broker/lilith_memory_broker/unreviewed.py",
            "services/core-api/app.py",
            "services/memory-broker/deploy/lilith-memory-broker.service",
            "scripts/unreviewed_runtime.py",
        ):
            with self.subTest(runtime=runtime):
                self.assertEqual(self.classify(changed(runtime)), gate.DEPLOY_REQUIRED)
                self.assertEqual(self.classify(changed(installer), changed(runtime)),
                                 gate.DEPLOY_REQUIRED)

    def test_runtime_and_unknown_paths_require_deploy(self):
        for path in (
            "services/core-api/app.py",
            "services/core-api/lilith_memory/owner_proof.py",
            "services/core-api/requirements.txt",
            "services/memory-broker/deploy/lilith-memory-broker.service",
            "services/memory-broker/lilith_memory_broker/unreviewed.py",
            "scripts/memory_broker_os_release.py",
            "scripts/memory_broker_validation.py",
            "scripts/deploy_core_api_dev_remote.sh",
            "scripts/run_memory_broker_dev_validation.sh",
            "scripts/audit_core_api_production_read_only.py",
            ".github/workflows/unreviewed.yml",
            ".github/changed-mode.json",
            "docs/architecture/unreviewed.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.classify(changed(path)), gate.DEPLOY_REQUIRED)

    def test_exact_broker_source_and_test_paths_use_candidate_lane(self):
        for path in sorted(gate.BROKER_CANDIDATE_PATHS):
            with self.subTest(path=path):
                self.assertEqual(self.classify(changed(path)), gate.BROKER_CANDIDATE_VALIDATE_ONLY)
        self.assertEqual(self.classify(
            changed("services/memory-broker/lilith_memory_broker/dev_core.py"),
            changed("services/memory-broker/tests/test_dev_synthetic.py"),
            changed("docs/architecture/slice15b2b-stage3-a2-fault-seam.md", "A", "000000"),
        ), gate.BROKER_CANDIDATE_VALIDATE_ONLY)

    def test_stage3_transition_is_control_only_and_not_a_dev_deployment(self):
        for path in (
            "scripts/memory_broker_stage3_transition.py",
            "scripts/memory_broker_stage3_liveness.py",
            "scripts/memory_broker_stage3_guard_worker.py",
            "scripts/memory_broker_stage3_adapters.py",
            "scripts/memory_broker_stage3_final.py",
            "scripts/memory_broker_stage3_dispatch.py",
            "scripts/memory_broker_stage3_wiring_install.py",
            "scripts/test_memory_broker_stage3_transition.py",
            "scripts/test_memory_broker_stage3_liveness.py",
            "scripts/test_memory_broker_stage3_guard_linux.py",
            "scripts/test_memory_broker_stage3_adapters.py",
            "scripts/test_memory_broker_stage3_final.py",
            "scripts/test_memory_broker_stage3_wiring.py",
            "docs/architecture/slice15b2b-stage3-a2-reversible-transition.md",
            "docs/architecture/slice15b2b-stage3-a2-control-adapters.md",
            "docs/architecture/slice15b2b-stage3-a2-final-controller.md",
            "docs/architecture/slice15b2b-stage3-a2-operational-wiring.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.classify(changed(path, "A", "000000")),
                                 gate.CONTROL_ONLY_NO_DEPLOY)

    def test_broker_mixed_or_self_modifying_diff_requires_full_deploy(self):
        broker = changed("services/memory-broker/lilith_memory_broker/dev_core.py")
        for other in (
            changed("services/core-api/app.py"),
            changed("services/core-api/lilith_memory/owner_proof.py"),
            changed(".github/workflows/deploy-dev.yml"),
            changed("scripts/classify_dev_deployment.py"),
            changed("scripts/run_memory_broker_dev_validation.sh"),
            changed("scripts/memory_broker_validation.py"),
            changed("services/memory-broker/lilith_memory_broker/unknown.py", "A", "000000"),
            changed("scripts/test_memory_broker_stage2_control.py"),
        ):
            with self.subTest(other=other):
                self.assertEqual(self.classify(broker, other), gate.DEPLOY_REQUIRED)
        for status, old, new in (("D", "100644", "000000"),
                                 ("M", "100644", "120000"),
                                 ("M", "120000", "100644")):
            self.assertEqual(self.classify(changed(broker[0], status, old, new)),
                             gate.DEPLOY_REQUIRED)

    def test_mixed_control_and_runtime_requires_deploy(self):
        self.assertEqual(
            self.classify(
                changed("scripts/test_memory_broker_stage2_control.py"),
                changed("services/core-api/app.py"),
            ),
            gate.DEPLOY_REQUIRED,
        )

    def test_e23_e5_fix_is_control_only_and_nothing_else_is(self):
        e23 = (
            "services/owner-memory-control/tools/e23_release_stages.py",
            "services/owner-memory-control/tools/e23_operator.py",
            "services/owner-memory-control/tests/test_trackb_e23_release_stages.py",
            "services/owner-memory-control/tests/test_trackb_e23_operator.py",
            "docs/architecture/trackb-e23-e5-adjudication.md",
        )
        this_pr = (*e23, "scripts/classify_dev_deployment.py", "scripts/test_classify_dev_deployment.py")
        self.assertEqual(self.classify(*(changed(path) for path in this_pr)), gate.CONTROL_ONLY_NO_DEPLOY)
        for extra in (
            changed("services/core-api/app.py"),                                   # Core API application code
            changed("services/core-api/lilith_memory/privacy_anchor_contracts.py"),
            changed("services/owner-memory-control/tools/e23_privacy_anchor_upgrade.py"),   # not exempted
            changed("services/owner-memory-control/tools/e22_operator.py"),
            changed("services/owner-memory-control/tools/unknown.py", "A", "000000"),
            changed("docs/architecture/trackb-e23-transition.md"),
            changed(e23[0], "D", "100644", "000000"),                              # a deletion
            changed(e23[0], "M", "100644", "120000"),                              # a symlink swap
        ):
            with self.subTest(extra=extra):
                self.assertEqual(self.classify(*(changed(path) for path in this_pr[1:]), extra),
                                 gate.DEPLOY_REQUIRED)
        self.assertEqual(self.classify(changed("services/core-api/app.py")), gate.DEPLOY_REQUIRED)

    def test_fm1_transition_tooling_is_control_only_and_nothing_else_is(self):
        fm1 = (
            "services/owner-memory-control/tools/fm1_signer_upgrade.py",
            "services/owner-memory-control/tools/fm1_release_stages.py",
            "services/owner-memory-control/tools/fm1_operator.py",
            "services/owner-memory-control/tests/test_first_memory_fm1_transition.py",
            "docs/architecture/first-memory-fm1-release-transition.md",
        )
        this_pr = (*(changed(path, "A", "000000") for path in fm1), changed("scripts/classify_dev_deployment.py"),
                   changed("scripts/test_classify_dev_deployment.py"))
        self.assertEqual(self.classify(*this_pr), gate.CONTROL_ONLY_NO_DEPLOY)
        for extra in (
            changed("services/authority-dev/lilith_authority_dev/issuance.py"),     # release payload
            changed("services/owner-memory-control/tools/first_memory_dev_host.py"),
            changed("services/owner-memory-control/tools/fm1_operator.py", "M", "100644", "120000"),   # symlink swap
            changed(fm1[0], "D", "100644", "000000"),                              # a deletion
        ):
            with self.subTest(extra=extra):
                self.assertEqual(self.classify(*this_pr[1:], extra), gate.DEPLOY_REQUIRED)

    def test_fm2_transition_and_origin_forget_tooling_is_control_only_and_nothing_else_is(self):
        fm2 = (
            "services/owner-memory-control/tools/fm2_signer_upgrade.py",
            "services/owner-memory-control/tools/fm2_release_stages.py",
            "services/owner-memory-control/tools/fm2_operator.py",
            "services/owner-memory-control/tools/relationship_origin_forget_dev.py",
            "services/owner-memory-control/tests/fm2_transform.py",
            "services/owner-memory-control/tests/test_personal_memory_fm2_transition.py",
            "services/owner-memory-control/tests/test_relationship_origin_forget_dev.py",
            "docs/architecture/personal-memory-fm2-dev-activation.md",
        )
        this_pr = (*(changed(path, "A", "000000") for path in fm2), changed("scripts/classify_dev_deployment.py"),
                   changed("scripts/test_classify_dev_deployment.py"))
        self.assertEqual(self.classify(*this_pr), gate.CONTROL_ONLY_NO_DEPLOY)
        for extra in (
            changed("services/authority-dev/lilith_authority_dev/protocol.py"),     # release payload
            changed("services/core-api/lilith_memory/privacy_forget_runner.py"),    # Core API runtime
            changed("services/owner-memory-control/tools/first_memory_dev_host.py"),
            changed(fm2[3], "M", "100644", "120000"),                              # symlink swap
            changed(fm2[0], "D", "100644", "000000"),                              # a deletion
        ):
            with self.subTest(extra=extra):
                self.assertEqual(self.classify(*this_pr[1:], extra), gate.DEPLOY_REQUIRED)

    def test_owner_prod_p3_transition_tooling_is_control_only_and_nothing_else_is(self):
        p3 = (
            "services/owner-memory-control/tools/owner_prod_release_stages.py",
            "services/owner-memory-control/tools/owner_prod_operator.py",
            "services/owner-memory-control/tests/owner_prod_transform.py",
            "services/owner-memory-control/tests/test_owner_prod_p3_transition.py",
            "docs/architecture/canonical-memory-p3-dev-transition.md",
        )
        modified = ("services/owner-memory-control/tools/owner_prod_signer_upgrade.py",
                    "services/owner-memory-control/tests/test_owner_prod_signer_upgrade.py")
        this_pr = (*(changed(path, "A", "000000") for path in p3), *(changed(path) for path in modified),
                   changed("scripts/classify_dev_deployment.py"), changed("scripts/test_classify_dev_deployment.py"))
        self.assertEqual(self.classify(*this_pr), gate.CONTROL_ONLY_NO_DEPLOY)
        for extra in (
            changed("services/authority-dev/lilith_authority_dev/profile.py"),      # release payload
            changed("services/core-api/lilith_memory/privacy_forget_runner.py"),    # Core API runtime
            changed("services/owner-memory-control/tools/owner_prod_keygen.py"),    # a PROD ceremony tool
            changed(p3[1], "M", "100644", "120000"),                               # symlink swap
            changed(modified[0], "D", "100644", "000000"),                         # a deletion
        ):
            with self.subTest(extra=extra):
                self.assertEqual(self.classify(*this_pr[1:], extra), gate.DEPLOY_REQUIRED)

    def test_source_consolidation_record_is_control_only_at_its_reviewed_revision(self):
        record = {
            "docs/adr/0016-private-repository-holds-reviewed-runtime-source.md": "A",
            "docs/adr/README.md": "M",
            "docs/engineering/source-consolidation-2026-10.md": "A",
            "docs/engineering/vm-only-source-gaps.md": "A",
        }
        reviewed = {path: gate.PINNED_CANDIDATE_BLOBS[path] for path in record}
        entries = [changed(path, status, "000000" if status == "A" else "100644") for path, status in record.items()]
        self.assertEqual(self.classify(*entries, blobs=reviewed), gate.CONTROL_ONLY_NO_DEPLOY)
        for path in record:
            with self.subTest(other_revision=path):
                self.assertEqual(self.classify(*entries, blobs={**reviewed, path: "f" * 40}), gate.DEPLOY_REQUIRED)
        self.assertEqual(self.classify(*entries), gate.DEPLOY_REQUIRED)               # revision unknown
        for extra in (
            changed("services/core-api/app.py"),
            changed("docs/adr/0017-unreviewed.md", "A", "000000"),
            changed("docs/engineering/development.md"),
            changed("docs/adr/README.md", "D", "100644", "000000"),
        ):
            with self.subTest(extra=extra):
                self.assertEqual(self.classify(*entries[:1], extra, blobs=reviewed), gate.DEPLOY_REQUIRED)

    def test_runner_amendment_is_control_only_at_its_reviewed_revision_only(self):
        pinned = (
            "services/owner-memory-control/tests/test_b1b3e_mb11_signer_start.py",
            "services/owner-memory-control/tests/test_b1b3e_mb11_restart_boundary.py",
            "docs/architecture/ci-contracts-runner-amendment-20261105.md",
        )
        reviewed = {path: gate.PINNED_CANDIDATE_BLOBS[path] for path in pinned}
        entries = [changed(pinned[0]), changed(pinned[1]), changed(pinned[2], "A", "000000"),
                   changed(".github/workflows/ci.yml"), changed("scripts/test_memory_broker_stage2_control.py"),
                   changed("scripts/classify_dev_deployment.py"), changed("scripts/test_classify_dev_deployment.py")]
        self.assertEqual(self.classify(*entries, blobs=reviewed), gate.CONTROL_ONLY_NO_DEPLOY)
        self.assertEqual(self.classify(*entries), gate.DEPLOY_REQUIRED)                  # revision unknown
        for path in pinned:
            with self.subTest(other_revision=path):
                self.assertEqual(self.classify(*entries, blobs={**reviewed, path: "f" * 40}), gate.DEPLOY_REQUIRED)
        for extra in (
            changed("services/owner-memory-control/tests/test_b1b3e_mb11_operator.py"),
            changed("services/owner-memory-control/tools/mb11_operator.py"),
            changed("docs/architecture/slice-15b2b-b1b3e-mb11-signer-start-design.md"),
            changed("services/core-api/app.py"),
            changed(pinned[2], "D", "100644", "000000"),
        ):
            with self.subTest(extra=extra):
                self.assertEqual(self.classify(*entries, extra, blobs=reviewed), gate.DEPLOY_REQUIRED)

    def test_deploy_gate_runner_addendum_is_control_only_at_the_reviewed_record_only(self):
        record = "docs/architecture/ci-contracts-runner-amendment-20261105.md"
        entries = [changed(".github/workflows/deploy-dev.yml"), changed(record),
                   changed("scripts/test_pr_ci_dev_separation.py"), changed("scripts/test_memory_broker_stage2_control.py"),
                   changed("scripts/classify_dev_deployment.py"), changed("scripts/test_classify_dev_deployment.py")]
        reviewed = {record: gate.PINNED_CANDIDATE_BLOBS[record]}
        self.assertEqual(self.classify(*entries, blobs=reviewed), gate.CONTROL_ONLY_NO_DEPLOY)
        self.assertEqual(self.classify(*entries, blobs={record: "0169fb517c469f38469fdec056dceb3c75829bca"}),
                         gate.DEPLOY_REQUIRED)                                    # the #322 revision is superseded
        self.assertEqual(self.classify(*entries), gate.DEPLOY_REQUIRED)
        for extra in (changed(".github/workflows/deploy.yml"), changed("scripts/dev_deployer/lilith-dev-deploy"),
                      changed("services/core-api/app.py")):
            with self.subTest(extra=extra):
                self.assertEqual(self.classify(*entries, extra, blobs=reviewed), gate.DEPLOY_REQUIRED)

    def test_new_preserved_hermes_source_is_control_only_and_nothing_else_is(self):
        additions = [
            changed("integrations/hermes/README.md", "A", "000000"),
            changed("integrations/hermes/patches/dev-f9c2.patch", "A", "000000"),
            changed("integrations/hermes/release/dev-f9c2/bin/install_f9c.sh", "A", "000000", "100755"),
            changed("integrations/hermes/home/lilith_router/config.py", "A", "000000"),
            changed("integrations/hermes/history/.gitattributes", "A", "000000"),
        ]
        self.assertEqual(self.classify(*additions), gate.CONTROL_ONLY_NO_DEPLOY)
        record = "docs/adr/0016-private-repository-holds-reviewed-runtime-source.md"
        self.assertEqual(self.classify(*additions, changed(record, "A", "000000"),
                                       blobs={record: gate.PINNED_CANDIDATE_BLOBS[record]}),
                         gate.CONTROL_ONLY_NO_DEPLOY)
        for extra in (
            changed("integrations/hermes/README.md"),                                  # modification
            changed("integrations/hermes/README.md", "D", "100644", "000000"),          # deletion
            changed("integrations/hermes/home/link.py", "A", "000000", "120000"),        # new symlink
            changed("integrations/hermes/vendor", "A", "000000", "160000"),              # new submodule
            changed("integrations/hermes/tools/run.sh", "M", "100644", "100755"),        # mode change
            changed("integrations/hermesx/new.py", "A", "000000"),                       # sibling prefix
            changed("integrations/other/new.py", "A", "000000"),
            changed("integrations/README.md", "A", "000000"),
            changed("services/core-api/lilith_memory/new_module.py", "A", "000000"),     # bundled by glob
            changed("services/core-api/app.py"),
            changed("scripts/new_tool.py", "A", "000000"),
            changed(".github/workflows/hermes.yml", "A", "000000"),
        ):
            with self.subTest(extra=extra):
                self.assertEqual(self.classify(*additions, extra), gate.DEPLOY_REQUIRED)
        self.assertEqual(
            self.classify(changed("services/core-api/app.py", "D", "100644", "000000"),
                          changed("integrations/hermes/app.py", "A", "000000")),
            gate.DEPLOY_REQUIRED,
        )

    def test_preserved_hermes_source_is_not_deployed_by_any_path(self):
        from scripts import build_core_api_bundle as bundle
        root = Path(__file__).resolve().parents[1]
        self.assertFalse(any(path.startswith(gate.PRESERVED_SOURCE_ADDITION_PREFIX) for path in bundle.FIXED_FILES))
        for archive_name, source in bundle._sources(root):
            with self.subTest(archive_name=archive_name):
                self.assertTrue(source.resolve().is_relative_to(root / "services" / "core-api"))
        for workflow in (root / ".github" / "workflows").glob("*.y*ml"):
            with self.subTest(workflow=workflow.name):
                self.assertNotIn("integrations/", workflow.read_text(encoding="utf-8"))

    def test_preserved_hermes_addition_classifies_from_a_real_merge(self):
        with tempfile.TemporaryDirectory() as temp:
            def run(*args):
                return subprocess.run(["git", "-C", temp, *args], check=True, capture_output=True,
                                      text=True).stdout.strip()
            run("init", "-q")
            run("config", "user.email", "t@t.invalid")
            run("config", "user.name", "t")
            run("config", "core.autocrlf", "false")
            (Path(temp) / "base.txt").write_text("base\n")
            run("add", "-A")
            run("commit", "-qm", "base")
            base = run("rev-parse", "HEAD")
            target = Path(temp) / "integrations" / "hermes" / "README.md"
            target.parent.mkdir(parents=True)
            target.write_text("preserved\n")
            run("add", "-A")
            run("commit", "-qm", "add")
            candidate = run("rev-parse", "HEAD")
            self.assertEqual(gate.classify_repository(Path(temp), base, candidate)[0], gate.CONTROL_ONLY_NO_DEPLOY)
            target.write_text("changed\n")
            run("commit", "-qam", "modify")
            modified = run("rev-parse", "HEAD")
            self.assertEqual(gate.classify_repository(Path(temp), candidate, modified)[0], gate.DEPLOY_REQUIRED)

    def test_symlink_and_mode_tricks_require_deploy(self):
        path = "scripts/memory_broker_stage2_control.py"
        for entry in (
            changed(path, "M", "100644", "120000"),
            changed(path, "M", "120000", "100644"),
            changed(path, "A", "000000", "160000"),
            changed(path, "D", "100644", "000000"),
        ):
            self.assertEqual(self.classify(entry), gate.DEPLOY_REQUIRED)

    def test_renamed_runtime_cannot_hide_in_control_diff(self):
        self.assertEqual(
            self.classify(
                changed("services/core-api/app.py", "D", "100644", "000000"),
                changed("scripts/memory_broker_stage2_control.py", "A", "000000"),
            ),
            gate.DEPLOY_REQUIRED,
        )

    def test_empty_malformed_and_noncanonical_diff_fail_closed(self):
        for raw in (
            b"",
            b"broken",
            b":100644 100644 " + b"0" * 40 + b" " + b"1" * 40 + b" M\0../escape\0",
            b":100644 100644 " + b"0" * 40 + b" " + b"1" * 40 + b" R100\0services/core-api/app.py\0",
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    gate.parse_raw_diff(raw)
        self.assertEqual(self.classify(), gate.DEPLOY_REQUIRED)

    def test_candidate_mode_override_is_not_an_input(self):
        script = Path(gate.__file__)
        env = dict(os.environ, LILITH_DEV_DEPLOYMENT_MODE=gate.CONTROL_ONLY_NO_DEPLOY)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            result = subprocess.run(
                [sys.executable, str(script), "--candidate-root", temp,
                 "--base-sha", "0" * 40, "--candidate-sha", "1" * 40,
                 "--github-output", str(output), "--mode", gate.CONTROL_ONLY_NO_DEPLOY],
                env=env, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_environment_mode_override_is_ignored(self):
        with patch.dict(os.environ, LILITH_DEV_DEPLOYMENT_MODE=gate.CONTROL_ONLY_NO_DEPLOY):
            self.assertEqual(self.classify(changed("services/core-api/app.py")), gate.DEPLOY_REQUIRED)

    # ---------------------------------------------------------------- frontend-only lane

    # The complete effective diff of Experience V2 RC1 (#426) against main cda3d85.
    RC1_EFFECTIVE_DIFF = (
        ("docs/roadmap/experience-v2-rc1.md", "A"), ("package.json", "M"),
        ("scripts/run-core-self-test.mjs", "M"), ("scripts/scan-prod-bundle.mjs", "A"),
        ("scripts/test-stubs/next-link.tsx", "A"), ("scripts/test-stubs/next-navigation.ts", "A"),
        ("src/app/page.tsx", "M"), ("src/components/conversation/conversation-provider.tsx", "M"),
        ("src/components/conversation/conversation-view.tsx", "M"), ("src/components/conversation/voice-toggle.tsx", "A"),
        ("src/components/home/next-card.tsx", "M"), ("src/components/home/today-card.tsx", "M"),
        ("src/components/layout/sidebar-rail.tsx", "M"), ("src/components/layout/status-bar.tsx", "M"),
        ("src/components/layout/top-bar.tsx", "M"), ("src/components/presence/avatar-presence.tsx", "M"),
        ("src/components/presence/avatar-scene.tsx", "M"), ("src/components/presence/command-input.tsx", "M"),
        ("src/components/presence/presence-fallback.tsx", "M"), ("src/components/presence/presence-hero.tsx", "M"),
        ("src/components/presence/presence-stage.tsx", "M"), ("src/components/ui/unavailable.ts", "A"),
        ("src/hooks/use-now.ts", "A"), ("src/lib/command/core/logger.ts", "M"),
        ("src/lib/conversation/turn-runner.ts", "A"), ("src/lib/conversation/turn-self-test.ts", "A"),
        ("src/lib/diagnostics-self-test.ts", "A"), ("src/lib/diagnostics.ts", "A"),
        ("src/lib/home/meetings-view.ts", "A"), ("src/lib/home/self-test.ts", "A"),
        ("src/lib/system/self-test.ts", "A"), ("src/lib/system/shell-health.ts", "A"),
        ("src/lib/ui/controls-self-test.ts", "A"), ("src/lib/voice/reply-voicing.ts", "A"),
        ("src/lib/voice/speech-controller.ts", "M"), ("src/lib/voice/types.ts", "M"),
        ("src/lib/voice/voice-self-test.ts", "A"), ("src/lib/voice/voice-settings.ts", "M"),
    )

    @staticmethod
    def frontend(path, status):
        return changed(path, status, "000000" if status == "A" else "100644", "100644")

    def test_frontend_only_diff_is_control_only(self):
        self.assertEqual(self.classify(
            self.frontend("src/components/home/today-card.tsx", "M"),
            self.frontend("src/lib/home/meetings-view.ts", "A"),
            self.frontend("src/app/globals.css", "M"),
            self.frontend("src/hooks/use-meetings.ts", "M"),
            self.frontend("package.json", "M"),
            self.frontend("package-lock.json", "M"),
            self.frontend("docs/roadmap/experience-v2-plan.md", "A"),
        ), gate.CONTROL_ONLY_NO_DEPLOY)

    def test_rc1_complete_effective_diff_is_control_only(self):
        entries = [self.frontend(path, status) for path, status in self.RC1_EFFECTIVE_DIFF]
        self.assertEqual(len(entries), 38)
        self.assertEqual(self.classify(*entries), gate.CONTROL_ONLY_NO_DEPLOY)
        # The same diff plus any one Core API change deploys.
        for extra in (changed("services/core-api/app.py"), changed("services/core-api/requirements.txt"),
                      changed("services/core-api/lilith_memory/new_module.py", "A", "000000")):
            with self.subTest(extra=extra):
                self.assertEqual(self.classify(*entries, extra), gate.DEPLOY_REQUIRED)

    def test_frontend_server_privileged_and_unlisted_paths_require_deploy(self):
        valid = self.frontend("src/components/home/next-card.tsx", "M")
        for path, status in (
            # Next.js server boundary (Core API service credentials, owner-capture gate)
            ("src/app/api/lilith/conversation/route.ts", "M"),
            ("src/app/api/lilith/[...path]/route.ts", "M"),
            ("src/app/api/voice/tts/helper.ts", "A"),
            ("src/app/api/new/thing.tsx", "A"),
            ("src/app/(group)/api/x.ts", "A"),
            ("src/app/feed/route.ts", "A"),
            ("src/app/feed/route.tsx", "A"),
            ("src/lib/core-api-credentials.ts", "M"),
            ("src/lib/conversation/owner-capture-auth.ts", "M"),
            ("src/lib/conversation/self-test.ts", "M"),
            ("src/lib/middleware.ts", "A"),
            ("src/components/instrumentation-client.ts", "A"),
            ("src/proxy.ts", "A"),
            ("src/middleware.ts", "A"),
            ("src/instrumentation.ts", "A"),
            # outside the reviewed trees, sibling prefixes, wrong types
            ("src/app.ts", "A"),
            ("src/types/x.ts", "A"),
            ("src/appx/page.tsx", "A"),
            ("srcx/app/page.tsx", "A"),
            ("SRC/app/page.tsx", "A"),
            ("src/app/favicon.ico", "M"),
            ("src/lib/tool.py", "A"),
            ("src/lib/run.sh", "A"),
            ("src/lib/data.json", "A"),
            ("src/lib/x.ts.py", "A"),
            ("src/lib/.env.ts", "A"),
            ("src/.hidden/x.ts", "A"),
            ("src/lib/.secret/x.ts", "A"),
            ("public/assets/avatars/Hsin.vrm", "M"),
            ("next.config.ts", "M"),
            ("tsconfig.json", "M"),
            ("docs/roadmap/nested/x.md", "A"),
            ("docs/roadmap/x.txt", "A"),
            ("docs/roadmap/.x.md", "A"),
            ("docs/roadmapx/x.md", "A"),
            ("docs/architecture/unreviewed.md", "A"),
            ("scripts/test-stubs/other.ts", "A"),
            ("scripts/run-core-self-test.py", "A"),
            ("scripts/deploy_core_api_dev_remote.sh", "M"),
            ("services/core-api/app.py", "M"),
            ("services/core-api/lilith_memory/owner_proof.py", "M"),
            (".github/workflows/ci.yml.new", "A"),
            ("node_modules/next/dist/server.js", "A"),
        ):
            entry = self.frontend(path, status)
            with self.subTest(path=path):
                self.assertFalse(gate.is_frontend_only(*entry))
                self.assertEqual(self.classify(entry), gate.DEPLOY_REQUIRED)
                self.assertEqual(self.classify(valid, entry), gate.DEPLOY_REQUIRED)

    def test_frontend_mode_symlink_submodule_and_deletion_tricks_require_deploy(self):
        valid = self.frontend("src/lib/home/meetings-view.ts", "M")
        for path in ("src/components/x.tsx", "package.json", "docs/roadmap/x.md", "scripts/run-core-self-test.mjs"):
            for entry in (
                changed(path, "A", "000000", "100755"),   # new executable
                changed(path, "M", "100644", "100755"),   # +x
                changed(path, "M", "100755", "100644"),   # was executable
                changed(path, "M", "100755", "100755"),
                changed(path, "A", "000000", "120000"),   # new symlink
                changed(path, "M", "100644", "120000"),   # file -> symlink
                changed(path, "M", "120000", "100644"),   # symlink -> file
                changed(path, "A", "000000", "160000"),   # submodule
                changed(path, "D", "100644", "000000"),   # deletion
                changed(path, "A", "100644", "100644"),   # inconsistent add
                changed(path, "M", "000000", "100644"),   # inconsistent modify
            ):
                with self.subTest(entry=entry):
                    self.assertFalse(gate.is_frontend_only(*entry))
                    self.assertEqual(self.classify(valid, entry), gate.DEPLOY_REQUIRED)

    def test_frontend_mixed_with_runtime_broker_or_control_lanes(self):
        valid = self.frontend("src/components/presence/presence-hero.tsx", "M")
        for extra in (
            changed("services/core-api/app.py"),
            changed("services/core-api/requirements.txt"),
            changed("services/core-api/lilith_memory/new_module.py", "A", "000000"),
            changed("services/memory-broker/lilith_memory_broker/dev_core.py"),          # broker lane mismatch
            changed("scripts/memory_broker_os_installer.py"),                           # pinned control, wrong blob
            changed(".github/workflows/deploy-dev.yml.bak", "A", "000000"),
            changed("integrations/hermes/README.md"),                                    # preserved-source modification
            changed("unknown.file", "A", "000000"),
        ):
            with self.subTest(extra=extra):
                self.assertEqual(self.classify(valid, extra), gate.DEPLOY_REQUIRED)
        # Two no-deploy lanes together stay no-deploy (neither reaches DEV).
        self.assertEqual(self.classify(valid, changed("scripts/test_broker_dev_lifecycle.py"),
                                       changed("integrations/hermes/notes.md", "A", "000000")),
                         gate.CONTROL_ONLY_NO_DEPLOY)

    def test_frontend_traversal_paths_are_rejected_before_classification(self):
        for path in (b"src/lib/../../services/core-api/app.py", b"src/./lib/x.ts", b"src//lib/x.ts", b"/src/lib/x.ts"):
            raw = b":100644 100644 " + b"0" * 40 + b" " + b"1" * 40 + b" M\0" + path + b"\0"
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    gate.parse_raw_diff(raw)

    def test_frontend_lane_record_is_control_only_at_its_reviewed_revision_only(self):
        record = "docs/architecture/dev-deploy-classifier-frontend-only.md"
        pinned = gate.PINNED_CANDIDATE_BLOBS[record]
        lane = (changed("scripts/classify_dev_deployment.py"), changed("scripts/test_classify_dev_deployment.py"))
        self.assertEqual(self.classify(*lane, changed(record, "A", "000000"), blobs={record: pinned}),
                         gate.CONTROL_ONLY_NO_DEPLOY)
        self.assertEqual(self.classify(*lane, changed(record), blobs={record: "0" * 40}), gate.DEPLOY_REQUIRED)
        self.assertEqual(self.classify(changed(record)), gate.DEPLOY_REQUIRED)  # unknown blob

    def test_core_api_changes_still_require_deploy(self):
        for entry in (
            changed("services/core-api/app.py"),
            changed("services/core-api/requirements.txt"),
            changed("services/core-api/tests/test_canonical_runtime.py"),
            changed("services/core-api/lilith_memory/owner_proof.py"),
            changed("services/core-api/lilith_memory/new_module.py", "A", "000000"),
        ):
            with self.subTest(entry=entry):
                self.assertEqual(self.classify(entry), gate.DEPLOY_REQUIRED)

    def test_server_boundary_closure_is_outside_the_frontend_lane(self):
        """Every module that runs on the Next.js server, or loads privileged code, is excluded from the lane."""
        self.assertEqual(server_boundary_violations(Path(__file__).resolve().parents[1]), [])

    def test_server_boundary_guard_catches_each_gap_class(self):
        cases = {
            # name: ({file: content}, modules expected to be reported as admitted to the lane)
            "relative import from a route": (
                {"src/app/feed/api/x/route.ts": 'import { h } from "../../../../lib/helper";',
                 "src/lib/helper.ts": "export const h = 1;"},
                {"src/lib/helper.ts"}),
            "re-export chain": (
                {"src/app/api/x/route.ts": 'import { b } from "@/lib/a";',
                 "src/lib/a.ts": 'export * from "./b";', "src/lib/b.ts": "export const b = 1;"},
                {"src/lib/a.ts", "src/lib/b.ts"}),
            "named re-export": (
                {"src/app/api/x/route.ts": 'export { b } from "@/lib/b";', "src/lib/b.ts": "export const b = 1;"},
                {"src/lib/b.ts"}),
            "side-effect import": (
                {"src/app/api/x/route.ts": 'import "@/lib/side";', "src/lib/side.ts": "globalThis.x = 1;"},
                {"src/lib/side.ts"}),
            "literal dynamic import": (
                {"src/app/api/x/route.ts": 'const m = await import("@/lib/dyn");', "src/lib/dyn.ts": "export {};"},
                {"src/lib/dyn.ts"}),
            "require": (
                {"src/app/api/x/route.ts": 'const m = require("../../../lib/req");', "src/lib/req.ts": "export {};"},
                {"src/lib/req.ts"}),
            "middleware outside src/app": (
                {"src/lib/middleware.ts": 'import { m } from "./mw-helper";', "src/lib/mw-helper.ts": "export const m = 1;"},
                {"src/lib/mw-helper.ts"}),
            "server component importing credentials": (
                {"src/app/page.tsx": 'import { coreApiHeaders } from "@/lib/core-api-credentials";'},
                {"src/app/page.tsx"}),
            "transitive importer of credentials": (
                {"src/components/card.tsx": 'import { y } from "@/lib/y";',
                 "src/lib/y.ts": 'import { coreApiHeaders } from "../lib/core-api-credentials";'},
                {"src/components/card.tsx", "src/lib/y.ts"}),
            "test or page importing a route": (
                {"src/lib/route-test.ts": 'import { POST } from "@/app/api/x/route";',
                 "src/app/api/x/route.ts": "export async function POST() {}"},
                {"src/lib/route-test.ts"}),
            "file-level server action": (
                {"src/lib/actions.ts": '"use server";\nexport async function save() {}'},
                {"src/lib/actions.ts"}),
            "inline server action and what it loads": (
                {"src/components/form.tsx": 'import { v } from "./v";\nasync function a() { "use server"; }',
                 "src/components/v.ts": "export const v = 1;"},
                {"src/components/form.tsx", "src/components/v.ts"}),
            "server-only package": (
                {"src/lib/s.ts": 'import "server-only";'}, {"src/lib/s.ts"}),
            "next/headers user": (
                {"src/lib/h.ts": 'import { cookies } from "next/headers";'}, {"src/lib/h.ts"}),
            "secret env reader and its importer": (
                {"src/lib/sec.ts": "export const t = process.env.SECRET_TOKEN;",
                 "src/components/c.tsx": 'import { t } from "@/lib/sec";'},
                {"src/lib/sec.ts", "src/components/c.tsx"}),
        }
        base = {"src/lib/core-api-credentials.ts": "export const coreApiHeaders = () => ({});"}
        for name, (tree, expected) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for rel, body in {**base, **tree}.items():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    (root / rel).write_text(body, encoding="utf-8")
                admitted = {path for path, reason in server_boundary_violations(root) if "admitted" in reason}
                self.assertEqual(admitted, expected)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for rel, body in {
                **base,
                "src/app/api/x/route.ts": 'const m = await import(`@/lib/${name}`);\nimport { z } from "./missing";',
                # negative controls: client code, public env, NODE_ENV, packages
                "src/components/ok.tsx": 'import { api } from "@/lib/api";\nimport React from "react";',
                "src/lib/api.ts": "export const api = process.env.NEXT_PUBLIC_API + process.env.NODE_ENV;",
            }.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(body, encoding="utf-8")
            reasons = {(path, reason.split(" ")[0]) for path, reason in server_boundary_violations(root)}
            self.assertEqual(reasons, {("src/app/api/x/route.ts", "non-literal"), ("src/app/api/x/route.ts", "unresolved")})

    def test_frontend_is_not_consumed_by_any_deployment_path(self):
        from scripts import build_core_api_bundle as bundle
        root = Path(__file__).resolve().parents[1]
        for archive_name, source in bundle._sources(root):
            with self.subTest(archive_name=archive_name):
                self.assertTrue(source.resolve().is_relative_to(root / "services" / "core-api"))
                self.assertFalse(gate.is_frontend_only(source.relative_to(root).as_posix(), "M", "100644", "100644"))
        for workflow in (root / ".github" / "workflows").glob("*.y*ml"):
            if workflow.name == "ci.yml":
                continue  # CI is where the frontend is built and tested, before deploy-dev can run
            text = workflow.read_text(encoding="utf-8")
            for marker in ("src/", "package.json", "package-lock.json", "npm ", "node_modules", ".next", "scripts/test-stubs",
                           "run-core-self-test", "scan-prod-bundle", "docs/roadmap"):
                with self.subTest(workflow=workflow.name, marker=marker):
                    self.assertNotIn(marker, text)

    def test_frontend_change_classifies_from_a_real_merge(self):
        with tempfile.TemporaryDirectory() as temp:
            def run(*args):
                return subprocess.run(["git", "-C", temp, *args], check=True, capture_output=True,
                                      text=True).stdout.strip()

            def write(rel, text):
                target = Path(temp) / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)

            run("init", "-q")
            run("config", "user.email", "t@t.invalid")
            run("config", "user.name", "t")
            run("config", "core.autocrlf", "false")
            write("services/core-api/app.py", "app\n")
            write("src/components/card.tsx", "card\n")
            run("add", "-A")
            run("commit", "-qm", "base")
            base = run("rev-parse", "HEAD")

            write("src/components/card.tsx", "card v2\n")
            write("src/lib/new.ts", "new\n")
            write("docs/roadmap/note.md", "note\n")
            run("add", "-A")
            run("commit", "-qm", "frontend")
            frontend = run("rev-parse", "HEAD")
            self.assertEqual(gate.classify_repository(Path(temp), base, frontend)[0], gate.CONTROL_ONLY_NO_DEPLOY)

            write("services/core-api/app.py", "app v2\n")
            write("src/components/card.tsx", "card v3\n")
            run("add", "-A")
            run("commit", "-qm", "mixed")
            mixed = run("rev-parse", "HEAD")
            self.assertEqual(gate.classify_repository(Path(temp), frontend, mixed)[0], gate.DEPLOY_REQUIRED)

            # Mode and symlink changes are set in the index, so this behaves the same on every OS.
            run("update-index", "--chmod=+x", "src/components/card.tsx")
            run("commit", "-qm", "exec")
            executable = run("rev-parse", "HEAD")
            self.assertEqual(gate.classify_repository(Path(temp), mixed, executable)[0], gate.DEPLOY_REQUIRED)

            blob = subprocess.run(["git", "-C", temp, "hash-object", "-w", "--stdin"], input="../../services/core-api/app.py",
                                  check=True, capture_output=True, text=True).stdout.strip()
            run("update-index", "--add", "--cacheinfo", f"120000,{blob},src/lib/link.ts")
            run("commit", "-qm", "symlink")
            symlink = run("rev-parse", "HEAD")
            self.assertEqual(gate.classify_repository(Path(temp), executable, symlink)[0], gate.DEPLOY_REQUIRED)

            run("rm", "-q", "--cached", "src/lib/new.ts")
            run("commit", "-qm", "delete")
            deleted = run("rev-parse", "HEAD")
            self.assertEqual(gate.classify_repository(Path(temp), symlink, deleted)[0], gate.DEPLOY_REQUIRED)


if __name__ == "__main__":
    unittest.main()
