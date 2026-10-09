"""15B2b-B1b-3e M-B6: the separate P1B-6 ledger denial proof (TEST-ONLY, stdlib).

Record: docs/architecture/slice-15b2b-b1b3e-mb6-ledger-remediation.md §13 (owner decision R-3).
The proof runs against injected seams; no host, account or unit is touched.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
for _p in (TOOLS, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mb6_ledger_denial_proof as D  # noqa: E402
import mb6_operator as O  # noqa: E402
import post_reboot_repin as RP  # noqa: E402

UID, GID = 991, 981
P1B5_PROOF = "scripts/authority_custody_denial_proof.py"
P1B5_PIN = "f4e39c81c24a01be5702f6a65a581fcd08f97e1c5ad4a07326883b605fef1455"
MB4_MB5_OPERATOR_PIN = "e380ab1852ba72fe511c650446867c8d229d95776af3c1d4266fa949c0a9de1a"
MB4_MB5_TOOL_PINS = {
    "services/authority-dev/ceremony/install_authority_dev.py":
        "fe10d9a37c53d4a32ca49d79ee5987c6546866feeebcee3c882087f51ed55487",
    "services/owner-memory-control/tools/mb4_mb5_installable_inputs.py":
        "dbe94a2d3a38fa838d4fd7eeb9016274c85c684221ddb770e8e993cc15b18d61",
    "services/owner-memory-control/tools/mb4_mb5_trust_install_verifier.py":
        "78f57c01811e20a03ebb06bc114847bad440c7435e85ceb0249a488c659b2361",
    "services/owner-memory-control/tools/mb4_mb5_remove_before_mb6.py":
        "db0629a6a5f39ca65e23010aeeccc565978b7d8990f38d6b8bb6c361046ee104",
    "services/owner-memory-control/tools/mb3_registry_ceremony.py":
        "c77b651ca2ae9d5f6c5526f958469a01c0d42e6ebdf189fc206ac2132af61320",
    "services/owner-memory-control/tools/verify_mb3_registry.py":
        "e710cfa623d494e243ab4a1fbaefe28e8d079e58398368f9dcabd645e06b5507",
    "services/authority-dev/ceremony/observe_authority_dev_host.py":
        "a2f21b45e57a153f099c79a734ab05a575ac5c50f7cbc0527e562e94dd6908bf",
    "scripts/verify_broker_dev_current_incarnation.py":
        "2e68160971a3b0dd05ffcb6cdc464fc612afb2b522a57fb534b25c6af83c10ba",
    P1B5_PROOF: P1B5_PIN,
}

# The exact PASS transcript of the successful post-M-B6 state (deterministic; record §13).
PASS_TRANSCRIPT = [
    "STATE: /var/lib/lilith-authority-dev directory lilith-authority-dev:lilith-authority-dev 0700 "
    "entries=authority_ledger.db",
    "STATE: /var/lib/lilith-authority-dev/authority_ledger.db regular lilith-authority-dev:lilith-authority-dev 0600 "
    "links=1",
    "UNIT: lilith-authority-dev.service ActiveState=inactive",
    "UNIT: lilith-recovery-witness.service ActiveState=inactive",
    "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT",
    *[f"DENIED: {principal} test {op} {path}"
      for op, path in (("-r", "/var/lib/lilith-authority-dev"), ("-x", "/var/lib/lilith-authority-dev"),
                       ("-w", "/var/lib/lilith-authority-dev"),
                       ("-r", "/var/lib/lilith-authority-dev/authority_ledger.db"),
                       ("-w", "/var/lib/lilith-authority-dev/authority_ledger.db"))
      for principal in ("lilith", "sa_112096412008414111981", "lilith-memory-broker", "lilith-recovery-witness")],
    "SCOPE: denial only; ledger provisioned != Registry V1 effective != authority active; signer and witness not started",
    "MB6_LEDGER_DENIAL_PROOF=PASS phase=P1B-6 denied=20 allowed=0",
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def st(kind: int, mode: int, uid: int = UID, gid: int = GID, nlink: int = 1) -> os.stat_result:
    return os.stat_result((kind | mode, 7, 9, nlink, uid, gid, 4096, 0, 0, 0))


class World:
    """The injected host: the reviewed successful post-M-B6 state unless a test changes it."""

    def __init__(self):
        self.stats = {D.AUTHORITY_STATE: st(stat.S_IFDIR, 0o700), D.LEDGER: st(stat.S_IFREG, 0o600)}
        self.entries = [D.LEDGER_NAME]
        self.ids: tuple[int, int] | None = (UID, GID)
        self.units = dict.fromkeys(D.UNITS, "inactive")
        self.activation_result = (1, "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false\n")
        self.codes: dict[tuple[str, str, str], int] = {}
        self.calls: list[list[str]] = []
        self.lines: list[str] = []
        self.euid = 0

    def run(self, argv):
        argv = list(argv)
        self.calls.append(argv)
        return self.codes.get((argv[2], argv[-2], argv[-1]), 1)

    def prove(self, phase: str = "P1B-6") -> bool:
        return D.prove(phase, run=self.run, lstat=self.stats.get, listdir=lambda path: sorted(self.entries),
                       signer_ids=lambda: self.ids, unit_state=self.units.__getitem__,
                       activation=lambda: self.activation_result, euid=lambda: self.euid, say=self.lines.append)


class LedgerDenialProofTests(unittest.TestCase):
    def test_successful_post_mb6_state_is_pass_with_the_exact_transcript(self):
        world = World()
        self.assertTrue(world.prove())
        self.assertEqual(world.lines, PASS_TRANSCRIPT)
        again = World()
        again.prove()
        self.assertEqual(again.lines, world.lines)                                      # deterministic
        self.assertEqual(len(world.calls), D.EXPECTED_DENIED)
        self.assertEqual(D.EXPECTED_DENIED, 20)
        for argv in world.calls:
            self.assertEqual(argv[:2] + argv[3:5], [D.RUNUSER, "-u", "--", D.TEST])
            self.assertNotEqual(argv[2], D.SIGNER)                                      # the owner is never probed
        self.assertFalse(any(line.startswith(("ALLOWED", "FAIL")) or "ALLOWED(" in line for line in world.lines))

    def test_each_row_is_denied_for_every_non_signer_principal(self):
        world = World()
        world.prove()
        probed = {(argv[2], argv[-2], argv[-1]) for argv in world.calls}
        for op in ("-w", "-r", "-x"):                                                   # write, read, traversal
            for principal in D.PRINCIPALS:
                self.assertIn((principal, op, D.AUTHORITY_STATE), probed)
                self.assertIn(f"DENIED: {principal} test {op} {D.AUTHORITY_STATE}", world.lines)
        for op in ("-r", "-w"):
            for principal in D.PRINCIPALS:
                self.assertIn(f"DENIED: {principal} test {op} {D.LEDGER}", world.lines)
        self.assertEqual(set(D.PRINCIPALS), {"lilith", "sa_112096412008414111981", "lilith-memory-broker",
                                             "lilith-recovery-witness"})

    def test_any_allowed_or_inconclusive_probe_fails(self):
        for key, code, needle in (
                (("lilith", "-w", D.AUTHORITY_STATE), 0, "FAIL: ALLOWED(unexpected) lilith test -w"),
                (("lilith-recovery-witness", "-x", D.AUTHORITY_STATE), 0, "FAIL: ALLOWED(unexpected)"),
                (("sa_112096412008414111981", "-r", D.LEDGER), 0, "FAIL: ALLOWED(unexpected)"),
                (("lilith-memory-broker", "-w", D.LEDGER), 0, "FAIL: ALLOWED(unexpected)"),
                (("lilith", "-r", D.AUTHORITY_STATE), 2, "FAIL: PROBE_INCONCLUSIVE rc=2"),
                (("lilith", "-r", D.LEDGER), 125, "FAIL: PROBE_INCONCLUSIVE rc=125")):
            with self.subTest(key=key, code=code):
                world = World()
                world.codes[key] = code
                self.assertFalse(world.prove())
                self.assertTrue(any(line.startswith(needle) for line in world.lines), world.lines)
                self.assertTrue(world.lines[-1].startswith("MB6_LEDGER_DENIAL_PROOF=FAIL phase=P1B-6"))
                self.assertEqual(len(world.calls), D.EXPECTED_DENIED)                   # every row still reported

    def test_grant_absent_is_required_and_never_changed(self):
        for name, result in (("accepted", (0, 'ACTIVATION=ACCEPTED {"grantId": "x"} advisoryConfigEnabled=true\n')),
                             ("other reason", (1, "ACTIVATION=NOT_ACCEPTED reason=SIGNATURE_ABSENT "
                                                  "advisoryConfigEnabled=false\n")),
                             ("extra output", (1, "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false"
                                                  "\nmore\n")),
                             ("unreadable", (2, ""))):
            with self.subTest(name):
                world = World()
                world.activation_result = result
                self.assertFalse(world.prove())
                self.assertIn("FAIL: ACTIVATION_NOT_GRANT_ABSENT", world.lines)
                self.assertEqual(world.calls, [])                                        # no probe on a precondition
        source = (TOOLS / "mb6_ledger_denial_proof.py").read_text(encoding="utf-8").split('"""', 2)[2]
        self.assertEqual(source.count("[ACTIVATION_VERIFY]"), 1)                          # the verifier takes no argument
        for forbidden in ("/etc/lilith-os-dev/activation", "grant.json", "ssh-keygen"):
            self.assertNotIn(forbidden, source, forbidden)

    def test_signer_or_witness_activation_is_a_refusal(self):
        for unit in D.UNITS:
            for state in ("active", "activating", "failed", "UNREADABLE"):
                with self.subTest(unit=unit, state=state):
                    world = World()
                    world.units[unit] = state
                    self.assertFalse(world.prove())
                    self.assertIn(f"FAIL: UNIT_NOT_INACTIVE {unit}", world.lines)
                    self.assertEqual(world.calls, [])

    def test_malformed_or_unexpected_state_is_refused_before_any_probe(self):
        cases = (
            ("directory absent", lambda w: w.stats.pop(D.AUTHORITY_STATE), "STATE_DIRECTORY_ABSENT"),
            ("directory symlink", lambda w: w.stats.update({D.AUTHORITY_STATE: st(stat.S_IFLNK, 0o777)}),
             "STATE_DIRECTORY_NOT_A_REAL_DIRECTORY"),
            ("directory root-owned (W6-1)", lambda w: w.stats.update({D.AUTHORITY_STATE: st(stat.S_IFDIR, 0o700, 0, 0)}),
             "STATE_DIRECTORY_OWNER_INEXACT"),
            ("directory 0750", lambda w: w.stats.update({D.AUTHORITY_STATE: st(stat.S_IFDIR, 0o750)}),
             "STATE_DIRECTORY_MODE_INEXACT"),
            ("empty directory (W6-2)", lambda w: (w.entries.clear(), w.stats.pop(D.LEDGER)),
             "STATE_DIRECTORY_ENTRIES_INEXACT:"),
            ("WAL present (W6-4 not clean)", lambda w: w.entries.append("authority_ledger.db-wal"),
             "STATE_DIRECTORY_ENTRIES_INEXACT:authority_ledger.db,authority_ledger.db-wal"),
            ("journal present", lambda w: w.entries.append("authority_ledger.db-journal"),
             "STATE_DIRECTORY_ENTRIES_INEXACT:authority_ledger.db,authority_ledger.db-journal"),
            ("ledger absent", lambda w: w.stats.pop(D.LEDGER), "LEDGER_ABSENT"),
            ("ledger symlink", lambda w: w.stats.update({D.LEDGER: st(stat.S_IFLNK, 0o777)}),
             "LEDGER_NOT_A_REGULAR_FILE"),
            ("ledger other owner", lambda w: w.stats.update({D.LEDGER: st(stat.S_IFREG, 0o600, 0, 0)}),
             "LEDGER_OWNER_INEXACT"),
            ("ledger 0644", lambda w: w.stats.update({D.LEDGER: st(stat.S_IFREG, 0o644)}), "LEDGER_MODE_INEXACT"),
            ("ledger hard link", lambda w: w.stats.update({D.LEDGER: st(stat.S_IFREG, 0o600, nlink=2)}),
             "LEDGER_LINK_COUNT_INEXACT"),
            ("signer account absent", lambda w: setattr(w, "ids", None), "SIGNER_ACCOUNT_INVALID"),
            ("signer account root", lambda w: setattr(w, "ids", (0, 0)), "SIGNER_ACCOUNT_INVALID"),
        )
        for name, change, reason in cases:
            with self.subTest(name):
                world = World()
                change(world)
                self.assertFalse(world.prove())
                self.assertTrue(any(line.startswith("FAIL: STATE_UNEXPECTED " + reason) for line in world.lines),
                                world.lines)
                self.assertEqual(world.lines[-1], "MB6_LEDGER_DENIAL_PROOF=FAIL phase=P1B-6 reason=PRECONDITION probes=0")
                self.assertEqual(world.calls, [])
                self.assertFalse(any(line.startswith("STATE: ") for line in world.lines))

    def test_usage_phase_and_root_refusals(self):
        world = World()
        for phase in ("P1B-5", "P1B-12", "P1A-10", "p1b-6", ""):
            self.assertFalse(world.prove(phase))
        world.euid = 1000
        self.assertFalse(world.prove())
        self.assertEqual(world.calls, [])
        self.assertEqual(world.lines[-1], "MB6_LEDGER_DENIAL_PROOF=FAIL phase=P1B-6 reason=NOT_ROOT")
        self.assertEqual(D.main([]), 2)
        self.assertEqual(D.main(["P1B-6", D.LEDGER]), 2)
        self.assertEqual(D.PHASE, "P1B-6")

    def test_no_signer_witness_or_authority_effect_in_source(self):
        source = (TOOLS / "mb6_ledger_denial_proof.py").read_text(encoding="utf-8").split('"""', 2)[2]
        for forbidden in ("os.unlink", "os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.rename",
                          "open(", "write_", "sqlite3", "nsenter", "systemctl start", '"start"', '"enable"',
                          '"provision"', "provision 1", "credstore", "K-ACT", "registry-root", "authority-registry"):
            self.assertNotIn(forbidden, source, forbidden)
        self.assertEqual(source.count("[SYSTEMCTL, "), 1)
        self.assertIn('[SYSTEMCTL, "show", "--property=ActiveState", "--value", "--", unit]', source)
        self.assertIn("ledger provisioned != Registry V1 effective != authority active", D.SCOPE_LINE)

    @unittest.skipUnless(os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() != 0,
                         "the streamed form is exercised as a non-root POSIX user")
    def test_streamed_form_runs_and_refuses_non_root(self):
        data = (TOOLS / "mb6_ledger_denial_proof.py").read_bytes()
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run([sys.executable, "-I", "-B", "-", "P1B-6"], input=data, capture_output=True,
                                    cwd=cwd, timeout=60)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(result.stdout, b"MB6_LEDGER_DENIAL_PROOF=FAIL phase=P1B-6 reason=NOT_ROOT\n")
            self.assertEqual(os.listdir(cwd), [])


class SeparationTests(unittest.TestCase):
    """Decision R-3: a separate file and pin; P1B-5 and the M-B4/M-B5 pins stay unchanged."""

    def test_existing_p1b5_proof_is_unchanged(self):
        self.assertEqual(sha((ROOT / P1B5_PROOF).read_bytes()), P1B5_PIN)
        text = (ROOT / P1B5_PROOF).read_text(encoding="utf-8")
        self.assertIn('PHASES = ("P1A-10", "P1B-5", "P1B-12")', text)
        self.assertNotIn("P1B-6", text)

    def test_mb4_mb5_operator_and_removal_pins_are_unchanged(self):
        operator = TOOLS / "mb4_mb5_operator.py"
        self.assertEqual(sha(operator.read_bytes()), MB4_MB5_OPERATOR_PIN)
        spec = importlib.util.spec_from_file_location("mb4_mb5_operator_r3", operator)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            del sys.modules[spec.name]
        self.assertEqual(module.TOOL_PINS, MB4_MB5_TOOL_PINS)
        for path, pin in MB4_MB5_TOOL_PINS.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), RP.tree_pin(path, pin), path)
        self.assertNotIn("mb6_ledger_denial_proof", operator.read_text(encoding="utf-8"))

    def test_the_new_proof_has_its_own_pin_in_the_mb6_operator(self):
        digest = sha((TOOLS / "mb6_ledger_denial_proof.py").read_bytes())
        self.assertEqual(O.TOOL_PINS[O.LEDGER_DENIAL], digest)
        self.assertEqual(O.LEDGER_DENIAL, "services/owner-memory-control/tools/mb6_ledger_denial_proof.py")
        self.assertEqual(O.TOOL_PINS[O.DENIAL], P1B5_PIN)
        record = (ROOT / "docs/architecture/slice-15b2b-b1b3e-mb6-ledger-remediation.md").read_text(encoding="utf-8")
        self.assertIn(f"SHA-256 `{digest}`", record)

    def test_operator_streams_p1b6_hash_gated_and_read_only(self):
        calls: list[list[str]] = []

        def run(argv):
            argv = list(argv)
            calls.append(argv)
            if argv[0] == "git":
                return subprocess.CompletedProcess(argv, 0, (ROOT / argv[-1].split(":", 1)[1]).read_bytes(), b"")
            return subprocess.CompletedProcess(argv, 0, "\n".join(PASS_TRANSCRIPT).encode() + b"\n", b"")

        with tempfile.TemporaryDirectory() as work:
            result = O.Operator(gcloud=("gcloud",), run=run).ledger_denial(ROOT, Path(work) / "evidence")
            self.assertEqual(result["result"], "MB6_LEDGER_DENIAL_P1B6_PASS")
            self.assertEqual(result["transcriptSha256"], sha("\n".join(PASS_TRANSCRIPT).encode() + b"\n"))
        command = calls[-1][-1]
        self.assertIn(f"grep -qx '{O.TOOL_PINS[O.LEDGER_DENIAL]}' || exit 96", command)
        self.assertTrue(command.endswith("sudo -n /usr/bin/python3 -I -B - P1B-6"))
        self.assertTrue(command.startswith('--command=test "$(hostname)" = lilith-dev-01 || exit 97; '))
        self.assertNotIn(O.PROVISION, command)


if __name__ == "__main__":
    unittest.main()
