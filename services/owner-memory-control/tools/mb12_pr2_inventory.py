#!/usr/bin/env python3
"""15B2b-B1b-3e M-B12 PR-B1: PR-2 snapshot-inventory construction and validation (control side, pure).

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb1-prerequisite-tooling.md.
REPOSITORY ONLY. It reads no host, no provider API and no credential; it never lists, creates or restores a snapshot.
It turns one caller-supplied inventory document (the read-only PR-2 provider and host listing, collected elsewhere) into
the closed RR-7 / RR-17 classification and, only when an owner acceptance names this exact inventory digest, into the
`snapshotInventory` input of the PR-1 package (E-20, `pr1_acceptance.SnapshotInventoryResultV1`).

Canonical rules applied unchanged (never weakened):

- gate §5.2 / §5.6 (RR-7, RR-17) and preflight §21: the minimum class of each artefact from what it holds, where it
  lies and whether its access history is known; `UNKNOWN_PROVENANCE` fails closed;
- the host credential key (`credential.secret`) seals every credential ciphertext on the host: an artefact holding it
  reclassifies every K-ACT and K-WIT ciphertext under it (preflight §21, row 3);
- E-20: every K-ACT, K-WIT and host-key artefact is `SAFE_RETAINED_CIPHERTEXT` or bounded, documented
  `KNOWN_CUSTODY_DEBT` with a named debt; `pr1_acceptance._snapshot_reason` is the package judge.

Evidence classes are never interchangeable:

    SYNTHETIC_FIXTURE  -> classified, never ACCEPTED, never a package input
    LIVE_OBSERVATION   -> classified; a package input only with an owner acceptance of this exact inventory digest
    classification PASS != owner acceptance;  owner acceptance != freshness at a later step;  inventory != authority

Forms (off-host, stdlib + rfc8785):

    ... classify <inventory.json>                         the classification report
    ... package-input <inventory.json> <acceptance.json> <notBefore>   the E-20 verifier input, or REFUSED
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import rfc8785

INVENTORY_TYPE = "LILITH_PR2_SNAPSHOT_INVENTORY"
INVENTORY_SCHEMA_VERSION = 1
INVENTORY_DOMAIN = b"LILITH_PR2_SNAPSHOT_INVENTORY_V1\x00"
ACCEPTANCE_TYPE = "LILITH_PR2_INVENTORY_OWNER_ACCEPTANCE"

SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
LIVE_OBSERVATION = "LIVE_OBSERVATION"
EVIDENCE_CLASSES = (SYNTHETIC_FIXTURE, LIVE_OBSERVATION)

# The complete provider listing PR-2 performed (record slice-15b2b-b1b3e-pr2-snapshot-inventory.md). A kind that is
# missing or not complete makes the whole inventory UNKNOWN_PROVENANCE.
LISTING_KINDS = ("DISK_SNAPSHOTS", "INSTANT_SNAPSHOTS", "IMAGES", "MACHINE_IMAGES", "SNAPSHOT_SCHEDULES",
                 "BACKUP_DR", "BUCKETS", "ADMIN_ACTIVITY_CREATE_CALLS")
ARTEFACT_KINDS = LISTING_KINDS[:-1]

# The custody roles PR-2 must relate (E-20). Both credential ciphertexts are sealed under the host credential key.
K_ACT, K_WIT, HOST_KEY = "K_ACT", "K_WIT", "HOST_KEY"
KEY_ROLES = (K_ACT, K_WIT, HOST_KEY)
SEALED_UNDER_HOST_KEY = (K_ACT, K_WIT)
MATERIAL = {"K_ACT_CIPHERTEXT": K_ACT, "K_WIT_CIPHERTEXT": K_WIT, "HOST_KEY_SECRET": HOST_KEY}
PLAINTEXT = "PLAINTEXT_PRIVATE"

INSIDE = "INSIDE_ACCEPTED_INVENTORIED_ENVIRONMENT"
OUTSIDE = "OUTSIDE_ACCEPTED_BOUNDARY"
LOCATIONS = (INSIDE, OUTSIDE)
KNOWN, UNKNOWN = "KNOWN", "UNKNOWN"

# gate §5.2, most severe first (a key's action follows its worst artefact).
COMPROMISED = "COMPROMISED"
EXPOSED = "EXPOSED_PRIVATE_MATERIAL"
UNKNOWN_PROVENANCE = "UNKNOWN_PROVENANCE"
STALE = "STALE_CREDENTIAL_PRESENT"
DEBT = "KNOWN_CUSTODY_DEBT"
SAFE = "SAFE_RETAINED_CIPHERTEXT"
NO_SNAPSHOTS = "NO_SNAPSHOTS"
SEVERITY = (COMPROMISED, EXPOSED, UNKNOWN_PROVENANCE, STALE, DEBT, SAFE, NO_SNAPSHOTS)
PERMITTED = frozenset({SAFE, DEBT, NO_SNAPSHOTS})          # = pr1_acceptance.SNAPSHOT_CLASSES_PERMITTED

# Accepted public identities on DEV (repository records; never host values, never private material).
DEV_KEY_IDENTITIES = {
    K_ACT: "dd13a1fb302375a4e7ec81131a72920e23e365e06a0b6dc9bb7ab124dadc01ed",   # B3, M-B3 completion
    K_WIT: "5d778701def439b6c896392750c12685c26b67edfc908bed1a80f02eab0d0bdf",   # M-B2 completion
}
# Recorded non-snapshot debt carried forward (M-B2 completion, crash window C-4). Named, never dropped.
DEV_CARRIED_DEBTS = ("C-4",)

INVENTORY_FIELDS = frozenset({"inventoryType", "schemaVersion", "environment", "evidenceClass", "window",
                              "keys", "listings", "artefacts", "carriedDebts", "privateEvidenceSha256"})
_WINDOW_FIELDS = frozenset({"startedAt", "endedAt"})
_KEY_FIELDS = frozenset({"role", "publicKeySha256", "sealedUnder"})
_LISTING_FIELDS = frozenset({"kind", "complete", "count", "listingSha256"})
_ARTEFACT_FIELDS = frozenset({"artefactId", "kind", "material", "location", "accessHistory", "debtName"})
_DEBT_FIELDS = frozenset({"name", "role", "recordSha256"})
ACCEPTANCE_FIELDS = frozenset({"acceptanceType", "schemaVersion", "environment", "acceptedInventoryDigest",
                               "acceptanceRecordSha256", "acceptedAt"})
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}\Z")
_DEBT_NAME = re.compile(r"[A-Z0-9][A-Z0-9._-]{0,63}\Z")

NONCLAIMS = ("snapshot inventory != authority", "classification PASS != owner acceptance",
             "wholeHostRollbackProtected: false", "inventory freshness ends at its window")


class Refused(ValueError):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason if detail is None else f"{reason}:{detail}")
        self.reason = reason
        self.detail = detail


def _need(condition: bool, reason: str, detail: str | None = None) -> None:
    if not condition:
        raise Refused(reason, detail)


def _exact(value: Any, fields: frozenset[str], name: str) -> Mapping[str, Any]:
    _need(isinstance(value, Mapping) and set(value) == fields, "INVENTORY_MALFORMED", name)
    return value


def _hex(value: Any, name: str) -> str:
    _need(isinstance(value, str) and _HEX64.fullmatch(value) is not None, "INVENTORY_MALFORMED", name)
    return value


def _instant(value: Any, name: str) -> datetime:
    _need(isinstance(value, str) and _INSTANT.fullmatch(value) is not None, "INVENTORY_MALFORMED", name)
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def inventory_digest(document: Mapping[str, Any]) -> str:
    """SHA-256(LILITH_PR2_SNAPSHOT_INVENTORY_V1\\0 ‖ JCS(document)): the `recordSha256` the package binds."""
    return hashlib.sha256(INVENTORY_DOMAIN + rfc8785.dumps(dict(document))).hexdigest()


def artefact_class(artefact: Mapping[str, Any], *, host_key_exposed_outside: bool,
                   host_key_retained_inside: bool) -> str:
    """The minimum RR-7 / RR-17 class of one artefact (gate §5.6, preflight §21). No 'probably safe' class."""
    material = set(artefact["material"])
    if PLAINTEXT in material:
        return EXPOSED                                         # plaintext is never below class 2
    if artefact["accessHistory"] != KNOWN:
        return UNKNOWN_PROVENANCE
    both = HOST_KEY in {MATERIAL[m] for m in material} and bool(material - {"HOST_KEY_SECRET"})
    if artefact["location"] == OUTSIDE:
        return EXPOSED if both or "HOST_KEY_SECRET" in material else UNKNOWN_PROVENANCE
    if "HOST_KEY_SECRET" in material:
        return DEBT                                            # inside an accepted, inventoried environment only
    # Ciphertext only, inside. Class 6 needs the host key never to have left the boundary.
    if host_key_exposed_outside:
        return EXPOSED
    return DEBT if host_key_retained_inside else SAFE


def classify(document: Any, *, environment: str, expected_keys: Mapping[str, str] | None = None,
             not_before: str | None = None, required_carried_debts: tuple[str, ...] = ()) -> dict[str, Any]:
    """The closed classification of one inventory. Refuses (never defaults) on any malformed or incomplete input.

    `expected_keys` are the accepted public identities (`DEV_KEY_IDENTITIES` on DEV); `not_before` is the freshness
    bound (an inventory whose window starts earlier is stale); `required_carried_debts` must all be named.
    """
    doc = _exact(document, INVENTORY_FIELDS, "inventory")
    _need(doc["inventoryType"] == INVENTORY_TYPE and type(doc["schemaVersion"]) is int
          and doc["schemaVersion"] == INVENTORY_SCHEMA_VERSION, "INVENTORY_MALFORMED", "type")
    _need(doc["environment"] == environment, "INVENTORY_ENVIRONMENT_MISMATCH", str(doc["environment"]))
    _need(doc["evidenceClass"] in EVIDENCE_CLASSES, "INVENTORY_MALFORMED", "evidenceClass")
    window = _exact(doc["window"], _WINDOW_FIELDS, "window")
    started, ended = _instant(window["startedAt"], "startedAt"), _instant(window["endedAt"], "endedAt")
    _need(started <= ended, "INVENTORY_MALFORMED", "window")
    if not_before is not None:
        _need(started >= _instant(not_before, "notBefore"), "INVENTORY_STALE", window["startedAt"])
    _hex(doc["privateEvidenceSha256"], "privateEvidenceSha256")

    # Keys: exactly K-ACT, K-WIT and the host key; both ciphertexts sealed under the host key.
    _need(isinstance(doc["keys"], list), "INVENTORY_MALFORMED", "keys")
    keys = {}
    for item in doc["keys"]:
        item = _exact(item, _KEY_FIELDS, "key")
        _need(item["role"] in KEY_ROLES and item["role"] not in keys, "INVENTORY_KEYS_NOT_EXACT", str(item["role"]))
        keys[item["role"]] = item
    _need(set(keys) == set(KEY_ROLES), "INVENTORY_KEYS_NOT_EXACT", ",".join(sorted(keys)))
    for role in SEALED_UNDER_HOST_KEY:
        _hex(keys[role]["publicKeySha256"], role)
        _need(keys[role]["sealedUnder"] == HOST_KEY, "INVENTORY_KEY_RELATIONSHIP", role)
        if expected_keys is not None:
            _need(keys[role]["publicKeySha256"] == expected_keys.get(role), "INVENTORY_KEY_IDENTITY_MISMATCH", role)
    # The host key has no public identity; the inventory never names or reads it.
    _need(keys[HOST_KEY]["publicKeySha256"] is None and keys[HOST_KEY]["sealedUnder"] is None,
          "INVENTORY_KEY_RELATIONSHIP", HOST_KEY)

    # Listings: every kind, complete; the artefacts are exactly what the listings counted.
    _need(isinstance(doc["listings"], list), "INVENTORY_MALFORMED", "listings")
    listings = {}
    for item in doc["listings"]:
        item = _exact(item, _LISTING_FIELDS, "listing")
        _need(item["kind"] in LISTING_KINDS and item["kind"] not in listings, "INVENTORY_LISTING_NOT_EXACT",
              str(item["kind"]))
        _need(type(item["complete"]) is bool and type(item["count"]) is int and item["count"] >= 0,
              "INVENTORY_MALFORMED", item["kind"])
        _hex(item["listingSha256"], item["kind"])
        listings[item["kind"]] = item
    missing = [kind for kind in LISTING_KINDS if kind not in listings]
    incomplete = [kind for kind in LISTING_KINDS if kind in listings and listings[kind]["complete"] is not True]

    _need(isinstance(doc["artefacts"], list), "INVENTORY_MALFORMED", "artefacts")
    artefacts, counted = [], {kind: 0 for kind in ARTEFACT_KINDS}
    for item in doc["artefacts"]:
        item = _exact(item, _ARTEFACT_FIELDS, "artefact")
        _need(isinstance(item["artefactId"], str) and _ID.fullmatch(item["artefactId"]) is not None,
              "INVENTORY_MALFORMED", "artefactId")
        _need(item["kind"] in ARTEFACT_KINDS, "INVENTORY_MALFORMED", "kind")
        _need(isinstance(item["material"], list) and len(set(item["material"])) == len(item["material"])
              and set(item["material"]) <= set(MATERIAL) | {PLAINTEXT}, "INVENTORY_MALFORMED", "material")
        _need(item["location"] in LOCATIONS and item["accessHistory"] in (KNOWN, UNKNOWN), "INVENTORY_MALFORMED",
              item["artefactId"])
        _need(item["debtName"] is None or (isinstance(item["debtName"], str)
                                           and _DEBT_NAME.fullmatch(item["debtName"]) is not None),
              "INVENTORY_MALFORMED", "debtName")
        counted[item["kind"]] += 1
        artefacts.append(item)
    _need(len({a["artefactId"] for a in artefacts}) == len(artefacts), "INVENTORY_MALFORMED", "artefactId duplicated")
    miscounted = [kind for kind in ARTEFACT_KINDS if kind in listings and listings[kind]["count"] != counted[kind]]

    _need(isinstance(doc["carriedDebts"], list), "INVENTORY_MALFORMED", "carriedDebts")
    carried = {}
    for item in doc["carriedDebts"]:
        item = _exact(item, _DEBT_FIELDS, "carriedDebt")
        _need(isinstance(item["name"], str) and _DEBT_NAME.fullmatch(item["name"]) is not None
              and item["name"] not in carried and item["role"] in KEY_ROLES, "INVENTORY_MALFORMED", "carriedDebt")
        _hex(item["recordSha256"], "carriedDebt.recordSha256")
        carried[item["name"]] = item

    # Classification (worst artefact per key).
    holds_secret = [a for a in artefacts if "HOST_KEY_SECRET" in a["material"]]
    exposed_outside = any(a["location"] == OUTSIDE or a["accessHistory"] != KNOWN for a in holds_secret)
    classes = {a["artefactId"]: artefact_class(a, host_key_exposed_outside=exposed_outside,
                                               host_key_retained_inside=bool(holds_secret)) for a in artefacts}
    per_key: dict[str, str] = {}
    for role in KEY_ROLES:
        found = [classes[a["artefactId"]] for a in artefacts
                 if role in {MATERIAL.get(m) for m in a["material"]}
                 or (role in SEALED_UNDER_HOST_KEY and a in holds_secret) or PLAINTEXT in a["material"]]
        per_key[role] = min(found, key=SEVERITY.index) if found else NO_SNAPSHOTS

    reasons = []
    if missing:
        reasons.append("LISTING_MISSING:" + ",".join(missing))
    if incomplete:
        reasons.append("LISTING_INCOMPLETE:" + ",".join(incomplete))
    if miscounted:
        reasons.append("LISTING_COUNT_MISMATCH:" + ",".join(miscounted))
    for role in KEY_ROLES:
        if per_key[role] not in PERMITTED:
            reasons.append(f"KEY_CLASS_NOT_PERMITTED:{role}:{per_key[role]}")
    unnamed = sorted(a["artefactId"] for a in artefacts if classes[a["artefactId"]] == DEBT and not a["debtName"])
    if unnamed:
        reasons.append("DEBT_NOT_NAMED:" + ",".join(unnamed))
    absent = sorted(set(required_carried_debts) - set(carried))
    if absent:
        reasons.append("CARRIED_DEBT_MISSING:" + ",".join(absent))
    if missing or incomplete or miscounted:
        artefact_classes = [UNKNOWN_PROVENANCE]               # an incomplete listing is unknown provenance
    elif not artefacts:
        artefact_classes = [NO_SNAPSHOTS]
    else:
        artefact_classes = sorted(set(classes.values()), key=SEVERITY.index)
    named = sorted({a["debtName"] for a in artefacts if classes[a["artefactId"]] == DEBT and a["debtName"]}
                   | set(carried))
    return {"inventoryDigest": inventory_digest(doc), "environment": doc["environment"],
            "evidenceClass": doc["evidenceClass"], "window": dict(window),
            "classification": "PASS" if not reasons else "FAIL", "reasons": reasons,
            "artefactClasses": artefact_classes, "keyClasses": per_key, "artefacts": classes, "namedDebts": named,
            "ownerAccepted": False, "authorityGranted": False, "nonclaims": list(NONCLAIMS)}


def package_input(document: Any, acceptance: Any, *, environment: str, expected_keys: Mapping[str, str] | None,
                  not_before: str | None, required_carried_debts: tuple[str, ...] = ()) -> dict[str, Any]:
    """The E-20 `snapshotInventory` verifier input, or Refused.

    Only a LIVE_OBSERVATION whose classification PASSes and whose owner acceptance names exactly this inventory
    digest becomes `status=ACCEPTED`. The acceptance is supplied, never created here."""
    report = classify(document, environment=environment, expected_keys=expected_keys, not_before=not_before,
                      required_carried_debts=required_carried_debts)
    _need(report["evidenceClass"] == LIVE_OBSERVATION, "SYNTHETIC_FIXTURE_NOT_PACKAGE_INPUT")
    _need(report["classification"] == "PASS", "INVENTORY_CLASSIFICATION_FAIL", ";".join(report["reasons"]))
    owner = _exact(acceptance, ACCEPTANCE_FIELDS, "acceptance") if acceptance is not None else None
    _need(owner is not None, "OWNER_ACCEPTANCE_ABSENT")
    _need(owner["acceptanceType"] == ACCEPTANCE_TYPE and type(owner["schemaVersion"]) is int
          and owner["schemaVersion"] == 1 and owner["environment"] == environment, "OWNER_ACCEPTANCE_MALFORMED")
    _hex(owner["acceptanceRecordSha256"], "acceptanceRecordSha256")
    _need(owner["acceptedInventoryDigest"] == report["inventoryDigest"], "OWNER_ACCEPTANCE_DIGEST_MISMATCH")
    _need(_instant(owner["acceptedAt"], "acceptedAt") >= _instant(report["window"]["endedAt"], "endedAt"),
          "OWNER_ACCEPTANCE_BEFORE_WINDOW_END")
    return {"status": "ACCEPTED", "recordSha256": report["inventoryDigest"],
            "artefactClasses": list(report["artefactClasses"]), "namedDebts": list(report["namedDebts"])}


def _load(path: str) -> Any:
    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise Refused("INPUT_DUPLICATE_KEY")
        return dict(pairs)
    return json.loads(Path(path).read_bytes().decode("utf-8"), object_pairs_hook=no_duplicates)


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 2 and argv[0] == "classify":
            out = classify(_load(argv[1]), environment="dev", expected_keys=DEV_KEY_IDENTITIES,
                           required_carried_debts=DEV_CARRIED_DEBTS)
        elif len(argv) == 4 and argv[0] == "package-input":
            # The freshness bound is an explicit argument: its DEV value is an owner decision (record OD-M12-3).
            out = package_input(_load(argv[1]), _load(argv[2]), environment="dev", expected_keys=DEV_KEY_IDENTITIES,
                                not_before=argv[3], required_carried_debts=DEV_CARRIED_DEBTS)
        else:
            raise Refused("USAGE")
    except (Refused, ValueError, OSError) as exc:
        print(f"mb12_pr2_inventory: REFUSED {getattr(exc, 'reason', type(exc).__name__)}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(out, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
