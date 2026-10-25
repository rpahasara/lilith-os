"""TEST_ONLY Track B fixtures: a simulated K-PAN witness and K-PCK owner device driving the REAL root freshness steps
(``privacy_freshness.apply_unlock`` / ``apply_checkpoint``) and the REAL ``PrivacyFreshnessGate``.

Keys are generated per test and never leave the temporary directory. ``AlwaysFresh`` is an explicit double for the
pre-Track-B restore-suppression suites, whose subject is the restore gate, not freshness.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from lilith_memory import privacy_anchor_contracts as A
from lilith_memory import privacy_freshness as F

ENV = "DEV_SYNTHETIC"
KPAN_ID = "kpan.test-only.dev-synthetic.01"
KPCK_ID = "kpck.test-only.dev-synthetic.01"


def stamp(n: int) -> str:
    return f"2026-10-25T10:{n // 60:02d}:{n % 60:02d}.000000Z"


class AlwaysFresh(F.PrivacyFreshnessGate):
    """TEST_ONLY double: freshness is outside the subject of the suite that uses it."""

    def __init__(self):  # noqa: D401 - deliberately no marker, no Privacy path
        pass

    def check(self) -> F.FreshnessCheck:
        return F.FreshnessCheck(F.READY)

    def durability(self) -> F.FreshnessCheck:
        return F.FreshnessCheck(F.READY)


class Witness:
    """Simulated recovery witness (K-PAN holder): signs only strict extensions, via the pure contract."""

    def __init__(self, key: Optional[Ed25519PrivateKey] = None, key_id: str = KPAN_ID):
        self.key = key or Ed25519PrivateKey.generate()
        self.key_id = key_id
        self.docs: List[Dict[str, Any]] = []
        self._t = 0

    def chain(self, keys: F.FreshnessKeys) -> Optional[A.AnchorChainV1]:
        return A.verify_anchor_chain(self.docs, keys.anchor_key, environment=ENV, key_id=self.key_id) \
            if self.docs else None

    def sign(self, body: Dict[str, Any]) -> Dict[str, Any]:
        return {**body, "signature": self.key.sign(A.signing_bytes("anchor", body)).hex()}

    def advance_to(self, keys: F.FreshnessKeys, privacy_db: Path) -> Dict[str, Any]:
        chain = self.chain(keys)
        local = set(F.local_suppression_entries(privacy_db))
        anchored = chain.entries if chain else frozenset()
        if not anchored <= local:
            raise A.PrivacyAnchorError("LOCAL_NOT_AN_EXTENSION")
        self._t += 1
        doc = self.sign(A.unsigned_anchor_advance(chain, sorted(local - anchored), environment=ENV,
                                                  updated_at=stamp(self._t), key_id=self.key_id))
        self.docs.append(doc)
        return doc


class OwnerDevice:
    """Simulated owner device (K-PCK holder, off-host): an extension-only checkpoint chain and boot unlocks."""

    def __init__(self, key: Optional[Ed25519PrivateKey] = None, key_id: str = KPCK_ID):
        self.key = key or Ed25519PrivateKey.generate()
        self.key_id = key_id
        self.checkpoints: List[Dict[str, Any]] = []
        self._t = 0

    def _sign(self, kind: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return {**body, "signature": self.key.sign(A.signing_bytes(kind, body)).hex()}

    @property
    def latest(self) -> Optional[Dict[str, Any]]:
        return self.checkpoints[-1] if self.checkpoints else None

    def checkpoint(self, chain: A.AnchorChainV1) -> Dict[str, Any]:
        self._t += 1
        doc = self._sign("checkpoint", A.unsigned_checkpoint(self.latest, chain, environment=ENV,
                                                              checkpointed_at=stamp(self._t), key_id=self.key_id))
        self.checkpoints.append(doc)
        return doc

    def unlock(self, challenge: Dict[str, Any]) -> Dict[str, Any]:
        self._t += 1
        return self._sign("unlock", A.unsigned_unlock(challenge, self.latest, unlocked_at=stamp(self._t),
                                                      key_id=self.key_id))


class FreshnessHarness:
    """One host: a Privacy DB, a witness, a tmpfs-like marker path, a boot id; plus the off-host owner device."""

    def __init__(self, root: Path, privacy_db: Path, *, intent_dir: Optional[Path] = None):
        self.root = Path(root)
        self.privacy_db = Path(privacy_db)
        self.marker = self.root / "run-lilith-privacy-fresh" / "verified"
        self.intent_dir = intent_dir or self.root / "intent"
        self.witness = Witness()
        self.owner = OwnerDevice()
        self.keys = F.FreshnessKeys(ENV, self.witness.key.public_key(), self.witness.key_id,
                                    self.owner.key.public_key(), self.owner.key_id)
        self.boot_id = "boot-" + secrets.token_hex(8)
        self._t = 100

    def now(self) -> str:
        self._t += 1
        return stamp(self._t)

    def gate(self) -> F.PrivacyFreshnessGate:
        return F.PrivacyFreshnessGate(self.privacy_db, environment=ENV, marker_path=self.marker,
                                      intent_dir=self.intent_dir, boot_id=lambda: self.boot_id,
                                      require_root_marker=False)

    def genesis(self) -> Dict[str, Any]:
        """The B6 genesis ceremony in miniature: anchor v1 + checkpoint 1, then the first boot unlock."""
        self.witness.advance_to(self.keys, self.privacy_db)
        self.owner.checkpoint(self.witness.chain(self.keys))
        return self.unlock()

    def challenge(self):
        nonce = secrets.token_hex(32)
        return F.issue_challenge(self.keys, self.witness.docs, self.privacy_db, boot_id=self.boot_id, nonce=nonce,
                                 issued_at=self.now()), nonce

    def unlock(self, checkpoint: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        challenge, nonce = self.challenge()
        unlock = self.owner.unlock(challenge)
        return F.apply_unlock(self.keys, self.witness.docs, self.privacy_db, challenge, unlock,
                              checkpoint or self.owner.latest, boot_id=self.boot_id, nonce=nonce,
                              verified_at=self.now(), marker_path=self.marker)

    def anchor_and_checkpoint(self) -> Dict[str, Any]:
        """After begin_forget: the witness advance, the owner's next checkpoint, the root republish."""
        self.witness.advance_to(self.keys, self.privacy_db)
        checkpoint = self.owner.checkpoint(self.witness.chain(self.keys))
        return F.apply_checkpoint(self.keys, self.witness.docs, self.privacy_db, checkpoint, boot_id=self.boot_id,
                                  verified_at=self.now(), marker_path=self.marker, require_root_marker=False)

    def reboot(self) -> None:
        self.boot_id = "boot-" + secrets.token_hex(8)
        if self.marker.exists():          # tmpfs: gone at boot (kept here would only be STALE_BOOT anyway)
            self.marker.unlink()
