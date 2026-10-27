"""F9-C privileged Hermes erasure executor: the T1-T25 synthetic matrix (offline layer; WSL, run as root).

The real Core API Privacy store, the Slice 3 runner, the real L04 and L18_V2 owners, the Slice 2 Hermes adapter and
the real spool client drive the real executor (bin/hermes_forget_executor.py) in a fresh interpreter, with real
SQLite (Hermes' own schema and FTS triggers, taken from its source), real files, real tar archives and a real
size-limited tmpfs for disk-full. Only systemd and journald are faked here (executor_driver.FakeHost); the systemd
mirror layer (f9c4-mirror.sh) exercises them for real. Synthetic canaries only; no provider, no DEV.

    F9C_CORE_API=<core-api dir> F9C_EXECUTOR_PKG=<pkgfiles dir> F9C_HERMES_SRC=<hermes src> python3 -m unittest ...
"""

from __future__ import annotations

import ast
import hashlib
import re
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import time
import unittest
from pathlib import Path

CORE = Path(os.environ["F9C_CORE_API"])
PKG = Path(os.environ["F9C_EXECUTOR_PKG"])
HERMES_SRC = Path(os.environ["F9C_HERMES_SRC"])
PY311 = os.environ.get("F9C_PY311", "/root/f9b/build/pkg/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11")
HERMES_HOME_TEMPLATE = Path(os.environ.get("F9C_HERMES_HOME_TEMPLATE", "/root/f9b/build/pkg/home"))
sys.path.insert(0, str(CORE / "tests"))
sys.path.insert(0, str(PKG / "bin"))

from test_privacy_forget_runner import FI, HERMES, CountingOwner, RunnerCase  # noqa: E402
from test_privacy_hermes_owner_v2 import SECRET  # noqa: E402

from lilith_memory import hermes_erasure_owner as H  # noqa: E402
from lilith_memory import hermes_erasure_spool as S  # noqa: E402
from lilith_memory import privacy_forget_intent as I  # noqa: E402
from lilith_memory import privacy_forget_runner as R  # noqa: E402
from lilith_memory import privacy_governance as privacy  # noqa: E402

import hermes_forget_executor as X  # noqa: E402  (module helpers only; the executor always runs in a subprocess)
import hermes_restore_guard as G  # noqa: E402

CANARY = b"F9C-EXEC-CANARY"
DRIVER = Path(__file__).with_name("executor_driver.py")
FAULT_POINTS = ("after:VALIDATE", "after:STOP", "sqlite:before-commit", "sqlite:after-commit", "after:SQLITE",
                "files:logs", "after:FILES", "journal:rotate", "after:JOURNAL", "backups:before-tombstone",
                "backups:after-tombstone", "after:BACKUPS", "after:EPOCH", "before:receipt", "after:RECEIPT-written",
                "after:RECEIPT-journalled")


def hermes_schema_sql() -> list:
    """SCHEMA_SQL / FTS_SQL / FTS_TRIGRAM_SQL string constants from Hermes' own source (not imported)."""
    tree = ast.parse((HERMES_SRC / "hermes_state_common.py").read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in ("SCHEMA_SQL", "FTS_SQL", "FTS_TRIGRAM_SQL") \
                and isinstance(node.value, ast.Constant):
            found[node.targets[0].id] = node.value.value
    assert {"SCHEMA_SQL", "FTS_SQL"} <= set(found), sorted(found)
    # The gateway's delivery ledger creates its table lazily in the same state.db (gateway/delivery_ledger.py).
    ledger = re.search(r'"""(CREATE TABLE IF NOT EXISTS delivery_obligations \(.*?\))"""',
                       (HERMES_SRC / "gateway" / "delivery_ledger.py").read_text(encoding="utf-8"), re.S)
    assert ledger, "delivery_obligations DDL not found in the Hermes source"
    return [found[k] for k in ("SCHEMA_SQL", "FTS_SQL", "FTS_TRIGRAM_SQL") if k in found] + [ledger.group(1)]


def sha_tree(path: Path) -> dict:
    out = {}
    for p in sorted(path.rglob("*")):
        if p.is_file() and not p.is_symlink():
            out[str(p.relative_to(path))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def canary_hits(*roots: Path) -> list:
    hits = []
    for root in roots:
        if not root.exists():
            continue
        for p in ([root] if root.is_file() else root.rglob("*")):
            if p.is_file() and not p.is_symlink() and CANARY in p.read_bytes():
                hits.append(str(p))
    return hits


class ExecutorCase(RunnerCase):
    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(os.geteuid(), 0, "the executor matrix runs as root")
        x = self.x = self.root / "host"
        self.home = x / "home" / "lilith" / ".hermes-dev"
        self.spool, self.state = x / "run" / "spool", x / "lib" / "state"
        self.receipts, self.epochs = x / "lib" / "receipts", x / "lib" / "epochs"
        self.backups, self.jdir = x / "backups", x / "journal"
        self.intent_dir = x / "lib" / "intent"
        for d, mode in ((self.spool, 0o730), (self.state, 0o700), (self.receipts, 0o750), (self.epochs, 0o700),
                        (self.backups, 0o700), (self.jdir, 0o755), (self.intent_dir, 0o1770)):
            d.mkdir(parents=True, exist_ok=True)
            os.chmod(d, mode)
        self.secret = x / "privacy.key"
        self.secret.write_bytes(SECRET)
        os.chmod(self.secret, 0o600)
        self.host_state = x / "host-state.json"
        self.set_host()
        self.config = x / "executor.json"
        self.write_config()
        self.build_hermes_home()
        self.build_backups()
        self.client = S.SpoolHermesErasureExecutor(self.spool, self.receipts, executor_uid=0)
        self.auto_run, self.run_log, self.ticks = True, [], 0.0

    # ------------------------------------------------------------------------------------------------ fixtures ---
    def write_config(self, **overrides) -> None:
        pkg = CORE / "lilith_memory"
        cfg = {
            "deploymentEnvironment": "DEV_SYNTHETIC", "hermesHome": str(self.home), "spoolDir": str(self.spool),
            "stateDir": str(self.state), "receiptDir": str(self.receipts), "receiptGid": 0,
            "epochLog": str(self.epochs / "epochs.log"), "inProgressMarker": str(self.x / "lib" / "in-progress"),
            "backupRoot": str(self.backups), "journalNamespace": "hermes-gateway-dev", "journalDir": str(self.jdir),
            "gatewayUnit": "hermes-gateway-dev.service", "gatewayPorts": [9901], "requesterUid": 0,
            "privacyDb": str(self.privacy_db), "privacySecret": str(self.secret), "coreApiDir": str(pkg),
            "coreApiSha256": {n: hashlib.sha256((pkg / n).read_bytes()).hexdigest() for n in X.CORE_API_MODULES},
            # The offline executor runs synchronously inside the adapter's wait, so it cannot also wait for the
            # adapter: no in-run release wait here (the mirror exercises it); release comes from reconcile.
            "releaseWaitSeconds": 0,
            "intentDir": str(self.intent_dir),
        }
        cfg.update(overrides)
        self.config.write_text(json.dumps(cfg))
        os.chmod(self.config, 0o644)

    def set_host(self, **state) -> None:
        base = {"gatewayActive": True, "processPresent": False, "portOpen": False, "journalEntries": 5}
        base.update(state)
        self.host_state.write_text(json.dumps(base))

    def host(self) -> dict:
        return json.loads(self.host_state.read_text())

    def build_state_db(self, path: Path, *, sessions=(("s1", "lilith_os", "owner"), ("s2", "lilith_os", "owner"))):
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        for sql in hermes_schema_sql():
            conn.executescript(sql)
        for sid, source, user in sessions:
            conn.execute("INSERT INTO sessions(id, source, user_id, started_at, system_prompt) VALUES (?,?,?,?,?)",
                         (sid, source, user, time.time(), "TEST_ONLY system " + CANARY.decode()))
            for i in range(3):
                conn.execute("INSERT INTO messages(session_id, role, content, timestamp) VALUES (?,?,?,?)",
                             (sid, "user" if i % 2 == 0 else "assistant",
                              f"{CANARY.decode()} turn {i} of {sid}", time.time()))
        conn.execute("INSERT INTO system_prompts(hash, prompt) VALUES (?,?)", ("h1", "TEST_ONLY " + CANARY.decode()))
        conn.execute("INSERT INTO delivery_obligations(obligation_id, session_key, platform, chat_id, content, state, "
                     "created_at, updated_at) VALUES ('o1', 'k', 'lilith_os', 'c', ?, 'PENDING', 0, 0)",
                     ("TEST_ONLY reply " + CANARY.decode(),))
        conn.execute("INSERT INTO gateway_routing(scope, session_key, entry_json, updated_at) VALUES ('', 'k', ?, 0)",
                     (json.dumps({"chat": CANARY.decode()}),))
        conn.commit()
        conn.close()

    def build_hermes_home(self) -> None:
        h = self.home
        shutil.copytree(HERMES_HOME_TEMPLATE, h, dirs_exist_ok=True)          # config.yaml, router, plugins
        (h / ".env").write_text("LILITH_OS_PORT=9901\nLILITH_OS_TOKEN=" + "ab" * 32 + "\n")
        (h / "SOUL.md").write_text("TEST_ONLY soul (protected)\n")
        for d in ("memories", "cron", "skills", *X.PURGE_DIRS):
            (h / d).mkdir(parents=True, exist_ok=True)
        (h / "memories" / "MEMORY.md").write_text("TEST_ONLY pre-existing memories (protected)\n")
        (h / "cron" / "jobs.json").write_text("[]\n")
        (h / "logs" / "gateway.log").write_bytes(b"msg_chars=12 " + CANARY + b"\n")
        (h / "logs" / "agent.log.1").write_bytes(CANARY)
        (h / "logs" / "lilith-router-decisions.log").write_bytes(b'{"event_id":"e1"} ' + CANARY)
        (h / "sessions" / "sessions.json").write_bytes(b'{"s1": "' + CANARY + b'"}')
        (h / "sessions" / "s1.jsonl").write_bytes(CANARY)
        (h / "sessions" / "request_dump_s1_1.json").write_bytes(b'{"content_free": true}')
        (h / "pending_messages" / "q1.json").write_bytes(CANARY)
        (h / "cache" / "xdg").mkdir(parents=True, exist_ok=True)
        (h / "cache" / "xdg" / "c.bin").write_bytes(CANARY)
        (h / "runtime" / "active_sessions.json").write_bytes(CANARY)
        (h / "state" / "s.json").write_bytes(CANARY)
        (h / "gateway" / "restart_loop.json").write_text("{}")
        (h / "channel_directory.json").write_bytes(CANARY)
        (h / "gateway_state.json").write_bytes(CANARY)
        (h / "cron" / "executions.db").write_bytes(CANARY)
        self.build_state_db(h / "state.db")
        self.protected_before = {k: v for k, v in sha_tree(h).items()
                                 if k.split("/")[0] in {p.split("/")[0] for p in X.PROTECTED}
                                 and not k.startswith("cron/executions")}

    def build_backups(self) -> None:
        b = self.backups
        pre = b / "pre-20261020T000000Z"
        pre.mkdir()
        stage = self.x / "tarstage" / ".hermes-dev"
        (stage / "sessions").mkdir(parents=True)
        (stage / "sessions" / "s0.jsonl").write_bytes(CANARY)
        (stage / "config.yaml").write_text("TEST_ONLY config (kept)\n")
        shutil.copy(self.home / "state.db", stage / "state.db")
        with tarfile.open(pre / "hermes-dev-home.tar", "w") as tar:
            tar.add(stage, arcname=".hermes-dev")
        (pre / "hermes-dev-home.listing").write_text("listing (metadata)\n")
        rb = b / "rollback-20261021T000000Z"
        (rb / "hermes-dev" / "logs").mkdir(parents=True)
        (rb / "hermes-dev" / "logs" / "gateway.log").write_bytes(CANARY)
        shutil.copy(self.home / "state.db", rb / "hermes-dev" / "state.db")
        (rb / "hermes-dev" / "SOUL.md").write_text("TEST_ONLY quarantined soul (kept)\n")
        (rb / "machineid.hermes-gateway-dev").mkdir()
        (rb / "machineid.hermes-gateway-dev" / "system.journal").write_bytes(CANARY)
        (rb / "opt" / "hermes-gateway-dev" / "src" / "gateway").mkdir(parents=True)
        (rb / "opt" / "hermes-gateway-dev" / "src" / "gateway" / "run.py").write_text("# TEST_ONLY code (kept)\n")
        (rb / "opt" / "hermes-gateway-dev" / "src" / "state").mkdir()
        (rb / "opt" / "hermes-gateway-dev" / "src" / "state" / "keep.py").write_text("# TEST_ONLY code (kept)\n")
        (b / "f8r4-evidence").mkdir()
        (b / "f8r4-evidence" / "decisions.tsv").write_text("event_id\tmode\n")
        self.backup_code_before = {k: v for k, v in sha_tree(b).items()
                                   if k.endswith(("run.py", "keep.py", "decisions.tsv", "SOUL.md", ".listing"))}

    # ------------------------------------------------------------------------------------------------ running ---
    def run_executor(self, fault: str = "") -> int:
        out = subprocess.run([PY311, "-I", "-B", str(DRIVER), str(PKG / "bin"), str(self.config), fault,
                              str(self.host_state)], capture_output=True, text=True, timeout=300)
        self.run_log.append(out.stderr)
        return out.returncode

    def _tick(self, seconds: float) -> None:
        if self.auto_run:
            self.run_executor()
        self.ticks += seconds

    def hermes(self, **kw):
        return H.HermesConversationErasureOwner(
            self.privacy, self.client, deployment_environment="DEV_SYNTHETIC", timeout_seconds=kw.get("timeout", 30),
            poll_seconds=1.0, sleep=self._tick, monotonic=lambda: self.ticks)

    def owners_real(self, **wrap):
        return self.owners(**{HERMES: self.hermes(), **wrap})

    def forget_real(self, runner=None):
        return self.forget(runner or self.runner(self.owners_real()))

    def in_flight(self):
        return self.privacy.in_flight_authorization(FI)

    def queue(self, ref, nonce, **extra):
        """Bypasses adapter check #1: writes a request straight into the spool."""
        body = {"v": 1, "owner": HERMES, "authorizationRefId": ref, "executionNonce": nonce, **extra}
        name = self.spool / f"t-{hashlib.sha256(json.dumps(body).encode()).hexdigest()[:12]}.req"
        name.write_text(json.dumps(body))
        return name

    def stalled(self):
        """An FI FORGET in flight with L04 + L18_V2 COMPLETE and Hermes pending (no executor ran)."""
        self.auto_run = False
        result = self.forget_real(self.runner(self.owners(**{HERMES: self.hermes(timeout=2)})))
        self.assertEqual((result.status, result.failure_code), (R.INCOMPLETE_HOLD_ACTIVE, "EXECUTOR_TIMEOUT"))
        for leftover in self.spool.glob("*.req"):
            leftover.unlink()                                                    # the adapter's queued request
        self.auto_run = True
        return self.in_flight()

    def receipt(self, ref):
        p = self.receipts / f"{ref}.receipt.json"
        return json.loads(p.read_text()) if p.exists() else None

    # ---------------------------------------------------------------------------------------------- assertions ---
    def counts(self):
        db = self.home / "state.db"
        if not db.exists():
            return {}
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("sessions", "messages", "system_prompts", "gateway_routing", "delivery_obligations")}
        finally:
            conn.close()

    def assert_untouched(self):
        self.assertEqual(self.counts(), {"sessions": 2, "messages": 6, "system_prompts": 1, "gateway_routing": 1, "delivery_obligations": 1})
        self.assertTrue((self.home / "logs" / "gateway.log").exists())
        self.assertTrue((self.backups / "rollback-20261021T000000Z" / "hermes-dev" / "state.db").exists())
        self.assertFalse((self.epochs / "epochs.log").exists())

    def assert_erased(self):
        self.assertEqual(self.counts(), {"sessions": 0, "messages": 0, "system_prompts": 0, "gateway_routing": 0, "delivery_obligations": 0})
        for d in X.PURGE_DIRS:
            self.assertEqual(list((self.home / d).iterdir()), [], d)
        for f in ("channel_directory.json", "gateway_state.json", "cron/executions.db"):
            self.assertFalse((self.home / f).exists(), f)
        protected_now = {k: v for k, v in sha_tree(self.home).items() if k in self.protected_before}
        self.assertEqual(protected_now, self.protected_before)                  # T23
        code_now = {k: v for k, v in sha_tree(self.backups).items() if k in self.backup_code_before}
        self.assertEqual(code_now, self.backup_code_before)                      # code/config in backups kept
        self.assertEqual(X.scan_backups(self.backups), [])
        with tarfile.open(self.backups / "pre-20261020T000000Z" / "hermes-dev-home.tar") as tar:
            self.assertEqual(sorted(m.name for m in tar if m.isfile()), [".hermes-dev/config.yaml"])
        self.assertEqual(canary_hits(self.home, self.backups, self.state, self.receipts, self.epochs), [])  # T19
        self.assertTrue(all(CANARY.decode() not in log for log in self.run_log))                         # T24
        self.assertEqual(self.run_executor(fault="reconcile"), 0)              # the timer's release check
        self.assertFalse((self.x / "lib" / "in-progress").exists())

    def assert_blocked(self):
        """Fail closed: Privacy incomplete with the hold ACTIVE, gateway marker present."""
        self.assertIsNotNone(self.in_flight())
        self.assertTrue(self.privacy.is_held(*FI))
        self.assertEqual(self.prows("SELECT COUNT(*) FROM privacy_completion_receipt"), [(0,)])


class HappyPathTests(ExecutorCase):
    def test_T1_T19_T23_T24_T25_full_forget_through_the_real_executor(self):
        result = self.forget_real()
        self.assertEqual(result.status, R.COMPLETE, (result, self.run_log))
        self.assert_erased()
        self.assert_fi_erased()
        receipts = list(self.receipts.glob("*.receipt.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text())
        self.assertEqual((receipt["status"], receipt["claim"], receipt["providerErasure"], receipt["erasureEpoch"]),
                         ("COMPLETE", "LOGICAL_ERASURE_VERIFIED", "ATTESTED_ZDR_NOT_VERIFIED", 1))      # T25
        self.assertEqual(receipt["receiptDigest"], H.receipt_digest(receipt))
        self.assertEqual(stat.S_IMODE(receipts[0].stat().st_mode), 0o640)
        self.assertEqual([e["epoch"] for e in X.read_epochs(self.epochs / "epochs.log")], [1])
        self.assertEqual(list(self.spool.glob("*")), [])
        tombs = list((self.backups / "FORGET-TOMBSTONES").glob("*.json"))
        self.assertEqual(len(tombs), 1)
        self.assertGreaterEqual(len(json.loads(tombs[0].read_text())["removed"]), 5)
        self.assertEqual(self.host()["gatewayActive"], False)                   # restart is OnSuccess= (mirror)
        self.assertNotIn(b"sessionIds", self.privacy_db.read_bytes())


class AuthorizationTests(ExecutorCase):
    def test_T3_wrong_nonce_forged_hmac_unlisted_owner_each_refused_by_the_executor_alone(self):
        ref, nonce = self.stalled()
        cases = {
            "wrong nonce": (ref, "execution." + "f" * 32, {}),
            "forged reference": ("erase." + "0" * 32, nonce, {}),
            "tampered HMAC (other secret)": (ref, nonce, {"secret": b"TEST_ONLY a different 32+ byte secret!!"}),
        }
        for label, (r, n, opt) in cases.items():
            with self.subTest(label):
                if "secret" in opt:
                    self.secret.write_bytes(opt["secret"])
                self.queue(r, n)
                self.assertEqual(self.run_executor(), 1)
                self.assertIn("AUTHORIZATION_NOT_VERIFIED", self.run_log[-1])
                self.assertIsNone(self.receipt(r))                               # a forged request writes nothing
                self.assert_untouched()
                self.secret.write_bytes(SECRET)
                for parked in self.spool.glob("*.failed"):
                    parked.unlink()
        self.assert_blocked()

    def test_T3_an_authorization_that_does_not_list_hermes_is_refused(self):
        from lilith_memory import canonical_contracts as C
        codename = C.FrozenMemoryActionV1(
            schema_version=1, actor_ref_id=self.actor.ACTOR.actor_ref_id, operation=C.FORGET,
            memory_class="SYNTHETIC_PROJECT_CODENAME_FACT", subject_namespace="project.synthetic",
            subject_key="codename", value_schema=None, payload_digest="0" * 64, expected_active_revision_id=None,
            restore_revision_id=None, purpose=C.LONG_TERM_PERSONAL_PROJECT_RECALL)
        evidence = self.actor.issue(action=codename, request_digest="2" * 64, nonce="exec.codename")
        _r, auth, _s = self.privacy.begin_forget(
            action=codename, actor_evidence_ref_id=evidence.actor_evidence_ref_id, intent_ref_id="i.c",
            memory_item_id=None, resource_owners=("L04", "L18_V2"), confirmation_event_ref="c.c")
        self.queue(auth.authorization_ref_id, auth.execution_nonce)
        self.assertEqual(self.run_executor(), 1)
        self.assertIn("AUTHORIZATION_NOT_VERIFIED", self.run_log[-1])
        self.assert_untouched()

    def test_T3_unpinned_core_api_modules_are_refused(self):
        ref, nonce = self.stalled()
        pins = json.loads(self.config.read_text())["coreApiSha256"]
        self.write_config(coreApiSha256={**pins, "privacy_governance.py": "0" * 64})
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(), 1)
        self.assertIn("CORE_API_MODULES_UNPINNED", self.run_log[-1])
        self.assert_untouched()

    def test_T3_tampered_core_api_code_is_never_imported(self):
        """The pins are checked BEFORE import: importing runs module code as root, so a tampered module must never
        execute (a post-import check alone would be too late)."""
        ref, nonce = self.stalled()
        tampered = self.x / "tampered" / "lilith_memory"
        shutil.copytree(CORE / "lilith_memory", tampered)
        executed = self.x / "TAMPERED-CODE-RAN"
        with open(tampered / "privacy_governance.py", "a") as fh:
            fh.write(f"\nopen({str(executed)!r}, 'w').close()\n")
        pins = json.loads(self.config.read_text())["coreApiSha256"]                # the genuine module hashes
        self.write_config(coreApiDir=str(tampered), coreApiSha256=pins)
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(), 1)
        self.assertIn("CORE_API_MODULES_UNPINNED", self.run_log[-1])
        self.assertFalse(executed.exists(), "tampered Core API code ran as root")
        self.assert_untouched()

    def test_T4_replay_after_completion_touches_nothing(self):
        self.assertEqual(self.forget_real().status, R.COMPLETE)
        ref = json.loads(next(self.receipts.glob("*.receipt.json")).read_text())
        (self.home / "logs" / "after.log").write_bytes(CANARY)                  # new content after the FORGET
        self.queue(ref["authorizationRefId"], ref["executionNonce"])
        self.assertEqual(self.run_executor(), 0)                                # journal + proven completion
        self.assertTrue((self.home / "logs" / "after.log").exists())           # nothing erased again
        for journal in self.state.glob("*.json"):                               # executor state lost
            journal.unlink()
        self.queue(ref["authorizationRefId"], ref["executionNonce"])
        self.assertEqual(self.run_executor(), 1)
        self.assertIn("AUTHORIZATION_NOT_VERIFIED", self.run_log[-1])           # the authorization is gone
        self.assertTrue((self.home / "logs" / "after.log").exists())
        self.assertEqual([e["epoch"] for e in X.read_epochs(self.epochs / "epochs.log")], [1])

    def test_production_entry_refuses_non_dev_synthetic_and_untrusted_config(self):
        self.write_config(deploymentEnvironment="DEV")
        with self.assertRaises(X.ExecutorError) as caught:
            X.Config.load(self.config)
        self.assertEqual(caught.exception.code, "INTERIM_V1_PATH_DEV_SYNTHETIC_ONLY")
        self.write_config()
        os.chmod(self.config, 0o666)
        with self.assertRaises(X.ExecutorError) as caught:
            X.Config.load(self.config)
        self.assertEqual(caught.exception.code, "CONFIG_UNTRUSTED")


class RequestTests(ExecutorCase):
    def test_T5_malformed_requests_are_rejected_before_any_action(self):
        ref, nonce = self.stalled()
        good = {"v": 1, "owner": HERMES, "authorizationRefId": ref, "executionNonce": nonce}
        bad = {
            "extra sessionIds": json.dumps({**good, "sessionIds": ["s1"]}),
            "wrong owner": json.dumps({**good, "owner": "L04"}),
            "oversize": json.dumps({**good}) + " " * 2000,
            "not json": "not json",
        }
        for label, body in bad.items():
            with self.subTest(label):
                p = self.spool / "bad.req"
                p.write_text(body)
                self.assertEqual(self.run_executor(), 1)
                self.assertIn("REQUEST_REJECTED", self.run_log[-1])
                self.assertFalse(p.exists())
                self.assertTrue((self.spool / "bad.failed").exists())
                (self.spool / "bad.failed").unlink()
                self.assert_untouched()
        target = self.x / "elsewhere.json"
        target.write_text(json.dumps(good))
        for label, make in (("symlink", lambda p: p.symlink_to(target)),
                             ("hardlink", lambda p: os.link(target, p)),
                             ("wrong uid", lambda p: (p.write_text(json.dumps(good)), os.chown(p, 65534, 65534)))):
            with self.subTest(label):
                p = self.spool / "odd.req"
                make(p)
                self.assertEqual(self.run_executor(), 1)
                self.assertIn("REQUEST_REJECTED", self.run_log[-1])
                for f in self.spool.iterdir():
                    f.unlink()
                self.assert_untouched()
        self.assertTrue(target.exists())

    def test_spool_client_writes_only_the_contract(self):
        self.client.submit(H.erasure_request("erase." + "1" * 32, "execution." + "2" * 32))
        (req,) = self.spool.glob("*.req")
        self.assertEqual(json.loads(req.read_text()), {"v": 1, "owner": HERMES,
                                                       "authorizationRefId": "erase." + "1" * 32,
                                                       "executionNonce": "execution." + "2" * 32})
        self.assertEqual(req.stat().st_nlink, 1)
        for bad in ({"v": 1}, {**H.erasure_request("erase." + "1" * 32, "n"), "sessionIds": []},
                    H.erasure_request("../../etc/passwd", "n")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.client.submit(bad)
        p = self.receipts / ("erase." + "3" * 32 + ".receipt.json")
        p.write_text("{}")
        os.chown(p, 65534, 65534)
        with self.assertRaises(PermissionError):
            self.client.read_receipt("erase." + "3" * 32)                       # not executor-owned
        with self.assertRaises(ValueError):
            self.client.read_receipt("../x")


class CrashTests(ExecutorCase):
    def test_T7_kill_at_every_phase_keeps_privacy_incomplete_and_a_retry_converges(self):
        for point in FAULT_POINTS:
            with self.subTest(point=point):
                self.tearDown()
                self.setUp()
                ref, nonce = self.stalled()
                self.queue(ref, nonce)
                self.assertEqual(self.run_executor(fault=point), 137)
                self.assert_blocked()
                self.assertTrue((self.x / "lib" / "in-progress").exists())      # gateway cannot start, at EVERY point
                if point.startswith("after:RECEIPT"):
                    self.assertEqual(self.receipt(ref)["status"], "COMPLETE")    # written, but not yet success
                    self.assertEqual(self.counts()["messages"], 0)
                else:
                    self.assertIsNone(self.receipt(ref))
                if point == "backups:before-tombstone":                          # tombstone strictly before deletion
                    self.assertTrue((self.backups / "rollback-20261021T000000Z" / "hermes-dev" / "state.db").exists())
                    self.assertFalse((self.backups / "FORGET-TOMBSTONES").exists()
                                     and any((self.backups / "FORGET-TOMBSTONES").iterdir()))
                self.assertEqual(self.runner().resume().status, R.COMPLETE, self.run_log[-3:])
                self.assert_erased()
                self.assertEqual([e["epoch"] for e in X.read_epochs(self.epochs / "epochs.log")], [1])

    def test_T8_reboot_loses_the_spool_and_the_adapter_retry_resumes(self):
        ref, nonce = self.stalled()
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(fault="after:SQLITE"), 137)
        for f in self.spool.iterdir():                                           # /run is a tmpfs: gone at boot
            f.unlink()
        self.assertTrue((self.x / "lib" / "in-progress").exists())
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        self.assert_erased()

    def test_T9_locked_database_and_a_gateway_that_will_not_stop(self):
        ref, nonce = self.stalled()
        holder = sqlite3.connect(self.home / "state.db", timeout=1)
        holder.execute("BEGIN EXCLUSIVE")
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(), 1)
        self.assertIn("STATE_DB_LOCKED", self.run_log[-1])
        holder.execute("ROLLBACK")
        holder.close()
        self.assertEqual(self.counts()["messages"], 6)                         # nothing deleted
        self.assert_blocked()
        self.set_host(gatewayActive=True, refuseStop=True)
        for f in self.spool.glob("*.failed"):
            f.unlink()
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(), 1)
        self.assertIn("GATEWAY_NOT_STOPPED", self.run_log[-1])
        self.assertEqual(self.counts()["messages"], 6)
        self.set_host(gatewayActive=False, portOpen=True)
        for f in self.spool.glob("*.failed"):
            f.unlink()
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(), 1)
        self.assertIn("GATEWAY_STILL_LISTENING", self.run_log[-1])
        self.set_host()
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        self.assert_erased()

    def test_T10_committed_rows_left_in_the_wal_are_erased(self):
        ref, nonce = self.stalled()
        writer = (f"import sqlite3,os\nc=sqlite3.connect({str(self.home / 'state.db')!r})\n"
                  "c.execute('PRAGMA wal_autocheckpoint=0')\n"
                  "c.execute(\"INSERT INTO messages(session_id, role, content, timestamp) VALUES "
                  "('s1','user','WAL-ONLY " + CANARY.decode() + "', 0)\")\nc.commit()\nos._exit(0)\n")
        subprocess.run([sys.executable, "-c", writer], check=True)              # like a SIGTERM'd gateway
        self.assertGreater((self.home / "state.db-wal").stat().st_size, 0)
        self.assertEqual(self.counts()["messages"], 7)
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        self.assert_erased()
        self.assertEqual((self.home / "state.db-wal").stat().st_size if (self.home / "state.db-wal").exists() else 0,
                         0)

    def test_T11_disk_full_fails_closed_and_converges_once_space_is_freed(self):
        """A real full filesystem: with secure_delete the purge itself must rewrite every content page through the
        WAL, so ENOSPC hits the COMMIT; it rolls back (nothing half-deleted), fails closed, and a retry after space is
        freed completes. (A VACUUM failure after the commit is T11b.)"""
        ref, nonce = self.stalled()
        mnt = self.x / "small"
        mnt.mkdir()
        subprocess.run(["mount", "-t", "tmpfs", "-o", "size=96m", "tmpfs", str(mnt)], check=True)
        try:
            shutil.copytree(self.home, mnt / "home", symlinks=True)
            shutil.rmtree(self.home)
            self.home = mnt / "home"
            self.write_config()
            conn = sqlite3.connect(self.home / "state.db")
            conn.executemany("INSERT INTO messages(session_id, role, content, timestamp) VALUES ('s1','user',?,0)",
                             [(CANARY.decode() + " " + "x" * 1500,) for _ in range(4000)])     # ~6 MB of history
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
            before = self.counts()
            filler = mnt / "filler"
            filler.write_bytes(b"\0" * max(shutil.disk_usage(mnt).free - (256 << 10), 0))
            self.queue(ref, nonce)
            self.assertEqual(self.run_executor(), 1, self.run_log[-1])
            self.assertEqual(self.counts(), before, "the failed purge rolled back completely")
            self.assertIsNone(self.receipt(ref))
            self.assert_blocked()
            self.assertTrue((self.x / "lib" / "in-progress").exists())
            filler.unlink()
            self.assertEqual(self.runner().resume().status, R.COMPLETE, self.run_log[-2:])
            self.assertEqual(self.counts(), {"sessions": 0, "messages": 0, "system_prompts": 0, "gateway_routing": 0, "delivery_obligations": 0})
            self.assertEqual(canary_hits(self.home), [])
        finally:
            subprocess.run(["umount", "-l", str(mnt)])

    def test_T11b_vacuum_failure_after_the_commit_keeps_deleted_rows_deleted(self):
        ref, nonce = self.stalled()
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(fault="raise:sqlite:vacuum"), 1)
        self.assertIn("STATE_DB_VACUUM_FAILED", self.run_log[-1])
        self.assertEqual(self.counts()["messages"], 0)                         # the purge committed before VACUUM
        self.assertIsNone(self.receipt(ref))
        self.assert_blocked()
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        self.assert_erased()

    def test_T12_journal_vacuum_failure_then_retry(self):
        ref, nonce = self.stalled()
        self.set_host(gatewayActive=False, journalFail="--vacuum-time")
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(), 1)
        self.assertIn("JOURNAL_VACUUM_FAILED", self.run_log[-1])
        self.assertIsNone(self.receipt(ref))
        self.assert_blocked()
        self.set_host(gatewayActive=False, journalEntries=3)
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        self.assertIn(["--rotate"], self.host()["journalCalls"])

    def test_T12b_a_vacuum_that_leaves_old_entries_is_not_accepted(self):
        ref, nonce = self.stalled()
        self.set_host(gatewayActive=False, journalStuck=True, journalEntries=2)
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(), 1)
        self.assertIn("JOURNAL_VERIFY_FAILED", self.run_log[-1])
        self.assertIsNone(self.receipt(ref))
        self.assert_blocked()

    def test_T13_tombstone_write_failure_deletes_no_backup_then_retry(self):
        ref, nonce = self.stalled()
        (self.backups / "FORGET-TOMBSTONES").write_text("not a directory")
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(), 1)
        self.assertTrue((self.backups / "rollback-20261021T000000Z" / "hermes-dev" / "state.db").exists())
        self.assert_blocked()
        (self.backups / "FORGET-TOMBSTONES").unlink()
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        self.assert_erased()

    def test_T23_a_protected_file_changing_mid_erasure_fails_closed(self):
        ref, nonce = self.stalled()
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(fault="after:SQLITE"), 137)
        (self.home / "SOUL.md").write_text("TEST_ONLY tampered soul\n")
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(), 1)
        self.assertIn("PROTECTED_FILES_CHANGED", self.run_log[-1])
        self.assert_blocked()


class FinalizationWindowTests(ExecutorCase):
    """Part 1 review: the receipt is written while the gateway stays blocked; only Privacy's own COMPLETED record of
    this authorization (with Hermes COMPLETE) releases the marker. Crashes exactly at the receipt boundary."""

    MARKER = property(lambda self: self.x / "lib" / "in-progress")

    def reconcile(self):
        self.assertEqual(self.run_executor(fault="reconcile"), 0)

    def assert_still_blocked(self):
        self.assert_blocked()                                    # Privacy hold ACTIVE, no Privacy completion
        self.assertTrue(self.MARKER.exists())                    # the gateway drop-in refuses every start
        self.reconcile()
        self.assertTrue(self.MARKER.exists(), "reconcile must not release before Privacy completion")

    def test_kill_right_after_the_receipt_is_written(self):
        ref, nonce = self.stalled()
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(fault="after:RECEIPT-written"), 137)
        self.assertEqual(self.receipt(ref)["status"], "COMPLETE")
        self.assertIsNone(self.privacy.owner_result(ref, nonce, HERMES))         # receipt alone is not success
        self.assert_still_blocked()
        submitted = len(list(self.spool.glob("*.req")))
        self.assertEqual(self.runner().resume().status, R.COMPLETE)              # adapter verifies and records
        self.assertEqual(len(list(self.spool.glob("*.req"))), submitted)         # no resubmission needed
        self.assertTrue(self.MARKER.exists(), "nothing has released the gateway yet")
        self.reconcile()                                                         # Privacy now proves completion
        self.assertFalse(self.MARKER.exists())
        self.assert_erased()

    def test_kill_right_before_the_receipt_is_written(self):
        ref, nonce = self.stalled()
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(fault="before:receipt"), 137)
        self.assertIsNone(self.receipt(ref))
        self.assert_still_blocked()
        self.assertEqual(self.runner().resume().status, R.COMPLETE)              # resubmits; receipt written
        self.assertTrue(self.MARKER.exists())
        self.reconcile()
        self.assert_erased()

    def test_privacy_completion_failing_after_hermes_was_recorded_keeps_the_gateway_blocked(self):
        from unittest import mock
        with mock.patch.object(self.privacy, "complete", side_effect=sqlite3.OperationalError("TEST_ONLY busy")):
            result = self.forget_real()
        self.assertEqual(result.failure_code, "PRIVACY_COMPLETION_FAILED:OperationalError")
        ref, nonce = self.in_flight()
        self.assertEqual(self.privacy.owner_result(ref, nonce, HERMES), "COMPLETE")
        self.assert_still_blocked()                                              # Hermes done, FORGET not
        self.assertEqual(self.runner().resume().status, R.COMPLETE)
        self.reconcile()
        self.assert_erased()

    def test_reconcile_under_a_wrong_secret_never_releases(self):
        self.assertEqual(self.forget_real().status, R.COMPLETE)
        self.secret.write_bytes(b"TEST_ONLY a different 32+ byte secret!!")
        self.reconcile()
        self.assertTrue(self.MARKER.exists())
        self.secret.write_bytes(SECRET)
        self.reconcile()
        self.assertFalse(self.MARKER.exists())

    def test_kill_inside_the_release_step_then_reconcile_again(self):
        self.assertEqual(self.forget_real().status, R.COMPLETE)
        self.assertEqual(self.run_executor(fault="reconcile:after:RELEASED"), 137)  # journal released, then killed
        self.assertTrue(self.MARKER.exists())
        self.reconcile()
        self.assertFalse(self.MARKER.exists())

    def test_a_requeued_request_after_completion_is_success_not_failure(self):
        self.assertEqual(self.forget_real().status, R.COMPLETE)
        receipt = json.loads(next(self.receipts.glob("*.receipt.json")).read_text())
        self.queue(receipt["authorizationRefId"], receipt["executionNonce"])
        self.assertEqual(self.run_executor(), 0, self.run_log[-1])                 # so OnSuccess restarts
        self.assertFalse(self.MARKER.exists())
        self.assertEqual(list(self.spool.glob("*.req")), [])


class RetryTests(ExecutorCase):
    def test_T15_another_owner_fails_first_then_everything_completes(self):
        l18 = CountingOwner(self.owners()["L18_V2"], fail_times=1)
        result = self.forget_real(self.runner(self.owners_real(L18_V2=l18)))
        self.assertEqual((result.status, result.failed_owner), (R.INCOMPLETE_HOLD_ACTIVE, "L18_V2"))
        self.assertEqual(list(self.receipts.iterdir()), [])                    # Hermes not reached yet
        self.assertEqual(self.runner(self.owners_real(L18_V2=l18)).resume().status, R.COMPLETE)
        self.assert_erased()

    def test_T16_adapter_timeout_then_a_late_receipt_is_reused(self):
        self.auto_run = False
        result = self.forget_real(self.runner(self.owners(**{HERMES: self.hermes(timeout=2)})))
        self.assertEqual(result.failure_code, "EXECUTOR_TIMEOUT")
        self.assertEqual(self.run_executor(), 0)                                # the executor finishes late
        submitted = len(list(self.spool.glob("*")))
        self.assertEqual(self.runner(self.owners(**{HERMES: self.hermes()})).resume().status, R.COMPLETE)
        self.assertEqual(len(list(self.spool.glob("*"))), submitted)            # no resubmission
        self.assert_erased()


class PrincipalTests(ExecutorCase):
    def expect_rejected(self, code):
        ref, nonce = self.stalled()
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(), 0)
        receipt = self.receipt(ref)
        self.assertEqual(receipt["status"], "REJECTED")
        self.assertEqual(receipt["receiptDigest"], H.receipt_digest(receipt))
        self.assertIn(f'"code": "{code}"', self.run_log[-1])
        self.assertEqual(self.counts()["messages"], 6)
        self.assertFalse((self.x / "lib" / "in-progress").exists())             # nothing started
        result = self.runner(self.owners_real()).resume()
        self.assertEqual((result.status, result.failure_code), (R.INCOMPLETE_HOLD_ACTIVE, "EXECUTOR_REJECTED"))
        self.assert_blocked()

    def test_T17_another_platform_token(self):
        with open(self.home / ".env", "a") as fh:
            fh.write("TELEGRAM_BOT_TOKEN=TEST_ONLY\n")
        self.expect_rejected("MULTI_PRINCIPAL_STORE")

    def test_T17_another_enabled_plugin(self):
        text = (self.home / "config.yaml").read_text().replace("    - lilith_os\n", "    - lilith_os\n    - telegram\n")
        (self.home / "config.yaml").write_text(text)
        self.protected_before["config.yaml"] = hashlib.sha256(text.encode()).hexdigest()
        self.expect_rejected("MULTI_PRINCIPAL_STORE")

    def test_T17_unrecognized_session_source(self):
        (self.home / "state.db").unlink()
        for f in self.home.glob("state.db-*"):
            f.unlink()
        self.build_state_db(self.home / "state.db", sessions=(("s1", "lilith_os", "owner"), ("s2", "telegram", "x")))
        self.expect_rejected("UNRECOGNIZED_SESSION")

    def test_T17_ambiguous_ownership(self):
        (self.home / "state.db").unlink()
        for f in self.home.glob("state.db-*"):
            f.unlink()
        self.build_state_db(self.home / "state.db", sessions=(("s1", "lilith_os", "owner"), ("s2", "lilith_os", "b")))
        self.expect_rejected("AMBIGUOUS_OWNERSHIP")

    def test_T17_unknown_hermes_table(self):
        conn = sqlite3.connect(self.home / "state.db")
        conn.execute("CREATE TABLE future_conversation_cache(x TEXT)")
        conn.commit()
        conn.close()
        self.expect_rejected("UNKNOWN_HERMES_SCHEMA")


class RestoreGuardTests(ExecutorCase):
    def test_T18_pre_epoch_conversation_copies_are_refused_code_config_and_newer_copies_allowed(self):
        old_copy = self.x / "outside" / "rollback-20261021T000000Z"
        shutil.copytree(self.backups / "rollback-20261021T000000Z", old_copy, symlinks=True)
        code_only = self.x / "outside" / "release-copy"
        (code_only / "opt").mkdir(parents=True)
        (code_only / "opt" / "run.py").write_text("# code\n")
        log = self.epochs / "epochs.log"
        self.assertEqual(G.check([old_copy], log)[0], G.ALLOWED)                # no epoch yet
        self.assertEqual(self.forget_real().status, R.COMPLETE)
        code, refused, epoch = G.check([old_copy], log)
        self.assertEqual((code, epoch), (G.SUPPRESSED, 1))
        self.assertGreaterEqual(refused, 3)
        self.assertEqual(G.check([code_only], log)[0], G.ALLOWED)
        renamed = self.x / "outside" / "rollback-29991231T000000Z"                # an old copy, newly stamped
        shutil.copytree(old_copy, renamed, symlinks=True)                         # copystat keeps the old mtime
        self.assertEqual(G.check([renamed], log)[0], G.SUPPRESSED, "a future name stamp cannot outrank the mtime")
        time.sleep(1.1)
        newer = self.x / "outside" / f"rollback-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(time.time() + 5))}"
        (newer / "hermes-dev" / "logs").mkdir(parents=True)
        (newer / "hermes-dev" / "logs" / "gateway.log").write_text("post-epoch\n")
        self.assertEqual(G.check([newer], log)[0], G.ALLOWED)                   # history captured after the epoch
        out = subprocess.run([PY311, "-I", "-B", str(PKG / "bin" / "hermes_restore_guard.py"), "--epoch-log",
                              str(log), "check", str(old_copy)], capture_output=True, text=True)
        self.assertEqual(out.returncode, 3)
        self.assertIn("F8_RESTORE_CONVERSATION_SUPPRESSED", out.stderr)

    def test_T18_restore_f8r2_runs_the_guard_before_moving_anything(self):
        script = (PKG / "bin" / "restore_f8r2.sh").read_text()
        guard, first_move = script.index("hermes_restore_guard.py"), script.index('mv "${Q}')
        self.assertLess(guard, first_move)
        self.assertIn("F8_RESTORE_CONVERSATION_SUPPRESSED", script)

    def test_epoch_log_must_be_root_only_and_contiguous(self):
        log = self.epochs / "epochs.log"
        log.write_text('{"epoch": 2, "at": "2026-10-24T00:00:00Z", "authDigest": "x"}\n')
        os.chmod(log, 0o600)
        with self.assertRaises(X.ExecutorError) as caught:
            X.read_epochs(log)
        self.assertEqual(caught.exception.code, "EPOCH_LOG_CORRUPT")
        os.chmod(log, 0o644)
        with self.assertRaises(X.ExecutorError):
            X.read_epochs(log)


class BoundaryTests(ExecutorCase):
    def test_T20_the_executor_never_writes_privacy_or_canonical_stores(self):
        ref, nonce = self.stalled()
        privacy_before, cognitive_before = self.privacy_db.read_bytes(), self.db.read_bytes()
        self.queue(ref, nonce)
        self.assertEqual(self.run_executor(), 0, self.run_log[-1])
        self.assertEqual((self.privacy_db.read_bytes(), self.db.read_bytes()), (privacy_before, cognitive_before))
        self.assertEqual(self.receipt(ref)["status"], "COMPLETE")

    def test_a_stale_full_text_index_is_rebuilt_not_trusted(self):
        """Index entries with no messages row (e.g. an interrupted Hermes reindex) are not removed by the delete
        triggers; the purge rebuilds every FTS table, so no indexed text survives in the file."""
        conn = sqlite3.connect(self.home / "state.db")
        conn.execute("INSERT INTO messages_fts(rowid, content, tool_name, tool_calls) VALUES (999999, ?, '', '')",
                     ("STALE-INDEX " + CANARY.decode(),))
        conn.commit()
        conn.close()
        self.assertEqual(self.forget_real().status, R.COMPLETE, self.run_log[-1:])
        self.assertNotIn(CANARY, (self.home / "state.db").read_bytes())

    def test_symlinks_inside_purged_paths_are_never_followed(self):
        outside = self.x / "precious"
        outside.mkdir()
        (outside / "keep.txt").write_text("must survive\n")
        (self.home / "logs" / "link").symlink_to(outside)
        (self.home / "cache" / "dirlink").symlink_to(outside, target_is_directory=True)
        shutil.rmtree(self.home / "audio_cache")
        (self.home / "audio_cache").symlink_to(outside, target_is_directory=True)   # a purge dir that IS a link
        self.assertEqual(self.forget_real().status, R.COMPLETE)
        self.assertEqual((outside / "keep.txt").read_text(), "must survive\n")
        self.assertFalse((self.home / "audio_cache").exists() or (self.home / "audio_cache").is_symlink())


if __name__ == "__main__":
    unittest.main()


class HostGateway:
    """The Core API's view of the (fake) gateway: stopped once the executor's phase_stop has stopped it."""

    def __init__(self, case):
        self.case = case

    def stopped(self):
        state = self.case.host()
        return not state.get("gatewayActive") and not state.get("portOpen")


class HoldFirstMatrixTests(ExecutorCase):
    """F9-C Track A: durable intent + root hold + gateway blocking + root-only intent release, real executor."""

    HELD_GID = 4243

    def setUp(self) -> None:
        super().setUp()
        self.write_config(receiptGid=self.HELD_GID)
        self.intents = I.ForgetIntentStore(self.intent_dir, holder_uid=0)
        self.intent = self.intent_dir / I.INTENT_NAME
        self.privacy_seen_before_hold = []

    def held(self):
        st = os.lstat(self.intent)
        return (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) == (0, self.HELD_GID, 0o640)

    def hold_tick(self, seconds):
        self.privacy_seen_before_hold.append(self.in_flight())
        self.assertEqual(self.run_executor("hold"), 0, self.run_log[-1])
        self.ticks += seconds

    def hold_first(self, runner=None):
        return I.HoldFirstForgetRunner(runner or self.runner(self.owners_real()), self.intents, HostGateway(self),
                                       hold_timeout_seconds=10, sleep=self.hold_tick, monotonic=lambda: self.ticks)

    def forget_hf(self, hf=None, evidence=None):
        evidence = evidence or self.evidence()
        return (hf or self.hold_first()).forget(
            actor_ref_id=self.actor.ACTOR.actor_ref_id, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
            intent_ref_id="intent.matrix.1", confirmation_event_ref="confirm.matrix.1")

    def reconcile(self, fault=""):
        return self.run_executor("reconcile" + (":" + fault if fault else ""))

    def test_hold_first_forget_end_to_end_privacy_waits_for_the_hold_and_root_releases_the_intent(self):
        result = self.forget_hf()
        self.assertEqual(result.status, R.COMPLETE, (result, self.run_log))
        self.assertEqual(self.privacy_seen_before_hold, [None])     # nothing authorized before the gateway stopped
        self.assertTrue(self.held())
        self.assertFalse(self.host()["gatewayActive"])
        self.assertTrue(any('"HELD"' in log and "GATEWAY_STOPPED" in log for log in self.run_log))
        self.assert_erased()                                        # includes the reconcile pass
        self.assertFalse(self.intent.exists())
        self.assertTrue(any("INTENT_RELEASED" in log for log in self.run_log))

    def test_H1_an_unlinked_temp_file_is_not_an_intent(self):
        tmp = self.intent_dir / f".{I.INTENT_NAME}.deadbeef.tmp"
        tmp.write_text("{}")
        self.assertEqual(self.run_executor("hold"), 0)
        self.assertEqual(list(self.intent_dir.glob("*.intent")), [])     # the gateway's and the hold's glob
        self.assertNotEqual(tmp.stat().st_gid, self.HELD_GID)              # never taken
        self.assertFalse(self.intent.exists())

    def test_H3_H4_hold_killed_before_or_after_taking_the_intent_converges_on_rerun(self):
        self.intents.record(intent_ref_id="intent.matrix.1", actor_ref_id=self.actor.ACTOR.actor_ref_id)
        self.assertEqual(self.run_executor("hold:hold:before-take"), 137)
        self.assertFalse(self.held())
        self.assertEqual(self.run_executor("hold:hold:after-take"), 137)
        self.assertTrue(self.held())
        self.assertTrue(self.host()["gatewayActive"])              # killed before the stop check (Conflicts= stops)
        self.assertEqual(self.run_executor("hold"), 0)
        self.assertTrue(self.held())
        self.assertFalse(self.host()["gatewayActive"])
        self.assertIsNone(self.in_flight())                         # the hold never authorizes anything

    def test_an_invalid_intent_is_kept_blocking_and_never_released_by_reconcile(self):
        self.intent.write_text('{"v": 1, "identity": "SOMETHING_ELSE"}')
        self.assertEqual(self.run_executor("hold"), 0)
        self.assertIn("INTENT_REJECTED", self.run_log[-1])
        self.assertTrue(self.intent.exists())
        self.assertEqual(self.reconcile(), 0)
        self.assertTrue(self.intent.exists())
        self.assertEqual(self.run_executor("cancel-confirmed"), 0)  # operator, owner-approved, nothing in flight
        self.assertFalse(self.intent.exists())

    def test_H5_H7_reconcile_never_releases_while_privacy_is_in_flight(self):
        self.stalled()
        self.intents.record(intent_ref_id="intent.matrix.1", actor_ref_id=self.actor.ACTOR.actor_ref_id)
        self.assertEqual(self.run_executor("hold"), 0)
        self.assertEqual(self.reconcile(), 0)
        self.assertTrue(self.intent.exists())
        self.assertEqual(self.run_executor("cancel-confirmed"), 2)  # an accepted FORGET cannot be cancelled
        self.assertIn("CANCEL_REFUSED_FORGET_IN_FLIGHT", self.run_log[-1])
        self.assertTrue(self.intent.exists())
        final = self.hold_first().resume()
        self.assertEqual(final.status, R.COMPLETE, (final, self.run_log))
        self.assertEqual(self.reconcile(), 0)
        self.assertFalse(self.intent.exists())

    def test_H6_consumed_evidence_without_a_privacy_transaction_keeps_the_intent_until_reconfirmed(self):
        evidence = self.evidence()
        real = self.privacy.begin_forget

        def crash_after_consumption(**kw):
            self.privacy.actor_authority.resolve_and_consume(
                kw["actor_evidence_ref_id"], action=kw["action"], consumer_ref="privacy.forget.v1")
            raise SystemExit("TEST_ONLY crash between evidence consumption and the Privacy transaction")

        self.privacy.begin_forget = crash_after_consumption
        try:
            with self.assertRaises(SystemExit):
                self.forget_hf(evidence=evidence)
        finally:
            self.privacy.begin_forget = real
        self.assertEqual(self.forget_hf(evidence=evidence).status, I.INTENT_STALLED_EVIDENCE_REFUSED)
        self.assertEqual(self.reconcile(), 0)
        self.assertTrue(self.intent.exists())                       # durable and blocking
        self.assertEqual(self.run_executor("cancel-unconfirmed"), 2)
        self.assertTrue(self.intent.exists())
        self.assert_untouched()
        result = self.forget_hf()                                   # owner re-confirms with fresh evidence
        self.assertEqual(result.status, R.COMPLETE, (result, self.run_log))
        self.assertEqual(self.reconcile(), 0)
        self.assertFalse(self.intent.exists())

    def test_H8_kill_inside_the_intent_release_then_reconcile_again(self):
        self.assertEqual(self.forget_hf().status, R.COMPLETE)
        self.assertEqual(self.reconcile("reconcile:before-intent-release"), 137)
        self.assertTrue(self.intent.exists())
        self.assertEqual(self.reconcile(), 0)
        self.assertFalse(self.intent.exists())

    def test_reconcile_under_a_wrong_secret_never_releases_the_intent(self):
        self.assertEqual(self.forget_hf().status, R.COMPLETE)
        wrong = self.x / "wrong.key"
        wrong.write_bytes(b"TEST_ONLY a different privacy secret, 32+ bytes")
        os.chmod(wrong, 0o600)
        self.write_config(receiptGid=self.HELD_GID, privacySecret=str(wrong))
        self.assertEqual(self.reconcile(), 0)
        self.assertTrue(self.intent.exists())
