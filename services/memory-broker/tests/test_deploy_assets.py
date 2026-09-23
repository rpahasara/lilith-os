"""Static DEV-only asset/import-surface checks; no installation."""

from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BROKER = ROOT / "services" / "memory-broker"


class DeployAssetCase(unittest.TestCase):
    def test_operational_modules_exclude_canonical_authority(self):
        names = ("request", "protocol", "state", "dev_config", "dev_state", "synthetic_evidence", "dev_core", "server")
        for name in names:
            tree = ast.parse((BROKER / "lilith_memory_broker" / f"{name}.py").read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
                    imports.extend(alias.name for alias in node.names)
            with self.subTest(module=name):
                self.assertNotIn("canonical_authority", imports)
                self.assertNotIn("app", imports)

    def test_single_shared_verification_engine(self):
        package = BROKER / "lilith_memory_broker"
        self.assertFalse((package / "dev_proof.py").exists())
        core = (package / "dev_core.py").read_text(encoding="utf-8")
        self.assertIn("P.DevSyntheticOwnerProofVerifier(", core)
        self.assertNotIn("Fido2Server", core)
        self.assertNotIn("authenticate_complete", core)

    def test_systemd_assets_are_dev_only_and_closed(self):
        deploy = BROKER / "deploy"
        service = (deploy / "lilith-memory-broker.service").read_text(encoding="utf-8")
        sock = (deploy / "lilith-memory-broker.socket").read_text(encoding="utf-8")
        tmp = (deploy / "lilith-memory-broker.tmpfiles.conf").read_text(encoding="utf-8")
        for directive in ("User=lilith-memory-broker", "Group=lilith-memory-broker", "Environment=LILITH_ENV=dev", "ProtectSystem=strict", "ProtectHome=yes", "RestrictAddressFamilies=AF_UNIX", "IPAddressDeny=any", "UMask=0077"):
            with self.subTest(directive=directive):
                self.assertIn(directive, service)
        self.assertNotIn("LILITH_ENV=test", service)
        self.assertNotIn("MemoryDenyWriteExecute=", service)
        self.assertNotIn("SystemCallFilter=", service)
        for directive in ("ListenStream=/run/lilith-memory/owner.sock", "SocketUser=lilith-memory-broker", "SocketGroup=lilith-memory-ipc", "SocketMode=0660", "Accept=no"):
            self.assertIn(directive, sock)
        self.assertEqual(tmp.strip(), "d /run/lilith-memory 0710 root lilith-memory-ipc -")
        schema = json.loads((deploy / "dev-config.schema.json").read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["deploymentEnvironment"]["const"], "dev")
        public = json.loads((deploy / "public-synthetic-credential.json").read_text(encoding="utf-8"))
        self.assertEqual(public["rpId"], "owner.lilith.invalid")
        self.assertNotIn("private", json.dumps(public).lower())


if __name__ == "__main__":
    unittest.main()
