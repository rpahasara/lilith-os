"""R3a (D-7): the OWNER_PROD First Memory host uses an ISOLATED canonical store, never LILITH's live PROD stores.

Record: docs/architecture/canonical-memory-prod-integration-plan.md §4.5 and R3a. Offline: the PROD paths are
constants, and the host's own guard is exercised on a synthetic root holding LILITH-shaped live files. Nothing here
touches a real host.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for _path in (ROOT / "services/owner-memory-control/tools", ROOT / "services/owner-memory-control",
              ROOT / "services/core-api", ROOT / "services/authority-dev", HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import first_memory_dev_host as HOST  # noqa: E402

LIVE_NAMES = ("cognitive_memory.db", "privacy_governance.db", "lilith.db", "actor_authority.key",
              "privacy_authority.key")
# LILITH's live files that no canonical-memory component may ever name (PROD audit run 2, 2026-11-05).
LIVE_OUTSIDE_DATA = (Path("/home/lilith/.hermes/state.db"), Path("/home/lilith/.hermes/SOUL.md"),
                     Path("/home/lilith/.hermes/memories/USER.md"))


def rebased(paths: HOST.HostPathsV1, root: Path) -> HOST.HostPathsV1:
    values = {f: root / Path(getattr(paths, f)).relative_to("/") for f in HOST.STORE_FIELDS}
    return HOST.HostPathsV1(**values, host_root=root)


class IsolatedStoreTests(unittest.TestCase):
    def test_every_prod_store_path_is_in_the_isolated_directory(self):
        for field in HOST.STORE_FIELDS:
            path = Path(getattr(HOST.PROD_PATHS, field))
            self.assertEqual(path.parent, HOST.PROD_CANONICAL, field)
        self.assertEqual(HOST.PROD_CANONICAL, Path("/home/lilith/.hermes/lilith-os/canonical"))
        self.assertNotEqual(HOST.PROD_CANONICAL, HOST.PROD_LIVE_DATA)
        self.assertNotIn(HOST.PROD_LIVE_DATA, HOST.PROD_CANONICAL.parents)

    def test_no_prod_store_path_names_a_live_file_or_the_15b2a_keys(self):
        live = {HOST.PROD_LIVE_DATA / n for n in LIVE_NAMES} | set(LIVE_OUTSIDE_DATA)
        for field in HOST.STORE_FIELDS:
            path = Path(getattr(HOST.PROD_PATHS, field))
            self.assertNotIn(path, live, field)
            self.assertNotIn(HOST.PROD_LIVE_DATA, path.parents, field)
        self.assertIsNone(HOST.prod_live_data_reason(HOST.PROD_PATHS))

    def test_dev_paths_are_unchanged(self):
        dev = HOST.DEV_PATHS
        self.assertEqual(dev.cognitive_db, HOST.DRILL / "cognitive_memory.f9drill.db")
        self.assertEqual(dev.actor_secret, HOST.DRILL / "actor-authority.f9drill.key")
        self.assertEqual(dev.privacy_secret, HOST.DRILL / "privacy-authority.f9drill.key")
        self.assertEqual(dev.privacy_db, HOST.FMC.AUTHORITATIVE_PRIVACY_DB)


class HostGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        live = self.root / HOST.PROD_LIVE_DATA.relative_to("/")
        live.mkdir(parents=True)
        for name in LIVE_NAMES:
            (live / name).write_bytes(b"live " + name.encode())
        self.live = live

    def digests(self) -> dict[str, tuple[str, int]]:
        out = {}
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                st = os.stat(path)
                out[str(path.relative_to(self.root))] = (hashlib.sha256(path.read_bytes()).hexdigest(), st.st_mtime_ns)
        return out

    def host(self, paths: HOST.HostPathsV1, environment: str = "prod") -> HOST.FirstMemoryDevHostV1:
        return HOST.FirstMemoryDevHostV1(transport=object(), paths=paths, environment=environment)

    def test_the_prod_host_accepts_the_isolated_paths_and_touches_nothing(self):
        before = self.digests()
        self.host(rebased(HOST.PROD_PATHS, self.root))
        self.assertEqual(self.digests(), before)
        self.assertFalse((self.root / HOST.PROD_CANONICAL.relative_to("/")).exists())   # the install creates it

    def test_the_prod_host_refuses_any_store_path_in_the_live_data_directory(self):
        for field in HOST.STORE_FIELDS:
            for name in (LIVE_NAMES[0], "anything-new.db"):
                with self.subTest(field=field, name=name):
                    paths = rebased(HOST.PROD_PATHS, self.root)
                    values = {f: getattr(paths, f) for f in HOST.STORE_FIELDS}
                    values[field] = self.live / name
                    bad = HOST.HostPathsV1(**values, host_root=self.root)
                    with self.assertRaises(HOST.HostRefused) as caught:
                        self.host(bad)
                    self.assertEqual(caught.exception.code, "PROD_PATH_IN_LIVE_DATA")
        traversal = rebased(HOST.PROD_PATHS, self.root)
        values = {f: getattr(traversal, f) for f in HOST.STORE_FIELDS}
        values["cognitive_db"] = self.root / "home/lilith/.hermes/lilith-os/canonical/../data/cognitive_memory.db"
        with self.assertRaises(HOST.HostRefused):
            self.host(HOST.HostPathsV1(**values, host_root=self.root))

    def test_the_guard_applies_to_prod_only(self):
        paths = rebased(HOST.PROD_PATHS, self.root)
        values = {f: getattr(paths, f) for f in HOST.STORE_FIELDS}
        values["cognitive_db"] = self.live / "cognitive_memory.db"
        self.host(HOST.HostPathsV1(**values, host_root=self.root), environment="dev")     # DEV behaviour unchanged


if __name__ == "__main__":
    unittest.main()
