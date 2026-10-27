"""MIRROR-ONLY Track A drill (run as lilith, the Core API identity, against the INSTALLED f9c1 units).

The hold-first runner over the real intent directory, the real root hold (hermes-forget-hold.path), the real
gateway probe (systemctl + port), the real spool client and the installed root executor; Privacy + L04 + L18_V2 from
the runner fixture, with the Privacy DB at the real DEV path so the executor's sandbox binds exactly what it binds on
DEV. Once the hold is established the drill pauses (signal files) so the orchestrating script can probe the blocked
state from outside before Privacy authorizes anything. Synthetic data only; no provider.
"""

import os
import shutil
import sys
import time
import unittest
from pathlib import Path

CORE = Path(os.environ["F9C_CORE_API"])
sys.path.insert(0, str(CORE / "tests"))

from test_privacy_forget_runner import HERMES, RunnerCase  # noqa: E402
from test_privacy_hermes_owner_v2 import SECRET  # noqa: E402

from lilith_memory import hermes_erasure_owner as H  # noqa: E402
from lilith_memory import hermes_erasure_spool as S  # noqa: E402
from lilith_memory import privacy_forget_intent as I  # noqa: E402
from lilith_memory import privacy_forget_runner as R  # noqa: E402
from lilith_memory import privacy_governance as privacy  # noqa: E402

DEV_PRIVACY = Path("/home/lilith/.hermes/lilith-os-dev/data/privacy_governance.dev.db")
SIGNAL = Path(os.environ.get("F9CA_SIGNAL_DIR", "/tmp/f9ca-signal"))


class PausingProbe:
    """The real probe; the first time the hold is fully established it signals and waits for the script."""

    def __init__(self, inner, intents):
        self.inner, self.intents, self.paused = inner, intents, False

    def stopped(self):
        ok = self.inner.stopped()
        if ok and not self.paused and self.intents.state() == I.HELD:
            self.paused = True
            (SIGNAL / "held").touch()
            for _ in range(600):
                if (SIGNAL / "continue").exists():
                    break
                time.sleep(0.5)
        return ok


class DrillCase(RunnerCase):
    def setUp(self) -> None:
        super().setUp()
        for suffix in ("", "-wal", "-shm"):
            Path(str(DEV_PRIVACY) + suffix).unlink(missing_ok=True)
        shutil.copy2(self.privacy_db, DEV_PRIVACY)
        os.chmod(DEV_PRIVACY, 0o600)
        self.privacy_db = DEV_PRIVACY
        self.privacy = privacy.PrivacyGovernanceStore(DEV_PRIVACY, SECRET, self.actor, now_fn=lambda: self.now)


class Drill(DrillCase):
    def test_hold_first_forget_through_the_installed_units(self):
        intents = I.ForgetIntentStore()
        hermes = H.HermesConversationErasureOwner(
            self.privacy, S.SpoolHermesErasureExecutor(), deployment_environment="DEV_SYNTHETIC",
            timeout_seconds=float(os.environ.get("F9C_TIMEOUT", "300")), poll_seconds=1.0)
        hf = I.HoldFirstForgetRunner(self.runner(self.owners(**{HERMES: hermes})), intents,
                                     PausingProbe(I.GatewayProbe(), intents), hold_timeout_seconds=180)
        evidence = self.evidence()
        result = hf.forget(actor_ref_id=self.actor.ACTOR.actor_ref_id, actor_evidence_ref_id=evidence.actor_evidence_ref_id,
                           intent_ref_id="intent.f9ca.drill", confirmation_event_ref="confirm.f9ca.drill")
        print(f"MIRROR_RESULT status={result.status} failure={result.failure_code} "
              f"completed={','.join(result.completed_owners)}", flush=True)
        self.assertEqual(result.status, R.COMPLETE)
        self.assert_fi_erased()

    def test_prepare_an_unforgotten_privacy_database(self):
        """Leaves a fresh First Interaction fixture (nothing forgotten) at the DEV path for the stall/cancel probes."""
        self.assertIsNone(self.privacy.in_flight_authorization(R.IDENTITY))
        self.assertFalse(self.privacy.suppression_matches(R.IDENTITY))
        print("MIRROR_PREPARED", flush=True)


class RecordIntent(unittest.TestCase):
    """Only records the durable intent (as the Core API would), touching nothing else."""

    def test_record_an_intent(self):
        print(f"MIRROR_INTENT {sorted(I.ForgetIntentStore().record(intent_ref_id='intent.f9ca.h2', actor_ref_id='actor.f9ca'))}",
              flush=True)


if __name__ == "__main__":
    unittest.main()
