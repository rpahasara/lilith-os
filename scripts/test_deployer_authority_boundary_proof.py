"""15B2b-B1b-3d DR-5 routine-deployer authority-boundary proof tests.

The decision logic runs against a fake host model: only the script's probe
functions are replaced. Static tests pin the workflow wiring, and a real-probe
smoke run executes the unmodified script on the CI runner, where it must fail
closed. Nothing touches DEV, PROD, or any authority material.
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/deployer_authority_boundary_proof.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/deploy-dev.yml").read_text(encoding="utf-8")
BASH = shutil.which("bash") if sys.platform.startswith("linux") else None
DEPLOYER = "sa_112096412008414111981"
UNITS = ("lilith-authority-dev.service", "lilith-authority-dev.socket")
SHA = "a" * 40

PARENTS = ("/opt", "/etc", "/etc/systemd/system", "/etc/tmpfiles.d", "/usr/local/sbin", "/var/lib/systemd",
           "/etc/needrestart/conf.d", "/usr/local/lib/lilith-dev-deploy")
ROOT_FILES = ("/etc/passwd", "/etc/group", "/usr/local/lib/lilith-dev-deploy/effective_sudo_proof.sh",
              "/etc/needrestart/conf.d/lilith-authority-sensitive.conf")
LADDER = {
    "L1a": {},
    "L1b.1": {"/opt/lilith-authority-dev": "directory|0|0|755", "/opt/lilith-authority-dev/releases": "directory|0|0|755",
              f"/opt/lilith-authority-dev/releases/{SHA}": "directory|0|0|755"},
    "L1b.2": {"/opt/lilith-authority-dev/current": "symbolic link|0|0|777"},
    "L1c.1": {"/etc/systemd/system/lilith-authority-dev.service": "regular file|0|0|644",
              "/etc/systemd/system/lilith-authority-dev.socket": "regular file|0|0|644",
              "/etc/tmpfiles.d/lilith-authority-dev.conf": "regular file|0|0|644"},
    "L1c.3": {"/usr/local/sbin/lilith-authority-keygen-dev": "regular file|0|0|755"},
    "L2a": {"/var/lib/systemd/credential.secret": "regular file|0|0|400"},
    "L2b.1": {"/etc/credstore.encrypted": "directory|0|0|700"},
}
ORDER = list(LADDER)

HARNESS = r'''
AB_LIBRARY_ONLY=1 . "$1"
F="$2"
ab_whoami() { cat "$F/whoami"; }
ab_uid() { cat "$F/uid"; }
ab_groups() { cat "$F/groups"; }
ab_stat() { awk -F'\t' -v p="$1" '$1==p{print $2; exit}' "$F/stat"; }
ab_readlink() { awk -F'\t' -v p="$1" '$1==p{print $2; exit}' "$F/links"; }
ab_can() { grep -qxF -- "$1 $2" "$F/can"; }
ab_list_dir() { awk -F'\t' -v p="$1" '$1==p{print $2}' "$F/ls"; }
ab_local_user() { grep -qxF -- "$1" "$F/users"; }
ab_sudo_query() {
  local c="$*"
  echo "$c" >> "$F/sudo_calls"
  if grep -qxF -- "$c" "$F/sudo_allow"; then echo "$c"; return 0; fi
  if grep -qxF -- "$c" "$F/sudo_unknown"; then echo "sudo: unknown user: x"; return 1; fi
  echo "Sorry, user $(cat "$F/whoami") is not allowed to execute '$c'"; return 1
}
ab_have_pkcheck() { test -e "$F/pkcheck"; }
ab_pkcheck() { grep -qxF -- "$1" "$F/pkcheck" && return 0; return "$(cat "$F/pkcheck_rc")"; }
ab_main
'''


def host(step: str = "PRE_L1A") -> dict:
    """A healthy DEV host at ladder `step`, as the routine deployer sees it."""
    stat = {path: "directory|0|0|755" for path in PARENTS}
    stat.update({path: "regular file|0|0|644" for path in ROOT_FILES})
    stat["/usr/bin/systemctl"] = "regular file|0|0|755"
    spec = {"whoami": DEPLOYER, "uid": "3826947836", "groups": DEPLOYER, "stat": stat,
            "links": {}, "can": set(), "ls": {}, "users": {"lilith", "lilith-memory-broker"},
            "sudo_allow": set(), "sudo_unknown": set(), "pkcheck": None, "pkcheck_rc": 2}
    if step != "PRE_L1A":
        for name in ORDER[:ORDER.index(step) + 1]:
            stat.update(LADDER[name])
        spec["users"].add("lilith-authority-dev")
    if "/opt/lilith-authority-dev/releases" in stat:
        spec["ls"]["/opt/lilith-authority-dev/releases"] = [SHA]
    if "/opt/lilith-authority-dev/current" in stat:
        spec["links"]["/opt/lilith-authority-dev/current"] = f"releases/{SHA}"
    return spec


@unittest.skipUnless(BASH, "needs Linux bash")
class ProofLogicTests(unittest.TestCase):
    def run_proof(self, spec: dict) -> tuple[int, str, list[str]]:
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            (d / "whoami").write_text(spec["whoami"])
            (d / "uid").write_text(spec["uid"])
            (d / "groups").write_text(spec["groups"])
            (d / "stat").write_text("".join(f"{p}\t{m}\n" for p, m in spec["stat"].items()))
            (d / "links").write_text("".join(f"{p}\t{t}\n" for p, t in spec["links"].items()))
            (d / "ls").write_text("".join(f"{p}\t{e}\n" for p, es in spec["ls"].items() for e in es))
            (d / "can").write_text("".join(f"{c}\n" for c in spec["can"]))
            (d / "users").write_text("".join(f"{u}\n" for u in spec["users"]))
            (d / "sudo_allow").write_text("".join(f"{c}\n" for c in spec["sudo_allow"]))
            (d / "sudo_unknown").write_text("".join(f"{c}\n" for c in spec["sudo_unknown"]))
            (d / "sudo_calls").write_text("")
            (d / "pkcheck_rc").write_text(str(spec["pkcheck_rc"]))
            if spec["pkcheck"] is not None:
                (d / "pkcheck").write_text("".join(f"{a}\n" for a in spec["pkcheck"]))
            result = subprocess.run([BASH, "-c", HARNESS, "harness", str(SCRIPT), str(d)],
                                    capture_output=True, text=True, timeout=60)
            calls = (d / "sudo_calls").read_text().splitlines()
        return result.returncode, result.stdout, calls

    def assertPass(self, spec, maturity):
        rc, out, _ = self.run_proof(spec)
        self.assertEqual(out.splitlines()[-1], f"AUTHORITY_BOUNDARY_PROOF=PASS maturity={maturity}", out)
        self.assertEqual(rc, 0)
        self.assertNotIn("FAIL:", out)
        return out

    def assertFails(self, spec, needle):
        rc, out, _ = self.run_proof(spec)
        self.assertNotEqual(rc, 0, out)
        self.assertTrue(out.splitlines()[-1].startswith("AUTHORITY_BOUNDARY_PROOF=FAIL"), out)
        self.assertIn(needle, out)
        return out

    # 4, 13: normal pre-L1a deployment passes, with real non-vacuous evidence.
    def test_pre_l1a_passes_with_non_vacuous_parent_and_proxy_evidence(self):
        out = self.assertPass(host(), "PRE_L1A")
        for parent in PARENTS:
            self.assertIn(f"DENIED: test -w {parent}", out)
        self.assertIn("DENIED: sudo -u lilith-memory-broker /usr/bin/true", out)
        self.assertIn("DEFERRED_UNTIL_OBJECT_EXISTS: sudo -u lilith-authority-dev", out)
        self.assertIn("DEFERRED_UNTIL_OBJECT_EXISTS: /etc/credstore.encrypted (L2b.1)", out)
        self.assertNotIn("DENIED: test -r /var/lib/systemd/credential.secret", out)  # absent != denied

    # 3: absence never counts as denial.
    def test_missing_parent_is_failure_not_denial(self):
        spec = host()
        del spec["stat"]["/etc/tmpfiles.d"]
        out = self.assertFails(spec, "PARENT_NOT_ROOT_DIRECTORY /etc/tmpfiles.d")
        self.assertNotIn("DENIED: test -w /etc/tmpfiles.d", out)

    def test_writable_parent_is_failure(self):
        spec = host()
        spec["can"].add("-w /usr/local/sbin")
        self.assertFails(spec, "ALLOWED(unexpected) test -w /usr/local/sbin")

    # 5: maturity cannot be satisfied or hidden by deployer/application state.
    def test_forged_ladder_object_is_failure(self):
        spec = host()
        spec["stat"]["/opt/lilith-authority-dev"] = "directory|3826947836|3826947836|755"
        self.assertFails(spec, "LADDER_OBJECT_CONTRACT /opt/lilith-authority-dev")
        spec = host("L1c.1")
        spec["stat"]["/etc/systemd/system/lilith-authority-dev.service"] = "regular file|1001|1002|644"
        self.assertFails(spec, "LADDER_OBJECT_CONTRACT /etc/systemd/system/lilith-authority-dev.service")

    def test_parent_not_root_owned_cannot_host_maturity(self):
        spec = host()
        spec["stat"]["/opt"] = "directory|3826947836|0|755"
        self.assertFails(spec, "PARENT_NOT_ROOT_DIRECTORY /opt")

    def test_account_only_via_nss_does_not_count(self):
        spec = host()  # a non-local (e.g. OS Login) name is not in /etc/passwd
        self.assertPass(spec, "PRE_L1A")

    # 6: an expected leaf missing after maturity is failure.
    def test_missing_leaf_after_maturity_is_failure(self):
        spec = host("L1c.1")
        del spec["stat"]["/opt/lilith-authority-dev/current"]
        del spec["links"]["/opt/lilith-authority-dev/current"]
        self.assertFails(spec, "LADDER_OBJECT_MISSING /opt/lilith-authority-dev/current")
        spec = host("L2b.1")
        spec["users"].discard("lilith-authority-dev")
        self.assertFails(spec, "LADDER_OBJECT_MISSING account lilith-authority-dev")
        spec = host("L1c.1")
        del spec["stat"]["/etc/tmpfiles.d/lilith-authority-dev.conf"]
        self.assertFails(spec, "LADDER_OBJECT_MISSING /etc/tmpfiles.d/lilith-authority-dev.conf")

    def test_unexplained_host_key_forces_ladder_failure(self):
        spec = host()
        spec["stat"]["/var/lib/systemd/credential.secret"] = "regular file|0|0|400"
        self.assertFails(spec, "LADDER_OBJECT_MISSING /opt/lilith-authority-dev")

    # 7: a writable leaf after maturity is failure.
    def test_writable_leaf_after_maturity_is_failure(self):
        for leaf in ("/etc/systemd/system/lilith-authority-dev.socket", "/opt/lilith-authority-dev/releases",
                     f"/opt/lilith-authority-dev/releases/{SHA}", "/usr/local/sbin/lilith-authority-keygen-dev",
                     "/etc/tmpfiles.d/lilith-authority-dev.conf"):
            spec = host("L2b.1")
            spec["can"].add(f"-w {leaf}")
            self.assertFails(spec, f"ALLOWED(unexpected) test -w {leaf}")

    def test_selector_and_release_entries_are_exact(self):
        spec = host("L1b.2")
        spec["links"]["/opt/lilith-authority-dev/current"] = "/tmp/evil"
        self.assertFails(spec, "SELECTOR_TARGET")
        spec = host("L1b.1")
        spec["ls"]["/opt/lilith-authority-dev/releases"].append(".staging")
        self.assertFails(spec, "UNEXPECTED_RELEASE_ENTRY .staging")

    # 8: sudo-as capability is failure; the pre-L1a proxy must be conclusive.
    def test_sudo_as_is_failure(self):
        spec = host()
        spec["sudo_allow"].add("-u lilith-memory-broker /usr/bin/true")
        self.assertFails(spec, "ALLOWED(unexpected) sudo -u lilith-memory-broker")
        spec = host("L1a")
        spec["sudo_allow"].add("-u lilith-authority-dev /usr/bin/true")
        self.assertFails(spec, "ALLOWED(unexpected) sudo -u lilith-authority-dev")
        spec = host("L1a")
        spec["sudo_unknown"].add("-u lilith-authority-dev /usr/bin/true")
        self.assertFails(spec, "SUDO_QUERY_INCONCLUSIVE -u lilith-authority-dev")
        spec = host()
        spec["users"].discard("lilith-memory-broker")
        self.assertFails(spec, "NON_VACUOUS_SUDO_AS_PROXY_MISSING")

    # 9: service control capability is failure (sudo and polkit).
    def test_service_control_is_failure(self):
        for unit in UNITS:
            for verb in ("start", "stop", "restart", "enable", "disable"):
                spec = host()
                spec["sudo_allow"].add(f"/usr/bin/systemctl {verb} {unit}")
                self.assertFails(spec, f"ALLOWED(unexpected) sudo /usr/bin/systemctl {verb} {unit}")
        spec = host()
        spec["pkcheck"] = ["org.freedesktop.systemd1.manage-units"]
        self.assertFails(spec, "ALLOWED(unexpected) polkit org.freedesktop.systemd1.manage-units")

    def test_polkit_is_a_tripwire_never_counted_as_denial(self):
        # A non-grant (challenge rc 2, refusal rc 1, error 127) is never evidence.
        for rc in (1, 2, 3, 127):
            spec = host()
            spec["pkcheck"] = []
            spec["pkcheck_rc"] = rc
            out = self.assertPass(spec, "PRE_L1A")
            self.assertIn(f"DEFERRED_NOT_IN_GATE: polkit org.freedesktop.systemd1.manage-unit-files pkcheck_rc={rc}", out)
            self.assertNotIn("DENIED: polkit", out)
        out = self.assertPass(host(), "PRE_L1A")  # pkcheck unavailable
        self.assertIn("DEFERRED_NOT_IN_GATE: polkit unit control (pkcheck unavailable; not counted)", out)
        self.assertNotIn("NOT_PROVEN", out)
        self.assertNotIn("DENIED: polkit", out)

    def test_every_unit_verb_is_queried_never_run(self):
        _rc, _out, calls = self.run_proof(host())
        for unit in UNITS:
            for verb in ("start", "stop", "restart", "enable", "disable", "mask"):
                self.assertIn(f"/usr/bin/systemctl {verb} {unit}", calls)
        self.assertIn("/usr/bin/systemctl daemon-reload", calls)

    # 10: keygen privileged execution capability is failure.
    def test_keygen_privilege_is_failure(self):
        spec = host("L1c.3")
        spec["sudo_allow"].add("/usr/local/sbin/lilith-authority-keygen-dev actor")
        self.assertFails(spec, "ALLOWED(unexpected) sudo /usr/local/sbin/lilith-authority-keygen-dev actor")
        spec = host("L1c.3")
        spec["sudo_unknown"].add("/usr/local/sbin/lilith-authority-keygen-dev")
        self.assertFails(spec, "SUDO_QUERY_INCONCLUSIVE /usr/local/sbin/lilith-authority-keygen-dev")
        out = self.assertPass(host("L1c.1"), "L1c.1")
        self.assertIn("DEFERRED_UNTIL_OBJECT_EXISTS: sudo /usr/local/sbin/lilith-authority-keygen-dev", out)

    # 11, 12: credstore and host-key access is failure.
    def test_credstore_and_host_key_access_is_failure(self):
        for op in ("-r", "-w", "-x"):
            spec = host("L2b.1")
            spec["can"].add(f"{op} /etc/credstore.encrypted")
            self.assertFails(spec, f"ALLOWED(unexpected) test {op} /etc/credstore.encrypted")
        spec = host("L2a")
        spec["can"].add("-r /var/lib/systemd/credential.secret")
        self.assertFails(spec, "ALLOWED(unexpected) test -r /var/lib/systemd/credential.secret")
        spec = host("L2b.1")
        spec["stat"]["/etc/credstore.encrypted"] = "directory|0|0|755"
        self.assertFails(spec, "LADDER_OBJECT_CONTRACT /etc/credstore.encrypted")

    def test_full_ladder_passes_with_leaf_denials(self):
        out = self.assertPass(host("L2b.1"), "L2b.1")
        for needle in ("DENIED: test -r /etc/credstore.encrypted", "DENIED: test -x /etc/credstore.encrypted",
                       "DENIED: test -r /var/lib/systemd/credential.secret",
                       "DENIED: sudo -u lilith-authority-dev /usr/bin/true",
                       "DENIED: sudo /usr/local/sbin/lilith-authority-keygen-dev actor",
                       f"DENIED: test -w /opt/lilith-authority-dev/releases/{SHA}",
                       "UNOBSERVABLE_BY_DESIGN: /etc/credstore.encrypted/lilith-authority-dev.owner-actor.cred"):
            self.assertIn(needle, out)

    def test_later_authority_state_is_denied_when_present(self):
        spec = host("L2b.1")
        spec["stat"]["/var/lib/lilith-authority-dev"] = "directory|990|980|700"
        out = self.assertPass(spec, "L2b.1")
        self.assertIn("DENIED: test -r /var/lib/lilith-authority-dev", out)
        spec["can"].add("-r /var/lib/lilith-authority-dev")
        self.assertFails(spec, "ALLOWED(unexpected) test -r /var/lib/lilith-authority-dev")

    def test_identity_and_group_checks(self):
        spec = host()
        spec["whoami"] = "lilith"
        self.assertFails(spec, "UNEXPECTED_EFFECTIVE_USER")
        spec = host()
        spec["uid"] = "0"
        self.assertFails(spec, "UNEXPECTED_EFFECTIVE_USER")
        for group in ("sudo", "lxd", "lilith-authority-dev", "lilith-memory-ipc", "adm"):
            spec = host()
            spec["groups"] = f"{DEPLOYER} {group}"
            self.assertFails(spec, f"PRIVILEGED_OR_AUTHORITY_GROUP {group}")


INLINE_QUERY = WORKFLOW[WORKFLOW.index("          query_denied() {"):]
INLINE_QUERY = INLINE_QUERY[:INLINE_QUERY.index("\n          }\n") + len("\n          }\n")]


class InlineDenyListTests(unittest.TestCase):
    """DENIAL PROOF != ATTEMPT THE FORBIDDEN MUTATION (existing B1c deny list)."""

    MUTATING = re.compile(r"\b(systemctl|service)\s+(start|stop|restart|reload|try-restart|reload-or-restart|"
                          r"enable|disable|reenable|mask|unmask|kill|daemon-reload|isolate)\b")

    def test_no_denial_probe_executes_a_mutating_unit_command(self):
        for line in WORKFLOW.splitlines():
            stripped = line.strip()
            if re.match(r"^deny\s", stripped):
                self.assertIsNone(self.MUTATING.search(stripped), stripped)
        self.assertNotIn("deny sudo -n /usr/bin/systemctl", WORKFLOW)
        self.assertIn("          query_denied /usr/bin/systemctl restart lilith-memory-broker.service\n", WORKFLOW)
        self.assertIn("DENIAL PROOF != ATTEMPT THE FORBIDDEN MUTATION", WORKFLOW)
        self.assertEqual(re.findall(r"sudo[^\n]*", INLINE_QUERY), ['sudo -n -l "$@" 2>&1)"; rc=$?'])

    @unittest.skipUnless(BASH, "needs Linux bash")
    def test_inline_query_semantics(self):
        cases = {  # stub sudo behaviour -> expected line, fail flag
            "exit 0": ("ALLOWED(unexpected) query: /usr/bin/systemctl restart lilith-memory-broker.service", "1"),
            'echo "sudo: unknown user: x"; exit 1': ("INCONCLUSIVE query:", "1"),
            'echo "bash: sudo: command not found"; exit 127': ("INCONCLUSIVE query:", "1"),
            'echo "Sorry, user sa_x is not allowed to execute"; exit 1':
                ("DENIED(query): /usr/bin/systemctl restart lilith-memory-broker.service", "0"),
        }
        for body, (expected, failed) in cases.items():
            with tempfile.TemporaryDirectory() as directory:
                stub = Path(directory) / "sudo"
                log = Path(directory) / "argv"
                stub.write_text(f'#!/bin/bash\necho "$*" >> "{log}"\n{body}\n', encoding="utf-8")
                stub.chmod(0o755)
                script = ("fail=0\n" + INLINE_QUERY +
                          "query_denied /usr/bin/systemctl restart lilith-memory-broker.service\necho FAIL=$fail\n")
                result = subprocess.run([BASH, "-c", script], capture_output=True, text=True, timeout=30,
                                        env={"PATH": f"{directory}:/usr/bin:/bin"})
                self.assertIn(expected, result.stdout)
                self.assertIn(f"FAIL={failed}", result.stdout)
                self.assertEqual(log.read_text().split(), ["-n", "-l", "/usr/bin/systemctl", "restart",
                                                           "lilith-memory-broker.service"])


class StaticSafetyTests(unittest.TestCase):
    def code_lines(self):
        lines = []
        for line in SOURCE.splitlines():
            code = re.sub(r"\s+#\s.*$", "", line).strip()  # drop trailing "  # comment"
            if code and not code.startswith("#"):
                lines.append(code)
        return lines

    def test_probes_are_read_only(self):
        sudo_uses = [line for line in self.code_lines() if re.search(r"(^|[;{(]\s*)sudo\b", line)]
        self.assertEqual(sudo_uses, ['ab_sudo_query() { sudo -n -l "$@" 2>&1; }'])
        for line in self.code_lines():
            self.assertIsNone(re.match(r'^("?\$\{AB_(SYSTEMCTL|KEYGEN)\}"?|systemctl|pkexec|runuser|su)\b', line), line)
            for forbidden in ("rm ", "mkdir", "touch ", "chmod", "chown", "mv ", "cp ", "tee ", "install ",
                              "useradd", "systemd-creds", "eval", "curl", "wget"):
                self.assertNotIn(forbidden, line, line)
            for redirect in re.findall(r"(?<![0-9&<])>\s*(\S+)", line):
                self.assertIn(redirect, ("/dev/null", "&1"), line)
        self.assertIn("pkcheck --action-id", SOURCE)
        self.assertIn('if [ "${AB_LIBRARY_ONLY:-}" != 1 ]; then', SOURCE)

    def test_workflow_wiring(self):
        step = WORKFLOW.index("      - name: Prove the routine DEV deployer has no authority-custody reach")
        self.assertLess(WORKFLOW.index("      - name: Prove the routine DEV deployer has no root, broker, or Stage III reach"), step)
        self.assertLess(step, WORKFLOW.index("      - name: Package exact-SHA bundle for the fixed DEV helper"))
        self.assertLess(step, WORKFLOW.index("      - name: Deploy through the fixed root-owned DEV helper"))
        block = WORKFLOW[step:WORKFLOW.index("      - name: Package exact-SHA bundle for the fixed DEV helper")]
        self.assertIn("if: steps.classify.outputs.mode == 'DEPLOY_REQUIRED'", block)
        self.assertIn("proof=candidate/scripts/deployer_authority_boundary_proof.sh", block)
        self.assertIn('--command="bash -s"', block)
        self.assertIn("set -o pipefail", block)
        self.assertIn("AUTHORITY_BOUNDARY_PROOF=PASS maturity=", block)
        self.assertNotIn("sudo", block)
        self.assertNotIn("compute scp", block)
        self.assertNotIn("always()", block)
        self.assertNotIn("continue-on-error", block)

    def test_deployer_capability_is_unchanged(self):
        # 1, 2, 14: no new sudo, exact effective proof, same single fixed helper deploy.
        self.assertEqual(WORKFLOW.count("sudo -n /usr/local/sbin/lilith-dev-deploy deploy ${VALIDATED_SHA}"), 1)
        self.assertIn("lilith_dev_effective_sudo_proof sa_112096412008414111981 self || fail=1", WORKFLOW)
        sudoers = (ROOT / "scripts/dev_deployer/sudoers-lilith-dev-deployer.in").read_text(encoding="utf-8")
        rules = [line for line in sudoers.splitlines() if line and not line.startswith("#")]
        self.assertEqual(rules, ["@DEPLOYER@ ALL=(root) NOPASSWD: /usr/local/sbin/lilith-dev-deploy deploy *, "
                                 "/usr/local/sbin/lilith-dev-deploy status"])
        helper = (ROOT / "scripts/dev_deployer/lilith-dev-deploy").read_text(encoding="utf-8")
        for needle in ("authority", "credstore", "systemd-creds", "keygen"):
            self.assertNotIn(needle, helper)

    def test_no_prod_trigger_or_path(self):
        deploy = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
        filters = re.findall(r'^\s+- "([^"]+)"', deploy.split("paths:", 1)[1].split("permissions:", 1)[0], re.MULTILINE)
        for path in ("scripts/deployer_authority_boundary_proof.sh", "scripts/test_deployer_authority_boundary_proof.py",
                     ".github/workflows/deploy-dev.yml"):
            for pattern in filters:
                self.assertFalse(fnmatch.fnmatch(path, pattern.replace("**", "*")), (path, pattern))
        self.assertNotIn("lilith-01", SOURCE.replace("lilith-dev-01", ""))
        self.assertNotIn("GCP_PROD", SOURCE)


@unittest.skipUnless(BASH, "needs Linux bash")
class RealProbeSmokeTests(unittest.TestCase):
    def test_unmodified_script_fails_closed_off_dev(self):
        # On a CI runner or workstation the effective user is not the DEV deployer,
        # so the real probes must end in FAIL (never a PASS line), without error.
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([BASH, "-s"], input=SOURCE, capture_output=True, text=True, timeout=120,
                                    cwd=directory, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": directory})
            self.assertEqual(os.listdir(directory), [])
        self.assertEqual(result.returncode, 1, result.stderr)
        last = result.stdout.splitlines()[-1]
        self.assertTrue(last.startswith("AUTHORITY_BOUNDARY_PROOF=FAIL"), last)
        self.assertIn("FAIL: UNEXPECTED_EFFECTIVE_USER", result.stdout)
        if os.geteuid() != 0:
            self.assertIn("DENIED: test -w /etc", result.stdout)


if __name__ == "__main__":
    unittest.main()
