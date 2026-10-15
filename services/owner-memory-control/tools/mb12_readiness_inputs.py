#!/usr/bin/env python3
"""15B2b-B1b-3e M-B12 PR-B1: the PR-1 readiness input builder and its stdin envelope reader (pure).

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb1-prerequisite-tooling.md.
REPOSITORY ONLY. Nothing here contacts a host, reads a credential, starts a unit or evaluates readiness.

`build` turns owner-held evidence into the closed `LILITH_PR1_VERIFIER_INPUTS` document that the release's root verifier
parses (`lilith_authority_root.verifier.parse_verifier_inputs`; the M-B11 `ownerInputs`), wrapped in one envelope whose
SHA-256 the owner reviews. `read_envelope` is the host-side half: it accepts the envelope on stdin, so no input file is
placed on DEV (OD-M11-15, PROPOSED), and returns the document only if the bytes are exactly the reviewed ones.

Fail-closed rules (never a default, never a synthetic PASS):

- the window's lower bound is the TRUST's freshness cutoff, never the caller's choice: DEV uses
  `mb12_pr2_inventory.DEV_FRESHNESS_NOT_BEFORE` (OD-M12-3), which is UNDECIDED, so every DEV build is REFUSED; every
  `observedAt` must lie inside the window;
- the K-ACT / K-WIT publication bytes must be the recorded ones (file SHA-256, B3, K-WIT fingerprint);
- the activation line is passed VERBATIM, and must be the complete host line (the PR #185 form). The release judge
  `pr1_acceptance` still compares the 3-field prefix: E-19 therefore FAILS on every real observation (record §8). The
  builder never rewrites the line to make E-19 pass;
- a proof is admitted only as the producer's own transcript BYTES: the producer script must be the pinned one, the
  bytes must satisfy that producer's exact terminal contract (phase, final line, exit status; for the custody denial
  proof the complete expected PASS transcript is rebuilt from the script's own rows), the result and transcript digest
  are DERIVED here, and the digest must be ESTABLISHED by the trust's accepted-transcript pins (DEV:
  `DEV_ACCEPTED_PROOF_TRANSCRIPTS`, EMPTY). `OS_DENIAL`, `SECRET_HYGIENE`, `PRESERVATION_SET` have the PR-B2
  producers (`mb12_os_denial_proof`, `mb12_secret_hygiene_proof`, `mb12_preservation_set_proof`) with exact contracts;
  a missing proof stays missing (NOT_READY downstream);
- PR-2 / PR-3 enter only through `mb12_pr2_inventory.package_input` / `mb12_pr3_material.package_input`, called here on
  the canonical inventory + acceptance / owner inputs + confirmation; a package object is never accepted. Both refuse
  on DEV until a merged owner record pins the accepted digest.

Trust boundary: a transcript, acceptance or confirmation supplied by a caller is never by itself evidence of what ran
on DEV or of an owner decision. The only established binding is a reviewed, merged record pinned in source. DEV trust
cannot be overridden; TEST must pass an explicit `ReadinessTrustV1`.

    input document != readiness;  envelope digest != owner acceptance;  READY is the verifier's, never the builder's

Forms:

    ... build <build-inputs.json>          owner side: the envelope bytes on stdout (JCS + LF)
    ... verify-envelope <sha256> < env     either side: check the stdin bytes; prints the document digest only
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Mapping

HERE = Path(__file__).resolve().parent
_OWNER_MEMORY = HERE.parent
REPO = HERE.parents[2]
for _path in (_OWNER_MEMORY, HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import rfc8785  # noqa: E402

import mb12_pr2_inventory as I2  # noqa: E402
import mb12_pr3_material as M3  # noqa: E402
from lilith_owner_memory import pr1_acceptance as PA  # noqa: E402
from lilith_owner_memory import pr1_bootstrap as B  # noqa: E402
from lilith_owner_memory import successor_custody as SC  # noqa: E402
from lilith_owner_memory import witness_readiness as WR  # noqa: E402

INPUT_TYPE = "LILITH_PR1_VERIFIER_INPUTS"               # = lilith_authority_root.verifier.INPUT_TYPE
ENVELOPE_TYPE = "LILITH_MB12_READINESS_INPUT_ENVELOPE"
ENVELOPE_FIELDS = frozenset({"envelopeType", "schemaVersion", "environment", "inputsSha256", "inputs", "provenance"})
BUILD_TYPE = "LILITH_MB12_READINESS_BUILD_INPUTS"
BUILD_FIELDS = frozenset({"buildType", "schemaVersion", "environment", "window", "release", "current", "kActPublication",
                          "kWitPublication", "proofs", "activation", "pr2", "pr3"})
MAX_ENVELOPE = 256 * 1024                                # = lilith_authority_root.cli.MAX_INPUT
MAX_TRANSCRIPT = 1024 * 1024
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")

# The complete line `lilith-activation-verify` prints on DEV (exit 1), byte-identical in every preserved host POST.
HOST_ACTIVATION_DARK_LINE = "ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT advisoryConfigEnabled=false"
HOST_ACTIVATION_EXIT = 1

# ------------------------------------------------------------ proof producers ---
# OD-M11-14 (PROPOSED, not accepted): proof name -> the one producer whose transcript may be bound. None = no producer.
CUSTODY_DENIAL = "scripts/authority_custody_denial_proof.py:P1B-12"
DEPLOYER_BOUNDARY = "scripts/deployer_authority_boundary_proof.sh:DR-5"
BROKER_PRESERVATION = "scripts/verify_broker_dev_current_incarnation.py:preservation"
OS_DENIAL_UNIT = "services/owner-memory-control/tools/mb12_os_denial_proof.py:UNIT"
SECRET_HYGIENE_SCOPE = "services/owner-memory-control/tools/mb12_secret_hygiene_proof.py:prove"
PRESERVATION_SET_COMPARE = "services/owner-memory-control/tools/mb12_preservation_set_proof.py:compare"
PROPOSED_PROOF_PRODUCERS = {
    "SIGNER_DENIAL": CUSTODY_DENIAL,
    "DEPLOYER_DENIAL": DEPLOYER_BOUNDARY,
    "BROKER_DENIAL": CUSTODY_DENIAL,
    "BROKER_PRESERVATION": BROKER_PRESERVATION,
    "OS_DENIAL": OS_DENIAL_UNIT,
    "SECRET_HYGIENE": SECRET_HYGIENE_SCOPE,
    "PRESERVATION_SET": PRESERVATION_SET_COMPARE,
}
assert tuple(PROPOSED_PROOF_PRODUCERS) == PA.REQUIRED_PROOFS
# The reviewed producer script bytes (repository HEAD). A changed producer invalidates every transcript contract.
PRODUCER_SCRIPT_SHA256 = {
    "scripts/authority_custody_denial_proof.py": "f4e39c81c24a01be5702f6a65a581fcd08f97e1c5ad4a07326883b605fef1455",
    "scripts/deployer_authority_boundary_proof.sh": "9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43",
    "scripts/verify_broker_dev_current_incarnation.py":
        "b90ed6efa203f7aade5519120e1658b866aa9f0d4f559e6ac39fcc51573ebfcf",
    "services/owner-memory-control/tools/mb12_os_denial_proof.py": "e67542287f869e6d8e56ee30321593424e41c964e682e5326fd8dc15a6fd8ef3",
    "services/owner-memory-control/tools/mb12_secret_hygiene_proof.py": "3a039a96c0a051aaa635d06879729a33978600551cbdf564ae778e81704b1355",
    "services/owner-memory-control/tools/mb12_preservation_set_proof.py": "79f47ae8f25e5d20f0066485196e910f78e3949c03dc97bebfbbf84681e485f8",
}
# Producer transcripts established by a merged owner record: proof name -> accepted transcript SHA-256s. EMPTY.
DEV_ACCEPTED_PROOF_TRANSCRIPTS: Mapping[str, frozenset[str]] = {}

# The accepted DEV records (public values only).
DEV_PINS = {
    "releaseSha": "ba943e1a188d98f4108c9eec7149c0cf1a8f68bb",                                          # E-19 U5
    "attestedManifestSha256": "b8393015e505495a81629411a4ecd33c0c372c7b16d2761094eb4e018bc300a2",      # E-19 U5
    "pinnedCurrentSha256": "6a61c350e848a833868f4573982fca9c75e2af79ccc9bd3716ae0303c26973f3",
    "kActPublicationFileSha256": "d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032",
    "kActPublicKeySha256": "dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed",
    "kWitPublicKeySha256": "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf",
}
PIN_FIELDS = frozenset(DEV_PINS)
_CURRENT_FIELDS = frozenset({"path", "kind", "uid", "gid", "mode", "device", "inode", "size", "mtimeNs", "ctimeNs",
                             "sha256"})
_OBSERVED = frozenset({"observedAt", "evidenceSha256"})
_PROOF_FIELDS = frozenset({"transcript", "exitCode"}) | _OBSERVED
_RUNTIME_DIGEST_NAMES = frozenset({"authority", "witness", "rootTooling"})

KNOWN_PACKAGE_DEFECTS = (
    "E19_ACTIVATION_LINE_FORM: pr1_acceptance.ACTIVATION_DARK_LINE is the 3-field prefix "
    "'ACTIVATION=NOT_ACCEPTED reason=GRANT_ABSENT'; the host prints the complete line with "
    "'advisoryConfigEnabled=false'; E19_ACTIVATION_DARK FAILs ACTIVATION_NOT_DARK on every real observation",
)
# Installed releases whose judge carries that defect. The repository judge is corrected (E-19 release maintenance
# record); the defect stays real for as long as aee323e is the installed release (retired at E-19 U5: history only).
E19_DEFECTIVE_RELEASES = frozenset({"aee323e94412accbe321bc84eae78c5b8cf95afc"})


@dataclass(frozen=True)
class ReadinessTrustV1:
    """What a build is judged against. DEV: `trust_for("dev", None)` only; never caller-supplied."""

    pins: Mapping[str, str]
    not_before: str
    accepted_proof_transcripts: Mapping[str, frozenset[str]]
    pr2: I2.Pr2TrustV1 | None
    pr3: M3.Pr3TrustV1 | None


class Refused(ValueError):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason if detail is None else f"{reason}:{detail}")
        self.reason = reason
        self.detail = detail


def _need(condition: Any, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise Refused(reason, detail)


def _exact(value: Any, fields: frozenset[str], name: str) -> Mapping[str, Any]:
    _need(isinstance(value, Mapping) and set(value) == fields, "INPUT_MALFORMED", name)
    return value


def _hex(value: Any, name: str) -> str:
    _need(isinstance(value, str) and _HEX64.fullmatch(value), "INPUT_MALFORMED", name)
    return value


def _instant(value: Any, name: str) -> datetime:
    _need(isinstance(value, str) and _INSTANT.fullmatch(value), "INPUT_MALFORMED", name)
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _b64u_decode(value: Any, name: str) -> bytes:
    _need(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]+", value), "INPUT_MALFORMED", name)
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    _need(_b64u(raw) == value, "INPUT_MALFORMED", name)
    return raw


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def document_digest(document: Mapping[str, Any]) -> str:
    """SHA-256(JCS(document)): the `inputsSha256` the envelope binds."""
    return _sha256(rfc8785.dumps(dict(document)))


def envelope_bytes(envelope: Mapping[str, Any]) -> bytes:
    """The one wire form: JCS + exactly one LF."""
    return rfc8785.dumps(dict(envelope)) + b"\n"


def trust_for(environment: str, trust: ReadinessTrustV1 | None) -> ReadinessTrustV1:
    """DEV: the pinned trust only (a caller value is refused; the cutoff must be decided). Elsewhere: explicit."""
    if environment == "dev":
        _need(trust is None, "DEV_TRUST_NOT_OVERRIDABLE")
        _need(I2.DEV_FRESHNESS_NOT_BEFORE is not None, "FRESHNESS_CUTOFF_UNDECIDED", "OD-M12-3")
        return ReadinessTrustV1(dict(DEV_PINS), I2.DEV_FRESHNESS_NOT_BEFORE, dict(DEV_ACCEPTED_PROOF_TRANSCRIPTS),
                                None, None)
    _need(isinstance(trust, ReadinessTrustV1) and isinstance(trust.pins, Mapping) and set(trust.pins) == PIN_FIELDS
          and isinstance(trust.accepted_proof_transcripts, Mapping), "TRUST_REQUIRED")
    _instant(trust.not_before, "trust.not_before")
    return trust


# ---------------------------------------------------- transcript contracts ---

def _producer_script(relative: str) -> bytes:
    raw = (REPO / relative).read_bytes()
    _need(_sha256(raw) == PRODUCER_SCRIPT_SHA256[relative], "PRODUCER_SCRIPT_NOT_PINNED", relative)
    return raw


def _producer_module(relative: str) -> Any:
    """The pinned producer, loaded for its constants and pure functions only (`main` runs under `__main__` alone)."""
    _producer_script(relative)
    spec = importlib.util.spec_from_file_location("_mb12_producer_" + Path(relative).stem, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_custody_denial_pass(phase: str = "P1B-12") -> bytes:
    """The complete PASS transcript `authority_custody_denial_proof.py <phase>` prints, rebuilt from its own rows."""
    module = _producer_module("scripts/authority_custody_denial_proof.py")
    active = module.PHASES.index(phase)
    lines = []
    for first, principals, op, path in module.ROWS:
        if module.PHASES.index(first) > active:
            lines.append(f"DEFERRED_UNTIL_PHASE: {first} {op} {path}")
            continue
        lines.extend(f"DENIED: {principal} test {op} {path}" for principal in principals)
    if phase == "P1B-12":
        lines.extend(f"DENIED: signer-namespace test {op} {path}" for op, path in module.NAMESPACE_ROWS)
    lines.append(f"AUTHORITY_CUSTODY_DENIAL_PROOF=PASS phase={phase}")
    return ("\n".join(lines) + "\n").encode("ascii")


def _lines(raw: bytes) -> list[str]:
    _need(0 < len(raw) <= MAX_TRANSCRIPT and raw.endswith(b"\n") and b"\r" not in raw, "TRANSCRIPT_CONTRACT", "form")
    try:
        return raw.decode("ascii")[:-1].split("\n")
    except UnicodeDecodeError as exc:
        raise Refused("TRANSCRIPT_CONTRACT", "ascii") from exc


def _custody_denial(raw: bytes, exit_code: int) -> tuple[str, str | None]:
    lines = _lines(raw)
    if exit_code == 0:
        _need(raw == expected_custody_denial_pass("P1B-12"), "TRANSCRIPT_CONTRACT", "custody denial PASS not exact")
        return PA.PASS, None
    _need(exit_code == 1 and re.fullmatch(r"AUTHORITY_CUSTODY_DENIAL_PROOF=FAIL phase=P1B-12", lines[-1])
          and any(line.startswith("FAIL: ") for line in lines[:-1]), "TRANSCRIPT_CONTRACT", "custody denial FAIL")
    return PA.FAIL, None


def _deployer_boundary(raw: bytes, exit_code: int) -> tuple[str, str | None]:
    lines = _lines(raw)
    _need(len(lines) >= 2, "TRANSCRIPT_CONTRACT", "DR-5 short")
    pr1 = re.fullmatch(r"PR1_AUTHORITY_BOUNDARY (maturity=\S+)", lines[-2])
    final = re.fullmatch(r"AUTHORITY_BOUNDARY_PROOF=(PASS|FAIL) maturity=\S+", lines[-1])
    _need(pr1 is not None and final is not None, "TRANSCRIPT_CONTRACT", "DR-5 final lines")
    _need((final.group(1) == "PASS") == (exit_code == 0) and exit_code in (0, 1), "TRANSCRIPT_CONTRACT", "DR-5 exit")
    return final.group(1), pr1.group(1)


def _broker_preservation(raw: bytes, exit_code: int) -> tuple[str, str | None]:
    lines = _lines(raw)
    _need(len(lines) == 1, "TRANSCRIPT_CONTRACT", "broker preservation lines")
    try:
        value = json.loads(lines[0], object_pairs_hook=SC._no_duplicate_keys)
    except ValueError as exc:
        raise Refused("TRANSCRIPT_CONTRACT", "broker preservation json") from exc
    _need(isinstance(value, dict) and json.dumps(value, sort_keys=True, separators=(",", ":")) == lines[0]
          and value.get("operation") == "READ_ONLY_BROKER_PRESERVATION"
          and value.get("BROKER_PRESERVATION") in (PA.PASS, PA.FAIL) and isinstance(value.get("failures"), list),
          "TRANSCRIPT_CONTRACT", "broker preservation document")
    result = value["BROKER_PRESERVATION"]
    _need((result == PA.PASS) == (not value["failures"]) and exit_code == (0 if result == PA.PASS else 2),
          "TRANSCRIPT_CONTRACT", "broker preservation exit")
    return result, None


def _fail_contract(lines: list[str], exit_code: int, final: str, what: str) -> tuple[str, str | None]:
    """A FAIL transcript: exit 1, the producer's FAIL final line, and at least one observed `FAIL: ` row. A refusal
    with no observation (NOT_ROOT, USAGE, an unestablished baseline) is not a proof result at all."""
    _need(exit_code == 1 and re.fullmatch(final, lines[-1]) is not None
          and any(line.startswith("FAIL: ") for line in lines[:-1]), "TRANSCRIPT_CONTRACT", what)
    return PA.FAIL, None


def _os_denial(raw: bytes, exit_code: int) -> tuple[str, str | None]:
    lines = _lines(raw)
    module = _producer_module(OS_DENIAL_UNIT.split(":")[0])
    if exit_code == 0:
        _need(raw in (module.expected_pass(module.DROPINS_NONE), module.expected_pass(module.DROPINS_P1B10R)),
              "TRANSCRIPT_CONTRACT", "OS_DENIAL PASS not exact")
        return PA.PASS, None
    return _fail_contract(lines, exit_code, re.escape(module.final_line(False)), "OS_DENIAL FAIL")


def _secret_hygiene(raw: bytes, exit_code: int) -> tuple[str, str | None]:
    lines = _lines(raw)
    module = _producer_module(SECRET_HYGIENE_SCOPE.split(":")[0])
    ceremonies = module.CEREMONIES
    scope = re.fullmatch(rf"SCOPE: sha256=([0-9a-f]{{64}}) ceremonies={re.escape(','.join(ceremonies))}", lines[0])
    _need(scope is not None, "TRANSCRIPT_CONTRACT", "SECRET_HYGIENE scope line")
    digest = scope.group(1)
    if exit_code != 0:
        return _fail_contract(lines, exit_code, rf"SECRET_HYGIENE_PROOF=FAIL scope={digest}", "SECRET_HYGIENE FAIL")
    # A PASS is admissible only when the producer's own (pinned) scope is closed: no open scope decision, every
    # canonical record named, every DEV window recorded.
    _need(not module.UNRESOLVED_SCOPE and all(c.record for c in ceremonies.values())
          and all(c.venue == "S25" or (c.window and None not in c.window) for c in ceremonies.values()),
          "TRANSCRIPT_CONTRACT", "SECRET_HYGIENE producer scope not closed")
    _need(len(lines) >= 3 and lines[-1] == f"SECRET_HYGIENE_PROOF=PASS scope={digest}"
          and re.fullmatch(r"JOURNAL_SCAN: sha256=[0-9a-f]{64} PASS", lines[-2]) is not None,
          "TRANSCRIPT_CONTRACT", "SECRET_HYGIENE final lines")
    seen: dict[str, set[str]] = {name: set() for name in ceremonies}
    for line in lines[1:-2]:
        item = re.fullmatch(r"ITEM: (\S+) (TRANSCRIPT|PUBLICATION:[A-Z0-9_]+) sha256=([0-9a-f]{64}) bytes=\d+ CLEAN",
                            line)
        covered = re.fullmatch(r"COVERED: (\S+) boot=[0-9a-f]{32} window=(\S+)/(\S+)", line)
        offhost = re.fullmatch(r"OFFHOST: (\S+) S25 \(no DEV journal\)", line)
        match = item or covered or offhost
        _need(match is not None and match.group(1) in ceremonies, "TRANSCRIPT_CONTRACT", "SECRET_HYGIENE line")
        spec = ceremonies[match.group(1)]
        if item is not None:
            role = item.group(2)
            if role != "TRANSCRIPT":
                _need(role == f"PUBLICATION:{spec.publication}" and (spec.publication_sha256 is None
                                                                      or item.group(3) == spec.publication_sha256),
                      "TRANSCRIPT_CONTRACT", "SECRET_HYGIENE publication")
            seen[match.group(1)].add(role)
        elif covered is not None:
            _need(spec.venue == "DEV" and (covered.group(2), covered.group(3)) == tuple(spec.window),
                  "TRANSCRIPT_CONTRACT", "SECRET_HYGIENE coverage")
            seen[match.group(1)].add("COVERED")
        else:
            _need(spec.venue == "S25", "TRANSCRIPT_CONTRACT", "SECRET_HYGIENE venue")
            seen[match.group(1)].add("OFFHOST")
    for name, spec in ceremonies.items():
        required = {"TRANSCRIPT", "COVERED" if spec.venue == "DEV" else "OFFHOST"}
        if spec.publication:
            required.add(f"PUBLICATION:{spec.publication}")
        _need(required <= seen[name], "TRANSCRIPT_CONTRACT", f"SECRET_HYGIENE scope incomplete {name}")
    return PA.PASS, None


def _preservation_set(raw: bytes, exit_code: int) -> tuple[str, str | None]:
    lines = _lines(raw)
    module = _producer_module(PRESERVATION_SET_COMPARE.split(":")[0])
    _need(len(lines) >= 2, "TRANSCRIPT_CONTRACT", "PRESERVATION_SET short")
    baseline = re.fullmatch(r"BASELINE: sha256=([0-9a-f]{64}) observedAt=(\S+)", lines[0])
    observation = re.fullmatch(r"OBSERVATION: sha256=([0-9a-f]{64}) observedAt=(\S+)", lines[1])
    _need(baseline is not None and observation is not None, "TRANSCRIPT_CONTRACT", "PRESERVATION_SET header")
    _need(baseline.group(1) in module.ACCEPTED_BASELINES, "TRANSCRIPT_CONTRACT", "PRESERVATION_SET baseline not accepted")
    if exit_code == 0:
        _need(raw == module.expected_pass(baseline.group(1), baseline.group(2), observation.group(1),
                                          observation.group(2)), "TRANSCRIPT_CONTRACT", "PRESERVATION_SET PASS not exact")
        return PA.PASS, None
    return _fail_contract(lines, exit_code, rf"PRESERVATION_SET_PROOF=FAIL baseline={baseline.group(1)}",
                          "PRESERVATION_SET FAIL")


CONTRACTS: Mapping[str, Callable[[bytes, int], tuple[str, str | None]]] = {
    CUSTODY_DENIAL: _custody_denial, DEPLOYER_BOUNDARY: _deployer_boundary, BROKER_PRESERVATION: _broker_preservation,
    OS_DENIAL_UNIT: _os_denial, SECRET_HYGIENE_SCOPE: _secret_hygiene, PRESERVATION_SET_COMPARE: _preservation_set}


def admit_proof(name: str, item: Any, trust: ReadinessTrustV1) -> dict[str, Any]:
    """One proof as the verifier input form, derived from the producer's transcript bytes, or Refused."""
    _need(name in PROPOSED_PROOF_PRODUCERS, "PROOF_NAME_UNKNOWN", str(name))
    producer = PROPOSED_PROOF_PRODUCERS[name]
    _need(producer is not None, "PROOF_PRODUCER_UNMAPPED", name)
    item = _exact(item, _PROOF_FIELDS, f"proof {name}")
    _need(type(item["exitCode"]) is int, "INPUT_MALFORMED", f"proof {name}.exitCode")
    raw = _b64u_decode(item["transcript"], f"proof {name}.transcript")
    _producer_script(producer.split(":")[0])
    result, detail = CONTRACTS[producer](raw, item["exitCode"])
    digest = _sha256(raw)
    _need(digest in trust.accepted_proof_transcripts.get(name, frozenset()), "PROOF_PROVENANCE_NOT_ESTABLISHED", name)
    return {"result": result, "transcriptSha256": digest, "detail": detail}


# ------------------------------------------------------------------- build ---

def build(build_inputs: Any, *, environment: str, trust: ReadinessTrustV1 | None = None
          ) -> tuple[bytes, dict[str, Any]]:
    """(envelope bytes, report). Refuses rather than default any field."""
    trust = trust_for(environment, trust)
    pins = trust.pins
    doc = _exact(build_inputs, BUILD_FIELDS, "build")
    _need(doc["buildType"] == BUILD_TYPE and type(doc["schemaVersion"]) is int and doc["schemaVersion"] == 1,
          "INPUT_MALFORMED", "type")
    _need(doc["environment"] == environment, "ENVIRONMENT_MISMATCH", str(doc["environment"]))
    window = _exact(doc["window"], frozenset({"notBefore", "notAfter"}), "window")
    lower, upper = _instant(window["notBefore"], "notBefore"), _instant(window["notAfter"], "notAfter")
    _need(lower <= upper, "INPUT_MALFORMED", "window")
    _need(lower >= _instant(trust.not_before, "trust.not_before"), "WINDOW_BEFORE_FRESHNESS_CUTOFF",
          window["notBefore"])
    provenance: dict[str, Any] = {"window": dict(window), "freshnessCutoff": trust.not_before}

    def observed(item: Mapping[str, Any], name: str) -> None:
        at = _instant(item["observedAt"], f"{name}.observedAt")
        _need(lower <= at <= upper, "INPUT_STALE", name)
        provenance[name] = {"observedAt": item["observedAt"], "evidenceSha256": _hex(item["evidenceSha256"], name)}

    # Release provenance and the reviewed runtime digests (E-1).
    release = _exact(doc["release"], frozenset({"releaseSha", "attestedManifestSha256", "reviewedRuntimeDigests"}),
                     "release")
    _need(release["releaseSha"] == pins["releaseSha"] and _SHA40.fullmatch(release["releaseSha"]),
          "RELEASE_NOT_RECORD")
    _need(release["attestedManifestSha256"] == pins["attestedManifestSha256"], "MANIFEST_NOT_RECORD")
    reviewed = release["reviewedRuntimeDigests"]
    if reviewed is not None:
        _need(isinstance(reviewed, Mapping) and set(reviewed) <= _RUNTIME_DIGEST_NAMES and reviewed,
              "INPUT_MALFORMED", "reviewedRuntimeDigests")
        for name, value in reviewed.items():
            _hex(value, f"reviewedRuntimeDigests.{name}")

    # First-preflight CURRENT (E-4): a root observation of the pinned ciphertext; never decrypted here.
    current = _exact(doc["current"], _CURRENT_FIELDS | _OBSERVED, "current")
    observed(current, "firstPreflightCurrent")
    _need(current["path"] == SC.CURRENT_PATH and current["kind"] == WR.REGULAR and current["mode"] == "0600",
          "CURRENT_NOT_PINNED_SLOT")
    _need(current["sha256"] == pins["pinnedCurrentSha256"], "CURRENT_SHA256_NOT_PINNED")
    for name in ("device", "inode", "mtimeNs", "ctimeNs"):
        try:
            _need(PA.parse_decimal(current[name]) is not None, "INPUT_MALFORMED", name)
        except ValueError as exc:
            raise Refused("INPUT_MALFORMED", name) from exc
    _need(type(current["uid"]) is int and type(current["gid"]) is int and type(current["size"]) is int,
          "INPUT_MALFORMED", "current identity")

    # Publications (E-2, E-10): exact recorded bytes.
    kact = _b64u_decode(_exact(doc["kActPublication"], frozenset({"bytes"}), "kActPublication")["bytes"], "kAct")
    try:
        _value, parsed = SC.parse_publication_bytes(kact)
    except Exception as exc:  # noqa: BLE001
        raise Refused("KACT_PUBLICATION_INVALID", getattr(exc, "code", type(exc).__name__)) from exc
    _need(_sha256(kact) == pins["kActPublicationFileSha256"], "KACT_PUBLICATION_NOT_RECORD")
    _need(parsed.public_key_sha256 == pins["kActPublicKeySha256"], "KACT_FINGERPRINT_MISMATCH")
    kwit = _b64u_decode(_exact(doc["kWitPublication"], frozenset({"bytes"}), "kWitPublication")["bytes"], "kWit")
    try:
        witness = B.WitnessKeyPublicationV1.from_dict(B.parse_publication_document(kwit))
    except Exception as exc:  # noqa: BLE001
        raise Refused("KWIT_PUBLICATION_INVALID", getattr(exc, "code", type(exc).__name__)) from exc
    _need(witness.public_key_sha256 == pins["kWitPublicKeySha256"], "KWIT_FINGERPRINT_MISMATCH")

    # Proofs (E-7 .. E-9, E-22, E-23): producer transcript bytes with established provenance only.
    _need(isinstance(doc["proofs"], Mapping), "INPUT_MALFORMED", "proofs")
    proofs, producers = {}, {}
    for name, item in sorted(doc["proofs"].items()):
        admitted = admit_proof(name, item, trust)
        observed(item, f"proof:{name}")
        proofs[name] = admitted
        producers[name] = PROPOSED_PROOF_PRODUCERS[name]
    provenance["proofProducers"] = producers

    # Activation (E-19): the complete host line, passed verbatim.
    activation = _exact(doc["activation"], frozenset({"stdout", "exitCode", "b1cUnchanged"}) | _OBSERVED,
                        "activation")
    observed(activation, "activation")
    text = activation["stdout"]
    _need(isinstance(text, str) and text.endswith("\n") and text.count("\n") == 1, "ACTIVATION_OUTPUT_NOT_ONE_LINE")
    _need(type(activation["exitCode"]) is int and activation["exitCode"] == HOST_ACTIVATION_EXIT
          and text[:-1] == HOST_ACTIVATION_DARK_LINE, "ACTIVATION_NOT_DARK", text[:-1])
    _need(activation["b1cUnchanged"] is True, "ACTIVATION_B1C_CHANGED")

    # PR-2 / PR-3: only through the tools, on the canonical owner inputs; never a package object.
    snapshot = None
    if doc["pr2"] is not None:
        pr2 = _exact(doc["pr2"], frozenset({"inventory", "acceptance"}), "pr2")
        try:
            snapshot = I2.package_input(pr2["inventory"], pr2["acceptance"], environment=environment, trust=trust.pr2)
        except I2.Refused as exc:
            raise Refused("PR2_" + exc.reason, exc.detail) from exc
        window_start = _instant(pr2["inventory"]["window"]["startedAt"], "pr2.window")
        _need(window_start >= lower, "INPUT_STALE", "pr2.window")
        provenance["pr2"] = {"inventoryDigest": snapshot["recordSha256"],
                             "acceptanceRecordSha256": pr2["acceptance"]["acceptanceRecordSha256"]}
    material = None
    if doc["pr3"] is not None:
        pr3 = _exact(doc["pr3"], frozenset({"inputs", "confirmation"}), "pr3")
        try:
            material = M3.package_input(pr3["inputs"], pr3["confirmation"], environment=environment, trust=trust.pr3)
        except M3.Refused as exc:
            raise Refused("PR3_" + exc.reason, exc.detail) from exc
        _need(material["releaseSha"] == pins["releaseSha"]
              and material["releaseManifestSha256"] == pins["attestedManifestSha256"]
              and material["kWitPublicKeySha256"] == pins["kWitPublicKeySha256"], "OFFHOST_MATERIAL_NOT_RECORD")
        provenance["pr3"] = {"candidateDigest": pr3["confirmation"]["confirmedCandidateDigest"],
                             "confirmationRecordSha256": pr3["confirmation"]["confirmationRecordSha256"]}

    inputs = {
        "inputType": INPUT_TYPE, "schemaVersion": 1, "environment": environment,
        "releaseSha": release["releaseSha"], "attestedManifestSha256": release["attestedManifestSha256"],
        "reviewedRuntimeDigests": None if reviewed is None else dict(reviewed),
        "pinnedCurrentSha256": pins["pinnedCurrentSha256"],
        "firstPreflightCurrent": {name: current[name] for name in sorted(_CURRENT_FIELDS)},
        "kActPublication": _b64u(kact), "kWitPublication": _b64u(kwit), "proofs": proofs,
        "activation": {"line": text[:-1], "b1cUnchanged": True},
        "snapshotInventory": snapshot, "offHostMaterial": material,
    }
    envelope = {"envelopeType": ENVELOPE_TYPE, "schemaVersion": 1, "environment": environment,
                "inputsSha256": document_digest(inputs), "inputs": inputs, "provenance": provenance}
    raw = envelope_bytes(envelope)
    _need(len(raw) <= MAX_ENVELOPE, "ENVELOPE_TOO_LARGE")
    missing = [name for name in PA.REQUIRED_PROOFS if name not in proofs]
    defective = release["releaseSha"] in E19_DEFECTIVE_RELEASES
    failing = [name for name, proof in proofs.items() if proof["result"] != PA.PASS]
    report = {"envelopeSha256": _sha256(raw), "inputsSha256": envelope["inputsSha256"],
              "expectedNotReady": sorted(
                  [f"PROOF_MISSING:{name}" for name in missing] + [f"PROOF_NOT_PASS:{name}" for name in failing]
                  + (["E20_SNAPSHOT_INVENTORY:SNAPSHOT_INVENTORY_ABSENT_PR2"] if snapshot is None else [])
                  + (["E21_OFFHOST_REGISTER:OFFHOST_REGISTER_ABSENT_PR3"] if material is None else [])
                  + (["E19_ACTIVATION_DARK:ACTIVATION_NOT_DARK"] if defective else [])),
              "knownPackageDefects": list(KNOWN_PACKAGE_DEFECTS) if defective else [], "readinessEvaluated": False,
              "authorityGranted": False}
    return raw, report


def read_envelope(stream: BinaryIO | bytes, *, expected_sha256: str, environment: str) -> dict[str, Any]:
    """The host-side reader: the verifier input document, only from exactly the reviewed envelope bytes."""
    _hex(expected_sha256, "expected_sha256")
    raw = stream if isinstance(stream, bytes) else stream.read(MAX_ENVELOPE + 1)
    _need(isinstance(raw, bytes) and 0 < len(raw) <= MAX_ENVELOPE, "ENVELOPE_SIZE")
    _need(hmac.compare_digest(_sha256(raw), expected_sha256), "ENVELOPE_DIGEST_MISMATCH")

    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        _need(len(keys) == len(set(keys)), "ENVELOPE_DUPLICATE_KEY")
        return dict(pairs)
    try:
        envelope = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, ValueError) as exc:
        if isinstance(exc, Refused):
            raise
        raise Refused("ENVELOPE_MALFORMED") from exc
    envelope = _exact(envelope, ENVELOPE_FIELDS, "envelope")
    try:
        canonical = envelope_bytes(envelope)
    except Exception as exc:  # noqa: BLE001 - e.g. a non-JCS number; never a crash, never a pass
        raise Refused("ENVELOPE_NOT_CANONICAL") from exc
    _need(canonical == raw, "ENVELOPE_NOT_CANONICAL")
    _need(envelope["envelopeType"] == ENVELOPE_TYPE and type(envelope["schemaVersion"]) is int
          and envelope["schemaVersion"] == 1, "ENVELOPE_MALFORMED")
    _need(envelope["environment"] == environment, "ENVELOPE_ENVIRONMENT_MISMATCH")
    inputs = envelope["inputs"]
    _need(isinstance(inputs, Mapping) and inputs.get("inputType") == INPUT_TYPE
          and inputs.get("environment") == environment, "ENVELOPE_INPUTS_MALFORMED")
    _need(hmac.compare_digest(document_digest(inputs), str(envelope["inputsSha256"])), "INPUTS_DIGEST_MISMATCH")
    return dict(inputs)


def _load(path: str) -> Any:
    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        _need(len(keys) == len(set(keys)), "INPUT_DUPLICATE_KEY")
        return dict(pairs)
    return json.loads(Path(path).read_bytes().decode("utf-8"), object_pairs_hook=no_duplicates)


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 2 and argv[0] == "build":
            raw, report = build(_load(argv[1]), environment="dev")   # DEV trust: pins only
            sys.stdout.buffer.write(raw)
            print(json.dumps(report, sort_keys=True), file=sys.stderr)
            return 0
        if len(argv) == 2 and argv[0] == "verify-envelope":
            inputs = read_envelope(sys.stdin.buffer, expected_sha256=argv[1], environment="dev")
            sys.stdout.write(json.dumps({"envelopeSha256": argv[1], "inputsSha256": document_digest(inputs),
                                         "readinessEvaluated": False}, sort_keys=True) + "\n")
            return 0
        raise Refused("USAGE")
    except (Refused, ValueError, OSError) as exc:
        print(f"mb12_readiness_inputs: REFUSED {getattr(exc, 'reason', type(exc).__name__)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
