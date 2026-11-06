#!/usr/bin/env python3
"""OWNER_PROD PR-1 hold-release eligibility: the release's own 24 checks, with E-8, E-9 and E-19 judged for PROD.

Record: canonical-memory PROD activation, Gate 6.3 feasibility (2026-11-06). Root on `lilith-01` only; read-only
except the one `release-initial` form, which writes exactly what the release's own hold store writes.

    python3 owner_prod_pr1_eligibility.py eligibility <inputs.json>
    python3 owner_prod_pr1_eligibility.py full <inputs.json>
    python3 owner_prod_pr1_eligibility.py release-initial <approvedPackageDigest> <inputs.json>

Why a separate tool. The signed release's PR-1 package (`pr1_acceptance`, a governed release member) was written for
the DEV_SYNTHETIC host, and three of its 24 checks name DEV infrastructure that `lilith-01` does not have:

- E-8 requires a deployer-denial proof scoped to the DEV deployer ladder (`maturity=P1A-9`);
- E-9 requires PASS proofs about the DEV memory broker, which PROD does not run (R3f);
- E-19 binds DEV's B1c deployer boundary (`b1cUnchanged`), which PROD does not have.

Changing the governed module would change the signed release. This tool leaves every release module untouched: it
runs the release's own verifier (`lilith_authority_root.verifier.evaluate`) over the real host, keeps its result for
the other 21 checks exactly, and re-judges ONLY these three by OWNER_PROD rules that are at least as strict:

- E-8: the DEPLOYER_DENIAL proof must PASS with exactly `scope=OWNER_PROD deployerHostLogin=NONE` (the routine
  deployer has no login of any kind on the host; its transcript is the owner's IAM observation);
- E-9: NO broker proof may be supplied (a PASS about a broker that does not exist would be vacuous), and the tool must
  itself observe the broker absent: no unit file, no loaded unit, no account, and every broker path absent or an
  EMPTY root:root 0700 directory (the `InaccessiblePaths=` placeholders the release units require);
- E-19: the owner's line must be exactly `PROD_ACTIVATION_DARK_LINE` with `b1cUnchanged` null, and the tool must
  itself observe canonical memory disabled (exact bytes), no owner-channel grant and no router canonical settings.

One release defect is corrected for OWNER_PROD only: Source Prep B readiness refuses any profile but DEV_SYNTHETIC at
one gate (`successor_readiness.py`, `PROFILE_NOT_DEV_SYNTHETIC`), although the release accepts the OWNER_PROD custody
profile everywhere else. For a `prod` evaluation the release's own function is used, compiled from the release's own
source with exactly that line widened to `SC.is_owner_prod(profile)` (see `owner_prod_readiness_source`).

The package is then rebuilt by the release's own package function, so its digest covers every check, all release
evidence and the three OWNER_PROD observations (`evidence.ownerProd`). `release-initial` uses the release's own hold
store and its own decision rule (`release_decision`: READY, eligibility mode, approved digest == a current re-run).
Nothing here signs, grants authority, wires issuance, or accepts any environment other than `prod`.

    OWNER_PROD rules != weaker rules;  observed absence != claimed absence
"""

from __future__ import annotations

import contextlib
import inspect
import json
import os
import pwd
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] if len(HERE.parents) > 2 else HERE
# In a checkout: the repository packages. On the host: the caller puts the installed release tree
# (/opt/lilith-authority-dev/current, byte-identical to these packages) on sys.path; nothing else is added.
for _path in (ROOT / "services/authority-dev", ROOT / "services/owner-memory-control", ROOT / "services/core-api",
              ROOT / "services/recovery-witness"):
    if _path.is_dir() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from lilith_authority_host import inputs as HI  # noqa: E402
from lilith_authority_host import paths as P  # noqa: E402
from lilith_authority_host.store_observer import observe_witness_state  # noqa: E402
from lilith_authority_root import clients  # noqa: E402
from lilith_authority_root import observers as O  # noqa: E402
from lilith_authority_root import verifier as V  # noqa: E402
from lilith_authority_root.hold_store import HoldStoreError, HoldStoreV1  # noqa: E402
from lilith_owner_memory import pr1_acceptance as PA  # noqa: E402
from lilith_owner_memory import successor_readiness as SR  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402

PROD = "prod"
RULES = "OWNER_PROD_PR1_RULES_V1"
REQUIRED_PROD_DEPLOYER_SCOPE = "scope=OWNER_PROD deployerHostLogin=NONE"
PROD_ACTIVATION_DARK_LINE = "ACTIVATION=NOT_ACCEPTED reason=CANONICAL_DISABLED grant=ABSENT routerSettings=ABSENT"
BROKER_PROOFS = ("BROKER_DENIAL", "BROKER_PRESERVATION")
REJUDGED = ("E08_DEPLOYER_DENIAL", "E09_BROKER_DENIAL_PRESERVATION", "E19_ACTIVATION_DARK")
BROKER_NAME = "lilith-memory-broker"
BROKER_UNITS = (BROKER_NAME + ".service", BROKER_NAME + ".socket")
BROKER_UNIT_DIRS = ("/etc/systemd/system", "/usr/lib/systemd/system", "/lib/systemd/system", "/run/systemd/system")
BROKER_PATHS = ("/etc/lilith-memory-broker", "/var/lib/lilith-memory-broker", "/opt/lilith-memory-broker",
                "/run/lilith-memory-broker")
CANONICAL_CONFIG = "/etc/lilith-first-memory-dev/canonical-config.json"
CANONICAL_DISABLED = b'{"activeCapabilities":[],"canonicalLtmEnabled":false,"schemaVersion":1}'
OWNER_CHANNEL_GRANT = "/etc/lilith-first-memory-dev/hermes-owner-channel.json"
ROUTER_CANONICAL_SETTINGS = "/home/lilith/.hermes/lilith_router/canonical_memory.json"
MAX_INPUT = 256 * 1024


class Refused(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class BrokerAbsenceV1:
    unit_files: tuple[str, ...]
    loaded_units: tuple[str, ...]
    account_present: bool
    occupied_paths: tuple[str, ...]

    @property
    def absent(self) -> bool:
        return not (self.unit_files or self.loaded_units or self.account_present or self.occupied_paths)

    def to_dict(self) -> dict[str, Any]:
        return {"unitFiles": list(self.unit_files), "loadedUnits": list(self.loaded_units),
                "accountPresent": self.account_present, "occupiedPaths": list(self.occupied_paths)}


@dataclass(frozen=True)
class ProdActivationV1:
    canonical_disabled: bool
    grant_absent: bool
    router_settings_absent: bool

    @property
    def dark(self) -> bool:
        return self.canonical_disabled is True and self.grant_absent is True and self.router_settings_absent is True

    def to_dict(self) -> dict[str, Any]:
        return {"canonicalDisabled": self.canonical_disabled, "grantAbsent": self.grant_absent,
                "routerSettingsAbsent": self.router_settings_absent}


def _host(root: Path, absolute: str) -> Path:
    return Path(root) / absolute.lstrip("/")


# ------------------------------------------------------------- observations ---

def observe_broker_absence(root: Path | str = Path("/"), *, run: O.Runner = O.default_runner,
                           passwd: Callable[[str], Any] = pwd.getpwnam, owner_uid: int = 0,
                           owner_gid: int = 0) -> BrokerAbsenceV1:
    """Read-only; never follows a link. `owner_*` are TEST seams (root on the host)."""
    root = Path(root)
    unit_files = tuple(f"{d}/{u}" for d in BROKER_UNIT_DIRS for u in BROKER_UNITS
                       if os.path.lexists(_host(root, f"{d}/{u}")))
    listed = run(["systemctl", "list-units", "--all", "--plain", "--no-legend", BROKER_NAME + "*"])
    out = listed.stdout if isinstance(listed.stdout, str) else (listed.stdout or b"").decode("utf-8", "replace")
    loaded = tuple(sorted({line.split()[0] for line in out.splitlines() if line.strip()})) \
        if listed.returncode == 0 else ("SYSTEMCTL_UNAVAILABLE",)
    try:
        passwd(BROKER_NAME)
        account = True
    except KeyError:
        account = False
    occupied = []
    for absolute in BROKER_PATHS:
        path = _host(root, absolute)
        if not os.path.lexists(path):
            continue
        st = os.lstat(path)
        if not stat.S_ISDIR(st.st_mode) or (st.st_uid, st.st_gid) != (owner_uid, owner_gid) \
                or stat.S_IMODE(st.st_mode) != 0o700:
            occupied.append(absolute)
            continue
        with os.scandir(path) as entries:
            if any(entries):
                occupied.append(absolute)
    return BrokerAbsenceV1(unit_files, loaded, account, tuple(occupied))


def observe_prod_activation(root: Path | str = Path("/")) -> ProdActivationV1:
    """Read-only: canonical memory disabled (exact bytes, not a link), no grant, no router canonical settings."""
    root = Path(root)
    config = _host(root, CANONICAL_CONFIG)
    try:
        disabled = (not config.is_symlink()) and config.read_bytes().rstrip(b"\n") == CANONICAL_DISABLED
    except OSError:
        disabled = False
    return ProdActivationV1(disabled, not os.path.lexists(_host(root, OWNER_CHANNEL_GRANT)),
                            not os.path.lexists(_host(root, ROUTER_CANONICAL_SETTINGS)))


# -------------------------------------------------------------------- rules ---

def deployer_reason(proofs: Mapping[str, PA.ExternalProofV1]) -> str | None:
    return PA._proof_reason(proofs, "DEPLOYER_DENIAL", detail=REQUIRED_PROD_DEPLOYER_SCOPE)


def broker_reason(proofs: Mapping[str, PA.ExternalProofV1], observed: BrokerAbsenceV1 | None) -> str | None:
    supplied = [name for name in BROKER_PROOFS if isinstance(proofs, Mapping) and name in proofs]
    if supplied:
        return "BROKER_PROOF_FOR_ABSENT_BROKER:" + ",".join(supplied)
    if not isinstance(observed, BrokerAbsenceV1):
        return "BROKER_ABSENCE_UNOBSERVED"
    return None if observed.absent else "BROKER_PRESENT"


def activation_reason(activation: PA.ActivationObservationV1 | None, observed: ProdActivationV1 | None) -> str | None:
    if not isinstance(activation, PA.ActivationObservationV1):
        return "ACTIVATION_UNOBSERVED"
    if type(activation.line) is not str or activation.line != PROD_ACTIVATION_DARK_LINE \
            or activation.b1c_unchanged is not None:
        return "ACTIVATION_NOT_DARK"
    if not isinstance(observed, ProdActivationV1):
        return "ACTIVATION_DARK_UNOBSERVED"
    return None if observed.dark else "ACTIVATION_NOT_DARK_ON_HOST"


def rejudge(base: PA.Pr1AcceptanceResultV1, *, proofs: Mapping[str, PA.ExternalProofV1],
            activation: PA.ActivationObservationV1 | None, broker: BrokerAbsenceV1 | None,
            dark: ProdActivationV1 | None) -> PA.Pr1AcceptanceResultV1:
    """The release result with E-8 / E-9 / E-19 replaced by the OWNER_PROD judgement; every other check, all the
    release evidence and the readiness result are kept exactly. Rebuilt by the release's own package function."""
    checks = dict(base.checks)
    for name, reason in zip(REJUDGED, (deployer_reason(proofs), broker_reason(proofs, broker),
                                       activation_reason(activation, dark))):
        checks[name] = WR.CheckOutcomeV1(PA.PASS) if reason is None else WR.CheckOutcomeV1(PA.FAIL, reason)
    evidence = dict(base.package["evidence"])
    evidence["ownerProd"] = {"rules": RULES, "rejudged": list(REJUDGED),
                             "releaseJudgement": {n: list(base.package["checks"][n]) for n in REJUDGED},
                             "deployerScope": REQUIRED_PROD_DEPLOYER_SCOPE,
                             "brokerAbsence": None if broker is None else broker.to_dict(),
                             "activation": None if dark is None else dark.to_dict()}
    return PA._package(base.mode, base.package["environment"], checks, evidence, base.readiness)


# ------------------------------------------------- readiness: the one DEV-only gate ---
# The release's Source Prep B readiness (`successor_readiness.evaluate_successor_readiness`) refuses every profile but
# DEV_SYNTHETIC at one gate, although the same release accepts the OWNER_PROD custody profile everywhere else
# (`successor_custody.require_dev_synthetic`, issuance, the hold store, the PUBLICATION_BYTES profile rule). For
# OWNER_PROD this tool uses the release's own function compiled from the release's own source with exactly that one
# line widened to `SC.is_owner_prod(profile)`; everything else, including the environment equalities on the same
# line, is the release's. A release whose source does not contain the exact line is refused, never guessed.
READINESS_GATE = ("    if not SC.is_dev_synthetic(profile) or base_inputs.environment != profile.environment \\\n")
READINESS_GATE_OWNER_PROD = ("    if not (SC.is_dev_synthetic(profile) or SC.is_owner_prod(profile)) "
                             "or base_inputs.environment != profile.environment \\\n")


def owner_prod_readiness_source() -> tuple[str, str]:
    """(release source, OWNER_PROD source) of `evaluate_successor_readiness`; they differ in exactly one line."""
    source = inspect.getsource(SR.evaluate_successor_readiness)
    if source.count(READINESS_GATE) != 1:
        raise Refused("RELEASE_READINESS_GATE_NOT_FOUND")
    return source, source.replace(READINESS_GATE, READINESS_GATE_OWNER_PROD)


def owner_prod_readiness() -> Callable[..., Any]:
    _release, widened = owner_prod_readiness_source()
    namespace = dict(vars(SR))                       # the release module's own globals (a copy; SR is not changed)
    exec(compile(widened, inspect.getsourcefile(SR) or "successor_readiness.py", "exec"), namespace)  # noqa: S102
    return namespace["evaluate_successor_readiness"]


@contextlib.contextmanager
def _owner_prod_readiness_in_force():
    """For the duration of ONE OWNER_PROD evaluation in this process only; restored even on error."""
    release = SR.evaluate_successor_readiness
    SR.evaluate_successor_readiness = owner_prod_readiness()
    try:
        yield
    finally:
        SR.evaluate_successor_readiness = release


def evaluate(mode: str, owner: V.VerifierInputsV1, *, root: Path | str = Path("/"), owner_uid: int = 0,
             owner_gid: int = 0, health: Callable[[], Mapping[str, Any]] = clients.signer_health,
             run: O.Runner = O.default_runner, hold: Any = None,
             passwd: Callable[[str], Any] = pwd.getpwnam) -> PA.Pr1AcceptanceResultV1:
    if owner.environment != PROD:
        raise Refused("ENVIRONMENT_NOT_OWNER_PROD")
    with _owner_prod_readiness_in_force():
        base = V.evaluate(mode, owner, root=root, owner_uid=owner_uid, owner_gid=owner_gid, health=health, run=run,
                          hold=hold)
    return rejudge(base, proofs=owner.proofs, activation=owner.activation,
                   broker=observe_broker_absence(root, run=run, passwd=passwd, owner_uid=owner_uid,
                                                 owner_gid=owner_gid),
                   dark=observe_prod_activation(root))


# ---------------------------------------------------------------------- CLI ---

def _document(path: str) -> Any:
    with open(path, "rb") as handle:
        raw = handle.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise Refused("INPUT_TOO_LARGE")
    return json.loads(raw.decode("utf-8"))


def main(argv: list[str], *, euid: int | None = None) -> int:
    euid = os.geteuid() if euid is None else euid
    try:
        if euid != 0:
            raise Refused("NOT_ROOT")
        if HI.read_deployment()[0] != PROD:
            raise Refused("DEPLOYMENT_NOT_OWNER_PROD")
        if argv[:1] in (["eligibility"], ["full"]) and len(argv) == 2:
            mode = SR.HOLD_RELEASE_ELIGIBILITY if argv[0] == "eligibility" else SR.FULL_READINESS
            result = evaluate(mode, V.parse_verifier_inputs(_document(argv[1])))
            print(json.dumps(V.report(result), sort_keys=True, separators=(",", ":")))
            return 0
        if argv[:1] == ["release-initial"] and len(argv) == 3:
            approved = argv[1]
            owner = V.parse_verifier_inputs(_document(argv[2]))
            inputs = HI.read_host_inputs(environment=PROD)
            if inputs.registry_root is None or inputs.witness_anchor is None:
                raise Refused("HOST_INPUTS_INCOMPLETE")
            context = inputs.store_context(authority_public_keys=HI.authority_public_keys(inputs))
            record = HoldStoreV1(environment=PROD).release_initial(
                approved_package_digest=approved,
                rerun=lambda held: evaluate(SR.HOLD_RELEASE_ELIGIBILITY, owner, hold=held),
                witness_store=observe_witness_state(P.WITNESS_STATE), context=context)
            print(json.dumps({"record": record, "authorityGranted": False}, sort_keys=True, separators=(",", ":")))
            return 0
        raise Refused("USAGE")
    except Refused as exc:
        print(f"owner_prod_pr1_eligibility: REFUSED {exc.reason}", file=sys.stderr)
        return 2
    except HoldStoreError as exc:
        print(f"owner_prod_pr1_eligibility: REFUSED {exc.reason}:{getattr(exc, 'detail', None)}", file=sys.stderr)
        return 2
    except (V.VerifierInputError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"owner_prod_pr1_eligibility: REFUSED {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
