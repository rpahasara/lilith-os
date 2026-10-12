"""15B2b-B1b-3e M-B11 PR-A1: the CANDIDATE signer restart boundary (OD-M11-11, O2-D). Source and fixture tests only.

The behaviour itself is proven (or falsified) by `scripts/probe_signer_restart_boundary.py` on the disposable CI
runner. These tests pin the candidate, the exact effective-configuration judgement, the derivation of the synthetic
probe units from the release units, the probe's safety gate and its fail-closed judgement.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "services/authority-dev"
sys.path.insert(0, str(SERVICE / "ceremony"))
sys.path.insert(0, str(SERVICE))

import release_file_set as RFS  # noqa: E402
import signer_restart_boundary as B  # noqa: E402

_spec = importlib.util.spec_from_file_location("probe_signer_restart_boundary",
                                               ROOT / "scripts/probe_signer_restart_boundary.py")
PROBE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PROBE)

UNIT = (SERVICE / "deploy/lilith-authority-dev.service").read_text(encoding="utf-8")
SOCKET = (SERVICE / "deploy/lilith-authority-dev.socket").read_text(encoding="utf-8")
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")


def good_show(unit):
    path = f"/etc/systemd/system/{unit}.d/{B.DROPINS[unit][0]}"
    show = {"DropInPaths": path, "UnitFileState": "static", "LoadState": "loaded", "NeedDaemonReload": "no",
            **B.EXPECTED_PROPERTIES[unit]}
    return show, {path: B.candidate_bytes(unit)}


class CandidateTests(unittest.TestCase):
    def test_the_candidate_drop_ins_are_pinned_and_carry_exactly_the_proposed_directives(self):
        self.assertEqual([(s, k, v) for s, k, v in B.parse_unit(B.candidate_bytes(B.SERVICE_UNIT).decode())],
                         [("Service", "Restart", "no")])
        self.assertEqual([(s, k, v) for s, k, v in B.parse_unit(B.candidate_bytes(B.SOCKET_UNIT).decode())],
                         [("Unit", "StopWhenUnneeded", "yes"), ("Unit", "RefuseManualStart", "yes")])
        for unit in (B.SERVICE_UNIT, B.SOCKET_UNIT):
            data = B.candidate_bytes(unit)
            self.assertNotIn(b"\r", data)
            self.assertTrue(data.endswith(b"\n"))
            self.assertIn(b"NOT accepted, NOT installed anywhere", data)
        self.assertEqual(sorted(p.relative_to(B.DROPIN_ROOT).as_posix() for p in B.DROPIN_ROOT.rglob("*") if p.is_file()),
                         ["lilith-authority-dev.service.d/10-no-implicit-restart.conf",
                          "lilith-authority-dev.socket.d/10-no-reactivation.conf"])

    def test_the_release_and_its_units_are_unchanged(self):
        self.assertIn("Restart=on-failure", UNIT.splitlines())                 # the candidate is not applied here
        self.assertNotIn("StopWhenUnneeded", SOCKET)
        self.assertNotIn("RefuseManualStart", SOCKET)
        self.assertNotIn("dropins", "".join(RFS.DEPLOY_ASSETS))
        source = (SERVICE / "release_file_set.py").read_text(encoding="utf-8")
        self.assertNotIn("dropins", source)
        self.assertNotIn("signer_restart_boundary", source)


class EffectiveCheckTests(unittest.TestCase):
    def test_only_exactly_the_candidate_passes(self):
        for unit in (B.SERVICE_UNIT, B.SOCKET_UNIT):
            show, data = good_show(unit)
            self.assertEqual(B.check_effective(unit, show, data), [], unit)

    def test_foreign_missing_altered_or_inexact_configuration_is_refused(self):
        unit = B.SERVICE_UNIT
        show, data = good_show(unit)
        foreign = "/etc/systemd/system/lilith-authority-dev.service.d/20-foreign.conf"
        cases = {
            "foreign drop-in": ({**show, "DropInPaths": show["DropInPaths"] + " " + foreign},
                                {**data, foreign: b"[Service]\nRestart=always\n"}, "DROPIN_SET_NOT_EXACT"),
            "type-level drop-in": ({**show, "DropInPaths": "/usr/lib/systemd/system/service.d/x.conf "
                                    + show["DropInPaths"]}, data, "DROPIN_SET_NOT_EXACT"),
            "missing candidate": ({**show, "DropInPaths": ""}, {}, "DROPIN_SET_NOT_EXACT"),
            "renamed candidate": ({**show, "DropInPaths": show["DropInPaths"].replace("10-", "11-")}, {},
                                  "DROPIN_SET_NOT_EXACT"),
            "duplicate path": ({**show, "DropInPaths": show["DropInPaths"] + " " + show["DropInPaths"]}, data,
                               "DROPIN_SET_NOT_EXACT"),
            "altered bytes": (show, {show["DropInPaths"]: b"[Service]\nRestart=no\n"},
                              "CANDIDATE_DROPIN_BYTES_NOT_PINNED"),
            "unread bytes": (show, {}, "CANDIDATE_DROPIN_UNREAD"),
            "restart always": ({**show, "Restart": "always"}, data, "EFFECTIVE_RESTART_NOT_NO"),
            "enabled": ({**show, "UnitFileState": "enabled"}, data, "UNIT_ENABLEABLE_OR_ENABLED"),
            "reload pending": ({**show, "NeedDaemonReload": "yes"}, data, "UNIT_NOT_LOADED_CURRENT"),
        }
        for label, (s, d, reason) in cases.items():
            with self.subTest(label=label):
                self.assertIn(reason, B.check_effective(unit, s, d))
        sock_show, sock_data = good_show(B.SOCKET_UNIT)
        for key, reason in (("StopWhenUnneeded", "EFFECTIVE_STOPWHENUNNEEDED_NOT_YES"),
                            ("RefuseManualStart", "EFFECTIVE_REFUSEMANUALSTART_NOT_YES")):
            self.assertIn(reason, B.check_effective(B.SOCKET_UNIT, {**sock_show, key: "no"}, sock_data))

    def test_a_recorded_preexisting_set_is_the_only_tolerance_and_never_covers_the_units_own_directory(self):
        unit = B.SERVICE_UNIT
        show, data = good_show(unit)
        vendor = "/usr/lib/systemd/system/service.d/10-timeout-abort.conf"
        with_vendor = {**show, "DropInPaths": vendor + " " + show["DropInPaths"]}
        self.assertEqual(B.check_effective(unit, with_vendor, {**data, vendor: b"x"}, preexisting=[vendor]), [])
        own = "/etc/systemd/system/lilith-authority-dev.service.d/05-earlier.conf"
        self.assertIn("PREEXISTING_SET_CONTAINS_UNIT_DROPIN",
                      B.check_effective(unit, {**show, "DropInPaths": own + " " + show["DropInPaths"]}, data,
                                        preexisting=[own]))

    def test_the_probe_name_is_judged_exactly_like_the_real_name(self):
        probe = "lilith-mb11rb-probe.service"
        path = f"/etc/systemd/system/{probe}.d/{B.DROPINS[B.SERVICE_UNIT][0]}"
        show = {"DropInPaths": path, "Restart": "no", "UnitFileState": "static", "LoadState": "loaded",
                "NeedDaemonReload": "no"}
        self.assertEqual(B.check_effective(B.SERVICE_UNIT, show, {path: B.candidate_bytes(B.SERVICE_UNIT)},
                                           probe_unit=probe), [])


class ProbeUnitDerivationTests(unittest.TestCase):
    def setUp(self):
        self.service, self.socket, self.report = B.derive_probe_units(UNIT, SOCKET, PROBE.NAME, PROBE.USER)

    def test_every_release_directive_is_classified_and_lifecycle_directives_are_verbatim(self):
        real = {k: v for _s, k, v in B.parse_unit(UNIT)}
        probe = {k: v for _s, k, v in B.parse_unit(self.service)}
        for key in ("StartLimitIntervalSec", "StartLimitBurst", "Type", "Restart", "RestartSec", "TimeoutStartSec",
                    "TimeoutStopSec", "UMask", "NoNewPrivileges", "ProtectSystem", "RestrictAddressFamilies"):
            self.assertEqual(probe[key], real[key], key)
        self.assertEqual(probe["Requires"], "lilith-mb11rb-probe.socket")
        self.assertEqual(probe["LoadCredentialEncrypted"].split(":", 1)[0], real["LoadCredentialEncrypted"].split(":", 1)[0])
        real_socket = {k: v for _s, k, v in B.parse_unit(SOCKET)}
        probe_socket = {k: v for _s, k, v in B.parse_unit(self.socket)}
        for key in ("Accept", "SocketMode", "DirectoryMode", "FlushPending", "RemoveOnStop", "Backlog",
                    "TriggerLimitIntervalSec", "TriggerLimitBurst", "SocketUser", "SocketGroup"):
            self.assertEqual(probe_socket[key], real_socket[key], key)
        self.assertEqual(sorted(k for k, _v in self.report["serviceDropped"]),
                         ["Environment", "Environment", "Environment", "InaccessiblePaths", "ReadOnlyPaths",
                          "ReadWritePaths"])
        with self.assertRaises(ValueError):
            B.derive_probe_units(UNIT + "OnFailure=x.service\n", SOCKET, PROBE.NAME, PROBE.USER)

    def test_probe_units_never_name_a_lilith_unit_path_or_credential(self):
        for text in (self.service, self.socket):
            for forbidden in ("lilith-authority-dev", "/etc/credstore", "/opt/lilith", "/var/lib/lilith-authority",
                              "lilith-recovery-witness", "lilith-memory-broker"):
                self.assertNotIn(forbidden, text)
        self.assertNotIn("[Install]", self.service + self.socket)


class ProbeSafetyTests(unittest.TestCase):
    def gate(self, argv=("run", "--disposable-runner"), *, euid=0, present=(), comm="systemd", machine="a" * 32,
             host="runnervm"):
        files = {"/proc/1/comm": comm + "\n", "/etc/machine-id": machine + "\n"}
        PROBE.require_disposable_runner(list(argv), euid=lambda: euid, exists=lambda p: p in present,
                                        read=lambda p: files[p], hostname=lambda: host)

    def test_the_probe_refuses_anything_but_a_disposable_runner(self):
        self.gate()
        refusals = {
            "NOT_DECLARED_DISPOSABLE": dict(argv=("run",)),
            "NOT_ROOT": dict(euid=1000),
            "PID1_NOT_SYSTEMD": dict(comm="init"),
            "DEV_HOST": dict(machine=PROBE.DEV_MACHINE_ID),
            "LILITH_PATH_PRESENT": dict(present=("/opt/lilith-authority-dev",)),
            "PROBE_STATE_ALREADY_PRESENT": dict(present=("/etc/systemd/system/lilith-mb11rb-probe.service",)),
        }
        for reason, kwargs in refusals.items():
            with self.subTest(reason=reason):
                with self.assertRaises(PROBE.Refused) as caught:
                    self.gate(**kwargs)
                self.assertTrue(str(caught.exception).startswith(reason))
        with self.assertRaises(PROBE.Refused):
            self.gate(host="lilith-dev-01.c.project.internal")

    def test_the_probe_never_names_a_lilith_unit_to_systemctl(self):
        with self.assertRaises(PROBE.Refused):
            PROBE.ctl("start", "lilith-authority-dev.service")
        with self.assertRaises(PROBE.Refused):
            PROBE.ctl("stop", "lilith-recovery-witness.service")
        self.assertNotEqual(PROBE.NAME, "lilith-authority-dev")
        self.assertTrue(PROBE.SERVICE.startswith("lilith-mb11rb-probe"))
        tree = ast.parse((ROOT / "scripts/probe_signer_restart_boundary.py").read_text(encoding="utf-8"))
        literals = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertFalse({"lilith-authority-dev.service", "lilith-authority-dev.socket"} & literals)
        for refused in ("/opt/lilith-authority-dev", "/var/lib/lilith-authority-custody", "/etc/lilith-recovery-witness"):
            self.assertIn(refused, PROBE.REFUSE_IF_PRESENT)


def passing_observations():
    exec1 = {"serviceExecAttempts": 1, "processInvocations": 1, "credentialDecryptionsObserved": 1,
             "credentialSetupFailures": 0}
    none = {"serviceExecAttempts": 0, "processInvocations": 0, "credentialDecryptionsObserved": 0,
            "credentialSetupFailures": 0}
    stopped = {"service": {"ActiveState": "inactive", "NRestarts": "0"}, "socket": {"ActiveState": "inactive"},
               "socketPathExists": False}
    failed = {"service": {"ActiveState": "failed", "NRestarts": "0"}, "socket": {"ActiveState": "inactive"},
              "socketPathExists": False}
    exact = {unit: {"reasons": []} for unit in (PROBE.SERVICE, PROBE.SOCKET)}
    return {
        "baseline": {
            "socketFirst": {"rc": 0, "socketActive": True, "reply": "PONG", "counts": dict(exec1)},
            "exitFailure": {"counts": {**exec1, "serviceExecAttempts": 3}},
            "afterStop": {"socketActiveAfterStop": "active", "reply": "PONG", "counts": dict(exec1)}},
        "candidate": {
            "effective": copy.deepcopy(exact),
            "socketFirst": {"rc": 1, "facts": stopped, "counts": dict(none), "reply": "ENOENT"},
            "normalStart": {"rc": 0, "up": True, "reply": "PONG", "counts": dict(exec1),
                            "dependencies": {"Requires": PROBE.SOCKET}},
            "crash": {"crashReply": "BYE", "facts": failed, "counts": dict(none),
                      "connectsAfterCrash": {"ENOENT": 900}, "replyAfter": "ENOENT"},
            "exitFailure": {"facts": failed, "counts": dict(exec1), "reply": "ENOENT"},
            "credentialFailure": {"facts": failed, "reply": "ENOENT",
                                  "counts": {**none, "serviceExecAttempts": 1, "credentialSetupFailures": 1}},
            "explicitStop": {"rc": 0, "facts": stopped, "counts": dict(none), "connectsAfterStop": {"ENOENT": 800},
                             "replyAfter": "ENOENT"},
            "reloadStopped": {"facts": stopped, "counts": dict(none)},
            "reloadRunning": {"before": {"InvocationID": "a" * 32, "MainPID": "7"},
                              "after": {"InvocationID": "a" * 32, "MainPID": "7"}, "counts": dict(none)},
            "reexec": {"effective": copy.deepcopy(exact), "counts": dict(none), "socketFirstRc": 1, "facts": stopped,
                       "unitFileStates": {PROBE.SERVICE: "static", PROBE.SOCKET: "static"}},
            "foreign": {"foreignServiceRestartAlways": {PROBE.SERVICE: {"reasons": ["DROPIN_SET_NOT_EXACT"]}},
                        "foreignSocketManualStart": {PROBE.SOCKET: {"reasons": ["DROPIN_SET_NOT_EXACT"]}},
                        "alteredCandidateBytes": {PROBE.SERVICE: {"reasons": ["CANDIDATE_DROPIN_BYTES_NOT_PINNED"]}},
                        "restored": copy.deepcopy(exact)}},
        "cleanup": {"unitsRemoved": True},
    }


class JudgementTests(unittest.TestCase):
    def failing(self, obs):
        return [c["id"] for c in PROBE.judge(obs) if not c["pass"]]

    def test_a_fully_safe_observation_passes(self):
        self.assertEqual(self.failing(passing_observations()), [])

    def test_any_contradiction_fails_closed(self):
        cases = {
            "CRASH_NO_RESTART_NO_REACTIVATION": ("crash", "counts", "serviceExecAttempts", 1),
            "EXIT_FAILURE_NO_AUTOMATIC_RESTART": ("exitFailure", "counts", "serviceExecAttempts", 2),
            "CREDENTIAL_FAILURE_ATTEMPTED_ONCE": ("credentialFailure", "counts", "serviceExecAttempts", 2),
            "SOCKET_FIRST_START_REFUSED": ("socketFirst", "rc", None, 0),
            "EXPLICIT_STOP_LEAVES_NO_ACTIVATION_ROUTE": ("explicitStop", "facts", "socketPathExists", True),
            "DAEMON_RELOAD_STARTS_NOTHING": ("reloadStopped", "counts", "serviceExecAttempts", 1),
        }
        for check_id, (phase, key, sub, value) in cases.items():
            with self.subTest(check=check_id):
                obs = passing_observations()
                if sub is None:
                    obs["candidate"][phase][key] = value
                else:
                    obs["candidate"][phase][key][sub] = value
                self.assertIn(check_id, self.failing(obs))
        obs = passing_observations()
        obs["candidate"]["crash"]["connectsAfterCrash"] = {"ENOENT": 10, "PONG": 1}      # reactivated mid-transition
        self.assertIn("CRASH_NO_RESTART_NO_REACTIVATION", self.failing(obs))
        obs = passing_observations()
        obs["candidate"]["foreign"]["foreignServiceRestartAlways"][PROBE.SERVICE]["reasons"] = []
        self.assertIn("FOREIGN_OR_ALTERED_DROPIN_REFUSED:foreignServiceRestartAlways", self.failing(obs))

    def test_a_non_discriminating_baseline_fails(self):
        obs = passing_observations()
        obs["baseline"]["exitFailure"]["counts"]["serviceExecAttempts"] = 1
        self.assertIn("BASELINE_EXIT_FAILURE_RESTARTS_AUTOMATICALLY", self.failing(obs))

    def test_missing_observations_never_pass(self):
        self.assertTrue(all(not c["pass"] for c in PROBE.judge({})))
        self.assertTrue(PROBE.judge({"error": "RuntimeError: x"}))


class CiWiringTests(unittest.TestCase):
    def test_the_probe_runs_only_inside_the_read_only_source_job_on_the_disposable_runner(self):
        self.assertEqual(CI.count("scripts/probe_signer_restart_boundary.py"), 1)
        job = CI.split("  repository-contracts:\n", 1)[1].split("\n  frontend-quality:\n", 1)[0]
        self.assertIn("scripts/probe_signer_restart_boundary.py run --disposable-runner", job)
        self.assertIn("sudo -n /usr/bin/python3 -I -B scripts/probe_signer_restart_boundary.py", job)
        self.assertIn("runs-on: ubuntu-latest", job)
        for forbidden in ("secrets.", "id-token", "google-github-actions", "gcloud", "systemctl restart"):
            self.assertNotIn(forbidden, CI)
        blocks = re.findall(r"^( *)permissions:\n((?:\1  .*\n)+)", CI, re.MULTILINE)
        self.assertTrue(blocks)
        for _, body in blocks:
            self.assertEqual(body.split(), ["contents:", "read"])
        self.assertIn("needs: [repository-contracts, frontend-quality, backend-quality]", CI)


if __name__ == "__main__":
    unittest.main()
