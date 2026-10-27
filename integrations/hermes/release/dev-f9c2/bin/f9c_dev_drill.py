#!/usr/bin/env python3
"""F9-C DEV_SYNTHETIC FORGET drill operator tool (run as lilith, the Core API identity, with the Core API venv).

    $CORE/api-venv/bin/python -I -B /opt/hermes-gateway-dev/current/bin/f9c_dev_drill.py --core-api $CORE/current PHASE

Phases (output is content-free JSON):
  provision   create the dedicated drill stores in DRILL_DIR: owner-only actor and Privacy secrets, a fresh cognitive DB
              (memory_store -> Slice 15B2a -> canonical v2 -> First Interaction family) and a fresh Privacy DB (Slice
              15B2a v1 -> v2 upgrade -> Hermes owner floor, DEV_SYNTHETIC). The exact library sequence of the DEV
              durability probe and the reviewed F9-C slices; refuses if any drill file already exists.
  forget      the governed hold-first First Interaction FORGET: the local DEV_SYNTHETIC actor authority (drill actor
              secret) issues ONE evidence for the canonical First Interaction FORGET action, then HoldFirstForgetRunner
              -> FirstInteractionForgetRunner -> Privacy begin_forget -> L04, L18_V2, HERMES_DEV_CONVERSATION (root
              executor via the spool). Requires --owner-approval REF (the owner's recorded go-ahead, used as the
              intent and confirmation references). Privacy Governance stays the only authority.
  resume      resume an in-flight FORGET (no new evidence).
  status      intent state, in-flight yes/no, completion proven yes/no.

Never reads or writes the deploy-time durability probe stores (data/cognitive_memory.dev.db,
data/privacy_governance.dev.db, data/canonical-durability-probe): the drill paths are fixed, outside data/, and match the
root executor's sandbox binds. Refused as root and on non-DEV_SYNTHETIC paths. No HTTP, no provider, no Hermes code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import stat
import sys
from pathlib import Path
from typing import Any, Dict, Optional

APP_ROOT = Path("/home/lilith/.hermes/lilith-os-dev")
DRILL_DIR = APP_ROOT / "f9-drill"
DATA_DIR = APP_ROOT / "data"
PROBE_PATHS = (DATA_DIR / "cognitive_memory.dev.db", DATA_DIR / "privacy_governance.dev.db",
               DATA_DIR / "canonical-durability-probe")
PRODUCTION_COGNITIVE_DB = Path("/home/lilith/.hermes/lilith-os/data/cognitive_memory.db")
PRODUCTION_PRIVACY_DB = Path("/home/lilith/.hermes/lilith-os/data/privacy_governance.db")
CAPTURE_DB = DATA_DIR / "conversation-evidence.db"      # app.py's capture path: L18_V2 must be given exactly this
DEV_SYNTHETIC = "DEV_SYNTHETIC"
REF_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")


class DrillError(RuntimeError):
    pass


class Paths:
    def __init__(self, drill_dir: Path):
        self.drill = Path(drill_dir)
        self.cognitive = self.drill / "cognitive_memory.f9drill.db"
        self.privacy = self.drill / "privacy_governance.f9drill.db"
        self.actor_key = self.drill / "actor-authority.f9drill.key"
        self.privacy_key = self.drill / "privacy-authority.f9drill.key"
        self.backups = self.drill / "backups"

    def all_files(self):
        return [self.cognitive, self.privacy, self.actor_key, self.privacy_key, self.backups,
                *(Path(str(db) + s) for db in (self.cognitive, self.privacy) for s in ("-wal", "-shm", "-journal"))]


def emit(**fields: Any) -> None:
    print(json.dumps(fields, sort_keys=True), flush=True)


def load_runtime(core_api: Path):
    """Import the DEPLOYED Core API package (never a copy shipped here)."""
    core_api = Path(core_api).resolve()
    if not (core_api / "lilith_memory" / "privacy_forget_intent.py").is_file():
        raise DrillError("deployed Core API lacks the F9-C modules")
    sys.path.insert(0, str(core_api))
    import importlib
    names = ("canonical_authority", "memory_store", "slice15b2a_migration", "backup", "canonical_migration",
             "first_interaction_migration", "privacy_governance", "privacy_schema_v2", "memory_v2",
             "privacy_forget_runner", "privacy_forget_intent", "hermes_erasure_owner", "hermes_erasure_spool", "config")
    return {n: importlib.import_module(f"lilith_memory.{n}") for n in names}


def guard(paths: Paths, *, test_root: bool) -> None:
    drill = paths.drill.resolve()
    if any(drill == p.resolve() or p.resolve() in drill.parents or drill in p.resolve().parents for p in PROBE_PATHS) \
            or DATA_DIR.resolve() in drill.parents or drill == DATA_DIR.resolve():
        raise DrillError("drill stores may never live in or under the durability probe's data directory")
    if not test_root and paths.drill != DRILL_DIR:
        raise DrillError("drill directory must be the fixed path the executor sandbox binds")
    if os.geteuid() == 0:
        raise DrillError("run as the Core API identity (lilith), never as root")
    st = os.lstat(paths.drill)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        raise DrillError("drill directory must exist, be owned by the caller and be mode 0700")


def provision(rt: Dict[str, Any], paths: Paths) -> Dict[str, Any]:
    if any(p.exists() or p.is_symlink() for p in paths.all_files()):
        raise DrillError("drill stores already exist: provisioning is one-time (nothing changed)")
    A, MS, M15, B = rt["canonical_authority"], rt["memory_store"], rt["slice15b2a_migration"], rt["backup"]
    rt["config"].assert_nonproduction_database(paths.cognitive, production_path=PRODUCTION_COGNITIVE_DB, environment="dev")
    rt["config"].assert_nonproduction_database(paths.privacy, production_path=PRODUCTION_PRIVACY_DB, environment="dev")
    paths.backups.mkdir(mode=0o700)
    A.create_owner_only_secret(paths.actor_key)
    A.create_owner_only_secret(paths.privacy_key)
    MS.migrate(paths.cognitive, production_path=PRODUCTION_COGNITIVE_DB)
    os.chmod(paths.cognitive, 0o600)
    pre = MS.create_verified_backup(paths.cognitive, paths.backups / "cognitive.pre-15b2a.db")
    M15.migrate_cognitive(paths.cognitive, verified_backup=pre, production_path=paths.cognitive)
    manifest = B.create_backup(paths.cognitive, paths.backups / "cognitive.pre-v2.db",
                               paths.backups / "cognitive.pre-v2.manifest.json", role="cognitive")
    canonical = rt["canonical_migration"].migrate(paths.cognitive, backup_manifest=manifest)
    fi_manifest = B.create_backup(paths.cognitive, paths.backups / "cognitive.pre-fi.db",
                                  paths.backups / "cognitive.pre-fi.manifest.json", role="cognitive")
    fi = rt["first_interaction_migration"].migrate(paths.cognitive, backup_manifest=fi_manifest)
    paths.privacy.touch(mode=0o600)
    os.chmod(paths.privacy, 0o600)
    B.create_backup(paths.privacy, paths.backups / "privacy.pre-migration.db",
                    paths.backups / "privacy.pre-migration.manifest.json", role="privacy")
    v1 = M15.migrate_privacy(paths.privacy)
    v2 = rt["privacy_schema_v2"].upgrade_privacy_v1_to_v2(paths.privacy)
    floor = rt["privacy_schema_v2"].provision_hermes_owner_floor(paths.privacy, deployment_environment=DEV_SYNTHETIC)
    for p in (paths.cognitive, paths.privacy):
        os.chmod(p, 0o600)
    return {"phase": "provision", "status": "PROVISIONED", "canonical": list(canonical),
            "firstInteraction": sorted(fi), "privacyV1": list(v1), "privacyV2": list(v2), "floorAdded": bool(floor)}


def stores(rt: Dict[str, Any], paths: Paths):
    actor = rt["canonical_authority"].LocalOwnerAuthority.from_secret_file(paths.cognitive, paths.actor_key)
    privacy = rt["privacy_governance"].PrivacyGovernanceStore.from_secret_file(paths.privacy, paths.privacy_key, actor)
    return actor, privacy


def runner(rt: Dict[str, Any], paths: Paths, privacy, *, hermes=None, intents=None, gateway=None):
    M, R, I = rt["memory_v2"], rt["privacy_forget_runner"], rt["privacy_forget_intent"]
    hermes = hermes or rt["hermes_erasure_owner"].HermesConversationErasureOwner(
        privacy, rt["hermes_erasure_spool"].SpoolHermesErasureExecutor(), deployment_environment=DEV_SYNTHETIC,
        timeout_seconds=600.0, poll_seconds=1.0)
    owners = {"L04": M.L04PrivacyErasureOwner(paths.cognitive, privacy),
              "L18_V2": M.L18V2PrivacyErasureOwner(paths.cognitive, privacy, capture_evidence_path=CAPTURE_DB),
              hermes.OWNER: hermes}
    inner = R.FirstInteractionForgetRunner(privacy, owners, deployment_environment=DEV_SYNTHETIC)
    return I.HoldFirstForgetRunner(inner, intents or I.ForgetIntentStore(), gateway or I.GatewayProbe(),
                                   hold_timeout_seconds=180.0)


def result(phase: str, r) -> Dict[str, Any]:
    return {"phase": phase, "status": r.status, "failure": r.failure_code, "failedOwner": r.failed_owner,
            "completedOwners": list(r.completed_owners), "pendingOwners": list(r.pending_owners),
            "authorizationDigest": None if r.authorization_ref_id is None
            else hashlib.sha256(r.authorization_ref_id.encode()).hexdigest()[:16]}


def forget(rt: Dict[str, Any], paths: Paths, approval: str, **kw) -> Dict[str, Any]:
    if not approval or len(approval) > 96 or not set(approval) <= REF_CHARS:
        raise DrillError("--owner-approval must be the owner's recorded go-ahead reference ([A-Za-z0-9._:-], <= 96)")
    import sqlite3
    actor, privacy = stores(rt, paths)
    pending = (kw.get("intents") or rt["privacy_forget_intent"].ForgetIntentStore()).read()
    if pending is not None and pending.get("intentRefId") != f"intent.{approval}":
        raise DrillError("another FORGET intent is pending: resume it, or cancel it (root, owner-approved)")
    action = rt["privacy_forget_runner"].first_interaction_forget_action(actor.ACTOR.actor_ref_id)
    try:
        evidence = actor.issue(action=action,
                               request_digest=hashlib.sha256(f"f9c-dev-drill:{approval}".encode()).hexdigest(),
                               nonce=f"f9c-dev-drill.{approval}", ttl_seconds=300)
    except sqlite3.IntegrityError as exc:
        raise DrillError("this --owner-approval reference was already used: evidence is single-use") from exc
    r = runner(rt, paths, privacy, **kw).forget(
        actor_ref_id=actor.ACTOR.actor_ref_id, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
        intent_ref_id=f"intent.{approval}", confirmation_event_ref=f"owner-approval.{approval}")
    return result("forget", r)


def status(rt: Dict[str, Any], paths: Paths) -> Dict[str, Any]:
    _actor, privacy = stores(rt, paths)
    R, I = rt["privacy_forget_runner"], rt["privacy_forget_intent"]
    return {"phase": "status", "intent": I.ForgetIntentStore().state(),
            "inFlight": privacy.in_flight_authorization(R.IDENTITY) is not None,
            "completed": privacy.identity_forget_completed(R.IDENTITY, privacy_hermes(rt)),
            "suppressionSelectors": privacy.verify_suppression_integrity()}


def privacy_hermes(rt):
    return rt["privacy_governance"].HERMES_DEV_CONVERSATION


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--core-api", required=True, type=Path)
    ap.add_argument("--owner-approval", default="")
    ap.add_argument("phase", choices=("provision", "forget", "resume", "status"))
    args = ap.parse_args(argv)
    test_root = os.environ.get("F9C_DRILL_TEST_ROOT")
    if test_root and socket.gethostname() == "lilith-dev-01":
        emit(phase=args.phase, status="REFUSED", failure="TEST_ROOT_ON_DEV")
        return 2
    paths = Paths(Path(test_root) if test_root else DRILL_DIR)
    try:
        guard(paths, test_root=bool(test_root))
        rt = load_runtime(args.core_api)
        if args.phase == "provision":
            out = provision(rt, paths)
        elif args.phase == "forget":
            out = forget(rt, paths, args.owner_approval)
        elif args.phase == "resume":
            _actor, privacy = stores(rt, paths)
            out = result("resume", runner(rt, paths, privacy).resume())
        else:
            out = status(rt, paths)
    except DrillError as exc:
        emit(phase=args.phase, status="REFUSED", failure=str(exc))
        return 2
    emit(**out)
    return 0 if out.get("status") in ("PROVISIONED", "COMPLETE", "ALREADY_COMPLETE", None) or args.phase == "status" else 1


if __name__ == "__main__":
    sys.exit(main())
