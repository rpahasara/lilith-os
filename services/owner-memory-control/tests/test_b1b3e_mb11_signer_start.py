"""15B2b-B1b-3e M-B11 (START_SIGNER) design slice: W11 classifier, DR-5 target, readiness modes, ledger and denial
boundaries (TEST-ONLY; synthetic credentials and fixtures; no live system, no real credential, no signer start).

Record: docs/architecture/slice-15b2b-b1b3e-mb11-signer-start-design.md.

Layers: the stdlib layer runs everywhere; the contract layer (the REAL signer core, the REAL root verifier and the REAL
durable ledger on a synthetic PR-1 host) needs POSIX and `cryptography` / `rfc8785` / `fido2`; the synthetic-host
layer (the UNCHANGED W9 / W10 verifiers over the M-B10 synthetic root) also needs root, like the M-B10 host tests.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "services/owner-memory-control/tools"
RECORD = ROOT / "docs/architecture/slice-15b2b-b1b3e-mb11-signer-start-design.md"
ADDENDUM = ROOT / "docs/architecture/slice-15b2b-b1b3e-mb10-first-post-freeze-deploy.md"
for _p in (ROOT / "services/core-api", ROOT / "services/owner-memory-control", TOOLS, ROOT / "services/authority-dev",
           ROOT / "services/authority-dev/ceremony", ROOT / "services/authority-dev/tests",
           ROOT / "services/recovery-witness", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import e19_p1b10_upgrade as E  # noqa: E402
import mb10_dr5_target as T10  # noqa: E402
import mb11_dr5_target as D  # noqa: E402
import mb11_signer_verifier as V  # noqa: E402
import mb9_dr5_target as T9  # noqa: E402

try:
    import cryptography  # noqa: F401
    import fido2  # noqa: F401
    import rfc8785  # noqa: F401
    HAVE_CRYPTO = True
except ImportError:  # pragma: no cover - the stdlib layer still runs
    HAVE_CRYPTO = False
POSIX = os.name == "posix"
FIXTURE = HERE / "b1b3e_mb9_post_mb6_dr5_baseline.json"
SCRIPT = (ROOT / D.DR5_SCRIPT).read_bytes()
INVOCATION = "a" * 32
OTHER_INVOCATION = "b" * 32
WITNESS_INVOCATION = "1" * 32
DB_SHA = "c" * 64


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def accepted_sets() -> dict[str, bytes]:
    return {name: T9.encode(lines) for name, lines in json.loads(FIXTURE.read_text(encoding="utf-8"))["sets"].items()}


# ------------------------------------------------------------------------------------------- pins ---

class PinTests(unittest.TestCase):
    def test_reused_tools_and_the_dr5_script_are_byte_unchanged(self):
        pins = {"services/owner-memory-control/tools/mb10_held_verifier.py":
                "73a8fe9aec48fab7fb628a3427bc690876b55a4ae1ead55f1b7e00032075b8e3",
                "services/owner-memory-control/tools/mb10_dr5_target.py": D.MB10_DR5_TARGET_SHA256,
                "services/owner-memory-control/tools/mb9_dr5_target.py": T10.MB9_DR5_TARGET_SHA256,
                D.DR5_SCRIPT: D.DR5_SCRIPT_SHA256}
        for path, pin in pins.items():
            self.assertEqual(sha((ROOT / path).read_bytes()), pin, path)

    def test_custody_bindings_are_the_repository_records(self):
        text = (ROOT / "docs/architecture/slice-15b2b-b1b3e-mb3-registry-sign-completion.md").read_text(encoding="utf-8")
        self.assertIn(f"publicKeySha256={V.B3_PUBLIC_KEY_SHA256} (SOLE CURRENT KEY)", text)
        self.assertIn(V.KACT_PUBLICATION_FILE_SHA256, text)
        preflight = (ROOT / "docs/architecture/slice-15b2b-b1b3e-pr1-live-install-preflight.md").read_text(
            encoding="utf-8")
        self.assertIn(V.B2_CURRENT_BLOB_SHA256, preflight)
        self.assertIn(V.KACT_KEY_ID, text)

    @unittest.skipUnless(POSIX, "the pinned denial proof needs os.geteuid at import")
    def test_the_twelve_deferred_and_nine_namespace_denial_rows_are_unchanged_and_not_performed_here(self):
        spec = importlib.util.spec_from_file_location("denial_proof", ROOT / "scripts/authority_custody_denial_proof.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(len([row for row in module.ROWS if row[0] == "P1B-12"]), 12)
        self.assertEqual(len(module.NAMESPACE_ROWS), 9)
        self.assertEqual(module.PHASES, ("P1A-10", "P1B-5", "P1B-12"))
        for path in (TOOLS / "mb11_signer_verifier.py", TOOLS / "mb11_dr5_target.py"):
            self.assertNotIn("authority_custody_denial_proof", path.read_text(encoding="utf-8"))

    def test_the_signer_unit_and_socket_are_the_release_assets(self):
        unit = (ROOT / "services/authority-dev/deploy/lilith-authority-dev.service").read_text(encoding="utf-8")
        sock = (ROOT / "services/authority-dev/deploy/lilith-authority-dev.socket").read_text(encoding="utf-8")
        for line in ("Restart=on-failure", "RestartSec=5s", "StartLimitIntervalSec=60", "StartLimitBurst=3",
                     f"ExecStart={' '.join(V.EXEC_ARGV)}",
                     f"LoadCredentialEncrypted={V.CREDENTIAL_NAME}:/etc/credstore.encrypted/"
                     "lilith-authority-dev.owner-actor.cred"):
            self.assertIn(line, unit.splitlines())                  # the exposure the record describes, unchanged
        for line in ("Accept=no", "SocketMode=0600", "TriggerLimitBurst=3", "Service=lilith-authority-dev.service"):
            self.assertIn(line, sock.splitlines())
        self.assertNotIn("RestartPreventExitStatus", unit)          # no unapproved restart change in this slice
        self.assertNotIn("[Install]", unit + sock)


# ------------------------------------------------------------------------------------------- DR-5 ---

class Dr5TargetTests(unittest.TestCase):
    def test_the_signer_delta_is_one_later_line_proven_from_the_pinned_script(self):
        derived = D.derive(accepted_sets(), SCRIPT)
        self.assertEqual(derived["delta"], "ONE_LATER_LINE_PROVEN_FROM_PINNED_SCRIPT")
        self.assertFalse(derived["accepted"])
        self.assertFalse(derived["liveW11ObservationExists"])
        running = derived["targets"][D.RUNNING_SIGNER_HELD]["sets"]
        for name in ("result-set", "dr5-block"):
            self.assertEqual(running[name]["added"], list(D.DENIED_LINES))
            self.assertEqual(running[name]["removed"], [D.DEFERRED_LINE])
            self.assertEqual(running[name]["lines"], T10.TARGETS[T10.RUNNING_HELD][name][0] + 2)
        self.assertEqual((running["predeploy-block"]["added"], running["predeploy-block"]["removed"]), ([], []))
        # record §14: derived on the accepted E-19 base (the pre-E-19 194 / 8c8b6eac and 155 / ba39512d are history)
        self.assertEqual(D.TARGETS[D.RUNNING_SIGNER_HELD]["result-set"],
                         (194, "ff2468f09fb6721de776c857e096fe485b2399e70fa6c5d37877179c4de47509"))
        self.assertEqual(D.TARGETS[D.RUNNING_SIGNER_HELD]["dr5-block"],
                         (155, "4337f769d984876468379caf7b1ba59dd0d503344f942e30eedb912d2bd96c64"))
        # a stopped signer leaves no deployer-visible trace: the post-HELD E-19 text, under a distinct name
        self.assertEqual(D.TARGETS[D.STOPPED_AFTER_LOAD_HELD], dict(E.NEW_DR5_TARGETS["WITNESS_RUNNING_HELD_E19"]))
        self.assertNotEqual(D.TARGETS[D.STOPPED_AFTER_LOAD_HELD], T10.TARGETS[T10.RUNNING_HELD])
        self.assertNotEqual(D.STOPPED_AFTER_LOAD_HELD, T10.RUNNING_HELD)
        texts = derived["targets"][D.RUNNING_SIGNER_HELD]["texts"]["result-set"]
        for line in D.PRESENT_BEFORE:                             # /run/lilith-authority-dev unchanged (OR-6)
            self.assertEqual(texts.count(line), 1)

    def test_any_script_that_could_observe_the_signer_differently_is_refused(self):
        with self.assertRaises(D.TargetError) as caught:
            D.derive(accepted_sets(), SCRIPT + b"\n")
        self.assertEqual(caught.exception.reason, "DR5_SCRIPT_PIN_MISMATCH")
        text = SCRIPT.decode()
        mutations = {
            "SIGNER_CREDENTIALS_NOT_ONE_LATER_ITEM": text.replace(" /run/credentials/lilith-authority-dev.service", "", 1),
            "SIGNER_PATH_OBSERVED_BY_SCRIPT:AB_PR1_CLIS": text.replace(
                'readonly AB_PR1_CLIS="', 'readonly AB_PR1_CLIS="/run/lilith-authority-dev/owner.sock '),
            "LATER_STATE_FUNCTION_NOT_EXACT": text.replace(
                '        /var/lib/*|/run/*) ab_deny -r "${path}"; ab_deny -x "${path}" ;;',
                '        /var/lib/*) ab_deny -r "${path}"; ab_deny -x "${path}" ;;'),
        }
        for reason, mutated in mutations.items():
            data = mutated.encode()
            self.assertNotEqual(data, SCRIPT, reason)
            with mock.patch.object(T10, "DR5_SCRIPT_SHA256", sha(data)):
                with self.assertRaises(D.TargetError) as caught:
                    D.prove_signer_delta(data)
            self.assertEqual(caught.exception.reason, reason)

    def test_a_source_text_without_the_deferred_line_is_refused(self):
        sets = json.loads(FIXTURE.read_text(encoding="utf-8"))["sets"]
        tampered = copy.deepcopy(sets)
        line = "DEFERRED_UNTIL_OBJECT_EXISTS: /run/credentials/lilith-authority-dev.service (later step)"
        self.assertIn(line, tampered["result-set"])
        tampered["result-set"] = [x for x in tampered["result-set"] if x != line]
        own_pins = {name: (len(lines), T9.digest(lines)) for name, lines in tampered.items()}
        with self.assertRaises(D.TargetError) as caught:
            D.derive({k: T9.encode(v) for k, v in tampered.items()}, SCRIPT, base_pins=own_pins, w9_pins=None,
                     w10_pins=None, e19_pins=None, target_pins=None)
        self.assertTrue(caught.exception.reason.startswith(("SUBSTITUTION_SOURCE_NOT_EXACTLY_ONCE",
                                                            "SOURCE_DEFERRED_LINE_NOT_EXACTLY_ONCE")),
                        caught.exception.reason)

    def test_compare_uses_only_an_independently_verified_w11_phase(self):
        texts = D.derive(accepted_sets(), SCRIPT)["targets"]
        log = "\n".join(texts[D.RUNNING_SIGNER_HELD]["texts"]["result-set"]) + "\n"
        result = D.compare("W11_1_SIGNER_STARTED_EXACT", log)
        self.assertEqual((result["result"], result["target"], result["targetAccepted"]),
                         ("EQUAL", D.RUNNING_SIGNER_HELD, False))
        self.assertIn("not signer evidence", result["note"])
        held_log = "\n".join(texts[D.STOPPED_AFTER_LOAD_HELD]["texts"]["result-set"]) + "\n"
        self.assertEqual(D.compare("W11_1S_STOPPED_AFTER_FIRST_LOAD", held_log)["result"], "EQUAL")
        self.assertEqual(D.compare("W11_1_SIGNER_STARTED_EXACT", held_log)["result"], "DRIFT")
        for phase in ("W10_1_HELD_EXACT", "W9_5_GENESIS_COMMITTED_EXACT", V.W11_0, V.W11_KEY, V.W11_RESTART,
                      V.UNCLASSIFIED):
            with self.assertRaises(D.TargetError) as caught:
                D.compare(phase, log)
            self.assertTrue(caught.exception.reason.startswith("NO_BASELINE_STOP"), phase)
        self.assertFalse(set(D.PHASE_TARGETS) & (set(T10.PHASE_TARGETS) | set(T9.PHASE_TARGETS)))
        drift = log.replace("DENIED: test -w /opt\n", "ALLOWED(unexpected) test -w /opt\n", 1)
        self.assertEqual(D.compare("W11_1_SIGNER_STARTED_EXACT", drift)["result"], "DRIFT")

    def test_the_cli_derives_from_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name, data in accepted_sets().items():
                path = Path(tmp) / name
                path.write_bytes(data)
                paths.append(str(path))
            script = Path(tmp) / "script.sh"
            script.write_bytes(SCRIPT)
            out = subprocess.run([sys.executable, "-B", str(TOOLS / "mb11_dr5_target.py"), "derive", *paths,
                                  str(script)], capture_output=True, check=False)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["targets"][D.RUNNING_SIGNER_HELD]["result-set"]["sha256"],
                         D.TARGETS[D.RUNNING_SIGNER_HELD]["result-set"][1])


E19_BASE_PINS = {"result-set": (192, "91c91ec7d5001d8c13f8438cb3d653ea3ee9b6bc1e41087ec154fec834def13d"),
                 "dr5-block": (153, "0692dc6df9dfbba2e6d81d985d56090025c11d2756a6397966346bb5f9e5fd16"),
                 "predeploy-block": (29, "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae")}
PRE_E19_W11 = ("8c8b6eacb144e1d3587a9e6ea1694ff122c0c219ac6e9b90f1f2addd9b41ce93",
               "ba39512d64bbc0966dca4125ab1d390adf2d3b41718a279d57e5a4aa4e6d1e59",
               "593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65",
               "ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a")


def release_line(sha_):
    return E.DR5_RELEASE_LINE.format(sha=sha_)


class Dr5E19RebaseTests(unittest.TestCase):
    """Record §14: the W11 targets are derived on the owner-accepted E-19 base `WITNESS_RUNNING_HELD_E19`."""

    @classmethod
    def setUpClass(cls):
        cls.derived = D.derive(accepted_sets(), SCRIPT)

    def test_the_base_is_exactly_the_accepted_e19_target_and_the_e19_pins_are_unchanged(self):
        self.assertEqual(D.E19_BASE, "WITNESS_RUNNING_HELD_E19")
        self.assertEqual({k: tuple(v) for k, v in E.NEW_DR5_TARGETS[D.E19_BASE].items()}, E19_BASE_PINS)
        self.assertEqual(E.NEW_DR5_SOURCES[D.E19_BASE], T10.RUNNING_HELD)
        self.assertEqual(sha((TOOLS / "e19_p1b10_upgrade.py").read_bytes()), D.E19_CONTRACT_SHA256)
        w10 = T10.derive(accepted_sets(), SCRIPT)["targets"][T10.RUNNING_HELD]["texts"]
        base = D.e19_base(w10)
        self.assertEqual({n: (len(base[n]), T9.digest(base[n])) for n in D.SETS}, E19_BASE_PINS)
        self.assertEqual(base, E.derive_release_swap(w10, old=E.OLD_RELEASE, new=E.NEW_RELEASE))

    def test_the_stopped_target_is_the_accepted_e19_base(self):
        sets = self.derived["targets"][D.STOPPED_AFTER_LOAD_HELD]["sets"]
        self.assertEqual({n: (sets[n]["lines"], sets[n]["sha256"]) for n in D.SETS}, E19_BASE_PINS)
        self.assertEqual({n: tuple(v) for n, v in D.TARGETS[D.STOPPED_AFTER_LOAD_HELD].items()}, E19_BASE_PINS)
        self.assertTrue(all(not sets[n]["added"] and not sets[n]["removed"] for n in D.SETS))

    def test_the_running_target_is_the_e19_base_plus_exactly_the_signer_delta(self):
        base = self.derived["targets"][D.STOPPED_AFTER_LOAD_HELD]["texts"]
        running = self.derived["targets"][D.RUNNING_SIGNER_HELD]
        for name in ("result-set", "dr5-block"):
            self.assertEqual(running["sets"][name]["added"], list(D.DENIED_LINES))
            self.assertEqual(running["sets"][name]["removed"], [D.DEFERRED_LINE])
            self.assertEqual(running["texts"][name], T9.substitute(base[name], ((D.DEFERRED_LINE, D.DENIED_LINES),)))
            self.assertEqual(running["sets"][name]["lines"], E19_BASE_PINS[name][0] + 2)
        self.assertEqual(running["texts"]["predeploy-block"], base["predeploy-block"])
        self.assertEqual(D.TARGETS[D.RUNNING_SIGNER_HELD]["predeploy-block"], E19_BASE_PINS["predeploy-block"])
        self.assertEqual({n: (running["sets"][n]["lines"], running["sets"][n]["sha256"]) for n in D.SETS},
                         {n: tuple(v) for n, v in D.TARGETS[D.RUNNING_SIGNER_HELD].items()})

    def test_release_lines_are_new_only_in_every_target(self):
        for target in (D.RUNNING_SIGNER_HELD, D.STOPPED_AFTER_LOAD_HELD):
            texts = self.derived["targets"][target]["texts"]
            for name in D.SETS:
                self.assertEqual(texts[name].count(release_line(E.NEW_RELEASE)), E.DR5_RELEASE_LINE_COUNTS[name])
                self.assertFalse(any(E.OLD_RELEASE in line for line in texts[name]), (target, name))
        self.assertEqual(self.derived["base"], D.E19_BASE)
        self.assertEqual(self.derived["release"], E.NEW_RELEASE)
        self.assertIs(self.derived["accepted"], False)

    def test_the_pre_e19_values_are_superseded(self):
        pinned = {v[1] for target in D.TARGETS.values() for v in target.values()}
        self.assertFalse(pinned & set(PRE_E19_W11))
        self.assertEqual(T10.TARGETS[T10.RUNNING_HELD]["result-set"][1], PRE_E19_W11[2])   # W10 history unchanged

    def test_a_pre_e19_log_is_never_equal(self):
        w10 = T10.derive(accepted_sets(), SCRIPT)["targets"][T10.RUNNING_HELD]["texts"]
        old_running = "\n".join(T9.substitute(w10["result-set"], ((D.DEFERRED_LINE, D.DENIED_LINES),))) + "\n"
        old_stopped = "\n".join(w10["result-set"]) + "\n"
        for phase, log in (("W11_1_SIGNER_STARTED_EXACT", old_running),
                           ("W11_1S_STOPPED_AFTER_FIRST_LOAD", old_stopped)):
            result = D.compare(phase, log)
            self.assertEqual(result["result"], "DRIFT", phase)
            self.assertGreater(result["oldReleaseLines"], 0, phase)
        new_log = "\n".join(self.derived["targets"][D.RUNNING_SIGNER_HELD]["texts"]["result-set"]) + "\n"
        result = D.compare("W11_1_SIGNER_STARTED_EXACT", new_log)
        self.assertEqual((result["result"], result["oldReleaseLines"], result["base"]), ("EQUAL", 0, D.E19_BASE))

    def test_a_base_that_is_not_the_accepted_e19_target_is_refused(self):
        w10 = T10.derive(accepted_sets(), SCRIPT)["targets"][T10.RUNNING_HELD]["texts"]
        tampered = copy.deepcopy(w10)
        tampered["dr5-block"] = [line for line in tampered["dr5-block"] if line != "DENIED: test -w /opt"] + \
            ["DENIED: test -w /opt"]
        with self.assertRaises(D.TargetError) as caught:
            D.e19_base(tampered)
        self.assertEqual(caught.exception.reason, "E19_BASE_NOT_ACCEPTED_TARGET:dr5-block")
        self.assertEqual(D.e19_base(tampered, e19_pins=None)["dr5-block"][-1], "DENIED: test -w /opt")  # TEST seam
        missing = copy.deepcopy(w10)
        missing["result-set"] = [line for line in missing["result-set"] if line != release_line(E.OLD_RELEASE)]
        with self.assertRaises(E.Refused):
            D.e19_base(missing, e19_pins=None)                     # the contract swap itself refuses

    def test_a_synthetic_base_derives_through_the_seams(self):
        sets = json.loads(FIXTURE.read_text(encoding="utf-8"))["sets"]
        tampered = copy.deepcopy(sets)
        tampered["result-set"].append("DENIED: test -w /synthetic-extra")
        own = {name: (len(lines), T9.digest(lines)) for name, lines in tampered.items()}
        encoded = {k: T9.encode(v) for k, v in tampered.items()}
        with self.assertRaises(D.TargetError) as caught:
            D.derive(encoded, SCRIPT, base_pins=own, w9_pins=None, w10_pins=None, target_pins=None)
        self.assertEqual(caught.exception.reason, "E19_BASE_NOT_ACCEPTED_TARGET:result-set")
        out = D.derive(encoded, SCRIPT, base_pins=own, w9_pins=None, w10_pins=None, e19_pins=None, target_pins=None)
        self.assertIn("DENIED: test -w /synthetic-extra",
                      out["targets"][D.STOPPED_AFTER_LOAD_HELD]["texts"]["result-set"])

    def test_pin_mismatches_are_refused(self):
        with mock.patch.object(D, "E19_CONTRACT_SHA256", "0" * 64):
            with self.assertRaises(D.TargetError) as caught:
                D.derive(accepted_sets(), SCRIPT)
            self.assertEqual(caught.exception.reason, "E19_CONTRACT_PIN_MISMATCH")
            with self.assertRaises(D.TargetError):
                D.compare("W11_1_SIGNER_STARTED_EXACT", "x\n")

    def test_phase_refusals_and_mapping_are_unchanged(self):
        self.assertEqual(D.PHASE_TARGETS, {"W11_1_SIGNER_STARTED_EXACT": D.RUNNING_SIGNER_HELD,
                                           "W11_1S_STOPPED_AFTER_FIRST_LOAD": D.STOPPED_AFTER_LOAD_HELD})
        log = "\n".join(self.derived["targets"][D.STOPPED_AFTER_LOAD_HELD]["texts"]["result-set"]) + "\n"
        for phase in ("W10_1_HELD_EXACT", "W10_1S_HELD_EXACT_WITNESS_STOPPED", "U5_OLD_RETIRED_REPLACEMENT_ACCEPTED",
                      V.W11_0, V.UNCLASSIFIED):
            with self.assertRaises(D.TargetError) as caught:
                D.compare(phase, log)
            self.assertTrue(caught.exception.reason.startswith("NO_BASELINE_STOP"), phase)
        result = D.compare("W11_1S_STOPPED_AFTER_FIRST_LOAD", log)
        self.assertEqual((result["result"], result["targetAccepted"], result["accepted"]), ("EQUAL", False, False))


# ------------------------------------------------------------------------------------ classifier ---

def good_health(**overrides):
    value = {**V.HEALTH_EXACT, "publicKeySha256": V.B3_PUBLIC_KEY_SHA256, "reasons": list(V.STRUCTURAL_REASONS)}
    value.update(overrides)
    return value


def good_readiness():
    dark = {"authorityGranted": False, "liveEntryAuthorized": False, "issuanceReady": False, "successorCurrent": False}
    flags = {"authorityGranted": False, "activationGranted": False, "issuanceWired": False}
    return {"eligibility": {"status": "READY", "reasons": [], "holdDetail": None,
                            "loadedKeyBinding": {"status": "PASS", "reason": None, "detail": None}, "facts": dict(dark),
                            "packageFlags": dict(flags)},
            "full": {"status": "NOT_READY", "reasons": list(V.EXPECTED_FULL_REASONS), "holdDetail": V.FULL_HOLD_DETAIL,
                     "loadedKeyBinding": {"status": "PASS", "reason": None, "detail": None}, "facts": dict(dark),
                     "packageFlags": dict(flags)}}


def running_units():
    return {V.SIGNER_SERVICE: {"Id": V.SIGNER_SERVICE, "LoadState": "loaded", "ActiveState": "active",
                               "SubState": "running", "UnitFileState": "static", "NeedDaemonReload": "no",
                               "MainPID": "4242", "NRestarts": "0", "InvocationID": INVOCATION, "Result": "success",
                               "ExecMainStatus": "0"},
            V.SIGNER_SOCKET_UNIT: {"Id": V.SIGNER_SOCKET_UNIT, "LoadState": "loaded", "ActiveState": "active",
                                   "SubState": "running", "UnitFileState": "static", "NeedDaemonReload": "no",
                                   "MainPID": "0", "NRestarts": "0", "InvocationID": "", "Result": "success",
                                   "ExecMainStatus": "0"}}


def stopped_units():
    units = running_units()
    for name in V.SIGNER_UNITS:
        units[name].update(ActiveState="inactive", SubState="dead", MainPID="0", InvocationID="")
    return units


def running(**overrides):
    obs = {
        "w10": {"phase": V.W10_1, "direct": "W10_SIGNER_OR_LATER_STATE", "maskExact": True, "holdClass": "HELD_EXACT",
                "witnessInvocationId": WITNESS_INVOCATION, "witnessMainPid": "777", "w9Failures": [], "failures": []},
        "units": running_units(),
        "paths": {"credentials": {"present": True, "kind": "dir", "uid": 995, "gid": 985, "mode": 0o500,
                                  "names": [V.CREDENTIAL_NAME]},
                  "ownerSocket": {"present": True, "kind": "socket", "uid": 0, "gid": 0, "mode": 0o600}},
        "process": {"cwd": V.RELEASE_CWD, "argv": list(V.EXEC_ARGV), "uid": 995, "gid": 985},
        "journal": {"readable": True, "invocations": [{"id": INVOCATION, "credentials": V.LOADED}]},
        "health": {"health": good_health(), "before": {"InvocationID": INVOCATION, "MainPID": "4242"},
                   "after": {"InvocationID": INVOCATION, "MainPID": "4242"}},
        "readiness": good_readiness(),
        "ledger": {"readable": True, "listing": {V.LEDGER_NAME: 61440}, "dbSha256": DB_SHA},
        "baseline": {"dbSha256": DB_SHA, "witnessInvocationId": WITNESS_INVOCATION, "witnessMainPid": "777"},
        "firstLoadRecorded": True, "signerIds": [995, 985], "restartBoundary": {"reasons": []},
    }
    obs.update(overrides)
    return obs


def stopped(loads=1, **overrides):
    invocations = [{"id": INVOCATION, "credentials": V.LOADED}][:loads]
    obs = running(units=stopped_units(), paths={"credentials": {"present": False}, "ownerSocket": {"present": False}},
                  process=None, health=None, readiness=None, journal={"readable": True, "invocations": invocations})
    obs.update(overrides)
    return obs


def phase(obs):
    return V.classify(obs)["phase"]


class ClassifierTests(unittest.TestCase):
    def test_the_exact_phases(self):
        report = V.classify(running())
        self.assertEqual(report["phase"], V.W11_1, report["reasons"])
        self.assertEqual(report["kActLoadCount"], 1)
        self.assertTrue(report["healthIsSignerClaim"])
        for flag in ("signerAvailableIsAuthority", "readinessIsAuthority", "registryEffective", "authorityActive",
                     "authorityGranted"):
            self.assertIs(report[flag], False)
        self.assertEqual(report["issuanceAuthority"], "NONE")
        self.assertEqual(phase(stopped()), V.W11_1S)
        self.assertEqual(phase(stopped(loads=0, firstLoadRecorded=False)), V.W11_0)

    def test_a_stopped_signer_after_its_first_load_is_never_w10_1_or_w11_0(self):
        # the unchanged W10 sees W10_1 again once the signer stopped: only the load record distinguishes the worlds
        self.assertEqual(phase(stopped()), V.W11_1S)
        self.assertEqual(phase(stopped(loads=0)), V.W11_START)            # a recorded load the journal does not show
        self.assertEqual(phase(stopped(journal={"readable": False, "invocations": []})), V.UNCLASSIFIED)
        self.assertEqual(phase(stopped(firstLoadRecorded=None)), V.UNCLASSIFIED)
        self.assertNotIn(V.W11_0, (phase(stopped()), phase(stopped(loads=0))))
        self.assertNotIn("W10_1_HELD_EXACT", V.HOST_PHASES)

    def test_halt_facts(self):
        cases = {
            V.W11_HOLD: running(w10={**running()["w10"], "phase": "W10_HELD_MISBOUND", "holdClass": "MISBOUND"}),
            V.W11_LEDGER: running(ledger={"readable": True, "listing": {V.LEDGER_NAME: 1, V.WAL_NAME: 4152},
                                          "dbSha256": DB_SHA}),
            V.W11_KEY: running(health={**running()["health"], "health": good_health(publicKeySha256="0" * 64)}),
            V.W11_CREDENTIAL: running(journal={"readable": True, "invocations": [{"id": INVOCATION,
                                                                                  "credentials": V.FAILED}]}),
            V.W11_DARK: running(health={**running()["health"], "health": good_health(readiness="READY")}),
        }
        for expected, obs in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(V.PHASE_TABLE[phase(obs)][0], V.HALT)
                self.assertEqual(phase(obs), expected)
        changed = running(ledger={"readable": True, "listing": {V.LEDGER_NAME: 1}, "dbSha256": "d" * 64})
        self.assertEqual(phase(changed), V.W11_LEDGER)
        logical = running(w10={**running()["w10"], "w9Failures": ["BASE_NOT_EXACT:ledgerExact"]})
        self.assertEqual(phase(logical), V.W11_LEDGER)
        binding = good_readiness()
        binding["eligibility"]["loadedKeyBinding"] = {"status": "FAIL", "reason": "HEALTH_FINGERPRINT_MISMATCH",
                                                      "detail": None}
        self.assertEqual(phase(running(readiness=binding)), V.W11_KEY)
        exit_code = running_units()
        exit_code[V.SIGNER_SERVICE].update(ActiveState="failed", Result="exit-code", ExecMainStatus="243")
        self.assertEqual(phase(running(units=exit_code)), V.W11_CREDENTIAL)
        absent = running(health={**running()["health"], "health": good_health(credential="CREDENTIAL_INVALID")})
        self.assertEqual(phase(absent), V.W11_CREDENTIAL)
        for mode, fact in (("full", "issuanceReady"), ("eligibility", "authorityGranted"), ("full", "successorCurrent")):
            value = good_readiness()
            value[mode]["facts"][fact] = True
            self.assertEqual(phase(running(readiness=value)), V.W11_DARK, (mode, fact))
        flags = good_readiness()
        flags["eligibility"]["packageFlags"]["issuanceWired"] = True
        self.assertEqual(phase(running(readiness=flags)), V.W11_DARK)
        self.assertEqual(phase(running(health={**running()["health"],
                                               "health": good_health(signing="SIGNING_AVAILABLE")})), V.W11_DARK)

    def test_halt_precedence_and_unknown_never_hides_a_halt(self):
        both = running(w10={**running()["w10"], "phase": "W10_HOLD_RECORD_MALFORMED", "holdClass": "MALFORMED"},
                       health={**running()["health"], "health": good_health(publicKeySha256="0" * 64)})
        self.assertEqual(phase(both), V.W11_HOLD)                          # the hold dominates the key
        unknown_and_key = running(units=None, health={**running()["health"],
                                                      "health": good_health(publicKeySha256="0" * 64)})
        self.assertEqual(phase(unknown_and_key), V.W11_KEY)               # a proven HALT survives UNKNOWN
        unknown_and_stop = running(units=None, w10={**running()["w10"], "phase": "W10_WITNESS_NOT_EXACT"})
        self.assertEqual(phase(unknown_and_stop), V.UNCLASSIFIED)        # UNKNOWN precedes every STOP
        self.assertEqual(list(V.HALT_PHASES), [V.W11_HOLD, V.W11_LEDGER, V.W11_KEY, V.W11_CREDENTIAL, V.W11_DARK])

    def test_unknown_is_never_success(self):
        for label, obs in {
            "units": running(units=None),
            "journal": running(journal={"readable": False, "invocations": []}),
            "seam": running(w10={**running()["w10"], "maskExact": False}),
            "w10": running(w10={**running()["w10"], "phase": "UNCLASSIFIED_STOP"}),
            "ledger": running(ledger={"readable": False}),
            "baseline": running(baseline={"dbSha256": DB_SHA}),
            "record": running(firstLoadRecorded="yes"),
            "boundary unobserved": running(restartBoundary=None),
            "boundary unreadable": running(restartBoundary={"error": "OSError"}),
            "nothing": {},
        }.items():
            with self.subTest(label=label):
                self.assertEqual(phase(obs), V.UNCLASSIFIED)

    def test_stop_classes(self):
        restarts = running_units()
        restarts[V.SIGNER_SERVICE]["NRestarts"] = "1"
        two_loads = {"readable": True, "invocations": [{"id": OTHER_INVOCATION, "credentials": V.LOADED},
                                                       {"id": INVOCATION, "credentials": V.LOADED}]}
        enabled = running_units()
        enabled[V.SIGNER_SERVICE]["UnitFileState"] = "enabled"
        reload = running_units()
        reload[V.SIGNER_SOCKET_UNIT]["NeedDaemonReload"] = "yes"
        socket_only = stopped_units()
        socket_only[V.SIGNER_SOCKET_UNIT]["ActiveState"] = "active"
        activating = running_units()
        activating[V.SIGNER_SERVICE].update(ActiveState="activating", SubState="auto-restart")
        cases = {
            "witness not exact": (running(w10={**running()["w10"], "phase": "W10_WITNESS_NOT_EXACT"}), V.W11_WITNESS),
            "witness stopped": (running(w10={**running()["w10"], "phase": "W10_1S_HELD_EXACT_WITNESS_STOPPED"}),
                                V.W11_WITNESS),
            "witness incarnation": (running(w10={**running()["w10"], "witnessInvocationId": "2" * 32}), V.W11_WITNESS),
            "restarts": (running(units=restarts), V.W11_RESTART),
            "two loads": (running(journal=two_loads), V.W11_RESTART),
            "health from another incarnation": (running(health={**running()["health"],
                                                                "before": {"InvocationID": OTHER_INVOCATION,
                                                                           "MainPID": "4242"}}), V.W11_RESTART),
            "running invocation not the loaded one": (running(journal={"readable": True, "invocations": [
                {"id": OTHER_INVOCATION, "credentials": V.LOADED}]}), V.W11_RESTART),
            "auto-restart": (running(units=activating), V.W11_START),
            "running without a load": (running(journal={"readable": True, "invocations": []}), V.W11_START),
            "unknown credential outcome": (running(journal={"readable": True, "invocations": [
                {"id": INVOCATION, "credentials": V.UNKNOWN}]}), V.W11_START),
            "enabled": (running(units=enabled), V.W11_UNIT),
            "reload pending": (running(units=reload), V.W11_UNIT),
            "socket only": (stopped(units=socket_only), V.W11_UNIT),
            "wrong cwd": (running(process={**running()["process"], "cwd": "/opt/lilith-authority-dev/releases/x"}),
                          V.W11_UNIT),
            "wrong argv": (running(process={**running()["process"], "argv": ["/usr/bin/python3"]}), V.W11_UNIT),
            "wrong uid": (running(process={**running()["process"], "uid": 0}), V.W11_UNIT),
            "extra credential": (running(paths={**running()["paths"], "credentials": {
                **running()["paths"]["credentials"], "names": [V.CREDENTIAL_NAME, "other"]}}), V.W11_UNIT),
            "socket mode": (running(paths={**running()["paths"], "ownerSocket": {
                **running()["paths"]["ownerSocket"], "mode": 0o666}}), V.W11_UNIT),
            "extra reason": (running(health={**running()["health"], "health": good_health(
                reasons=[*V.STRUCTURAL_REASONS, "WITNESS_MISSING"])}), V.W11_HEALTH),
            "reordered reasons": (running(health={**running()["health"], "health": good_health(
                reasons=list(reversed(V.STRUCTURAL_REASONS)))}), V.W11_HEALTH),
            "extra field": (running(health={**running()["health"], "health": {**good_health(), "x": 1}}),
                            V.W11_HEALTH),
            "no health": (running(health=None), V.W11_RESTART),
            "boundary not effective": (running(restartBoundary={"reasons": ["lilith-authority-dev.service:"
                                                                            "EFFECTIVE_RESTART_NOT_NO"]}), V.W11_UNIT),
            "boundary not effective before start": (stopped(loads=0, firstLoadRecorded=False, restartBoundary={
                "reasons": ["OVERLAY_EMPTY"]}), V.W11_UNIT),
            "residue": (running(ledger={"readable": True, "listing": {V.LEDGER_NAME: 1, V.WAL_NAME: 0,
                                                                     V.SHM_NAME: 32768}, "dbSha256": DB_SHA}),
                        V.W11_RESIDUE),
        }
        for label, (obs, expected) in cases.items():
            with self.subTest(label=label):
                self.assertEqual(phase(obs), expected, V.classify(obs)["reasons"])
        not_eligible = good_readiness()
        not_eligible["eligibility"].update(status="NOT_READY", reasons=["LOADED_KEY_BINDING:BINDING_INPUT_MISSING"])
        self.assertEqual(phase(running(readiness=not_eligible)), V.W11_READINESS)
        extra_full = good_readiness()
        extra_full["full"]["reasons"] = ["CREDENTIAL_INVENTORY:X", *V.EXPECTED_FULL_REASONS]
        self.assertEqual(phase(running(readiness=extra_full)), V.W11_READINESS)
        detail = good_readiness()
        detail["full"]["holdDetail"] = "OTHER"
        self.assertEqual(phase(running(readiness=detail)), V.W11_READINESS)
        self.assertEqual(phase(running(readiness=None)), V.W11_READINESS)

    def test_every_phase_has_a_route_and_only_exact_phases_proceed(self):
        self.assertEqual(set(V.PHASE_TABLE), set(V.HOST_PHASES))
        for name, (route, _note) in V.PHASE_TABLE.items():
            if name not in (V.W11_0, V.W11_1, V.W11_1S):
                self.assertIn(route, (V.HALT, V.STOP_REVALIDATE, V.STOP_OWNER_ADJUDICATION), name)
        self.assertIn("RESTART_BOUND_PROVEN", V.PHASE_TABLE[V.W11_0][0])
        self.assertIn("new go", V.PHASE_TABLE[V.W11_1S][1])

    def test_journal_parsing(self):
        lines = [json.dumps({"_SYSTEMD_INVOCATION_ID": INVOCATION, "_COMM": "systemd",
                             "MESSAGE": "Started lilith-authority-dev.service - LILITH DEV_SYNTHETIC ..."}),
                 json.dumps({"_SYSTEMD_INVOCATION_ID": OTHER_INVOCATION, "_COMM": "systemd",
                             "MESSAGE": "lilith-authority-dev.service: Failed to set up credentials: Bad message"}),
                 json.dumps({"_SYSTEMD_INVOCATION_ID": "c" * 32, "_COMM": "systemd", "MESSAGE": "Stopping ..."}),
                 json.dumps({"MESSAGE": "no invocation"}), ""]
        parsed = V.parse_journal(lines)
        self.assertEqual([(i["id"], i["credentials"]) for i in parsed["invocations"]],
                         [(INVOCATION, V.LOADED), (OTHER_INVOCATION, V.FAILED), ("c" * 32, V.UNKNOWN)])
        self.assertFalse(V.parse_journal(["not json"])["readable"])
        later = V.parse_journal([json.dumps({"_SYSTEMD_INVOCATION_ID": INVOCATION, "_COMM": "python",
                                             "MESSAGE": "x"}),
                                 json.dumps({"_SYSTEMD_INVOCATION_ID": INVOCATION,
                                             "MESSAGE": "Main process exited, code=exited, status=243/CREDENTIALS"})])
        self.assertEqual(later["invocations"][0]["credentials"], V.FAILED)       # failure dominates

    def test_journal_reader_is_cursor_bound_and_unknown_on_error(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 1, "", "cursor not found")
        self.assertFalse(V.journal_invocations("s=abc", run=run)["readable"])
        self.assertEqual(calls[0][:3], [V.JOURNALCTL, "-u", V.SIGNER_SERVICE])
        self.assertIn("--after-cursor=s=abc", calls[0])
        self.assertFalse(V.journal_invocations("bad cursor", run=run)["readable"])
        self.assertEqual(len(calls), 1)

    def test_the_cli_classifies_a_recorded_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "obs.json"
            path.write_text(json.dumps(running()), encoding="utf-8")
            out = subprocess.run([sys.executable, "-B", str(TOOLS / "mb11_signer_verifier.py"), "classify", str(path)],
                                 capture_output=True, check=False)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["phase"], V.W11_1)
        bad = subprocess.run([sys.executable, "-B", str(TOOLS / "mb11_signer_verifier.py"), "start"],
                             capture_output=True, check=False)
        self.assertEqual(bad.returncode, 2)


# ------------------------------------------------------------------------------- static boundaries ---

class StaticBoundaryTests(unittest.TestCase):
    def test_the_verifier_never_touches_a_socket_a_credential_or_a_unit_verb(self):
        source = (TOOLS / "mb11_signer_verifier.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in node.names} | {node.module.split(".")[0] for node in ast.walk(tree)
                                                if isinstance(node, ast.ImportFrom) and node.module}
        self.assertNotIn("socket", imported)
        for needle in ("clients", "signer_health", "signer_recovery", "connect(", ".bind(", "encode_frame",
                       "ISSUE_OWNER_EVIDENCE", "RECOVERY_", "load_der_private_key", "release_initial",
                       "create_initial_held", "\"start\"", "\"stop\"", "\"restart\"", "\"enable\"", "daemon-reload",
                       "os.unlink", "os.remove", "rmtree", "O_WRONLY", "O_CREAT", "write_bytes", "write_text"):
            self.assertFalse(needle in source, needle)
        commands = {node.elts[0].id: node for node in ast.walk(tree) if isinstance(node, ast.List) and node.elts
                    and isinstance(node.elts[0], ast.Name) and node.elts[0].id in ("SYSTEMCTL", "JOURNALCTL")}
        self.assertEqual(set(commands), {"SYSTEMCTL", "JOURNALCTL"})
        self.assertEqual(ast.literal_eval(commands["SYSTEMCTL"].elts[1]), "show")    # systemctl show only
        self.assertEqual(ast.literal_eval(commands["JOURNALCTL"].elts[1]), "-u")

    def test_the_dr5_tool_reads_and_writes_nothing_live(self):
        source = (TOOLS / "mb11_dr5_target.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names} | {node.module.split(".")[0] for node in ast.walk(tree)
                                                if isinstance(node, ast.ImportFrom) and node.module}
        self.assertEqual(imported - {"__future__"}, {"hashlib", "json", "re", "sys", "pathlib", "mb10_dr5_target",
                                                     "mb9_dr5_target", "e19_p1b10_upgrade"})
        for needle in ("write_bytes", "write_text", "open(", ".unlink"):
            self.assertFalse(needle in source, needle)

    def test_no_live_capable_operator_or_workflow_change_in_this_slice(self):
        # Owner exception (PR #183, 2026-10-12): the ONE disposable-runner synthetic restart-boundary probe step is the
        # only M-B11 workflow reference allowed; everything else stays prohibited (`mb11_workflow_violations`).
        # The M-B11 operator slice (2026-10-15) adds exactly the reviewed operator, pinned by its record; no workflow
        # may name it (LIVE_TOKENS), and nothing in this design slice runs it.
        operator = hashlib.sha256((TOOLS / "mb11_operator.py").read_bytes()).hexdigest()
        record = (ROOT / "docs/architecture/slice-15b2b-b1b3e-mb11-signer-start-operator.md").read_text("utf-8")
        self.assertIn(f"`mb11_operator.py` | `{operator}`", record)
        self.assertEqual(mb11_workflow_violations(workflow_texts()), [])


# ----------------------------------------------------------- M-B11 workflow guard (owner exception) ---
# The single approved M-B11 workflow reference: the synthetic restart-boundary probe (PR-A1, OD-M11-11) in the
# read-only `repository-contracts` job of `ci.yml`, byte-exact. It drives only synthetic units through the
# control-side `scripts/probe_signer_restart_boundary.py`; it never names the live operator, the real signer, a real
# credential or an authority operation. Any other M-B11 reference, any live-capable token, a moved, renamed or
# altered step, a self-hosted runner, wider permissions, credentials, or a weakened PR / DEV separation fails.
APPROVED_WORKFLOW = "ci.yml"
APPROVED_JOB = "repository-contracts"
APPROVED_STEP = (
    "      - name: Probe the candidate M-B11 signer restart boundary with synthetic units on this disposable runner\n"
    "        shell: bash\n"
    "        run: |\n"
    "          # Synthetic units only (never a LILITH unit); a throwaway credential under this runner's own host key.\n"
    "          set +e\n"
    "          sudo -n /usr/bin/python3 -I -B scripts/probe_signer_restart_boundary.py run --disposable-runner --out "
    "\"${RUNNER_TEMP}/mb11-restart-boundary.json\"\n"
    "          status=$?\n"
    "          set -e\n"
    "          sudo -n cat \"${RUNNER_TEMP}/mb11-restart-boundary.json\" || true\n"
    "          exit \"${status}\"\n")
PROBE_SCRIPT = "scripts/probe_signer_restart_boundary.py"
MB11_MARK = re.compile(r"(?i)m-?b11")
# Live-capable M-B11 / signer / credential / authority operations: never in any workflow.
LIVE_TOKENS = ("mb11_operator", "mb11_signer_verifier", "mb11_dr5_target", "lilith-authority-hold-dev",
               "lilith-authority-verify-dev", "lilith-authority-recovery-dev", "lilith-authority-keygen-dev",
               "lilith-recovery-witness-owner-dev", "systemd-creds", "LoadCredentialEncrypted", "owner-actor",
               "credstore", "release_initial", "create_initial_held", "ISSUE_OWNER_EVIDENCE")
LIVE_PATTERNS = (re.compile(r"systemctl\s+(?:--\S+\s+)*(?:start|restart|enable|try-restart|reload-or-restart)\s+"
                            r"lilith-(?:authority|recovery)"),)
CI_HEADER = ("on:\n  pull_request:\n  push:\n    branches:\n      - main\n  workflow_dispatch:\n\n"
             "permissions:\n  contents: read\n")
CI_FORBIDDEN = ("secrets.", "id-token", "google-github-actions", "gcloud", "environment:", "self-hosted",
                "systemctl restart", "pull_request_target")
DEV_SEPARATION = ("name: LILITH DEV deployment", "if: always() && github.event_name == 'pull_request'",
                  "needs: [repository-contracts, frontend-quality, backend-quality]", "permissions:\n      contents: read",
                  'test "${CONTRACTS}" = success', 'test "${FRONTEND}" = success', 'test "${BACKEND}" = success',
                  "PR_SOURCE_VALIDATION=PASS DEV_AUTH=NONE DEV_DEPLOYMENT=NONE")


def workflow_texts() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted((ROOT / ".github/workflows").glob("*.yml"))}


def _jobs(text: str) -> dict[str, str]:
    body = text.split("\njobs:\n", 1)[1] if "\njobs:\n" in text else ""
    heads = list(re.finditer(r"(?m)^  ([A-Za-z0-9_-]+):\n", body))
    return {m.group(1): body[m.start():heads[i + 1].start() if i + 1 < len(heads) else len(body)]
            for i, m in enumerate(heads)}


def _steps(job: str) -> list[str]:
    heads = list(re.finditer(r"(?m)^      - ", job))
    return [job[m.start():heads[i + 1].start() if i + 1 < len(heads) else len(job)].rstrip("\n") + "\n"
            for i, m in enumerate(heads)]


def mb11_workflow_violations(workflows: dict[str, str]) -> list[str]:
    """Every reason the workflow set leaves the owner exception. `[]` only for exactly the approved probe step."""
    out: list[str] = []
    for name, text in workflows.items():
        out += [f"LIVE_TOKEN:{name}:{token}" for token in LIVE_TOKENS if token in text]
        out += [f"LIVE_COMMAND:{name}" for pattern in LIVE_PATTERNS if pattern.search(text)]
        if name != APPROVED_WORKFLOW and (MB11_MARK.search(text) or PROBE_SCRIPT in text):
            out.append("MB11_OUTSIDE_APPROVED_WORKFLOW:" + name)
    ci = workflows.get(APPROVED_WORKFLOW)
    if ci is None:
        return out + ["APPROVED_WORKFLOW_MISSING"]
    header = ci.split("\njobs:\n", 1)[0]
    if CI_HEADER not in header or header.count("permissions:") != 1 or header.count("on:") != 1:
        out.append("CI_TRIGGERS_OR_PERMISSIONS_CHANGED")
    out += [f"CI_FORBIDDEN:{token}" for token in CI_FORBIDDEN if token in ci]
    if ci.count("permissions:") != 2 or len(re.findall(r"(?m)^ *contents: read$", ci)) != 2 \
            or re.search(r"(?m)^ *[a-z-]+: write$", ci):
        out.append("CI_PERMISSIONS_NOT_READ_ONLY")
    jobs = _jobs(ci)
    marked = [(job, step) for job, text in jobs.items() for step in _steps(text)
              if MB11_MARK.search(step) or PROBE_SCRIPT in step]
    if marked != [(APPROVED_JOB, APPROVED_STEP)]:
        out.append("MB11_STEPS_NOT_EXACTLY_THE_APPROVED_PROBE")
    if len(MB11_MARK.findall(ci)) != len(MB11_MARK.findall(APPROVED_STEP)) or ci.count(PROBE_SCRIPT) != 1:
        out.append("MB11_REFERENCE_OUTSIDE_THE_APPROVED_STEP")
    job = jobs.get(APPROVED_JOB, "")
    if re.findall(r"(?m)^    runs-on: (.+)$", job) != ["ubuntu-latest"]:
        out.append("APPROVED_JOB_NOT_ON_A_GITHUB_HOSTED_RUNNER")
    if re.search(r"(?m)^    (?:permissions|environment|container|services|env|if|needs|strategy|uses):", job):
        out.append("APPROVED_JOB_CONTEXT_CHANGED")
    separation = jobs.get("pr-source-required-check", "")
    if any(needle not in separation for needle in DEV_SEPARATION):
        out.append("PR_DEV_SEPARATION_WEAKENED")
    return out


class Mb11WorkflowGuardTests(unittest.TestCase):
    def setUp(self):
        self.workflows = workflow_texts()
        self.ci = self.workflows[APPROVED_WORKFLOW]

    def violations(self, **changed):
        return mb11_workflow_violations({**self.workflows, **changed})

    def test_the_exact_approved_synthetic_step_passes_and_uses_only_control_side_code(self):
        self.assertEqual(mb11_workflow_violations(self.workflows), [])
        self.assertEqual(self.ci.count(APPROVED_STEP), 1)
        self.assertIn(APPROVED_STEP, _jobs(self.ci)[APPROVED_JOB])
        tree = ast.parse((ROOT / PROBE_SCRIPT).read_text(encoding="utf-8"))
        imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | \
            {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        self.assertIn("mb11_restart_boundary", imported)
        self.assertFalse(imported & {"mb11_operator", "mb11_signer_verifier", "mb11_dr5_target", "lilith_authority_dev",
                                     "lilith_authority_root"})

    def test_every_departure_from_the_exception_fails(self):
        extra = ("      - name: Run another M-B11 check\n        run: python scripts/probe_signer_restart_boundary.py run\n\n")
        anchor = "      - name: Validate trusted broker lifecycle and production absence gates\n"
        cases = {
            "extra M-B11 step": self.ci.replace(anchor, extra + anchor),
            "live command substituted": self.ci.replace(
                "scripts/probe_signer_restart_boundary.py run --disposable-runner",
                "services/owner-memory-control/tools/mb11_operator.py mb11 . . go.txt"),
            "self-hosted runner": self.ci.replace("    name: Repository contracts\n    runs-on: ubuntu-latest\n",
                                                  "    name: Repository contracts\n    runs-on: self-hosted\n"),
            "wider token permissions": self.ci.replace("permissions:\n  contents: read\n",
                                                       "permissions:\n  contents: write\n", 1),
            "id-token added": self.ci.replace("permissions:\n  contents: read\n",
                                              "permissions:\n  contents: read\n  id-token: write\n", 1),
            "credentials added": self.ci.replace("        shell: bash\n        run: |\n          # Synthetic",
                                                 "        shell: bash\n        env:\n          K: ${{ secrets.DEV_KEY }}\n"
                                                 "        run: |\n          # Synthetic"),
            "unauthorized invocation elsewhere": self.ci.replace(
                "      - name: Run Slice 8-15 architecture regressions\n",
                "      - name: Classify\n        run: python services/owner-memory-control/tools/mb11_signer_verifier.py"
                " classify x\n\n      - name: Run Slice 8-15 architecture regressions\n"),
            "probe-named live step": self.ci.replace(anchor, "      - name: Probe synthetic test\n        run: sudo -n "
                                                     "/usr/local/sbin/lilith-authority-verify-dev eligibility x\n\n"
                                                     + anchor),
            "signer start disguised": self.ci.replace(anchor, "      - name: Warm cache\n        run: sudo systemctl "
                                                      "start lilith-authority-dev.service\n\n" + anchor),
            "DEV separation weakened": self.ci.replace("PR_SOURCE_VALIDATION=PASS DEV_AUTH=NONE DEV_DEPLOYMENT=NONE",
                                                       "PR_SOURCE_VALIDATION=PASS"),
            "aggregator needs changed": self.ci.replace("needs: [repository-contracts, frontend-quality, backend-quality]",
                                                        "needs: [frontend-quality, backend-quality]"),
            "trigger widened": self.ci.replace("  pull_request:\n", "  pull_request_target:\n", 1),
            "approved job context changed": self.ci.replace("    name: Repository contracts\n",
                                                            "    name: Repository contracts\n    environment: dev\n"),
        }
        for label, mutated in cases.items():
            with self.subTest(case=label):
                self.assertNotEqual(mutated, self.ci, label)
                self.assertNotEqual(self.violations(**{APPROVED_WORKFLOW: mutated}), [], label)
        moved_ci = self.ci.replace(APPROVED_STEP + "\n", "")
        self.assertNotEqual(moved_ci, self.ci)
        deploy = self.workflows["deploy-dev.yml"]
        self.assertNotEqual(self.violations(**{APPROVED_WORKFLOW: moved_ci, "deploy-dev.yml": deploy + APPROVED_STEP}),
                            [])
        self.assertIn("MB11_OUTSIDE_APPROVED_WORKFLOW:deploy-dev.yml",
                      self.violations(**{"deploy-dev.yml": deploy + "\n# mb11\n"}))


# ------------------------------------------------------------------------------------------ records ---

class RecordTests(unittest.TestCase):
    def setUp(self):
        self.text = RECORD.read_text(encoding="utf-8")

    def test_the_record_names_every_phase_and_pins_the_tools(self):
        for name in V.HOST_PHASES:
            self.assertTrue(f"`{name}`" in self.text, name)
        for path in ("services/owner-memory-control/tools/mb11_signer_verifier.py",
                     "services/owner-memory-control/tools/mb11_dr5_target.py"):
            self.assertTrue(f"`{path}`" in self.text, path)
            # this record, or EXACTLY the E-19 completion re-pin of that file (only the two re-pinned M-B11 tools)
            import e19_completion as C
            value = sha((ROOT / path).read_bytes())
            self.assertTrue(value in self.text or C.MB11_REPINNED_SHA256.get(path) == value, path)
        for value in (V.B3_PUBLIC_KEY_SHA256, V.B2_CURRENT_BLOB_SHA256, *V.STRUCTURAL_REASONS,
                      V.EXPECTED_FULL_REASONS[0], D.TARGETS[D.RUNNING_SIGNER_HELD]["result-set"][1],
                      D.TARGETS[D.RUNNING_SIGNER_HELD]["dr5-block"][1]):
            self.assertTrue(value in self.text, value)

    def test_the_record_keeps_every_decision_open_and_every_boundary(self):
        for od in range(1, 16):
            self.assertTrue(f"OD-M11-{od}" in self.text, od)
        self.assertNotIn("OWNER-ACCEPTED (OD-M11", self.text)
        state = self.text.split("## 13. State", 1)[1]
        for line in ("MB11 = DESIGN / REPOSITORY ONLY; NOT RUN", "OD-M11-1..OD-M11-15 = PROPOSED; NONE ACCEPTED",
                     "RESTART_AND_SOCKET_REACTIVATION_BOUND = NOT PROVEN (LIVE STARTUP BLOCKER)",
                     "M-B11 = NOT AUTHORIZED", "SIGNER = INACTIVE", "K_ACT_LOADS = 0",
                     "P1B12_DEFERRED_ROWS = 12 NOT PERFORMED", "P1B12_NAMESPACE_ROWS = 9 NOT PERFORMED",
                     "REGISTRY_EFFECTIVE = NO", "AUTHORITY_ACTIVE = NO", "authorityGranted = false",
                     "ISSUANCE_AUTHORITY = NONE", "FIRST_MEMORY = NOT AUTHORIZED",
                     "FIRST_MEMORY_READY = NOT REACHED", "PROD = NOT AUTHORIZED"):
            self.assertIn(line, state.splitlines(), line)
        for claim in ("M-B11 = AUTHORIZED", "SIGNER = ACTIVE", "FIRST_MEMORY_READY = REACHED", "REGISTRY_EFFECTIVE = YES",
                      "AUTHORITY_ACTIVE = YES", "RESTART_AND_SOCKET_REACTIVATION_BOUND = PROVEN"):
            self.assertNotIn(claim, self.text)
        for conflict in ("E-25", "E-28", "eligibilityReady", "PR-3 full material"):
            self.assertTrue(conflict in self.text, conflict)

    def test_the_post_freeze_addendum_records_the_evidence_without_claiming_reproduction(self):
        text = ADDENDUM.read_text(encoding="utf-8")
        for value in ("38162573937", "5e83bd187e7f44feae7acae13adcd6370625a195", "W10_1_HELD_EXACT",
                      "ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a",
                      "593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65",
                      "f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae", "MB10_HOST_POST_PASS",
                      "914e885ef47af10b2464a549d9af3b1973566343019b2943451c01b2784ca401"):
            self.assertTrue(value in text, value)
        self.assertTrue("does not reproduce" in text)
        for claim in ("HELD = MUTATED", "AUTHORITY_ACTIVE = YES", "M-B11 = AUTHORIZED"):
            self.assertNotIn(claim, text)


# ---------------------------------------------------------- contract layer (synthetic PR-1 host) ---

if HAVE_CRYPTO and POSIX:
    import pr1s_fixtures as X
    from pr1s_fixtures import PB, SC
    import install_authority_dev as I
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
    from lilith_authority_dev import core as CORE
    from lilith_authority_dev import credential as CRED
    from lilith_authority_dev import protocol as W
    from lilith_authority_dev import recovery as REC
    from lilith_authority_dev import server as S
    from lilith_authority_dev import state as STATE
    from lilith_authority_root import verifier as RV
    from lilith_owner_memory import pr1_acceptance as PA
    from lilith_owner_memory import successor_readiness as SR


@unittest.skipUnless(HAVE_CRYPTO and POSIX, "POSIX owner/mode semantics and cryptography/rfc8785/fido2 required")
class SyntheticHostContractTests(unittest.TestCase):
    """The REAL signer core (HEALTH over a socketpair), the REAL root verifier (both modes) and the REAL durable ledger
    on the synthetic PR-1 host through INITIAL_CUSTODY HELD. The credential is the TEST_ONLY fixture key, never a
    real one; the environment is `test`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host = X.Pr1Host(self.tmp.name).genesis_host()
        with X.stand_in_wheels() as wheels:
            payloads = X.release_payloads(wheels)
        manifest = X.install_release(self.host.root, X.RELEASE_SHA, payloads)
        self.manifest_sha = sha(I.canonical(manifest))
        self.first = X.current_document(self.host)
        self.credentials = Path(self.tmp.name + "-credentials")
        self.credentials.mkdir()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.credentials, ignore_errors=True))

    def tearDown(self):
        self.tmp.cleanup()

    def owner(self, **inputs):
        return X.verifier_inputs(self.host, manifest_sha256=self.manifest_sha, first_current=self.first, **inputs)

    def credential(self, key_id=None):
        key = PB.private(key_id or X.P0)
        (self.credentials / V.CREDENTIAL_NAME).write_bytes(
            key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption()))
        return CRED.inspect_owner_actor_credential(str(self.credentials), expected_directory=str(self.credentials))

    def core(self, credential):
        def view():
            return STATE.signer_view(environment=X.ENV, root=self.host.root, owner_uid=X.UID)
        return CORE.DevAuthoritySignerCoreV1(credential, self_view=lambda: STATE.self_view(view(), self.host.ledger))

    def health_over_socket(self, core, *, peer=0):
        left, right = socket.socketpair()
        left.sendall(W.encode_frame(W.HEALTH, {}))
        S.serve_connection(right, core, peer_uid_reader=lambda _c: peer)
        left.settimeout(2)
        data = b""
        try:
            while True:
                chunk = left.recv(W.MAX_FRAME_BYTES + 8)
                if not chunk:
                    break
                data += chunk
        except ConnectionResetError:
            data = b""
        left.close()
        if not data:
            return None
        return json.loads(data[4:])["payload"]

    def pair(self, health, **inputs):
        return V.readiness_pair(self.owner(**inputs), health, root=self.host.root, owner_uid=X.UID, owner_gid=X.GID,
                                run=X.fake_systemctl())

    def test_real_core_health_over_the_owner_socket_is_exactly_h(self):
        credential = self.credential()
        self.assertEqual(credential.state, CRED.CREDENTIAL_PRESENT_UNVERIFIED)
        reply = self.health_over_socket(self.core(credential))
        self.assertEqual(reply["status"], "OK")
        health = reply["health"]
        self.assertEqual(V.health_mismatches(health), [])               # H, apart from the TEST fingerprint
        self.assertEqual(health["publicKeySha256"], X.health_p0()["publicKeySha256"])
        self.assertEqual(health["reasons"], list(V.STRUCTURAL_REASONS))
        self.assertIsNone(self.health_over_socket(self.core(credential), peer=990))   # non-root peers get nothing
        # the HEALTH constants of this verifier are the release's own
        from lilith_authority_dev import profile as PROFILE

        self.assertEqual(V.STRUCTURAL_REASONS, STATE.STRUCTURAL_SELF_VIEW_REASONS)
        self.assertEqual((V.HEALTH_EXACT["profile"], V.HEALTH_EXACT["signingDomain"], V.HEALTH_EXACT["foundation"],
                          V.HEALTH_EXACT["service"], V.HEALTH_EXACT["signing"], V.HEALTH_EXACT["readiness"]),
                         (PROFILE.PROFILE, PROFILE.SIGNING_DOMAIN, CORE.FOUNDATION, CORE.SERVICE_AVAILABLE,
                          CORE.SIGNING_NOT_AVAILABLE, CORE.NOT_READY))
        self.assertEqual((V.CREDENTIAL_NAME, V.SIGNER_CREDENTIALS, V.SIGNER_OWNER_SOCKET, V.LEDGER_STATE_DIR),
                         (PROFILE.CREDENTIAL_NAME, PROFILE.CREDENTIALS_DIRECTORY, PROFILE.OWNER_SOCKET_PATH,
                          PROFILE.STATE_DIR))
        self.assertEqual(V.KACT_KEY_ID, PROFILE.PROPOSED_K_ACT_KEY_ID)
        # HEALTH cannot see the hold store: identical with and without HELD
        self.assertIn("HOLD_STORE_UNOBSERVABLE_BY_SIGNER", health["reasons"])

    def test_e_and_f_with_the_real_health_and_the_real_root_verifier(self):
        health = self.health_over_socket(self.core(self.credential()))["health"]
        pair = self.pair(health)
        self.assertEqual(V.readiness_mismatches(pair), [])
        self.assertEqual(pair["eligibility"]["status"], "READY")
        self.assertEqual(pair["eligibility"]["loadedKeyBinding"]["status"], "PASS")
        self.assertEqual(pair["full"]["reasons"], list(V.EXPECTED_FULL_REASONS))
        self.assertEqual(pair["full"]["holdDetail"], V.FULL_HOLD_DETAIL)
        for mode in ("eligibility", "full"):
            self.assertTrue(all(value is False for value in pair[mode]["facts"].values()), pair[mode]["facts"])
            self.assertTrue(all(value is False for value in pair[mode]["packageFlags"].values()))
        # the PR-1 package is recorded, never judged at M-B11: PR-2 / PR-3 absent is not an M-B11 failure
        failing = {reason.split(":", 1)[0] for reason in pair["eligibility"]["packageReasons"]}
        self.assertEqual(failing, {"E18_OFFHOST_REPRODUCTION_INPUTS", "E20_SNAPSHOT_INVENTORY", "E21_OFFHOST_REGISTER"})

    def test_a_stopped_signer_misses_only_the_binding_input(self):
        pair = self.pair(None)
        self.assertEqual(pair["eligibility"]["reasons"], ["LOADED_KEY_BINDING:BINDING_INPUT_MISSING"])
        self.assertEqual(pair["eligibility"]["loadedKeyBinding"]["detail"], "B4_HEALTH")
        self.assertEqual(pair["full"]["reasons"], ["LOADED_KEY_BINDING:BINDING_INPUT_MISSING",
                                                   *V.EXPECTED_FULL_REASONS])

    def test_a_wrong_loaded_key_is_a_binding_mismatch_and_a_key_halt(self):
        health = self.health_over_socket(self.core(self.credential(PB.S2)))["health"]
        pair = self.pair(health)
        self.assertEqual(pair["eligibility"]["loadedKeyBinding"]["reason"], "HEALTH_FINGERPRINT_MISMATCH")
        obs = running(readiness=pair, health={**running()["health"], "health": {**health,
                                                                               "publicKeySha256": V.B3_PUBLIC_KEY_SHA256}})
        self.assertEqual(phase(obs), V.W11_KEY)

    def test_after_the_canonical_release_full_readiness_is_outside_m_b11_and_halts_the_darkness_check(self):
        health = self.health_over_socket(self.core(self.credential()))["health"]
        approved = RV.evaluate(SR.HOLD_RELEASE_ELIGIBILITY, RV.parse_verifier_inputs(self.owner(with_pr2=True,
                                                                                               with_pr3=True)),
                               root=self.host.root, owner_uid=X.UID, owner_gid=X.GID, health=lambda: dict(health),
                               run=X.fake_systemctl())
        self.assertEqual(approved.status, "READY", approved.reasons)
        owner = RV.parse_verifier_inputs(self.owner(with_pr2=True, with_pr3=True))
        self.host.holds.release_initial(
            approved_package_digest=approved.package_digest,
            rerun=lambda held: RV.evaluate(SR.HOLD_RELEASE_ELIGIBILITY, owner, root=self.host.root, owner_uid=X.UID,
                                           owner_gid=X.GID, health=lambda: dict(health), run=X.fake_systemctl(),
                                           hold=held),
            witness_store=self.host.witness_store(), context=self.host.context())
        pair = self.pair(health, with_pr2=True, with_pr3=True)
        self.assertEqual(pair["eligibility"]["reasons"], ["CEREMONY_HOLD:HOLD_NOT_HELD"])
        self.assertEqual((pair["full"]["status"], pair["full"]["reasons"]), ("READY", []))
        self.assertIs(pair["full"]["facts"]["issuanceReady"], True)     # a fact name only: issuance stays unwired
        self.assertEqual(health["signing"], "SIGNING_NOT_AVAILABLE")
        self.assertEqual(phase(running(readiness=pair)), V.W11_DARK)     # never an M-B11 success

    def test_health_reads_leave_the_ledger_bytes_and_a_crashed_reader_leaves_residue(self):
        core = self.core(self.credential())
        before = V.observe_ledger_bytes(self.host.root)
        logical = self.host.ledger_observation()
        self.assertEqual(set(before["listing"]), {V.LEDGER_NAME})
        for _ in range(25):
            self.assertEqual(self.health_over_socket(core)["status"], "OK")
        after = V.observe_ledger_bytes(self.host.root)
        self.assertEqual(after, before)                                  # bytes and listing unchanged
        self.assertEqual(self.host.ledger_observation(), logical)
        path = self.host.path(V.LEDGER_STATE_DIR) / V.LEDGER_NAME
        reader = subprocess.Popen([sys.executable, "-I", "-c",
                                   "import sqlite3,sys,time;c=sqlite3.connect('file:'+sys.argv[1]+'?mode=rw',uri=True,"
                                   "isolation_level=None);c.execute('SELECT seq FROM authority_journal_v1').fetchall();"
                                   "print('open',flush=True);time.sleep(60)", str(path)], stdout=subprocess.PIPE,
                                  text=True)
        try:
            self.assertEqual(reader.stdout.readline().strip(), "open")
        finally:
            reader.kill()
            reader.wait()
            reader.stdout.close()
        residue = V.observe_ledger_bytes(self.host.root)
        self.assertEqual(residue["listing"].get(V.WAL_NAME), 0)
        self.assertIn(V.SHM_NAME, residue["listing"])
        self.assertEqual(residue["dbSha256"], before["dbSha256"])
        obs = running(ledger=residue, baseline={**running()["baseline"], "dbSha256": before["dbSha256"]})
        self.assertEqual(phase(obs), V.W11_RESIDUE)
        self.assertEqual(self.health_over_socket(core)["status"], "OK")  # one clean read closes the residue
        self.assertEqual(V.observe_ledger_bytes(self.host.root), before)
        self.assertEqual(self.host.ledger_observation(), logical)

    def test_recovery_operations_are_refused_under_the_real_initial_custody_held_with_no_ledger_write(self):
        calls = []

        def view():
            return STATE.signer_view(environment=X.ENV, root=self.host.root, owner_uid=X.UID)
        handler = REC.RecoveryHandlerV1(view=view, open_ledger=self.host.ledger,
                                        record_ledger_advance=lambda *a: calls.append(a) or {"status": "OK"},
                                        profile=X.CUSTODY_PROFILE)
        snapshot = dict(self.host.holds.observe().snapshot)
        before = V.observe_ledger_bytes(self.host.root)
        for operation in sorted(W.RECOVERY_OPERATIONS):
            with self.subTest(operation=operation):
                result = handler.handle(operation, {"holdStore": snapshot, "epochAuthorization": {}}
                                        if operation == W.RECOVERY_ADVANCE_EPOCH else {"holdStore": snapshot})
                self.assertEqual(result["status"], "REFUSED", result)
        self.assertEqual(calls, [])
        self.assertEqual(V.observe_ledger_bytes(self.host.root), before)


# ------------------------------------------------- synthetic host (the unchanged W10 / W9, root) ---

if HAVE_CRYPTO and POSIX:
    import test_b1b3e_mb10_held_package as T10H
    _HostBase = T10H.HeldHostTests
else:  # pragma: no cover
    _HostBase = unittest.TestCase


@unittest.skipUnless(HAVE_CRYPTO and POSIX and hasattr(sqlite3.Connection, "deserialize"),
                     "POSIX owner/mode semantics, sqlite3 deserialize, cryptography/rfc8785/fido2 required")
class SignerHostTests(_HostBase):
    """The UNCHANGED W9 / W10 verifiers over the M-B10 synthetic root (REAL hold writer, committed synthetic witness
    genesis), with the signer side simulated (unit facts, the credentials directory, a bound owner socket) and judged
    by the W11 verifier. No signer process runs and no credential exists."""

    def signer_running(self, running_now: bool) -> None:
        credentials = self.target(V.SIGNER_CREDENTIALS)
        sock_path = self.target(V.SIGNER_OWNER_SOCKET)
        if running_now:
            credentials.mkdir(parents=True, exist_ok=True)
            (credentials / V.CREDENTIAL_NAME).write_bytes(b"TEST_ONLY placeholder (never a key)")
            sock_path.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(sock_path.parent, 0o700)
            self._bound = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._bound.bind(str(sock_path))
            os.chmod(sock_path, 0o600)
            for name, sub in ((V.SIGNER_SERVICE, "running"), (V.SIGNER_SOCKET_UNIT, "listening")):
                self.unit_overrides[name] = {"ActiveState": "active", "SubState": sub,
                                             "MainPID": "4242" if name == V.SIGNER_SERVICE else "0",
                                             "InvocationID": INVOCATION if name == V.SIGNER_SERVICE else ""}
        else:
            __import__("shutil").rmtree(credentials, ignore_errors=True)
            if getattr(self, "_bound", None) is not None:
                self._bound.close()
                self._bound = None
            if sock_path.exists():
                sock_path.unlink()
            for name in V.SIGNER_UNITS:
                self.unit_overrides.pop(name, None)

    def seams(self):
        return dict(signer=self.signer_ids, witness=self.witness_ids, pins=self.pins, trust_pins=self.trust_pins)

    def w11(self, *, loads, first_load_recorded, health=True):
        evidence = {"expectedHead": self.head, "candidateDigest": self.digest, "updatedAt": self.updated_at,
                    "baseline": dict(self.baseline), "firstLoadRecorded": first_load_recorded,
                    "signerIds": list(self.signer_ids), "ownerInputs": {"placeholder": True},
                    "healthCapture": ({"health": good_health(), "before": {"InvocationID": INVOCATION,
                                                                           "MainPID": "4242"},
                                       "after": {"InvocationID": INVOCATION, "MainPID": "4242"}} if health else None)}
        journal = {"readable": True, "invocations": [{"id": INVOCATION, "credentials": V.LOADED}][:loads]}
        with mock.patch.object(T10H.P9.socket, "socket", T10H.P9._no_socket), \
                mock.patch.object(T10H.P9.socket, "create_connection", T10H.P9._no_socket):
            return V.evaluate(evidence, root=self.root, owner_uid=T10H.UID, owner_gid=T10H.GID, units=self.view,
                              journal=lambda _cursor: journal,
                              process=lambda _root, pid: ({"cwd": V.RELEASE_CWD, "argv": list(V.EXEC_ARGV),
                                                           "uid": self.signer_ids[0], "gid": self.signer_ids[1]}
                                                          if pid == "4242" else None),
                              readiness=lambda *_a, **_k: good_readiness(),
                              restart_boundary=lambda _root, _units: {"reasons": []}, **self.seams())

    def test_w11_0_then_running_then_stopped_after_the_first_load(self):
        self.committed()
        self.write_held()
        self.assertEqual(self.w10()["phase"], T10H.V.W10_1)
        ledger = V.observe_ledger_bytes(self.root)
        self.baseline = {"dbSha256": ledger["dbSha256"], "witnessInvocationId": self.invocation,
                         "witnessMainPid": "777"}
        pre = self.w11(loads=0, first_load_recorded=False, health=False)
        self.assertEqual(pre["phase"], V.W11_0, pre["reasons"])
        self.signer_running(True)
        self.addCleanup(self.signer_running, False)
        self.assertEqual(self.w10()["phase"], T10H.V.W10_LATER)          # the unchanged W10 judgement
        started = self.w11(loads=1, first_load_recorded=True)
        self.assertEqual(started["phase"], V.W11_1, started["reasons"])
        self.assertEqual((started["w10PhaseDirect"], started["w10PhaseSignerJudgedSeparately"]),
                         (T10H.V.W10_LATER, T10H.V.W10_1))
        self.assertTrue(started["observation"]["w10"]["maskExact"])
        self.assertEqual(started["observation"]["paths"]["ownerSocket"]["kind"], "socket")
        self.signer_running(False)
        self.assertEqual(self.w10()["phase"], T10H.V.W10_1)              # W10 alone cannot see the load
        after = self.w11(loads=1, first_load_recorded=True, health=False)
        self.assertEqual(after["phase"], V.W11_1S, after["reasons"])
        self.assertNotEqual(self.w11(loads=0, first_load_recorded=True, health=False)["phase"], V.W11_0)

    def test_hold_tampering_halts_through_the_signer_masked_w10(self):
        self.committed()
        self.write_held()
        ledger = V.observe_ledger_bytes(self.root)
        self.baseline = {"dbSha256": ledger["dbSha256"], "witnessInvocationId": self.invocation,
                         "witnessMainPid": "777"}
        self.signer_running(True)
        self.addCleanup(self.signer_running, False)
        path = self.target(T10H.V.HOLD_STORE) / T10H.V.expected_held(self.digest)["name"]
        path.write_bytes(T10H.V.pinned_expected_held("1" * 64)["bytes"])
        self.assertEqual(self.w11(loads=1, first_load_recorded=True)["phase"], V.W11_HOLD)


for _name in [n for n in dir(_HostBase) if n.startswith("test") and _HostBase is not unittest.TestCase]:
    if _name not in SignerHostTests.__dict__:
        setattr(SignerHostTests, _name, None)                          # run only the M-B11 host tests here
del _HostBase                                                          # never collect the M-B10 class twice


if __name__ == "__main__":
    unittest.main()
