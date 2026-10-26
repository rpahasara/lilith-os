#!/usr/bin/env python3
"""Relationship origin: the owner-directed DEV FORGET of the owner-provided origin memory (DEV_SYNTHETIC; SOURCE ONLY).

Record: docs/architecture/personal-memory-fm2-dev-activation.md. No form below is authorized by the repository; each
`forget` is one owner go.

The F9c2 drill tool (`f9c_dev_drill.py`, Hermes package) is the only installed FORGET trigger. It is First-Interaction
only and builds its runner without the Track B durability barrier, which the runner now refuses. This tool is the same
governed hold-first FORGET for the one other closed profile, composed only from merged parts and the First Memory DEV
host's fixed paths:

- `privacy_forget_runner.RELATIONSHIP_ORIGIN_FORGET`, owners L04 and L18_V2 (Privacy admits the Hermes owner only where
  its floor provisions the origin scope; no tool provisions that, and this tool passes no Hermes adapter, so a floor
  that names Hermes is refused before anything is held);
- the durable `relationship-origin.intent` and the root hold (`privacy_forget_intent.HoldFirstForgetRunner`): nothing
  is authorized until root holds the intent and the Hermes gateway is observed stopped;
- `privacy_freshness.DurabilityBarrier` over the authoritative Privacy DB (`PrivacyBindingV1`): no owner erases until
  the new suppression is anchored by the witness (K-PAN) and checkpointed by the owner device (K-PCK); until then the
  FORGET stays INCOMPLETE_HOLD_ACTIVE and `resume` continues it;
- the DEV_SYNTHETIC actor authority issues exactly one evidence for the one origin FORGET action, keyed to the owner's
  recorded approval reference (single use), as for the F9c2 FORGET.

Forms (run as `lilith`, never root, with the root-owned authority release interpreter, from the First Memory host tree;
output is one content-free JSON object):

    status                         read-only: intent state, in flight, completed (the executor's release proof),
                                   Privacy freshness and durability
    forget --owner-approval REF    Privacy READY for this boot, an origin memory present, no other intent pending:
                                   record the intent, wait for the root hold, then Privacy `begin_forget`; owners erase
                                   only once durable
    resume                         continue the in-flight origin FORGET (no new evidence)

Root alone removes the intent (the patched executor's reconcile, once Privacy proves the origin FORGET COMPLETED with
L18_V2). Nothing here deletes without Privacy authorization, touches First Interaction, or reads a private key.

    owner approval != Privacy authorization;  COMPLETE != intent released (root reconcile)
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import first_memory_dev_host as HOST  # noqa: E402  (fixed DEV paths and the import roots of the host tree)
from lilith_memory import canonical_authority as CA  # noqa: E402
from lilith_memory import memory_action_v2 as MA  # noqa: E402
from lilith_memory import memory_v2  # noqa: E402
from lilith_memory import privacy_forget_intent as I  # noqa: E402
from lilith_memory import privacy_forget_runner as R  # noqa: E402
from lilith_memory import privacy_freshness as F  # noqa: E402
from lilith_memory import privacy_governance as PG  # noqa: E402
from lilith_owner_memory import first_memory_conversation as FMC  # noqa: E402

PROFILE = R.RELATIONSHIP_ORIGIN_FORGET
DEV_SYNTHETIC = R.DEV_SYNTHETIC
COMPLETION_OWNER = "L18_V2"            # the owner whose COMPLETE the root executor requires to release the intent
REF_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
ORIGIN_TABLES = ("learning_ro_intent_v1", "learning_ro_candidate_v1", "learning_ro_proposal_v1")


class OriginForgetRefused(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise OriginForgetRefused(code)


@dataclass
class OriginForgetDevV1:
    """A FRESH composition per call. `freshness`, `intents` and `gateway` are TEST seams (DEV: the current-boot gate,
    the root intent directory, the Hermes gateway unit and port)."""

    paths: HOST.HostPathsV1 = HOST.DEV_PATHS
    freshness: Optional[F.PrivacyFreshnessGate] = None
    intents: Optional[I.ForgetIntentStore] = None
    gateway: Optional[Any] = None
    hold_timeout_seconds: float = 180.0

    def _stores(self) -> tuple[CA.LocalOwnerAuthority, PG.PrivacyGovernanceStore, FMC.PrivacyBindingV1]:
        paths = self.paths
        _need(paths.cognitive_db.is_file(), "COGNITIVE_DB_UNAVAILABLE")
        actor = CA.LocalOwnerAuthority(paths.cognitive_db, paths.actor_secret.read_bytes())
        privacy = PG.PrivacyGovernanceStore(paths.privacy_db, paths.privacy_secret.read_bytes(), actor)
        binding = FMC.PrivacyBindingV1(paths.privacy_db, privacy, paths.cognitive_db,
                                       authoritative=paths.authoritative_privacy_db, stale=paths.stale_privacy_db,
                                       freshness=self.freshness)
        return actor, privacy, binding

    def _intents(self) -> I.ForgetIntentStore:
        return self.intents or I.ForgetIntentStore(profile=PROFILE)

    def _runner(self, privacy: PG.PrivacyGovernanceStore, binding: FMC.PrivacyBindingV1) -> I.HoldFirstForgetRunner:
        cognitive = self.paths.cognitive_db
        owners = {"L04": memory_v2.L04PrivacyErasureOwner(cognitive, privacy),
                  "L18_V2": memory_v2.L18V2PrivacyErasureOwner(cognitive, privacy)}
        inner = R.FirstInteractionForgetRunner(privacy, owners, deployment_environment=DEV_SYNTHETIC,
                                               durability_barrier=F.DurabilityBarrier(binding.freshness),
                                               profile=PROFILE)
        return I.HoldFirstForgetRunner(inner, self._intents(), self.gateway or I.GatewayProbe(),
                                       hold_timeout_seconds=self.hold_timeout_seconds)

    def origin_rows(self) -> int:
        """Read-only: every L04 / L18 row of the origin identity (what a FORGET would erase)."""
        conn = sqlite3.connect(f"{self.paths.cognitive_db.resolve().as_uri()}?mode=ro", uri=True)
        try:
            names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            rows = sum(conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in ORIGIN_TABLES if t in names)
            return rows + conn.execute("SELECT COUNT(*) FROM memory_item WHERE memory_class=? AND subject_namespace=? "
                                       "AND subject_key=?", MA.RELATIONSHIP_ORIGIN_IDENTITY).fetchone()[0]
        finally:
            conn.close()

    def status(self) -> dict[str, Any]:
        _actor, privacy, binding = self._stores()
        return {"form": "status", "intent": self._intents().state(),
                "inFlight": privacy.in_flight_authorization(PROFILE.identity) is not None,
                "completed": privacy.identity_forget_completed(PROFILE.identity, COMPLETION_OWNER),
                "freshness": binding.freshness.check().status, "durability": binding.freshness.durability().status,
                "originRows": self.origin_rows()}

    def forget(self, approval: str) -> dict[str, Any]:
        _need(bool(approval) and len(approval) <= 96 and set(approval) <= REF_CHARS, "OWNER_APPROVAL_REF_INVALID")
        actor, privacy, binding = self._stores()
        intents = self._intents()
        _need(not intents.other_pending(), "FORGET_INTENT_PENDING_OTHER_IDENTITY")
        _need(intents.state() == I.ABSENT, "ORIGIN_FORGET_INTENT_PENDING:resume_or_cancel")
        binding.require_ready()                        # Privacy fresh for THIS boot before anything is recorded
        _need(not privacy.suppression_matches(PROFILE.identity), "ORIGIN_ALREADY_FORGOTTEN")
        _need(self.origin_rows() > 0, "ORIGIN_MEMORY_ABSENT")        # never suppress an identity nobody admitted
        action = R.forget_action(PROFILE, actor.ACTOR.actor_ref_id)
        try:
            evidence = actor.issue(action=action,
                                   request_digest=hashlib.sha256(f"origin-forget-dev:{approval}".encode()).hexdigest(),
                                   nonce=f"origin-forget-dev.{approval}", ttl_seconds=300)
        except sqlite3.IntegrityError as exc:
            raise OriginForgetRefused("OWNER_APPROVAL_REF_ALREADY_USED") from exc
        result = self._runner(privacy, binding).forget(
            actor_ref_id=actor.ACTOR.actor_ref_id, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id=f"intent.{approval}", confirmation_event_ref=f"owner-approval.{approval}")
        return _result("forget", result)

    def resume(self) -> dict[str, Any]:
        _actor, privacy, binding = self._stores()
        return _result("resume", self._runner(privacy, binding).resume())


def _result(form: str, r: R.ForgetRunResult) -> dict[str, Any]:
    return {"form": form, "status": r.status, "failure": r.failure_code, "failedOwner": r.failed_owner,
            "completedOwners": list(r.completed_owners), "pendingOwners": list(r.pending_owners),
            "authorizationDigest": None if r.authorization_ref_id is None
            else hashlib.sha256(r.authorization_ref_id.encode()).hexdigest()[:16]}


def main(argv: list[str]) -> int:
    def emit(value: Mapping[str, Any]) -> None:
        sys.stdout.write(json.dumps(dict(value), sort_keys=True, separators=(",", ":")) + "\n")

    try:
        refused = HOST.unprivileged_reason()
        _need(refused is None, str(refused))
        tool = OriginForgetDevV1()
        if argv == ["status"]:
            emit(tool.status())
            return 0
        if argv == ["resume"]:
            out = tool.resume()
        elif len(argv) == 3 and argv[:2] == ["forget", "--owner-approval"]:
            out = tool.forget(argv[2])
        else:
            raise OriginForgetRefused("USAGE")
        emit(out)
        return 0 if out["status"] in (R.COMPLETE, R.ALREADY_COMPLETE) else 1
    except (OriginForgetRefused, FMC.FirstMemoryRefused, I.ForgetIntentError, R.ForgetRunnerError) as exc:
        print(f"relationship-origin-forget-dev: REFUSED {exc.code}", file=sys.stderr)
        return 2
    except (OSError, ValueError, sqlite3.Error, PG.PrivacyError) as exc:
        print(f"relationship-origin-forget-dev: REFUSED {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
