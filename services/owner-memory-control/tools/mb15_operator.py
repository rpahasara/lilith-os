#!/usr/bin/env python3
"""15B2b-B1b-3e M-B15 (EVALUATE_FULL_READINESS): the W14 post-RELEASED READ-ONLY verification (owner laptop).

Record: docs/architecture/slice-15b2b-b1b3e-mb15-w14-full-readiness-package.md.
DESIGN / SOURCE ONLY: no form below is authorized by this repository. `observe` contacts DEV read-only and needs a
separate owner authorization; it writes nothing on DEV, needs no go and consumes no marker.

It reuses, unchanged: the M-B14 operator (`mb14_operator.Operator`: the E-22 transport, the pinned W11 BOOT bundle,
the owner-inputs reader, the hold `observe` / staging / units read-back and its judge, the expected RELEASED record),
the W11 verifier's HEALTH, readiness summary and signer judgements, and the release verifier (`verify full` and
`verify eligibility` evaluated in-process by the read-only tail `mb15_full_remote`, never re-implemented).

| Form | Effect |
| --- | --- |
| `pins <repo>` | local: clean control checkout; every pinned tool exact; this operator at control |
| `observe <repo> <outdir> <envelope>` | read-only DEV: hold `observe`, staging path, units, then ONE `mb15_full_remote full` (both modes over one HEALTH frame and one hold observation); W14 judged into a fresh `<outdir>` |
| `classify <outdir>` | local, off-host: W14 re-judged from the retained transcripts only (the independent reproduction); package digests recomputed |

W14 judges only what a root observer can see now. It never decides owner freshness (the S25 Replica B read), the
preservation set, the owner-input envelope's currency, or the M-B15 owner decision, and reports each as OUTSTANDING.

    W14_1 (technical) != M-B15 established != owner acceptance != activation != Registry V1 effective != First Memory
    FULL_READINESS READY = local issuance readiness facts only; issuance stays unwired (RR-39);  UNKNOWN != success
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mb14_operator as MB14  # noqa: E402  (pinned M-B14 operator; reused unchanged)
import mb15_full_remote as F  # noqa: E402  (pinned below)

E22 = MB14.E22
J = E22.J
Stop = MB14.Stop
_need = MB14._need
sha256_hex = MB14.sha256_hex

OPERATOR = E22.T + "mb15_operator.py"
REMOTE = E22.T + "mb15_full_remote.py"
TOOL_PINS = {
    **MB14.TOOL_PINS,
    MB14.OPERATOR: "37db0b0308673ac709fe3229772d7cba230e9917fe108db96e03aa39a9222028",
    REMOTE: "9021982a3a498de467747d49dc2705153a3503eb902b6b0616cbe64ee27722d6",
}

# The accepted bindings (repository records only; never host values).
SIGNER = MB14.SIGNER                                                    # E-22 completion: accepted V6 signer
WITNESS = ("8cbfbed20c954c478425c7233084ce17", "127192")                 # E-22 completion: accepted V5 witness
RELEASE_CWD = "/opt/lilith-authority-dev/releases/" + str(J.NEW_RELEASE)  # E-22 V7: the only installed release
FULL, ELIGIBILITY = "FULL_READINESS", "HOLD_RELEASE_ELIGIBILITY"
# The post-RELEASED eligibility outcome the release contract produces (`successor_readiness.hold_binding_reason`,
# `pr1_acceptance._hold_store_reason`; reproduced on the synthetic host by the tests): NOT_READY for the hold only.
ELIGIBILITY_READINESS_REASONS = ("CEREMONY_HOLD:HOLD_NOT_HELD",)
ELIGIBILITY_PACKAGE_REASONS = ("E16_HOLD_STORE:CEREMONY_HOLD:HOLD_NOT_HELD", "E17_READINESS:READINESS_NOT_READY")
# Authority darkness under RELEASED: no grant, no live entry, no activation, issuance unwired. `issuanceReady` and
# `successorCurrent` are readiness FACT NAMES the contract sets at FULL_READINESS READY; they are reported, and are
# never darkness failures here (W11 treats them as HALT only because FULL must not be READY while HELD).
DARK_FALSE_FACTS = ("authorityGranted", "liveEntryAuthorized")
ADJUDICATED_E22 = "OWNER_RISK_ADJUDICATED"
# Provenance of the FULL package checks (`pr1_acceptance.evaluate_pr1_acceptance`). These PASS on the owner-supplied
# input envelope, not on a live host read: E-19 is the activation line in the envelope (`inputs.activation`), the
# proofs are owner transcripts, E-20 / E-21 the owner's PR-2 / PR-3 material. W14 reports their status; it never
# observes them, and never judges whether the envelope is current.
OWNER_INPUT_CHECKS = ("E07_SIGNER_CUSTODY_DENIAL", "E08_DEPLOYER_DENIAL", "E09_BROKER_DENIAL_PRESERVATION",
                      "E19_ACTIVATION_DARK", "E20_SNAPSHOT_INVENTORY", "E21_OFFHOST_REGISTER", "E22_SECRET_HYGIENE",
                      "E23_PRESERVATION_SET")
# A live observation compared against an owner-supplied pin or material.
OWNER_INPUT_BOUND_CHECKS = ("E04_CURRENT_PRESERVED", "E18_OFFHOST_REPRODUCTION_INPUTS")
ACTIVATION_SOURCE = "OWNER_ENVELOPE_ACTIVATION_LINE"

W14_1 = "W14_1_RELEASED_FULL_READY_OBSERVED"
W14_STOP = "W14_STOP"
OUTSTANDING = ("OWNER_FRESHNESS_CURRENT_S25_REPLICA_B", "PRESERVATION_SET_RELEASED_PINS", "OWNER_INPUT_ENVELOPE_CURRENCY",
               "OWNER_OFFHOST_REPRODUCTION_AND_DECISION", "DR5_AND_PREVIEW_AT_M_B15_TIME", "PENDING_REBOOT_WINDOW")
OBSERVATION_FILE, W14_FILE = "OBSERVATION.json", "W14.json"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def expected(document: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Everything W14 compares against: the M-B14 expected RELEASED (re-derived), the accepted identities."""
    doc = dict(document) if document is not None else MB14.expected_document()
    return {"name": doc["name"], "ceremonyId": doc["ceremonyId"], "genesis": doc["genesis"],
            "released": doc["released"], "held": doc["held"], "environment": "dev",
            "signer": list(SIGNER), "witness": list(WITNESS), "releaseCwd": RELEASE_CWD}


# ------------------------------------------------------------------ judges ---

def _w() -> Any:
    import mb11_signer_verifier as W  # noqa: N811  (pinned via the W11 bundle; pure judgements reused)

    return W


def judge_package(report: Any, mode: str, exp: Mapping[str, Any]) -> list[str]:
    """One `verifier.report` of the given mode: well-formed, its digest recomputed here, and (FULL) every check PASS
    (E-22 may be the pinned owner-risk adjudication) over exactly the expected RELEASED. The package's
    `authorityGranted` / `activationGranted` / `issuanceWired` are CONTRACT CONSTANTS (always false in
    `pr1_acceptance._package`): checking them detects only tampering or a contract change, never live activation."""
    from lilith_owner_memory import pr1_acceptance as PA

    tag = "FULL" if mode == FULL else "ELIGIBILITY"
    if not isinstance(report, Mapping) or report.get("mode") != mode or not isinstance(report.get("package"), Mapping):
        return [f"{tag}_REPORT_MISSING"]
    package = report["package"]
    reasons = []
    if not isinstance(report.get("packageDigest"), str) or _HEX64.fullmatch(report["packageDigest"]) is None \
            or PA.package_digest(package) != report["packageDigest"]:
        reasons.append(f"{tag}_PACKAGE_DIGEST_NOT_REPRODUCED")
    if (package.get("mode"), package.get("environment"), package.get("scope")) != (mode, exp["environment"],
                                                                                  "PR1_INITIAL_CUSTODY") \
            or package.get("status") != report.get("status"):
        reasons.append(f"{tag}_PACKAGE_NOT_THIS_SCOPE")
    if any(package.get(flag) is not False for flag in ("authorityGranted", "activationGranted", "issuanceWired")) \
            or report.get("authorityGranted") is not False:
        reasons.append(f"{tag}_AUTHORITY_NOT_DARK")
    evidence = package.get("evidence") if isinstance(package.get("evidence"), Mapping) else {}
    holds = evidence.get("holdStore") if isinstance(evidence.get("holdStore"), Mapping) else {}
    if holds.get("records") != [[exp["ceremonyId"], "INITIAL_CUSTODY", "RELEASED"]] \
            or holds.get("listingDigest") != exp["released"]["listingDigest"]:
        reasons.append(f"{tag}_PACKAGE_HOLD_NOT_THE_RELEASED")
    witness = evidence.get("witness") if isinstance(evidence.get("witness"), Mapping) else {}
    if witness.get("classification") != "CONSISTENT" or witness.get("chainLength") != 1 \
            or witness.get("headDigest") != exp["genesis"] or witness.get("genesisDigest") != exp["genesis"]:
        reasons.append(f"{tag}_WITNESS_HEAD_NOT_GENESIS")
    checks = package.get("checks") if isinstance(package.get("checks"), Mapping) else {}
    if mode == FULL:
        if report.get("status") != "READY" or report.get("reasons") != []:
            reasons.append("FULL_NOT_READY")
        if set(checks) != set(PA.PACKAGE_CHECKS) or any(
                value[0] != PA.PASS and not (name == "E22_SECRET_HYGIENE" and value[0] == ADJUDICATED_E22)
                for name, value in checks.items()):
            reasons.append("FULL_CHECKS_NOT_ALL_PASS")
        elif checks["E22_SECRET_HYGIENE"][0] == ADJUDICATED_E22 and not e22_adjudication_accepted(package):
            reasons.append("FULL_E22_ADJUDICATION_NOT_ACCEPTED")
    elif report.get("status") != "NOT_READY" or tuple(report.get("reasons") or ()) != ELIGIBILITY_PACKAGE_REASONS:
        reasons.append("ELIGIBILITY_NOT_EXACTLY_THE_RELEASED_HOLD")
    return reasons


def e22_adjudication_accepted(package: Mapping[str, Any]) -> bool:
    """An E-22 OWNER_RISK_ADJUDICATED check names exactly an owner-accepted adjudication (OD-M12-10) and carries its
    pinned evidence and nonclaim, as `pr1_acceptance` writes them. Any other identifier is not admitted."""
    from lilith_owner_memory import pr1_acceptance as PA

    adjudication = (package.get("checks") or {}).get("E22_SECRET_HYGIENE", [None, None])[1]
    if not isinstance(adjudication, str) or adjudication not in PA.ACCEPTED_E22_ADJUDICATIONS:
        return False
    evidence = (package.get("evidence") or {}).get("secretHygieneAdjudication")
    if not isinstance(evidence, Mapping) or not isinstance(evidence.get("transcriptSha256"), str) \
            or _HEX64.fullmatch(evidence["transcriptSha256"]) is None:
        return False
    expected = {"status": PA.OWNER_RISK_ADJUDICATED, "decision": "OD-M12-10", "adjudicationSha256": adjudication,
                "ownerRecordSha256": PA.ACCEPTED_E22_ADJUDICATIONS[adjudication], "keyId": PA.E22_ADJUDICATION_KEY_ID,
                "transcriptSha256": evidence["transcriptSha256"], "failures": list(PA.E22_ADJUDICATED_FAILURES),
                "nonclaim": PA.E22_ADJUDICATION_NONCLAIM}
    return json.loads(json.dumps(dict(evidence))) == json.loads(json.dumps(expected)) \
        and PA.E22_ADJUDICATION_NONCLAIM in (package.get("nonclaims") or [])


def judge_summary(summary: Any, mode: str) -> list[str]:
    """The W11 `_summary` of the same evaluation: the readiness reasons, the loaded-key binding, darkness."""
    tag = "FULL" if mode == FULL else "ELIGIBILITY"
    if not isinstance(summary, Mapping):
        return [f"{tag}_SUMMARY_MISSING"]
    reasons = []
    if mode == FULL and (summary.get("status") != "READY" or summary.get("reasons") != []):
        reasons.append("FULL_READINESS_NOT_READY")
    if mode == ELIGIBILITY and (summary.get("status") != "NOT_READY"
                                or tuple(summary.get("reasons") or ()) != ELIGIBILITY_READINESS_REASONS):
        reasons.append("ELIGIBILITY_READINESS_NOT_EXACTLY_HOLD_NOT_HELD")
    if mode == FULL and (summary.get("loadedKeyBinding") or {}).get("status") != "PASS":
        reasons.append("FULL_LOADED_KEY_BINDING_NOT_PASS")
    facts = summary.get("facts") if isinstance(summary.get("facts"), Mapping) else {}
    flags = summary.get("packageFlags") if isinstance(summary.get("packageFlags"), Mapping) else {}
    if any(facts.get(key) is not False for key in DARK_FALSE_FACTS) \
            or any(flags.get(key) is not False for key in ("authorityGranted", "activationGranted", "issuanceWired")):
        reasons.append(f"{tag}_AUTHORITY_NOT_DARK")
    return reasons


def judge_signer(remote: Mapping[str, Any], exp: Mapping[str, Any]) -> list[str]:
    """The W11 signer facts under RELEASED: one exact RUNNING incarnation (the accepted one), from this release, the
    credentials directory with exactly one name, the root 0600 owner socket, the effective restart boundary, the
    signer HEALTH exactly H (a claim: still NOT_READY), bound before and after to that incarnation."""
    W = _w()
    reasons = []
    signer = remote.get("signer") if isinstance(remote.get("signer"), Mapping) else {}
    units, paths = signer.get("units"), signer.get("paths") or {}
    if not isinstance(units, Mapping) or not isinstance(paths.get("credentials"), Mapping) \
            or not isinstance(paths.get("ownerSocket"), Mapping):
        return ["SIGNER_UNOBSERVED"]
    service = units.get(W.SIGNER_SERVICE) or {}
    if W._signer_state(units, paths) != "RUNNING":
        reasons.append("SIGNER_NOT_RUNNING")
    current = [service.get("InvocationID"), service.get("MainPID")]
    if current != list(exp["signer"]) or service.get("NRestarts") != "0":
        reasons.append("SIGNER_NOT_THE_ACCEPTED_INCARNATION")
    for name in W.SIGNER_UNITS:
        facts = units.get(name) or {}
        if facts.get("UnitFileState") not in ("static", "") or facts.get("LoadState") != "loaded" \
                or facts.get("NeedDaemonReload") != "no":
            reasons.append("UNIT_NOT_STATIC_LOADED_CURRENT:" + name)
    process = signer.get("process")
    if not isinstance(process, Mapping) or process.get("cwd") != exp["releaseCwd"] \
            or tuple(process.get("argv") or ()) != W.EXEC_ARGV:
        reasons.append("PROCESS_NOT_THE_RELEASE_SIGNER")
    if paths["credentials"].get("kind") != "dir" or paths["credentials"].get("names") != [W.CREDENTIAL_NAME]:
        reasons.append("CREDENTIALS_DIRECTORY_NOT_EXACTLY_ONE_NAME")
    sock = paths["ownerSocket"]
    if (sock.get("kind"), sock.get("uid"), sock.get("gid"), sock.get("mode")) != ("socket", 0, 0, 0o600):
        reasons.append("OWNER_SOCKET_NOT_ROOT_0600")
    boundary = remote.get("restartBoundary")
    if not isinstance(boundary, Mapping) or boundary.get("reasons") != []:
        reasons.append("RESTART_BOUNDARY_NOT_EFFECTIVE")
    capture = remote.get("healthCapture") if isinstance(remote.get("healthCapture"), Mapping) else {}
    bound = {"InvocationID": exp["signer"][0], "MainPID": exp["signer"][1]}
    if capture.get("attempted") is not True or capture.get("before") != bound or capture.get("after") != bound:
        reasons.append("HEALTH_NOT_BOUND_TO_THE_ACCEPTED_INCARNATION")
    health = capture.get("health")
    reasons += W.health_mismatches(health)
    if isinstance(health, Mapping) and health.get("publicKeySha256") != W.B3_PUBLIC_KEY_SHA256:
        reasons.append("HEALTH_FINGERPRINT_NOT_B3")
    ledger = remote.get("ledger") if isinstance(remote.get("ledger"), Mapping) else {}
    if ledger.get("readable") is not True or set(ledger.get("listing") or {}) != {W.LEDGER_NAME}:
        reasons.append("LEDGER_NOT_EXACTLY_THE_DATABASE")
    return reasons


def judge(read: Mapping[str, Any], remote: Any, exp: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """W14, pure: the M-B14 read-back (hold, staging, units) plus the `full` tail. W14_1 only when every part is exact.
    Missing, malformed or unexpected evidence is a reason, never a default."""
    exp = exp or expected()
    reasons: list[str] = []
    codes = read.get("codes") if isinstance(read.get("codes"), Mapping) else {}
    if set(codes) != {"observe", "stage", "units"} or any(code != 0 for code in codes.values()):
        reasons.append("READBACK_NOT_COMPLETE")
    if (read.get("hold") or {}).get("class") != MB14.RELEASED_EXACT:
        reasons.append("HOLD_NOT_EXACTLY_THE_RELEASED:" + str((read.get("hold") or {}).get("class")))
    if read.get("stage") != "ABSENT":
        reasons.append("STAGING_PATH_NOT_ABSENT")
    if list(read.get("signer") or []) != list(exp["signer"]):
        reasons.append("UNITS_SIGNER_NOT_THE_ACCEPTED_INCARNATION")
    if list(read.get("witness") or []) != list(exp["witness"]):
        reasons.append("UNITS_WITNESS_NOT_THE_ACCEPTED_INCARNATION")
    facts: dict[str, Any] = {}
    if not isinstance(remote, Mapping) or remote.get("remoteType") != F.REMOTE_TYPE \
            or remote.get("authorityGranted") is not False:
        reasons.append("FULL_REMOTE_NOT_RECEIVED")
    else:
        readiness = remote.get("readiness")
        if not isinstance(readiness, Mapping):
            reasons.append("READINESS_NOT_EVALUATED")
        else:
            if readiness.get("holdListingDigest") != exp["released"]["listingDigest"]:
                reasons.append("READINESS_HOLD_LISTING_NOT_THE_RELEASED")
            reasons += judge_package(readiness.get("full"), FULL, exp)
            reasons += judge_package(readiness.get("eligibility"), ELIGIBILITY, exp)
            reasons += judge_summary(readiness.get("fullSummary"), FULL)
            reasons += judge_summary(readiness.get("eligibilitySummary"), ELIGIBILITY)
            full = readiness.get("full") if isinstance(readiness.get("full"), Mapping) else {}
            package = full.get("package") if isinstance(full.get("package"), Mapping) else {}
            checks = package.get("checks") if isinstance(package.get("checks"), Mapping) else {}
            evidence = package.get("evidence") if isinstance(package.get("evidence"), Mapping) else {}
            facts = {"fullPackageDigest": full.get("packageDigest"), "fullStatus": full.get("status"),
                     "eligibilityStatus": (readiness.get("eligibility") or {}).get("status"),
                     "fullFacts": (readiness.get("fullSummary") or {}).get("facts"),
                     "ownerInputChecks": {name: (checks.get(name) or [None])[0] for name in OWNER_INPUT_CHECKS},
                     "ownerInputBoundChecks": {name: (checks.get(name) or [None])[0]
                                               for name in OWNER_INPUT_BOUND_CHECKS},
                     "activationEvidence": evidence.get("activation")}
        reasons += judge_signer(remote, exp)
    return {"w14": W14_1 if not reasons else W14_STOP, "reasons": reasons, **facts,
            "releasedSha256": exp["released"]["sha256"], "releasedListingDigest": exp["released"]["listingDigest"],
            "signer": list(exp["signer"]), "witness": list(exp["witness"]),
            "activationDarkSource": ACTIVATION_SOURCE, "activationObservedLive": False,
            "envelopeCurrency": "NOT_JUDGED", "ownerFreshness": "NOT_EVALUATED",
            "outstanding": list(OUTSTANDING), "mb15Established": False, "authorityGranted": False}


# ------------------------------------------------------------------ operator ---

class Operator(MB14.Operator):
    """The M-B14 transport and read-back, unchanged; every pin lookup is this operator's."""

    def tool_bytes(self, repo: Path, path: str) -> bytes:
        data = self._git(repo, "show", f"HEAD:{path}")
        _need(sha256_hex(data) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return data

    def pins(self, repo: Path) -> dict:
        base = super().pins(repo)                      # the M-B14 operator's own check (it must be at control too)
        for path in (MB14.OPERATOR, REMOTE):
            self.tool_bytes(repo, path)
        for module, path in ((MB14, MB14.OPERATOR), (F, REMOTE)):
            _need(sha256_hex(Path(module.__file__).read_bytes()) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        operator = sha256_hex(self._git(repo, "show", f"HEAD:{OPERATOR}"))
        _need(operator == sha256_hex(Path(__file__).read_bytes()), "OPERATOR_NOT_AT_CONTROL")
        return {"control": base["control"], "operatorSha256": operator, "result": "MB15_TOOL_PINS_EXACT"}

    @staticmethod
    def bundle_payload(read: Any, doc: Mapping[str, Any]) -> tuple[bytes, str]:
        """(the base64 payload, the BOOT pin list): the pinned W11 sources, the generated evidence, the E-22 tail,
        then the `full` tail (the entry point). `read(path)` returns pin-checked tool bytes."""
        import base64
        import gzip

        sources = {Path(path).stem: read(path).decode("utf-8") for path in E22.W11_BUNDLE}
        sources[F.EVIDENCE_MODULE] = F.evidence_module_source(doc)
        for path in (E22.REMOTE, REMOTE):
            sources[Path(path).stem] = read(path).decode("utf-8")
        payload = base64.b64encode(gzip.compress(json.dumps(sources).encode("utf-8"), mtime=0))
        return payload, ",".join(f"{name}={sha256_hex(text.encode('utf-8'))}" for name, text in sources.items())

    @staticmethod
    def local_tool(path: str) -> bytes:
        """Off-host: a pinned tool from THIS checkout, required byte-equal to its pin."""
        data = (HERE.parents[2] / path).read_bytes()
        _need(sha256_hex(data) == TOOL_PINS[path], "TOOL_PIN_MISMATCH:" + path)
        return data

    @staticmethod
    def code_identity(payload: bytes) -> dict[str, str]:
        """The verification code of one observation: this operator, the pin table, the `full` tail, and the exact
        stdin bundle the host checked before running (the command's own payload digest, exit 96 otherwise)."""
        return {"operatorSha256": sha256_hex(Path(__file__).read_bytes()),
                "toolPinsSha256": sha256_hex(json.dumps(TOOL_PINS, sort_keys=True).encode("ascii")),
                "remoteSha256": TOOL_PINS[REMOTE], "bundlePayloadSha256": sha256_hex(payload)}

    def full_bundle(self, repo: Path, doc: dict) -> tuple[str, bytes]:
        """The reviewed mb6 BOOT stdin bundle (`bundle_payload` over the control's pinned bytes)."""
        import base64

        payload, pins = self.bundle_payload(lambda path: self.tool_bytes(repo, path), doc)
        boot = base64.b64encode(E22.M6.BOOT.encode("ascii")).decode("ascii")
        loader = f"import base64;exec(base64.b64decode('{boot}'))"
        command = (f"B=$(cat); printf %s \"$B\" | sha256sum | cut -c1-64 | grep -qx '{sha256_hex(payload)}' || exit 96; "
                   f"printf %s \"$B\" | base64 -d | sudo -n {E22.M9.RELEASE_PYTHON} -I -B -c \"{loader}\" "
                   f"{pins} {Path(REMOTE).stem} {doc['form']} {F.evidence_digest(doc)}")
        return command, payload + b"\n"

    @staticmethod
    def parse_remote(code: int | None, raw: bytes, doc: Mapping[str, Any]) -> dict | None:
        """The tail's document only if it ran (exit 0) and echoes exactly this evidence."""
        try:
            value = json.loads(raw.decode("utf-8")) if code == 0 else None
        except (UnicodeDecodeError, ValueError):
            return None
        if not isinstance(value, dict) or value.get("remoteType") != F.REMOTE_TYPE or value.get("form") != doc["form"] \
                or value.get("evidenceSha256") != F.evidence_digest(doc):
            return None
        return value

    def observe(self, repo: Path, outdir: Path, envelope: Path) -> dict:
        """ONE read-only W14 observation: the M-B14 read-back, then ONE `full` tail invocation; judged into outdir."""
        pins = self.pins(repo)
        outdir = Path(outdir)
        _need(not outdir.exists(), "OUTDIR_EXISTS")
        raw = Path(envelope).read_bytes()
        inputs = self.owner_inputs(raw)                          # the pinned reader's refusal is a STOP
        exp_doc = MB14.expected_document()
        outdir.mkdir(mode=0o700, parents=True)
        (outdir / MB14.ENVELOPE_FILE).write_bytes(raw)
        self._record(outdir / MB14.EXPECTED_FILE, exp_doc)
        self._readback(outdir, exp_doc)                          # observe / stage / units, each its own transcript
        doc = {"form": "full", "ownerInputs": inputs}
        F.check_evidence(doc, "full")
        command, stdin = self.full_bundle(repo, doc)
        self._save(outdir, "full", self._invoke_once(command, stdin))
        self._record(outdir / OBSERVATION_FILE, {
            "control": pins["control"], "codeIdentity": self.code_identity(stdin.rstrip(b"\n")),
            "envelopeSha256": sha256_hex(raw), "evidenceSha256": F.evidence_digest(doc), "observedAt": self._now(),
            "transcripts": {p.name: sha256_hex(p.read_bytes()) for p in sorted(outdir.iterdir())
                            if p.is_file() and p.suffix in (".out", ".err", ".rc")}})
        return self.classify(outdir)

    def classify(self, outdir: Path) -> dict:
        """Off-host: W14 from the retained transcripts only (no DEV, no clock); the transcript digests re-checked."""
        outdir = Path(outdir)
        observation = MB14.Operator._json(outdir / OBSERVATION_FILE, "OBSERVATION_INVALID")
        _need(all(sha256_hex((outdir / name).read_bytes()) == digest
                  for name, digest in (observation.get("transcripts") or {}).items())
              and {"observe.out", "stage.out", "units.out", "full.out"} <= set(observation.get("transcripts") or {}),
              "TRANSCRIPTS_CHANGED_OR_MISSING")
        _need(sha256_hex((outdir / MB14.ENVELOPE_FILE).read_bytes()) == observation.get("envelopeSha256"),
              "ENVELOPE_CHANGED")
        exp_doc = json.loads((outdir / MB14.EXPECTED_FILE).read_bytes())
        _need(exp_doc == json.loads(json.dumps(MB14.expected_document())), "EXPECTED_NOT_REDERIVED")
        read = self._reread(outdir, exp_doc)
        doc = {"form": "full", "ownerInputs": self.owner_inputs((outdir / MB14.ENVELOPE_FILE).read_bytes())}
        _need(F.evidence_digest(doc) == observation.get("evidenceSha256"), "EVIDENCE_NOT_THE_OBSERVED")
        # The classifier must be the code that observed: rebuild the exact bundle from this checkout's pinned bytes.
        payload, _pins = self.bundle_payload(self.local_tool, doc)
        _need(observation.get("codeIdentity") == self.code_identity(payload), "CODE_NOT_THE_OBSERVED_CODE")
        remote = self.parse_remote(self._rc(outdir, "full"), (outdir / "full.out").read_bytes(), doc)
        result = judge(read, remote, expected(exp_doc))
        result.update(envelopeSha256=observation["envelopeSha256"], control=observation.get("control"),
                      codeIdentity=observation["codeIdentity"],
                      observationSha256=sha256_hex((outdir / OBSERVATION_FILE).read_bytes()))
        path = outdir / W14_FILE
        if path.exists():                    # a later re-classification must reproduce the recorded judgement
            _need(MB14.Operator._json(path, "W14_RECORD_INVALID") == json.loads(json.dumps(result)),
                  "W14_RECORD_DIFFERS_FROM_REJUDGEMENT")
        else:
            self._record(path, result)
        return dict(result, w14Sha256=sha256_hex(path.read_bytes()),
                    next="nothing is authorized: freshness, preservation, the envelope and the owner decision stay "
                         "OUTSTANDING")

    @staticmethod
    def _rc(outdir: Path, name: str) -> int | None:
        text = (Path(outdir) / f"{name}.rc").read_text(encoding="ascii").strip()
        return int(text) if re.fullmatch(r"-?\d+", text) else None

    def _reread(self, outdir: Path, exp_doc: Mapping[str, Any]) -> dict[str, Any]:
        """The M-B14 read-back judged again from its retained transcripts (the same judge, no invocation)."""
        codes = {name: self._rc(outdir, name) for name in ("observe", "stage", "units")}
        hold = MB14.judge_observe(codes["observe"], (outdir / "observe.out").read_bytes(), exp_doc)
        stage = (outdir / "stage.out").read_bytes().strip()
        units = MB14.parse_units((outdir / "units.out").read_bytes()) if codes["units"] == 0 else {}
        return {"codes": codes, "hold": hold,
                "stage": {b"STAGE=absent": "ABSENT", b"STAGE=present": "PRESENT"}.get(stage, "UNKNOWN")
                if codes["stage"] == 0 else "UNKNOWN",
                "signer": list(MB14.identity(units, E22.SIGNER_SERVICE)),
                "witness": list(MB14.identity(units, E22.WITNESS_SERVICE))}


def main(argv: Sequence[str], operator: Operator | None = None) -> int:
    operator = operator or Operator()
    forms = {
        ("pins", 1): lambda a: operator.pins(Path(a[0])),
        ("observe", 3): lambda a: operator.observe(Path(a[0]), Path(a[1]), Path(a[2])),
        ("classify", 1): lambda a: operator.classify(Path(a[0])),
    }
    form = forms.get((argv[0], len(argv) - 1)) if argv else None
    if form is None:
        print(__doc__.split("| Form |", 1)[1].split("\n\n", 1)[0], file=sys.stderr)
        return 2
    try:
        result = form(list(argv[1:]))
    except Stop as exc:
        print(f"mb15_operator: STOP {exc.code}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
