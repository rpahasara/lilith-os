"""MIRROR-ONLY end to end (run as lilith, the Core API identity): the Slice 3 runner with the real L04/L18_V2 owners and
the Slice 2 Hermes adapter over the REAL spool client -> /run/hermes-forget/spool -> hermes-forget.path -> the root
executor in its real sandbox -> receipt -> adapter verification -> Privacy completion. The Privacy DB lives at the real
DEV path so the executor's sandbox binds exactly what it will bind on DEV. Synthetic data only."""

import os
import shutil
import sys
import unittest
from pathlib import Path

CORE = Path(os.environ["F9C_CORE_API"])
sys.path.insert(0, str(CORE / "tests"))

from test_privacy_forget_runner import HERMES, RunnerCase  # noqa: E402
from test_privacy_hermes_owner_v2 import SECRET  # noqa: E402

from lilith_memory import hermes_erasure_owner as H  # noqa: E402
from lilith_memory import hermes_erasure_spool as S  # noqa: E402
from lilith_memory import privacy_forget_runner as R  # noqa: E402
from lilith_memory import privacy_governance as privacy  # noqa: E402

DEV_PRIVACY = Path("/home/lilith/.hermes/lilith-os-dev/data/privacy_governance.dev.db")


class MirrorEndToEnd(RunnerCase):
    def setUp(self) -> None:
        super().setUp()
        for suffix in ("", "-wal", "-shm"):
            Path(str(DEV_PRIVACY) + suffix).unlink(missing_ok=True)
        shutil.copy2(self.privacy_db, DEV_PRIVACY)
        os.chmod(DEV_PRIVACY, 0o600)
        self.privacy_db = DEV_PRIVACY
        self.privacy = privacy.PrivacyGovernanceStore(DEV_PRIVACY, SECRET, self.actor, now_fn=lambda: self.now)

    def test_forget_through_the_installed_executor(self):
        hermes = H.HermesConversationErasureOwner(
            self.privacy, S.SpoolHermesErasureExecutor(), deployment_environment="DEV_SYNTHETIC",
            timeout_seconds=float(os.environ.get("F9C_TIMEOUT", "240")), poll_seconds=1.0)
        result = self.forget(self.runner(self.owners(**{HERMES: hermes})))
        print(f"MIRROR_RESULT status={result.status} failure={result.failure_code} "
              f"completed={','.join(result.completed_owners)}", flush=True)
        self.assertEqual(result.status, R.COMPLETE)
        self.assert_fi_erased()

    def test_locked_store_fails_closed_then_the_same_authorization_completes(self):
        """M6: the real executor meets a locked state.db: no receipt, marker kept (the gateway must refuse to start;
        the orchestrating script checks that between the two signal files), then the same authorization retries."""
        import subprocess
        import time
        signal_dir = Path(os.environ.get("F9C_SIGNAL_DIR", "/tmp/f9c4-m6"))
        db = Path("/home/lilith/.hermes-dev/state.db")
        locker = subprocess.Popen([sys.executable, "-c",
                                   "import sqlite3,sys,time;c=sqlite3.connect(sys.argv[1]);c.execute('BEGIN EXCLUSIVE')"
                                   ";print('locked',flush=True);time.sleep(600)", str(db)], stdout=subprocess.PIPE,
                                  text=True)
        self.assertEqual(locker.stdout.readline().strip(), "locked")
        hermes = H.HermesConversationErasureOwner(
            self.privacy, S.SpoolHermesErasureExecutor(), deployment_environment="DEV_SYNTHETIC",
            timeout_seconds=25.0, poll_seconds=1.0)
        runner = self.runner(self.owners(**{HERMES: hermes}))
        first = self.forget(runner)
        print(f"MIRROR_LOCKED status={first.status} failure={first.failure_code}", flush=True)
        self.assertEqual((first.status, first.failure_code), (R.INCOMPLETE_HOLD_ACTIVE, "EXECUTOR_TIMEOUT"))
        self.assertTrue(Path("/var/lib/hermes-forget/in-progress").exists())
        (signal_dir / "failed").touch()
        for _ in range(120):                                       # the script tries to start the gateway now
            if (signal_dir / "continue").exists():
                break
            time.sleep(1)
        locker.kill()
        locker.wait()
        final = runner.resume()
        print(f"MIRROR_RESUMED status={final.status} failure={final.failure_code}", flush=True)
        self.assertEqual(final.status, R.COMPLETE)
        self.assert_fi_erased()


if __name__ == "__main__":
    unittest.main()
