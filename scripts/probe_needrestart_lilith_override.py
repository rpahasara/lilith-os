#!/usr/bin/env python3
"""Read-only probe: does the loaded needrestart config exclude LILITH units?

Record: docs/architecture/slice15b2b-b1b3d-current-runtime-baseline.md.

It loads ``needrestart.conf`` the way needrestart 3.6 does (a Perl ``eval``,
which itself evals ``conf.d/*.conf`` in sort order), then reports, for each
unit, every ``override_rc`` regex that matches it. needrestart takes the first
match in hash order, so a unit is only reported EXCLUDED when exactly one
regex matches and its value is 0. Nothing is restarted, scanned, or written.
The only subprocess is ``/usr/bin/perl`` running the fixed program below.

Stream protected-main source to ``sudo python3 -I -B - probe`` on
lilith-dev-01 only, as part of the owner runbook. Root is needed only because
the runbook runs it beside other root reads; the probe itself reads only
world-readable needrestart configuration.
"""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
from pathlib import Path

DEV_INSTANCE = "lilith-dev-01"
PERL = "/usr/bin/perl"
MAIN_CONF = "/etc/needrestart/needrestart.conf"
INSTALL_PATH = "/etc/needrestart/conf.d/lilith-authority-sensitive.conf"
ARTIFACT = "services/memory-broker/deploy/needrestart-lilith-authority-sensitive.conf"
ARTIFACT_SHA256 = "503279315ccc884d8a68505c86b51dfd09387b393c9becba684b1fa1c28068d2"

EXCLUDED_UNITS = (
    "lilith-memory-broker.service",
    "lilith-authority-dev.service",
    "lilith-recovery-witness.service",
)
# Units that must keep the distribution default (restart after upgrades).
DEFAULT_UNITS = (
    "lilith-os-api-dev.service",
    "lilith-os-api.service",
    "polkit.service",
    "ssh.service",
    "cron.service",
    "lilith-memory-broker.socket",
    "lilith-memory-broker-extra.service",
)

# Mirrors needrestart's own loader: package %nrconf, then a string eval of
# the main file. Prints one tab-separated line per unit: unit, match count,
# then regex=value pairs. The last line reports global restart settings.
PERL_PROGRAM = r"""
no strict; no warnings;
our %nrconf = (verbosity => 1, override_rc => {}, blacklist_rc => []);
our $LOGPREF = '[probe]';
my ($conf, @units) = @ARGV;
my $src = do { local(@ARGV, $/) = $conf; <> };
defined $src or die "CONFIG_UNREADABLE\n";
eval $src;
die "CONFIG_PARSE_ERROR:$@" if $@;
for my $u (@units) {
    my @m = grep { $u =~ /$_/ } sort keys %{$nrconf{override_rc}};
    print join("\t", 'UNIT', $u, scalar(@m), map { $_ . '=' . $nrconf{override_rc}{$_} } @m), "\n";
}
print join("\t", 'GLOBAL',
    'restart=' . (defined $nrconf{restart} ? $nrconf{restart} : 'DEFAULT'),
    'blacklist_rc=' . scalar(@{$nrconf{blacklist_rc} || []}),
    'override_rc=' . scalar(keys %{$nrconf{override_rc}})), "\n";
"""


class ProbeError(RuntimeError):
    pass


def probe_argv(perl: str, conf: str) -> list[str]:
    return [perl, "-e", PERL_PROGRAM, conf, *EXCLUDED_UNITS, *DEFAULT_UNITS]


def parse(output: str) -> dict:
    units: dict[str, list[tuple[str, str]]] = {}
    globals_: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split("\t")
        if fields[0] == "UNIT":
            count = int(fields[2])
            pairs = [tuple(item.rsplit("=", 1)) for item in fields[3:]]
            if len(pairs) != count:
                raise ProbeError("PROBE_OUTPUT_FORMAT")
            units[fields[1]] = pairs
        elif fields[0] == "GLOBAL":
            globals_ = dict(item.split("=", 1) for item in fields[1:])
    return {"units": units, "global": globals_}


def evaluate(parsed: dict) -> dict:
    """Pure: probe output -> verdict. Missing units fail closed."""
    units = parsed.get("units", {})
    failures: list[str] = []
    states: dict[str, str] = {}
    for unit in EXCLUDED_UNITS:
        matches = units.get(unit)
        if matches is None:
            states[unit] = "MISSING"
        elif len(matches) == 1 and matches[0][1] == "0":
            states[unit] = "EXCLUDED"
        elif not matches:
            states[unit] = "DEFAULT"
        else:
            states[unit] = "AMBIGUOUS_OR_ENABLED"
        if states[unit] != "EXCLUDED":
            failures.append("NOT_EXCLUDED:" + unit)
    for unit in DEFAULT_UNITS:
        matches = units.get(unit)
        lilith = [pair for pair in (matches or []) if "lilith" in pair[0]]
        states[unit] = "MISSING" if matches is None else ("DEFAULT" if not lilith else "LILITH_MATCH")
        if states[unit] != "DEFAULT":
            failures.append("UNEXPECTED_SCOPE:" + unit)
    glob = parsed.get("global", {})
    if glob.get("blacklist_rc") != "0":
        failures.append("BLACKLIST_RC_PRESENT")
    return {
        "operation": "READ_ONLY_PROBE",
        "NEEDRESTART_LILITH_OVERRIDE": "PASS" if not failures else "FAIL",
        "failures": failures,
        "units": states,
        "restartMode": glob.get("restart"),
        "overrideRcEntries": glob.get("override_rc"),
    }


def run_probe(conf: str, perl: str = PERL) -> dict:
    completed = subprocess.run(probe_argv(perl, conf), check=False, text=True,
                               capture_output=True, timeout=30)
    if completed.returncode != 0:
        raise ProbeError(completed.stderr.strip() or "PERL_FAILED")
    return evaluate(parse(completed.stdout))


def artifact_sha256(text: bytes) -> str:
    return hashlib.sha256(text).hexdigest()


def installed_state(path: str = INSTALL_PATH) -> dict:
    target = Path(path)
    if not target.exists():
        return {"present": False}
    meta = target.lstat()
    return {"present": True, "sha256": artifact_sha256(target.read_bytes()),
            "uid": meta.st_uid, "gid": meta.st_gid, "mode": oct(meta.st_mode & 0o7777),
            "matchesArtifact": artifact_sha256(target.read_bytes()) == ARTIFACT_SHA256}


def main(argv: list[str]) -> int:
    if argv != ["probe"]:
        raise ProbeError("FIXED_PROBE_COMMAND_ONLY")
    if socket.gethostname() != DEV_INSTANCE:
        raise ProbeError("WRONG_HOST_REFUSED")
    result = run_probe(MAIN_CONF)
    result["installedFile"] = installed_state()
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["NEEDRESTART_LILITH_OVERRIDE"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (ProbeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"NEEDRESTART_PROBE_FAILED:{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
