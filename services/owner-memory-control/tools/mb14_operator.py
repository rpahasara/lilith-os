#!/usr/bin/env python3
"""15B2b-B1b-3e M-B14 (WRITE_RELEASED, `release-initial`): the reviewed owner-laptop operator.

Record: docs/architecture/slice-15b2b-b1b3e-mb14-release-initial-package.md.
DESIGN / SOURCE ONLY: no form below is authorized by this repository. The live `release` needs a fresh, explicit
owner go (`render GO`), consumed by an `O_EXCL` marker written BEFORE its one remote invocation.

It reuses, unchanged: the E-22 operator (`e22_operator.Operator`: the pinned `gcloud compute ssh` route for a plain
command, the pinned direct-plink stdin route, the go check, the marker, the record helpers, the owner-inputs reader and
the read-only `package` form), the M-B10 expected-HELD derivation (`mb10_held_verifier.pinned_expected_held`) and
the release contract (`successor_custody`, `pr1_acceptance`). The writer is the INSTALLED, reviewed release CLI
`lilith-authority-hold-dev release-initial <approvedPackageDigest> <inputs.json>`; nothing here re-implements it.

| Form | Effect |
| --- | --- |
| `pins <repo>` | local: clean control checkout; every pinned tool exact; this operator at control |
| `prepare <repo> <workdir> <envelope>` | local: a NEW workdir; the accepted envelope, the verifier input document and the independently derived expected HELD / RELEASED records (EXPECTED.json) |
| `pre <repo> <workdir>` | read-only DEV: hold `observe` (= the expected HELD), staging path absent, signer / witness identity, and ONE `e22_operator package` re-run (= the approved digest) |
| `render <repo> <workdir> <GO\\|ACCEPT\\|UNSTAGE>` | local: the exact canonical owner text |
| `release <repo> <workdir> <go>` | **mutation, one go, one marker**: a fresh read-only check, marker `mb14`, ONE remote invocation (stage the input document, `release-initial` once, unstage), then the independent read-back |
| `post <repo> <workdir>` | read-only DEV: the independent read-back (hold `observe`, staging path, identity) judged against EXPECTED.json; the C-19 root-observer classification |
| `unstage <repo> <workdir> <statement>` | **its own owner statement and marker**: removes exactly the staged input document (by digest) and its directory, only when a read-back found it |
| `accept <repo> <workdir> <statement>` | local: the owner's verbatim M-B14 acceptance of a RELEASED read-back |

The RELEASED record REPLACES the HELD record in place: one record per ceremony, the same name
(`sha256(ceremonyId).json`), `HELD -> RELEASED` (`hold_store.HoldStoreV1._publish`, `successor_custody.
hold_store_transition_reason`: no record may disappear, RELEASED never returns to HELD). The HELD bytes are retained
OFF-HOST only: the M-B10 evidence and this workdir (EXPECTED.json and the `pre` observation).

    re-run digest = approved digest != owner acceptance;  RELEASED = the hold check only != issuance != activation
    RELEASED != Registry V1 effective != FULL_READINESS (M-B15) != First Memory;  UNKNOWN != success

It never opens, loads or copies a key, never starts, stops, enables or reloads a unit, runs the hold CLI's
`release-initial` only inside `release`, once, and removes nothing but the staged input document (`release`, after
the CLI returns; `unstage`, once per owner statement).
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import e22_operator as E22  # noqa: E402  (pinned E-22 operator; reused unchanged)
import mb10_held_verifier as H10  # noqa: E402  (pinned M-B10 expected-HELD derivation)

M6, M9, M10 = E22.M6, E22.M9, E22.M10
Stop = E22.Stop
_need = E22._need
sha256_hex = E22.sha256_hex

OPERATOR = E22.T + "mb14_operator.py"
TOOL_PINS = {
    **E22.TOOL_PINS,
    E22.OPERATOR: "7a04d4567ea6d8ea5d4f9074ba4d61d51beeb17cd61c366edfcaddfa8ba3452b",
}

# The owner-accepted M-B12 / M-B13 binding (record slice-15b2b-b1b3e-mb12-completion-mb13-preparation.md).
APPROVED_PACKAGE_DIGEST = "eab79d56e58f0d7ce88217c43acdba1d31dec30743d79245dca6a893b49a1a86"
ENVELOPE_SHA256 = "3128a0a857cae8a0121c2febf97f2e6e0e9a3f0e92f9fa6bec843dba13c875fb"
GENESIS = H10.ACCEPTED_GENESIS
HELD_LISTING_DIGEST = "ee7aaa61c2e52d1aa8bb2c2a5c086e1d85a4b432df20cbb78a60f88495df6a82"   # M-B12 package evidence
SIGNER = ("efbc078492634b0280565d8990dab3d3", "128648")                                     # accepted E-22 V6
# Derived (stdlib and release contract, `expected_released`) and pinned for review; the derivation must reproduce it.
EXPECTED_RELEASED_SHA256 = "bb7576f4437fb61dd31adafe50ac56eba467c7f98b329b7149942e630f1ef003"
EXPECTED_RELEASED_LISTING = "c4cb131983b450d1e931d1121e5b125a98c2dc1625934db0ff0a5f3f661e195c"

HOLD_CLI = M10.HOLD_CLI
OBSERVE_COMMAND = M10.HOLD_OBSERVE_COMMAND
STAGE_DIR = "/run/lilith-mb14-release-initial"
STAGE_FILE = STAGE_DIR + "/inputs.json"
MAX_INPUT = 256 * 1024                                  # lilith_authority_root.cli.MAX_INPUT
# Both answers are printed by the ROOT shell only: a failed `sudo` prints neither and is UNKNOWN, never absent.
STAGE_COMMAND = (f"sudo -n /usr/bin/sh -c 'if /usr/bin/test -e {STAGE_DIR}; then echo STAGE=present; else echo STAGE=absent; fi'")
UNITS_COMMAND = ("systemctl show -p Id,ActiveState,SubState,MainPID,NRestarts,InvocationID "
                 f"{E22.SIGNER_SERVICE} {E22.WITNESS_SERVICE} --no-pager")
MARKER, UNSTAGE_MARKER = "mb14", "mb14-unstage"
PREPARED, PRE_DIR, RELEASE_DIR, POST_DIR = "PREPARED.json", "pre", "release", "post"
EXPECTED_FILE, ENVELOPE_FILE, INPUTS_FILE = "EXPECTED.json", "envelope.out", "inputs.json"
ACCEPT_FILE, ATTEMPT_FILE = "MB14_ACCEPTANCE.json", "ATTEMPT.json"

# Read-back classes (the C-19 root observer decides; ambiguous = STOP).
RELEASED_EXACT, HELD_UNCHANGED = "RELEASED_EXACT", "HELD_UNCHANGED"
UNEXPECTED, UNOBSERVABLE = "HOLD_SET_UNEXPECTED", "HOLD_STORE_UNOBSERVABLE"
READBACK_EXACT = "MB14_READBACK_RELEASED_EXACT"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

PONR = ("I understand that INITIAL_CUSTODY RELEASED is forward only: it replaces the HELD record of the same ceremony "
        "in place, never returns to HELD, and no automatic retry is authorized after the attempt marker.")
GO_LINES = (
    "I authorize M-B14 / WRITE_RELEASED (release-initial) for DEV_SYNTHETIC now, for exactly one attempt.",
    "Control commit: {control}. Operator: " + OPERATOR + " SHA-256 {operator}.",
    "Approved package digest: " + APPROVED_PACKAGE_DIGEST + ". Envelope SHA-256: " + ENVELOPE_SHA256 + ".",
    "Pre-check SHA-256: {pre}; re-run package digest {rerun} (equal to the approved digest).",
    "Input document SHA-256 {inputs} ({length} bytes), staged at " + STAGE_FILE + " (root 0600 in a new 0700 "
    "directory) only for this invocation and removed after it.",
    "Command: sudo -n " + HOLD_CLI + " release-initial " + APPROVED_PACKAGE_DIGEST + " " + STAGE_FILE +
    ", exactly one invocation.",
    "Pre-state: HELD record {name}, SHA-256 {held}; hold listing {held_listing}; signer {sinv} / {spid}.",
    "Expected RELEASED record: {name}, SHA-256 {released}, bound to witness genesis " + GENESIS +
    "; hold listing {released_listing}.",
    PONR,
    "RELEASED passes the hold check only. This go does not authorize FULL_READINESS (M-B15), authority activation, "
    "Registry V1 effectiveness, First Memory or PROD.",
    "Any REFUSED, FAILED, traceback, timeout, SSH loss, unexpected output or other STOP after the attempt marker "
    "consumes this go. The read-back decides; there is no automatic retry.",
)
ACCEPT_LINES = (
    "I accept M-B14 / WRITE_RELEASED for DEV_SYNTHETIC: INITIAL_CUSTODY RELEASED is COMPLETED.",
    "RELEASED record: {name}, SHA-256 {released}, bound to witness genesis " + GENESIS + ". Read-back SHA-256: "
    "{readback}. Approved and re-run package digest: " + APPROVED_PACKAGE_DIGEST + ".",
    "The HELD record SHA-256 {held} is retained off-host only. authorityGranted remains false.",
    "This acceptance authorizes nothing further: not FULL_READINESS (M-B15), authority activation, Registry V1 "
    "effectiveness, First Memory or PROD.",
)
ADOPTION_LINE = ("I adopt this RELEASED record although the writer's response was not received exactly: the "
                 "independent read-back is exact.")
UNSTAGE_LINES = (
    "I authorize removing the staged M-B14 input document now, for exactly one invocation.",
    "Path: " + STAGE_FILE + " and its directory " + STAGE_DIR + "; SHA-256 {inputs}. Read-back SHA-256: {readback}.",
    "This removes nothing else, writes no hold record and is not a retry of M-B14.",
)


# ---------------------------------------------------------------- derivation ---

def _canonical(value: Any) -> bytes:
    """Sorted compact ASCII JSON: for these ASCII-only records exactly the RFC 8785 form (the tests prove it)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def listing_digest(entries: Sequence[tuple[str, bytes]]) -> str:
    """`pr1_acceptance.hold_listing_digest`, stdlib: SHA-256 of the JCS list `[[name, sha256(bytes)], ...]`."""
    return sha256_hex(_canonical([[name, sha256_hex(data)] for name, data in sorted(entries)]))


def pinned_expected_released(genesis: str = GENESIS) -> dict[str, Any]:
    """The ONE RELEASED record `release_initial` writes over the pinned HELD, stdlib only: the same fields, the state
    RELEASED, the reason OWNER_RELEASE_AFTER_ELIGIBILITY and the witness head (= the genesis: chain length 1)."""
    held = H10.pinned_expected_held(genesis)
    _need(held["name"] == H10.EXPECTED_HELD_NAME and held["sha256"] == H10.EXPECTED_HELD_SHA256, "HELD_PIN_MISMATCH")
    record = dict(held["record"], state="RELEASED", reason="OWNER_RELEASE_AFTER_ELIGIBILITY",
                  observedWitnessDigest=genesis)
    data = _canonical(record)
    return {"record": record, "bytes": data, "name": held["name"], "sha256": sha256_hex(data), "length": len(data),
            "ceremonyId": held["ceremonyId"], "held": held}


def expected_released(genesis: str = GENESIS) -> dict[str, Any]:
    """The same record by the release contract, required equal to the stdlib form, and the HELD -> RELEASED step
    required permitted by the writer's own transition rule. Any difference is a STOP before anything is rendered."""
    from lilith_owner_memory import pr1_acceptance as PA
    from lilith_owner_memory import successor_custody as SC

    pinned = pinned_expected_released(genesis)
    profile = SC.custody_profile(H10.ENVIRONMENT)
    ceremony = SC.initial_ceremony_id(H10.ENVIRONMENT, profile.initial_key_id)
    held = SC.CeremonyHoldV1(H10.ENVIRONMENT, ceremony, SC.INITIAL_CUSTODY, SC.HELD, SC.INITIAL_CUSTODY_BOOTSTRAP,
                             None, profile.initial_key_id, genesis).to_dict()
    released = SC.CeremonyHoldV1(H10.ENVIRONMENT, ceremony, SC.INITIAL_CUSTODY, SC.RELEASED,
                                 SC.OWNER_RELEASE_AFTER_ELIGIBILITY, None, profile.initial_key_id, genesis).to_dict()
    _need(SC.hold_record_bytes(held) == pinned["held"]["bytes"], "HELD_CONTRACT_MISMATCH")
    _need(SC.hold_record_bytes(released) == pinned["bytes"], "RELEASED_CONTRACT_MISMATCH")
    _need(SC.hold_record_name(ceremony) == pinned["name"], "RECORD_NAME_MISMATCH")
    before, after = SC.hold_store(held), SC.hold_store(released)
    _need(SC.hold_store_transition_reason(before, after, profile=profile) is None, "TRANSITION_NOT_PERMITTED")
    _need(PA.hold_listing_digest(before) == listing_digest([(pinned["name"], pinned["held"]["bytes"])])
          == HELD_LISTING_DIGEST, "HELD_LISTING_MISMATCH")
    _need(PA.hold_listing_digest(after) == listing_digest([(pinned["name"], pinned["bytes"])])
          == EXPECTED_RELEASED_LISTING, "RELEASED_LISTING_MISMATCH")
    _need(pinned["sha256"] == EXPECTED_RELEASED_SHA256, "RELEASED_PIN_MISMATCH")
    return pinned


def expected_document(genesis: str = GENESIS) -> dict[str, Any]:
    """EXPECTED.json: everything the go and the read-back judge, derived before execution."""
    e = expected_released(genesis)
    held = e["held"]
    return {"expectedType": "LILITH_MB14_EXPECTED", "schemaVersion": 1, "name": e["name"], "ceremonyId": e["ceremonyId"],
            "genesis": genesis, "approvedPackageDigest": APPROVED_PACKAGE_DIGEST,
            "held": {"sha256": held["sha256"], "length": held["length"], "bytes": held["bytes"].decode("ascii"),
                     "listingDigest": listing_digest([(e["name"], held["bytes"])])},
            "released": {"sha256": e["sha256"], "length": e["length"], "bytes": e["bytes"].decode("ascii"),
                         "record": e["record"], "listingDigest": listing_digest([(e["name"], e["bytes"])])}}


# ------------------------------------------------------------------ judges ---

def _b64u(text: Any) -> bytes | None:
    if not isinstance(text, str) or re.fullmatch(r"[A-Za-z0-9_-]*", text) is None:
        return None
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except ValueError:
        return None


def judge_observe(rc: int | None, stdout: bytes, expected: Mapping[str, Any]) -> dict[str, Any]:
    """The hold CLI's `observe` (the release's own complete root observer, shared lock) against EXPECTED.json.
    Exactly the expected RELEASED, or exactly the expected HELD; anything else is a STOP for owner adjudication."""
    try:
        doc = json.loads(stdout.decode("utf-8")) if rc == 0 else None
    except (UnicodeDecodeError, ValueError):
        doc = None
    snapshot = doc.get("snapshot") if isinstance(doc, dict) else None
    if not isinstance(snapshot, dict) or doc.get("authorityGranted") is not False \
            or not isinstance(snapshot.get("entries"), list):
        return {"class": UNOBSERVABLE, "entries": None, "listingDigest": None}
    entries = []
    for entry in snapshot["entries"]:
        data = _b64u(entry.get("data")) if isinstance(entry, dict) else None
        if data is None or not isinstance(entry.get("name"), str):
            return {"class": UNEXPECTED, "entries": None, "listingDigest": doc.get("listingDigest")}
        entries.append((entry["name"], data))
    listing = listing_digest(entries)
    consistent = doc.get("listingDigest") == snapshot.get("listingDigest") == listing \
        and snapshot.get("environment") == H10.ENVIRONMENT
    by_state = {"released": RELEASED_EXACT, "held": HELD_UNCHANGED}
    verdict = UNEXPECTED
    for state, label in by_state.items():
        want = expected[state]
        if consistent and entries == [(expected["name"], want["bytes"].encode("ascii"))] \
                and listing == want["listingDigest"]:
            verdict = label
    return {"class": verdict, "listingDigest": listing,
            "entries": [{"name": n, "sha256": sha256_hex(d), "length": len(d)} for n, d in entries]}


def readback_verdict(record: Mapping[str, Any]) -> str:
    """The one read-back classification, from the recorded facts. RELEASED_EXACT needs every required observation
    successful (exit 0), the exact RELEASED, the staging path proven absent and the accepted signer unchanged."""
    codes = record.get("codes")
    observed = isinstance(codes, Mapping) and set(codes) == {"observe", "stage", "units"}         and all(code == 0 for code in codes.values())
    released, unchanged = record.get("hold") == RELEASED_EXACT, record.get("signerUnchanged") is True
    if observed and released and unchanged and record.get("stage") == "ABSENT":
        return READBACK_EXACT
    if observed and released and unchanged and record.get("stage") == "PRESENT":
        return "MB14_READBACK_RELEASED_STAGING_RESIDUE"
    if record.get("hold") == HELD_UNCHANGED:
        return "MB14_READBACK_NOT_WRITTEN"
    return "MB14_READBACK_STOP_C19"


def parse_units(stdout: bytes) -> dict[str, dict[str, str]]:
    units: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    for line in (stdout.decode("utf-8", "replace") + "\n").splitlines():
        if not line.strip():
            if current.get("Id"):
                units[current["Id"]] = current
            current = {}
            continue
        key, _, value = line.partition("=")
        current[key] = value
    return units


def identity(units: Mapping[str, Mapping[str, str]], unit: str) -> tuple[str | None, str | None]:
    facts = units.get(unit) or {}
    return facts.get("InvocationID"), facts.get("MainPID")


def parse_release(stdout: bytes) -> tuple[dict | None, int | None, str | None]:
    """The release invocation's transcript: (CLI JSON or None, CLI rc or None, the unstage line or None)."""
    lines = stdout.decode("utf-8", "replace").splitlines()
    if lines[:1] != ["MB14_CLI_BEGIN"]:
        return None, None, None
    rc_lines = [i for i, line in enumerate(lines) if line.startswith("MB14_CLI_RC=")]
    if len(rc_lines) != 1:
        return None, None, None
    body = lines[1:rc_lines[0]]
    try:
        cli = json.loads(body[0]) if len(body) == 1 else None
    except ValueError:
        cli = None
    rc = lines[rc_lines[0]].partition("=")[2]
    unstaged = next((line for line in lines[rc_lines[0] + 1:] if line.startswith("MB14_UNSTAGED=")), None)
    return cli if isinstance(cli, dict) else None, int(rc) if rc.isdigit() else None, unstaged


# ------------------------------------------------------------------ operator ---

class Operator(E22.Operator):
    """The E-22 transport, marker, go and package helpers, unchanged; every pin lookup is this operator's."""

    def tool_bytes(self, repo: Path, path: str) -> bytes:
        data = self._git(repo, "show", f"HEAD:{path}")
        _need(sha256_hex(data) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return data

    def pins(self, repo: Path) -> dict:
        base = super().pins(repo)
        _need(sha256_hex(Path(E22.__file__).read_bytes()) == TOOL_PINS[E22.OPERATOR], "TOOL_PIN_MISMATCH:" + E22.OPERATOR)
        _need(sha256_hex(Path(H10.__file__).read_bytes()) == TOOL_PINS[E22.M10.MB10_VERIFIER],
              "TOOL_PIN_MISMATCH:" + E22.M10.MB10_VERIFIER)
        operator = sha256_hex(self._git(repo, "show", f"HEAD:{OPERATOR}"))
        _need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")
        return {"control": base["control"], "operatorSha256": operator, "result": "MB14_TOOL_PINS_EXACT"}

    # ----------------------------------------------------------------- helpers ---

    @staticmethod
    def _json(path: Path, reason: str) -> Any:
        try:
            return json.loads(Path(path).read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise Stop(reason) from exc

    def _prepared(self, workdir: Path) -> tuple[dict, bytes, dict]:
        workdir = Path(workdir)
        prepared = self._json(workdir / PREPARED, "NOT_PREPARED")
        inputs = (workdir / INPUTS_FILE).read_bytes()
        expected = self._json(workdir / EXPECTED_FILE, "EXPECTED_INVALID")
        _need(sha256_hex(inputs) == prepared["inputsSha256"]
              and sha256_hex((workdir / EXPECTED_FILE).read_bytes()) == prepared["expectedSha256"]
              and sha256_hex((workdir / ENVELOPE_FILE).read_bytes()) == ENVELOPE_SHA256, "PREPARED_EVIDENCE_CHANGED")
        _need(expected == json.loads(json.dumps(expected_document())), "EXPECTED_NOT_REDERIVED")
        return prepared, inputs, expected

    @staticmethod
    def _runs(directory: Path) -> list[Path]:
        return sorted(directory.iterdir()) if directory.is_dir() else []

    def _new_run(self, directory: Path, suffix: str) -> Path:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        out = directory / f"{len(self._runs(directory)) + 1:02d}-{suffix}"
        out.mkdir(mode=0o700)
        return out

    def _readback(self, out: Path, expected: Mapping[str, Any]) -> dict[str, Any]:
        """Read-only: hold observe, the staging path, the unit identities. Each its own invocation and transcript."""
        codes = {name: self._save(out, name, self._invoke_once(command, None))
                 for name, command in (("observe", OBSERVE_COMMAND), ("stage", STAGE_COMMAND), ("units", UNITS_COMMAND))}
        hold = judge_observe(codes["observe"], (out / "observe.out").read_bytes(), expected)
        stage = (out / "stage.out").read_bytes().strip()
        units = parse_units((out / "units.out").read_bytes()) if codes["units"] == 0 else {}
        return {"codes": codes, "hold": hold,
                "stage": {b"STAGE=absent": "ABSENT", b"STAGE=present": "PRESENT"}.get(stage, "UNKNOWN")
                if codes["stage"] == 0 else "UNKNOWN",
                "signer": list(identity(units, E22.SIGNER_SERVICE)), "witness": list(identity(units, E22.WITNESS_SERVICE))}

    def _latest_record(self, workdir: Path, directory: str, file: str) -> tuple[dict | None, str | None]:
        runs = [run / file for run in self._runs(Path(workdir) / directory) if (run / file).is_file()]
        if not runs:
            return None, None
        return self._json(runs[-1], "RECORD_INVALID"), sha256_hex(runs[-1].read_bytes())

    def _marker_exists(self, workdir: Path, name: str = MARKER) -> bool:
        return (Path(workdir) / M6.ATTEMPT_DIR / f"{name}.json").exists()

    # ------------------------------------------------------------- local forms ---

    def prepare(self, repo: Path, workdir: Path, envelope: Path) -> dict:
        control = self.pins(repo)["control"]
        workdir = Path(workdir)
        _need(not workdir.exists(), "WORKDIR_EXISTS")
        raw = Path(envelope).read_bytes()
        _need(sha256_hex(raw) == ENVELOPE_SHA256, "ENVELOPE_NOT_ACCEPTED")
        inputs = _canonical(self.owner_inputs(raw)) + b"\n"
        _need(len(inputs) <= MAX_INPUT, "INPUT_DOCUMENT_TOO_LARGE")
        expected = expected_document()
        workdir.mkdir(mode=0o700, parents=True)
        (workdir / ENVELOPE_FILE).write_bytes(raw)
        (workdir / INPUTS_FILE).write_bytes(inputs)
        data = self._record(workdir / EXPECTED_FILE, expected)
        self._record(workdir / PREPARED, {"control": control, "envelopeSha256": ENVELOPE_SHA256,
                                          "inputsSha256": sha256_hex(inputs), "inputsLength": len(inputs),
                                          "expectedSha256": sha256_hex(data), "preparedAt": self._now()})
        return {"result": "MB14_PREPARED", "name": expected["name"], "heldSha256": expected["held"]["sha256"],
                "releasedSha256": expected["released"]["sha256"],
                "releasedListingDigest": expected["released"]["listingDigest"], "inputsSha256": sha256_hex(inputs),
                "next": "`pre` (read-only DEV), then `render GO` for the owner"}

    def _now(self) -> str:
        return self.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _go_values(self, repo: Path, workdir: Path) -> dict:
        control = self.pins(repo)["control"]
        prepared, inputs, expected = self._prepared(workdir)
        _need(prepared["control"] == control, "CONTROL_NOT_THE_PREPARED_CONTROL")
        pre, pre_sha = self._latest_record(workdir, PRE_DIR, "PRE.json")
        _need(pre is not None and pre.get("exact") is True, "PRE_NOT_EXACT")
        return {"control": control, "operator": sha256_hex(Path(__file__).read_bytes()), "pre": pre_sha,
                "rerun": pre["packageDigest"], "inputs": sha256_hex(inputs), "length": str(len(inputs)),
                "name": expected["name"], "held": expected["held"]["sha256"],
                "held_listing": expected["held"]["listingDigest"], "sinv": pre["signer"][0], "spid": pre["signer"][1],
                "released": expected["released"]["sha256"], "released_listing": expected["released"]["listingDigest"]}

    def _accept_values(self, workdir: Path) -> tuple[dict, bool]:
        _prepared, _inputs, expected = self._prepared(workdir)
        record, record_sha = self._latest_record(workdir, POST_DIR, "POST.json")
        _need(record is not None and readback_verdict(record) == READBACK_EXACT
              and record.get("result") == READBACK_EXACT, "READBACK_NOT_RELEASED_EXACT")
        _need(self._marker_exists(workdir) and (Path(workdir) / ATTEMPT_FILE).is_file(), "RELEASE_NOT_RUN")
        attempt = self._json(Path(workdir) / ATTEMPT_FILE, "ATTEMPT_INVALID")
        return ({"name": expected["name"], "released": expected["released"]["sha256"], "readback": record_sha,
                 "held": expected["held"]["sha256"]}, attempt.get("cliExact") is not True)

    def _unstage_values(self, workdir: Path) -> dict:
        _prepared, inputs, _expected = self._prepared(workdir)
        record, record_sha = self._latest_record(workdir, POST_DIR, "POST.json")
        _need(self._marker_exists(workdir) and record is not None and record.get("stage") == "PRESENT",
              "NO_STAGED_DOCUMENT_OBSERVED")
        return {"inputs": sha256_hex(inputs), "readback": record_sha}

    def render(self, repo: Path, workdir: Path, act: str) -> dict:
        if act == "GO":
            _need(not self._marker_exists(workdir), "ATTEMPT_ALREADY_CONSUMED:" + MARKER)
            values, lines = self._go_values(repo, workdir), GO_LINES
        elif act == "ACCEPT":
            values, adoption = self._accept_values(workdir)
            lines = ACCEPT_LINES + ((ADOPTION_LINE,) if adoption else ())
        elif act == "UNSTAGE":
            values, lines = self._unstage_values(workdir), UNSTAGE_LINES
        else:
            raise Stop("ACT_INVALID")
        text = "\n".join(line.format(**values) for line in lines) + "\n"
        return {"act": act, "text": text, "textSha256": sha256_hex(text.encode("ascii")), "values": values}

    def accept(self, repo: Path, workdir: Path, statement: Path) -> dict:
        raw = Path(statement).read_bytes()
        _need(raw == self.render(repo, workdir, "ACCEPT")["text"].encode("ascii"), "STATEMENT_NOT_CANONICAL")
        try:
            self._record(Path(workdir) / ACCEPT_FILE, {"act": "MB14_ACCEPTANCE", "statementSha256": sha256_hex(raw)})
        except FileExistsError as exc:
            raise Stop("ACCEPTANCE_ALREADY_RECORDED") from exc
        return {"result": "MB14_ACCEPTED", "authorityGranted": False, "next": "nothing is authorized (M-B15 separate)"}

    # --------------------------------------------------------- read-only remote ---

    def pre(self, repo: Path, workdir: Path) -> dict:
        """The read-only pre-check: the exact HELD, no staging residue, the accepted signer, and ONE package re-run
        (`e22_operator package`, unchanged) whose digest must equal the approved one."""
        self.pins(repo)
        _prepared, _inputs, expected = self._prepared(workdir)
        _need(not self._marker_exists(workdir), "ATTEMPT_ALREADY_CONSUMED:" + MARKER)
        out = self._new_run(Path(workdir) / PRE_DIR, "PRE")
        read = self._readback(out, expected)
        package = self.package(repo, out / "package", Path(workdir) / ENVELOPE_FILE)
        report = (self._json(out / "package" / "remote.out", "PACKAGE_INVALID").get("report") or {}) \
            if package["result"] == "E22_PACKAGE_READY" else {}
        evidence = (report.get("package") or {}).get("evidence") or {}
        witness, holds = evidence.get("witness") or {}, (evidence.get("holdStore") or {}).get("records")
        reasons = [name for name, ok in (
            ("HOLD_NOT_THE_EXPECTED_HELD", read["hold"]["class"] == HELD_UNCHANGED),
            ("STAGING_PATH_NOT_ABSENT", read["stage"] == "ABSENT"),
            ("SIGNER_NOT_THE_ACCEPTED_INCARNATION", tuple(read["signer"]) == SIGNER),
            ("PACKAGE_NOT_READY", package["result"] == "E22_PACKAGE_READY" and package["mode"] == "HOLD_RELEASE_ELIGIBILITY"
             and package["reasons"] == []),
            ("RERUN_DIGEST_NOT_APPROVED", package["packageDigest"] == APPROVED_PACKAGE_DIGEST),
            ("WITNESS_HEAD_NOT_GENESIS", witness.get("classification") == "CONSISTENT" and witness.get("chainLength") == 1
             and witness.get("headDigest") == witness.get("genesisDigest") == GENESIS),
            ("PACKAGE_HOLD_NOT_HELD", holds == [[expected["ceremonyId"], "INITIAL_CUSTODY", "HELD"]]
             and report.get("holdListingDigest") == expected["held"]["listingDigest"]),
        ) if not ok]
        record = {"exact": reasons == [], "reasons": reasons, "hold": read["hold"]["class"], "stage": read["stage"],
                  "signer": read["signer"], "witness": read["witness"], "codes": read["codes"],
                  "packageDigest": package["packageDigest"], "packageResult": package["result"],
                  "observedAt": self._now()}
        self._record(out / "PRE.json", record)
        return dict(record, pre=out.name, result="MB14_PRE_EXACT" if not reasons else "MB14_PRE_NOT_EXACT")

    def post(self, repo: Path, workdir: Path) -> dict:
        """The independent read-back (also the C-19 root-observer classification after an interruption)."""
        self.pins(repo)
        _prepared, _inputs, expected = self._prepared(workdir)
        out = self._new_run(Path(workdir) / POST_DIR, "POST")
        read = self._readback(out, expected)
        unchanged = tuple(read["signer"]) == SIGNER
        record = {"hold": read["hold"]["class"], "listingDigest": read["hold"]["listingDigest"],
                  "entries": read["hold"]["entries"], "stage": read["stage"], "signer": read["signer"],
                  "witness": read["witness"], "signerUnchanged": unchanged, "codes": read["codes"],
                  "markerConsumed": self._marker_exists(workdir), "observedAt": self._now()}
        record["result"] = readback_verdict(record)
        self._record(out / "POST.json", record)
        return dict(record, post=out.name)

    # ------------------------------------------------------------------ mutation ---

    @staticmethod
    def release_command(inputs: bytes) -> tuple[str, bytes]:
        """ONE remote invocation over the direct-plink stdin route: the payload digest is checked; the staging
        directory must be absent; the document is written root 0600 in a new 0700 directory and its digest checked;
        the CLI runs exactly once; the document and directory are removed; the CLI exit code is returned."""
        payload = base64.b64encode(inputs)
        inner = f"umask 077 && mkdir -m 0700 {STAGE_DIR} && cat > {STAGE_FILE}"
        unstage = f"sudo -n /usr/bin/rm -f -- {STAGE_FILE}; sudo -n /usr/bin/rmdir -- {STAGE_DIR}"
        command = (
            f"B=$(cat); printf %s \"$B\" | sha256sum | cut -c1-64 | grep -qx '{sha256_hex(payload)}' || exit 96; "
            f"sudo -n /usr/bin/test ! -e {STAGE_DIR} || exit 95; "
            f"printf %s \"$B\" | base64 -d | sudo -n /usr/bin/sh -c '{inner}' || {{ {unstage}; exit 94; }}; "
            f"sudo -n /usr/bin/sha256sum {STAGE_FILE} | cut -c1-64 | grep -qx '{sha256_hex(inputs)}' || {{ {unstage}; exit 93; }}; "
            f"echo MB14_CLI_BEGIN; sudo -n {HOLD_CLI} release-initial {APPROVED_PACKAGE_DIGEST} {STAGE_FILE}; rc=$?; "
            f"echo MB14_CLI_RC=$rc; {unstage}; echo MB14_UNSTAGED=$?; exit $rc")
        return command, payload + b"\n"

    def release(self, repo: Path, workdir: Path, go_file: Path) -> dict:
        raw = Path(go_file).read_bytes()
        _need(raw == self.render(repo, workdir, "GO")["text"].encode("ascii"), "GO_NOT_CANONICAL")
        _prepared, inputs, expected = self._prepared(workdir)
        out = self._new_run(Path(workdir) / RELEASE_DIR, "RELEASE")
        gate_dir = out / "gate"
        gate_dir.mkdir(mode=0o700)
        gate = self._readback(gate_dir, expected)                                      # read-only, before the marker
        _need(gate["hold"]["class"] == HELD_UNCHANGED and gate["stage"] == "ABSENT" and tuple(gate["signer"]) == SIGNER,
              "GATE_NOT_EXACT")
        command, stdin = self.release_command(inputs)
        self.plink_argv(command)          # B1: every local transport binding checked BEFORE the marker; nothing launched
        self._one_attempt(workdir, MARKER, raw)                                         # the go is consumed HERE
        code = self._save(out, MARKER, self._invoke_once(command, stdin))
        cli, cli_rc, unstaged = parse_release((out / f"{MARKER}.out").read_bytes())
        cli_exact = code == 0 and cli_rc == 0 and cli == {"record": expected["released"]["record"]}
        attempt = {"marker": MARKER, "goSha256": sha256_hex(raw), "run": out.name, "code": code, "cliRc": cli_rc,
                   "cliExact": cli_exact, "unstaged": unstaged, "approvedPackageDigest": APPROVED_PACKAGE_DIGEST,
                   "releasedSha256": expected["released"]["sha256"]}
        self._record(Path(workdir) / ATTEMPT_FILE, attempt)   # B2: the invocation facts, before anything can fail
        try:
            post = self.post(repo, workdir)
        except Stop as exc:            # the read-back did not complete: never a retry; `post` re-observes (C-19)
            post = {"post": None, "result": "MB14_READBACK_NOT_COMPLETED:" + exc.code}
        record = dict(attempt, post=post["post"], readback=post["result"],
                      result=("MB14_RELEASED_EXACT" if cli_exact and post["result"] == "MB14_READBACK_RELEASED_EXACT"
                              else "MB14_RELEASED_ADOPTION_REQUIRED" if post["result"] == "MB14_READBACK_RELEASED_EXACT"
                              else "MB14_STOP:" + post["result"]))
        self._record(out / "RELEASE.json", record)
        return dict(record, next="owner acceptance (`render ACCEPT`); nothing further is authorized"
                    if post["result"] == "MB14_READBACK_RELEASED_EXACT"
                    else "STOP: no retry; read-only `post` re-observation and owner adjudication (C-19)")

    def unstage(self, repo: Path, workdir: Path, statement: Path) -> dict:
        raw = Path(statement).read_bytes()
        _need(raw == self.render(repo, workdir, "UNSTAGE")["text"].encode("ascii"), "STATEMENT_NOT_CANONICAL")
        _prepared, inputs, _expected = self._prepared(workdir)
        command = (f"sudo -n /usr/bin/sha256sum {STAGE_FILE} | cut -c1-64 | grep -qx '{sha256_hex(inputs)}' || exit 93; "
                   f"sudo -n /usr/bin/rm -f -- {STAGE_FILE} && sudo -n /usr/bin/rmdir -- {STAGE_DIR}")
        out = self._new_run(Path(workdir) / RELEASE_DIR, "UNSTAGE")
        self._one_attempt(workdir, UNSTAGE_MARKER, raw)
        code = self._save(out, UNSTAGE_MARKER, self._invoke_once(command, None))
        post = self.post(repo, workdir)
        return {"code": code, "post": post["post"], "stage": post["stage"],
                "result": "MB14_UNSTAGED" if code == 0 and post["stage"] == "ABSENT" else "MB14_UNSTAGE_STOP"}


def main(argv: Sequence[str], operator: Operator | None = None) -> int:
    operator = operator or Operator()
    forms = {
        ("pins", 1): lambda a: operator.pins(Path(a[0])),
        ("prepare", 3): lambda a: operator.prepare(Path(a[0]), Path(a[1]), Path(a[2])),
        ("pre", 2): lambda a: operator.pre(Path(a[0]), Path(a[1])),
        ("render", 3): lambda a: operator.render(Path(a[0]), Path(a[1]), a[2]),
        ("release", 3): lambda a: operator.release(Path(a[0]), Path(a[1]), Path(a[2])),
        ("post", 2): lambda a: operator.post(Path(a[0]), Path(a[1])),
        ("unstage", 3): lambda a: operator.unstage(Path(a[0]), Path(a[1]), Path(a[2])),
        ("accept", 3): lambda a: operator.accept(Path(a[0]), Path(a[1]), Path(a[2])),
    }
    form = forms.get((argv[0], len(argv) - 1)) if argv else None
    if form is None:
        print(__doc__.split("| Form |", 1)[1].split("\n\n", 1)[0], file=sys.stderr)
        return 2
    try:
        result = form(list(argv[1:]))
    except Stop as exc:
        print(f"mb14_operator: STOP {exc.code}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
