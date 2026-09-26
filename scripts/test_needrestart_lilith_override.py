"""Regressions for the LILITH needrestart service-specific restart exclusion."""

from __future__ import annotations

import hashlib
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import probe_needrestart_lilith_override as probe
from scripts import verify_broker_dev_current_incarnation as baseline

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / probe.ARTIFACT
RAW = ARTIFACT.read_bytes()
TEXT = RAW.decode("ascii")
CODE = [line for line in TEXT.splitlines() if line.strip() and not line.lstrip().startswith("#")]
EXPECTED_CODE = [
    r"$nrconf{override_rc}{qr(^lilith-memory-broker\.service$)} = 0;",
    r"$nrconf{override_rc}{qr(^lilith-authority-dev\.service$)} = 0;",
    r"$nrconf{override_rc}{qr(^lilith-recovery-witness\.service$)} = 0;",
]
PERL = shutil.which("perl")

# A reduced stand-in for needrestart 3.6-7ubuntu4.5's needrestart.conf, as
# read on lilith-dev-01 on 2026-09-26: the same default-hash assignment form,
# a commented restart mode, and the same conf.d loader (path substituted).
FIXTURE_MAIN = r"""
#$nrconf{restart} = 'i';
$nrconf{blacklist} = [
    qr(^/usr/bin/sudo(\.dpkg-new)?$),
];
$nrconf{override_rc} = {
    qr(^dbus) => 0,
    qr(^network) => 0,
    qr(^docker) => 0,
    qr(^apt-daily-upgrade\.service$) => 0,
    qr(^unattended-upgrades\.service$) => 0,
    qr(^systemd-logind) => 0,
};
$nrconf{override_cont} = {
};
if(-d q(@CONFD@)) {
      foreach my $fn (sort <@CONFD@/*.conf>) {
	      print STDERR "$LOGPREF eval $fn\n" if($nrconf{verbosity} > 1);
	      eval do { local(@ARGV, $/) = $fn; <>};
	      die "Error parsing $fn: $@" if($@);
      }
}
"""


def python_patterns() -> list[re.Pattern]:
    return [re.compile(re.search(r"qr\((.*)\)\}", line).group(1)) for line in CODE]


class ArtifactContent(unittest.TestCase):
    def test_pinned_hash_and_deterministic_encoding(self) -> None:
        self.assertEqual(hashlib.sha256(RAW).hexdigest(), probe.ARTIFACT_SHA256)
        self.assertNotIn(b"\r", RAW)
        self.assertTrue(RAW.endswith(b"\n") and not RAW.endswith(b"\n\n"))
        self.assertTrue(all(0x20 <= byte < 0x7F or byte in (0x0A, 0x09) for byte in RAW))

    def test_only_three_additive_override_statements(self) -> None:
        self.assertEqual(CODE, EXPECTED_CODE)

    def test_each_authority_sensitive_unit_is_covered_exactly(self) -> None:
        patterns = python_patterns()
        for unit in probe.EXCLUDED_UNITS:
            self.assertEqual(sum(bool(p.search(unit)) for p in patterns), 1, unit)

    def test_unrelated_units_are_not_excluded(self) -> None:
        patterns = python_patterns()
        for unit in (*probe.DEFAULT_UNITS, "xlilith-memory-broker.service",
                     "lilith-memory-broker.service.bak", "lilith-authority-dev@1.service",
                     "lilith-recovery-witness.timer", "lilith.service", ""):
            self.assertFalse(any(p.search(unit) for p in patterns), unit)

    def test_no_global_restart_or_upgrade_change(self) -> None:
        code = "\n".join(CODE)
        for forbidden in ("{restart}", "blacklist", "{ui}", "defno", "override_cont",
                          "override_rc} =", "override_rc}=", "NEEDRESTART", "Unattended",
                          "APT::", "Periodic", "=> 1", "= 1;"):
            self.assertNotIn(forbidden, code)

    def test_install_target_is_needrestart_conf_d_not_apt(self) -> None:
        self.assertEqual(probe.INSTALL_PATH, "/etc/needrestart/conf.d/lilith-authority-sensitive.conf")
        self.assertTrue(probe.INSTALL_PATH.endswith(".conf"))
        self.assertNotIn("apt.conf.d", TEXT)
        self.assertIn(probe.INSTALL_PATH, TEXT)

    def test_cannot_be_confused_with_authority(self) -> None:
        code = "\n".join(CODE)
        for forbidden in ("system", "exec", "`", "open", "do ", "require", "use ", "eval",
                          "sudo", "systemctl", "key", "cred", "token", "secret", "grant",
                          "/etc", "/var", "/run", "/opt", "$ENV", "unlink", "chmod"):
            self.assertNotIn(forbidden, code)
        self.assertIn("grants no authority", TEXT)

    def test_existing_baseline_observer_recognises_all_three(self) -> None:
        parsed = baseline.parse_needrestart([TEXT])
        self.assertEqual(parsed["restartMode"], "DEFAULT")
        self.assertEqual(parsed["serviceSpecificExclusion"],
                         {name: True for name in baseline.AUTHORITY_SENSITIVE_SERVICES})


class ProbeLogic(unittest.TestCase):
    def pass_parsed(self) -> dict:
        units = {unit: [(f"(?^:^{re.escape(unit)}$)", "0")] for unit in probe.EXCLUDED_UNITS}
        units.update({unit: [] for unit in probe.DEFAULT_UNITS})
        return {"units": units, "global": {"restart": "DEFAULT", "blacklist_rc": "0", "override_rc": "9"}}

    def test_pass(self) -> None:
        self.assertEqual(probe.evaluate(self.pass_parsed())["NEEDRESTART_LILITH_OVERRIDE"], "PASS")

    def test_missing_default_and_ambiguous_fail_closed(self) -> None:
        for mutate, code in (
            (lambda p: p["units"].pop("lilith-memory-broker.service"), "NOT_EXCLUDED:lilith-memory-broker.service"),
            (lambda p: p["units"].__setitem__("lilith-authority-dev.service", []), "NOT_EXCLUDED:lilith-authority-dev.service"),
            (lambda p: p["units"]["lilith-recovery-witness.service"].append(("(?^:^lilith)", "1")),
             "NOT_EXCLUDED:lilith-recovery-witness.service"),
            (lambda p: p["units"].__setitem__("polkit.service", [("(?^:lilith|polkit)", "0")]), "UNEXPECTED_SCOPE:polkit.service"),
            (lambda p: p["global"].__setitem__("blacklist_rc", "1"), "BLACKLIST_RC_PRESENT"),
        ):
            parsed = self.pass_parsed()
            mutate(parsed)
            result = probe.evaluate(parsed)
            self.assertEqual(result["NEEDRESTART_LILITH_OVERRIDE"], "FAIL")
            self.assertIn(code, result["failures"])

    def test_only_subprocess_is_fixed_perl_program(self) -> None:
        argv = probe.probe_argv(probe.PERL, probe.MAIN_CONF)
        self.assertEqual(argv[:3], ["/usr/bin/perl", "-e", probe.PERL_PROGRAM])
        self.assertEqual(argv[3], "/etc/needrestart/needrestart.conf")
        source = Path(probe.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count("subprocess.run("), 1)
        for forbidden in ("systemctl", "needrestart -", "os.remove", "unlink", "write_", "rename", "chmod"):
            self.assertNotIn(forbidden, source)

    def test_refuses_wrong_host_and_command(self) -> None:
        with mock.patch.object(probe.socket, "gethostname", return_value="lilith-01"):
            with self.assertRaisesRegex(probe.ProbeError, "WRONG_HOST_REFUSED"):
                probe.main(["probe"])
        with self.assertRaisesRegex(probe.ProbeError, "FIXED_PROBE_COMMAND_ONLY"):
            probe.main(["install"])


@unittest.skipUnless(PERL, "perl is required for needrestart semantics")
class PerlSemantics(unittest.TestCase):
    """Evaluate the artifact with real Perl through needrestart's own loader form."""

    def run_fixture(self, extra: dict[str, str] | None = None, with_artifact: bool = True) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            confd = Path(tmp) / "conf.d"
            confd.mkdir()
            (confd / "README.needrestart").write_text("not parsed\n", encoding="ascii")
            if with_artifact:
                (confd / Path(probe.INSTALL_PATH).name).write_bytes(RAW)
            for name, body in (extra or {}).items():
                (confd / name).write_text(body, encoding="ascii")
            main = Path(tmp) / "needrestart.conf"
            main.write_text(FIXTURE_MAIN.replace("@CONFD@", confd.as_posix()), encoding="ascii", newline="\n")
            return probe.run_probe(main.as_posix(), PERL)

    def test_installed_artifact_excludes_exactly_the_three_units(self) -> None:
        result = self.run_fixture()
        self.assertEqual(result["NEEDRESTART_LILITH_OVERRIDE"], "PASS", result)
        self.assertEqual({u: result["units"][u] for u in probe.EXCLUDED_UNITS},
                         {u: "EXCLUDED" for u in probe.EXCLUDED_UNITS})
        self.assertTrue(all(result["units"][u] == "DEFAULT" for u in probe.DEFAULT_UNITS))
        self.assertEqual(result["restartMode"], "DEFAULT")

    def test_distribution_defaults_are_preserved(self) -> None:
        self.assertEqual(self.run_fixture()["overrideRcEntries"], "9")  # 6 defaults + 3

    def test_without_artifact_units_keep_default_restart(self) -> None:
        result = self.run_fixture(with_artifact=False)
        self.assertEqual(result["NEEDRESTART_LILITH_OVERRIDE"], "FAIL")
        self.assertEqual({u: result["units"][u] for u in probe.EXCLUDED_UNITS},
                         {u: "DEFAULT" for u in probe.EXCLUDED_UNITS})

    def test_conflicting_later_snippet_is_detected(self) -> None:
        result = self.run_fixture({"zz-other.conf": "$nrconf{override_rc}{qr(^lilith)} = 1;\n"})
        self.assertEqual(result["NEEDRESTART_LILITH_OVERRIDE"], "FAIL")
        self.assertEqual(result["units"]["lilith-memory-broker.service"], "AMBIGUOUS_OR_ENABLED")

    def test_parse_error_fails_closed(self) -> None:
        with self.assertRaisesRegex(probe.ProbeError, "CONFIG_PARSE_ERROR|Error parsing"):
            self.run_fixture({"bad.conf": "$nrconf{override_rc}{qr(^x} = ;\n"})


if __name__ == "__main__":
    unittest.main()
