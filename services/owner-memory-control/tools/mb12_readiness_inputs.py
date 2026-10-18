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
  `DEV_ACCEPTED_PROOF_TRANSCRIPTS`; OD-M12-6 pins SIGNER_DENIAL, BROKER_DENIAL, OS_DENIAL, BROKER_PRESERVATION,
  PRESERVATION_SET and DEPLOYER_DENIAL; SECRET_HYGIENE is unpinned). `OS_DENIAL`,
  `SECRET_HYGIENE`, `PRESERVATION_SET` have the PR-B2 producers (`mb12_os_denial_proof`, `mb12_secret_hygiene_proof`,
  `mb12_preservation_set_proof`) with exact contracts;
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
from dataclasses import dataclass, field
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
E22_BUILD_FIELD = "e22Adjudication"                    # optional (OD-M12-10): absent = no adjudication offered
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
    "services/owner-memory-control/tools/mb12_secret_hygiene_proof.py": "83b275b480f31e88596e7ba13251987c581e3477a61ba3d75cd094d470889bb7",
    "services/owner-memory-control/tools/mb12_preservation_set_proof.py": "8b659beed2e50de6c62464cb273f1beac3d86a764750eb422b6276f42af7dde0",
}
# Producer transcripts established by a merged owner record: proof name -> accepted transcript SHA-256s.
# OD-M12-6 (owner-accepted 2026-10-16; docs/architecture/slice-15b2b-b1b3e-mb11-signer-start-operator.md §15):
# the one owner-authorized `e07` run of 2026-10-16T15:40Z (evidence lilith-mb12-e07-ef64037). One P1B-12
# transcript serves SIGNER_DENIAL and BROKER_DENIAL (OD-M11-14 mapping, accepted for these names only).
# BROKER_PRESERVATION: the one owner-authorized E-09 run of 2026-10-17T08:28Z (evidence lilith-mb12-broker-pres-5994f6a),
# owner-accepted under OD-M12-6 for this transcript only (operator record §16).
# PRESERVATION_SET: the E-23 compare of baseline 019e0117 vs the 2026-10-17T11:15:43Z observation (evidence
# lilith-e23-compare-c2cbb2d), owner-accepted under OD-M12-6 for this transcript only (operator record §18).
# DEPLOYER_DENIAL: the exact DR-5 stdout retained as artifact 12125829855 of protected-main run 39100360778
# (e6401448; evidence lilith-mb12-e08-artifact-e640144), owner-accepted under OD-M12-6 for this transcript only
# (operator record §19). SECRET_HYGIENE stays unpinned (E-22 BLOCKED).
_P1B12_TRANSCRIPT = "92dcb9aa87a40244ef02a38901f319491197b82e31fb064f6e356a57a9ec32c1"
_OS_DENIAL_TRANSCRIPT = "3cb0e744abda6a2540ad56a25e4ad1b144449833af296756eb37b0c21bd29b4a"
_BROKER_PRESERVATION_TRANSCRIPT = "79387fe7d1db1e7eab0d8e508991656ba195d284cefac3889ffff9595f221c40"
_PRESERVATION_SET_TRANSCRIPT = "4692f3bae979aca82782a66605a3235939420223aa7841a931ad9a473f1e863e"
_DEPLOYER_DENIAL_TRANSCRIPT = "4337f769d984876468379caf7b1ba59dd0d503344f942e30eedb912d2bd96c64"
DEV_ACCEPTED_PROOF_TRANSCRIPTS: Mapping[str, frozenset[str]] = {
    "SIGNER_DENIAL": frozenset({_P1B12_TRANSCRIPT}),
    "BROKER_DENIAL": frozenset({_P1B12_TRANSCRIPT}),
    "OS_DENIAL": frozenset({_OS_DENIAL_TRANSCRIPT}),
    "BROKER_PRESERVATION": frozenset({_BROKER_PRESERVATION_TRANSCRIPT}),
    "PRESERVATION_SET": frozenset({_PRESERVATION_SET_TRANSCRIPT}),
    "DEPLOYER_DENIAL": frozenset({_DEPLOYER_DENIAL_TRANSCRIPT}),
}

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


# --------------------------------------------- E-22 owner risk adjudication ---
# OD-M12-10 (owner, 2026-10-18; record slice-15b2b-b1b3e-mb12-prb2-proof-producers.md §17): a limited acceptance of the
# historical E-22 uncertainty for the DEV_SYNTHETIC K-ACT only. The object binds the verified evidence of the genuine
# off-host proof (evidence lilith-mb12-e22-realscope-f6e79eb). A later SECRET_HYGIENE FAIL qualifies only if its own
# transcript body (items, coverage, off-host lines and the four FAIL lines), its journal boot and markers, and a
# fresh marker attribution all equal what was approved here; four matching text lines alone never qualify.
E22_ADJUDICATION_V1: Mapping[str, Any] = {
    "adjudicationType": "LILITH_MB12_E22_OWNER_RISK_ADJUDICATION",
    "schemaVersion": 1,
    "decision": "OD-M12-10",
    "decidedOn": "2026-10-18",
    "environment": SC.ENVIRONMENT,
    "custodyProfile": SC.PROFILE,
    "keyId": PA.E22_ADJUDICATION_KEY_ID,
    "proof": "SECRET_HYGIENE",
    "producerSha256": "83b275b480f31e88596e7ba13251987c581e3477a61ba3d75cd094d470889bb7",
    "failures": list(PA.E22_ADJUDICATED_FAILURES),
    # SHA-256 of the approved transcript lines between the SCOPE line and the final line (ITEM, OFFHOST, COVERED and
    # the four FAIL lines, in order), each followed by LF.
    "approvedBodySha256": "6f7c86839d7f98bd5ffe790d8958d795248f6b1b0d26f13b0027031ddab1ec03",
    "journal": {
        "bootLine": "BOOT: 24d1771de1b54e5f816dda08ad8b367a firstRealtimeUs=1789322319069344 "
                    "lastRealtimeUs=1790672449937963 entries=380255",
        "markers": [["PEM_PRIVATE_KEY", 12]],
    },
    # SHA-256 of the `attribute` transcript after its first (JOURNAL) line: the 12 MATCH lines (boot 24d1771d,
    # sudo sessions 3837 / 3845 / 3850, MESSAGE / _CMDLINE, verdict UNKNOWN), COUNTS, SUMMARY, NONCLAIM and final line.
    "attribution": {"bodySha256": "4c293fd887f026e2051c6e0083e994ee97fc1ca338d5a9b18b86077a23e5d9f0", "matches": 12},
    "evidence": {
        "proofTranscriptSha256": "46a3c6414e6cf52d73cef5a2d768d9dae11134dee359eba6a9edc4a778f774fc",
        "scopeSha256": "cd073c96adfcddbe644c40b522239670ab37f622c73c18fb797940cbdf023feb",
        "proofEvidenceSums": "b355f75a2d93a4a46fec5fc9f425d9ae09a68ec9373b40d70515301484440788",
        "journalTranscriptSha256": "e1d70588e94705007492d6ad1b4daa227fcafa85e8a4961e5f42b2139866ccc5",
        "journalEvidenceSums": "0c236f8635222556c00d9a38b731459e033903747e39bc6c05f44c8ab08ea2e3",
        "attributionTranscriptSha256": "c4233055dd9d5ba5298558218794fcc9397692b8c01113474a3b3f15e8deb4a8",
        "attributionEvidenceSums": "dce427ad3c57b677a2cfe33d0cf2d8d414cd67d35b06ffe41150d66c55ae6091",
        "purposeEvidenceSums": "8bda5cbb5684eb08d133a4d4b062503c6a9bb27e7dd6f05641ad408f1d62d310",
    },
    "acceptedRisk": "private material exposure of the DEV_SYNTHETIC K-ACT test-only.dev-synthetic.actor.b1b3d.1 during "
                    "or around B1b-3d L2b cannot be conclusively excluded: 12 PEM_PRIVATE_KEY markers in three sudo "
                    "GREP sessions (purpose UNKNOWN x3); the L2b transcript was not retained; the L2b window was not "
                    "recorded",
    "nonclaims": [
        "JOURNAL_SECRET_SCAN=FAIL stands; this is not a clean scan and not a PASS",
        "no private material exposure is asserted absent",
        "the accepted L2b closure is historical evidence of execution, not proof of complete secret hygiene",
        "no other key, ceremony, environment, PROD or future private-material handling",
        "no custody release, swap, restart, authority activation or First Memory",
    ],
}
E22_ADJUDICATION_SHA256 = "9528f7338b0a832bb821884654b1b8e2a8c86c1b65f4bf17ea2be2a48cbe9989"
# Adjudications accepted by a merged owner record: adjudication SHA-256 -> owner decision record SHA-256.
# OD-M12-10 (owner decision record lilith-mb12-e22-adjudication-f6e79eb\OWNER-RISK-DECISION-RECORD.txt).
DEV_ACCEPTED_E22_ADJUDICATIONS: Mapping[str, str] = {
    E22_ADJUDICATION_SHA256: "56e71df1b7bf5c599c7d3f09edd5b12a37cf642c63d715b2f823f2ff92242c5a"}
_E22_FIELDS = frozenset({"adjudicationSha256", "scope", "journalTranscript", "attributionTranscript"}) | frozenset(
    {"observedAt", "evidenceSha256"})


@dataclass(frozen=True)
class ReadinessTrustV1:
    """What a build is judged against. DEV: `trust_for("dev", None)` only; never caller-supplied."""

    pins: Mapping[str, str]
    not_before: str
    accepted_proof_transcripts: Mapping[str, frozenset[str]]
    pr2: I2.Pr2TrustV1 | None
    pr3: M3.Pr3TrustV1 | None
    accepted_e22_adjudications: Mapping[str, str] = field(default_factory=dict)


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
                                None, None, dict(DEV_ACCEPTED_E22_ADJUDICATIONS))
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
    # A PASS is admissible only when the producer's own (pinned) scope is closed: no open scope decision, no
    # ceremony transcript recorded as not retained (OD-M12-9), every canonical record named, every DEV window recorded.
    _need(not module.UNRESOLVED_SCOPE and not module.TRANSCRIPT_NOT_RETAINED
          and all(c.record for c in ceremonies.values())
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


def adjudication_digest(adjudication: Mapping[str, Any]) -> str:
    """SHA-256(JCS(adjudication))."""
    return _sha256(rfc8785.dumps(dict(adjudication)))


def _body_sha256(lines: list[str]) -> str:
    return _sha256("".join(line + "\n" for line in lines).encode("ascii"))


def admit_e22_adjudication(item: Any, proof_item: Mapping[str, Any], admitted: Mapping[str, Any],
                           trust: ReadinessTrustV1, *, environment: str) -> str:
    """The SECRET_HYGIENE `detail` naming the owner adjudication (OD-M12-10), or Refused.

    `admitted` is the already admitted SECRET_HYGIENE proof (producer contract and OD-M12-6 pin). The result stays FAIL;
    the adjudication is only the reference the release judge resolves against its own pin."""
    _need(environment == PA.E22_ADJUDICATION_ENVIRONMENT, "E22_ADJUDICATION_OUT_OF_SCOPE", str(environment))
    item = _exact(item, _E22_FIELDS, E22_BUILD_FIELD)
    adjudication = _hex(item["adjudicationSha256"], "e22Adjudication.adjudicationSha256")
    _need(adjudication == adjudication_digest(E22_ADJUDICATION_V1) == E22_ADJUDICATION_SHA256,
          "E22_ADJUDICATION_UNKNOWN")
    _need(isinstance(trust.accepted_e22_adjudications, Mapping)
          and trust.accepted_e22_adjudications.get(adjudication) is not None, "E22_ADJUDICATION_NOT_ACCEPTED")
    spec = E22_ADJUDICATION_V1
    _need(admitted.get("result") == PA.FAIL, "E22_ADJUDICATION_NOT_FOR_FAIL")
    producer = SECRET_HYGIENE_SCOPE.split(":")[0]
    _need(PRODUCER_SCRIPT_SHA256[producer] == spec["producerSha256"], "E22_PRODUCER_CHANGED")
    module = _producer_module(producer)

    # The proof transcript: the approved body exactly (items, coverage, off-host, the four FAIL lines).
    lines = _lines(_b64u_decode(proof_item["transcript"], "proof SECRET_HYGIENE.transcript"))
    head = re.fullmatch(r"SCOPE: sha256=([0-9a-f]{64}) ceremonies=\S+", lines[0])
    _need(head is not None and lines[-1] == f"SECRET_HYGIENE_PROOF=FAIL scope={head.group(1)}",
          "E22_TRANSCRIPT_FORM")
    _need([line for line in lines if line.startswith("FAIL: ")] == list(spec["failures"]),
          "E22_FAILURE_SET_MISMATCH")
    _need(_body_sha256(lines[1:-1]) == spec["approvedBodySha256"], "E22_TRANSCRIPT_BODY_MISMATCH")

    # The scope that transcript names, and the journal transcript that scope names.
    scope_raw = _b64u_decode(item["scope"], "e22Adjudication.scope")
    _need(_sha256(scope_raw) == head.group(1), "E22_SCOPE_NOT_THE_PROVED_SCOPE")
    try:
        scope = module.parse_scope(scope_raw)
    except module.ScopeError as exc:
        raise Refused("E22_SCOPE_MALFORMED", exc.args[0]) from exc
    journal_raw = _b64u_decode(item["journalTranscript"], "e22Adjudication.journalTranscript")
    _need(_sha256(journal_raw) == scope["journalScan"]["sha256"], "E22_JOURNAL_NOT_THE_SCOPE_JOURNAL")
    failed = module.parse_journal_fail_transcript(journal_raw)
    _need(failed is not None, "E22_JOURNAL_NOT_A_FAIL_TRANSCRIPT")
    _need([list(mark) for mark in failed[1]] == spec["journal"]["markers"], "E22_JOURNAL_MARKERS_MISMATCH")
    _need(spec["journal"]["bootLine"] in _lines(journal_raw), "E22_JOURNAL_BOOT_MISMATCH")

    # A marker attribution: the same 12 attributed matches, sessions and verdicts as approved.
    attribution = _lines(_b64u_decode(item["attributionTranscript"], "e22Adjudication.attributionTranscript"))
    _need(re.fullmatch(r"JOURNAL: entries=\d+ bytes=\d+ sha256=[0-9a-f]{64} boots=\d+", attribution[0]) is not None,
          "E22_ATTRIBUTION_FORM")
    _need(_body_sha256(attribution[1:]) == spec["attribution"]["bodySha256"], "E22_ATTRIBUTION_MISMATCH")
    return PA.E22_ADJUDICATION_DETAIL_PREFIX + adjudication


# ------------------------------------------------------------------- build ---

def build(build_inputs: Any, *, environment: str, trust: ReadinessTrustV1 | None = None
          ) -> tuple[bytes, dict[str, Any]]:
    """(envelope bytes, report). Refuses rather than default any field."""
    trust = trust_for(environment, trust)
    pins = trust.pins
    _need(isinstance(build_inputs, Mapping) and set(build_inputs) in (BUILD_FIELDS, BUILD_FIELDS | {E22_BUILD_FIELD}),
          "INPUT_MALFORMED", "build")
    doc = build_inputs
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
    adjudicated = E22_BUILD_FIELD in doc
    if adjudicated:
        _need("SECRET_HYGIENE" in proofs, "E22_ADJUDICATION_WITHOUT_PROOF")
        item = doc[E22_BUILD_FIELD]
        proofs["SECRET_HYGIENE"]["detail"] = admit_e22_adjudication(item, doc["proofs"]["SECRET_HYGIENE"],
                                                                    proofs["SECRET_HYGIENE"], trust,
                                                                    environment=environment)
        observed(item, E22_BUILD_FIELD)
        provenance[E22_BUILD_FIELD]["adjudicationSha256"] = item["adjudicationSha256"]

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
    failing = [name for name, proof in proofs.items()
               if proof["result"] != PA.PASS and not (adjudicated and name == "SECRET_HYGIENE")]
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
