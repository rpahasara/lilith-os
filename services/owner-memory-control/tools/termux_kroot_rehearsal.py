#!/usr/bin/env python3
"""LILITH 15B2b-B1b-3e B-4: Termux capability rehearsal for the K-ROOT owner tooling (TEST ONLY).

Record: docs/architecture/slice-15b2b-b1b3e-b4-termux-kroot-rehearsal.md.

The owner chose K-ROOT custody Option A1: K-ROOT is generated and retained
only in S25 Termux private storage. Before the real M-B1, this rehearsal
proves on the phone that the reviewed owner tool
(`services/authority-dev/ceremony/lilith_authority_owner_dev.py`) can do
three things there with a **throwaway TEST key** and **synthetic inputs**:

- `root-keygen`: an encrypted PKCS#8 file, `O_EXCL`, mode `0600`, no
  temporary copy, the anchor, and `publicKeySha256`;
- `registry-v1`: signing registry v1 over a synthetic K-ACT publication;
- `reproduce`: the off-host genesis candidate and genesis pin.

It runs the tool's functions and its CLI entry point with an injected TEST
passphrase. The real ceremony types the passphrase, and this rehearsal never
asks for one. Everything is created in one fresh `mkdtemp` directory under
Termux private `$TMPDIR` and removed at the end. The transcript contains only
public values. Every identity it creates is reported as **burned**, so none
can ever be accepted as real.

    rehearsal key != K-ROOT;  rehearsal PASS != M-B1 authorization

It contacts nothing, reads no real replica or pin, and writes nothing
outside its own temporary directory.

    python -B termux_kroot_rehearsal.py rehearse
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import platform
import secrets
import shutil
import stat
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                                     # the repository (or bundle) root
OWNER_TOOL = ROOT / "services/authority-dev/ceremony/lilith_authority_owner_dev.py"
KEYGEN_TOOL = ROOT / "services/authority-dev/ceremony/lilith_authority_keygen_dev.py"

REHEARSAL_TYPE = "LILITH_B4_TERMUX_KROOT_REHEARSAL"
SCHEMA_VERSION = 1
# A fixed, public, TEST-only passphrase. It protects nothing real and is
# never a K-ROOT passphrase; the real ceremony types its own on the phone.
TEST_PASSPHRASE = b"TEST_ONLY b4 termux kroot rehearsal passphrase"
SYNTHETIC_MACHINE_ID = "7e57" * 8                          # "test": never the DEV machine id
SYNTHETIC_POLICY = "policy.dev-synthetic.v1"
WORKDIR_PREFIX = ".lilith-b4-kroot-rehearsal-TEST-"
TERMUX_ROOTS = ("/data/data/com.termux/", "/data/user/0/com.termux/")
ROOT_KEY_FILE = "k-root.REHEARSAL-TEST.der"
CLI_KEY_FILE = "k-root-cli.REHEARSAL-TEST.der"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module              # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


def _b64u_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _cli(owner, argv: list[str]) -> tuple[int, Any]:
    """The tool's own `main`, with the TEST passphrase injected and stdout captured."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = owner.main(argv, passphrase=lambda: TEST_PASSPHRASE)
    text = out.getvalue().strip()
    return code, (json.loads(text) if code == 0 and text else err.getvalue().strip())


def _only(directory: Path, names: set[str]) -> bool:
    return set(os.listdir(directory)) == names


def rehearse(base: Path, *, clock: Callable[[], float] = time.time) -> dict[str, Any]:
    """Run the full rehearsal in a fresh directory under `base`, then remove it."""
    from cryptography import __version__ as cryptography_version
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_der_private_key

    owner = _load("lilith_authority_owner_dev", OWNER_TOOL)
    keygen = _load("lilith_authority_keygen_dev", KEYGEN_TOOL)
    from lilith_owner_memory import pr1_bootstrap as B          # importable once the owner tool set sys.path

    checks: dict[str, str] = {}
    burned: dict[str, str] = {}
    workdir = Path(tempfile.mkdtemp(prefix=WORKDIR_PREFIX, dir=str(base)))
    issued = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(clock()))

    def check(name: str, function: Callable[[], bool]) -> bool:
        try:
            ok = bool(function())
            checks[name] = "PASS" if ok else "FAIL"
        except Exception as exc:  # contained: every check reports, cleanup always runs
            ok = False
            checks[name] = f"FAIL:{type(exc).__name__}"
        return ok

    def raises(function: Callable[[], Any], exception: type[BaseException]) -> bool:
        try:
            function()
        except exception:
            return True
        return False

    def raw_public() -> bytes:
        return Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    state: dict[str, Any] = {}
    try:
        key_path = workdir / ROOT_KEY_FILE

        # ---- root-keygen (function) ----
        def keygen_api() -> bool:
            state["root"] = owner.root_keygen(key_path, passphrase=TEST_PASSPHRASE)
            return True
        check("rootKeygen", keygen_api)
        check("keyFileRegular0600", lambda: stat.S_ISREG(os.lstat(key_path).st_mode)
              and stat.S_IMODE(os.lstat(key_path).st_mode) == 0o600)
        check("keyFileOnlyEntry", lambda: _only(workdir, {ROOT_KEY_FILE}))       # no temporary copy
        check("keyNotLoadableWithoutPassphrase",
              lambda: raises(lambda: load_der_private_key(key_path.read_bytes(), password=None), TypeError))
        check("keyNotLoadableWithWrongPassphrase",
              lambda: raises(lambda: load_der_private_key(key_path.read_bytes(), password=b"TEST_ONLY wrong 12"),
                             ValueError))

        def anchor_consistent() -> bool:
            anchor = state["root"]["registryRoot"]
            public = _b64u_decode(anchor["publicKey"])
            loaded = owner._root_key(key_path, TEST_PASSPHRASE)
            same = loaded.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw) == public
            burned["rehearsalRootPublicKeySha256"] = state["root"]["publicKeySha256"]
            return (same and hashlib.sha256(public).hexdigest() == state["root"]["publicKeySha256"]
                    and anchor["rootKeyId"] == owner.ROOT_KEY_ID and anchor["environment"] == "dev")
        check("anchorMatchesKeyAndFingerprint", anchor_consistent)
        check("existingKeyNeverOverwritten", lambda: raises(
            lambda: owner.root_keygen(key_path, passphrase=TEST_PASSPHRASE), FileExistsError))
        check("shortPassphraseRefused", lambda: raises(
            lambda: owner.root_keygen(workdir / "short.der", passphrase=b"short"), owner.OwnerToolError)
            and not (workdir / "short.der").exists())

        # ---- root-keygen (CLI entry point) ----
        def keygen_cli() -> bool:
            code, result = _cli(owner, ["root-keygen", str(workdir / CLI_KEY_FILE)])
            state["cliRoot"] = result
            burned["rehearsalCliRootPublicKeySha256"] = result["publicKeySha256"]
            return (code == 0 and stat.S_IMODE(os.lstat(workdir / CLI_KEY_FILE).st_mode) == 0o600
                    and result["publicKeySha256"] != state["root"]["publicKeySha256"])   # a second run = a new key
        check("rootKeygenCli", keygen_cli)

        # ---- synthetic public inputs (production constructors, throwaway keys) ----
        def synthetic_inputs() -> bool:
            state["kact"] = keygen.publication(raw_public(), b"TEST_ONLY synthetic K-ACT ciphertext",
                                               SYNTHETIC_MACHINE_ID)
            state["kwit"] = B.witness_publication(raw_public(), b"TEST_ONLY synthetic K-WIT ciphertext",
                                                  SYNTHETIC_MACHINE_ID)
            burned["syntheticKActPublicKeySha256"] = state["kact"]["publicVerificationMaterial"]["publicKeySha256"]
            burned["syntheticKWitPublicKeySha256"] = state["kwit"]["witnessKey"]["publicKeySha256"]
            for name, value in (("kact.json", state["kact"]), ("kwit.json", state["kwit"]),
                                ("root-anchor.json", state["root"]["registryRoot"])):
                (workdir / name).write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
            return True
        check("syntheticInputs", synthetic_inputs)

        # ---- registry-v1 (function and CLI must agree byte for byte) ----
        epoch_random = secrets.token_hex(16)

        def registry_api() -> bool:
            key = owner._root_key(key_path, TEST_PASSPHRASE)
            state["registry"] = owner.registry_v1(key, state["kact"], epoch_random=epoch_random,
                                                  policy_version=SYNTHETIC_POLICY, issued_at=issued)
            return state["registry"]["registryVersion"] == 1 and len(state["registry"]["keys"]) == 1
        check("registryV1", registry_api)

        def registry_cli() -> bool:
            code, result = _cli(owner, ["registry-v1", str(key_path), str(workdir / "kact.json"), epoch_random,
                                        SYNTHETIC_POLICY, issued])
            (workdir / "registry.json").write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
            return code == 0 and owner._jcs(result) == owner._jcs(state["registry"])     # Ed25519 is deterministic
        check("registryV1CliEqualsFunction", registry_cli)

        def wrong_passphrase_cli() -> bool:
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = owner.main(["registry-v1", str(key_path), str(workdir / "kact.json"), epoch_random,
                                   SYNTHETIC_POLICY, issued], passphrase=lambda: b"TEST_ONLY wrong 12")
            return code == 2 and out.getvalue() == ""
        check("registryV1WrongPassphraseRefused", wrong_passphrase_cli)

        # ---- witness-anchor and reproduce ----
        def anchor_cli() -> bool:
            state["witnessAnchor"] = owner.witness_anchor(state["kwit"])
            code, result = _cli(owner, ["witness-anchor", str(workdir / "kwit.json")])
            (workdir / "witness-anchor.json").write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
            return code == 0 and result == state["witnessAnchor"]
        check("witnessAnchor", anchor_cli)

        def reproduce_all() -> bool:
            first = owner.reproduce(state["registry"], state["root"]["registryRoot"], state["witnessAnchor"], issued)
            second = owner.reproduce(state["registry"], state["root"]["registryRoot"], state["witnessAnchor"], issued)
            code, cli = _cli(owner, ["reproduce", str(workdir / "registry.json"), str(workdir / "root-anchor.json"),
                                     str(workdir / "witness-anchor.json"), issued])
            burned["rehearsalRegistryDigest"] = first["registryHead"]["registryDigest"]
            burned["rehearsalGenesisCandidateDigest"] = first["genesisCandidateDigest"]
            return (code == 0 and owner._jcs(first) == owner._jcs(second) == owner._jcs(cli)
                    and first["registryVerified"] is True and first["authorityGranted"] is False
                    and first["genesisPin"]["genesisWitnessDigest"] == first["genesisCandidateDigest"]
                    and first["genesisPin"]["environment"] == "dev")
        check("reproduceDeterministicAndVerified", reproduce_all)
        check("allFilesInsideWorkdir", lambda: all(
            Path(p).resolve().parent == workdir.resolve() for p in (workdir / n for n in os.listdir(workdir))))
    finally:
        entries = sorted(os.listdir(workdir))
        for name in entries:
            path = workdir / name
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        workdir.rmdir()
        checks["cleanup"] = "PASS" if not workdir.exists() else "FAIL"
    passed = all(value == "PASS" for value in checks.values())
    return {
        "rehearsalType": REHEARSAL_TYPE, "schemaVersion": SCHEMA_VERSION, "testOnly": True,
        "REHEARSAL": "PASS" if passed else "FAIL", "checks": checks,
        "removedEntries": entries,
        "burnedTestIdentities": burned,
        "environment": {"python": platform.python_version(), "cryptography": cryptography_version,
                        "machine": platform.machine(), "system": platform.system()},
        "realAuthorityMaterial": "NONE",
        "nonclaims": ["NOT_K_ROOT", "NOT_M_B1", "NOT_A_GENESIS_PIN", "NOT_AUTHORITY", "NO_REPLICA_TOUCHED"],
    }


def termux_base() -> Path:
    base = os.environ.get("TMPDIR") or os.path.join(os.environ.get("PREFIX", ""), "tmp")
    real = os.path.realpath(base) + "/"
    if not base or not os.path.isdir(base) or not any(real.startswith(root) for root in TERMUX_ROOTS):
        raise SystemExit("B4_KROOT_REHEARSAL refused: not Termux private app storage")
    return Path(base)


def main(argv: list[str]) -> int:
    if argv != ["rehearse"]:
        print("usage: termux_kroot_rehearsal.py rehearse", file=sys.stderr)
        return 2
    result = rehearse(termux_base())
    print(json.dumps(result, sort_keys=True, indent=1))
    print(f"B4_KROOT_REHEARSAL={result['REHEARSAL']}")
    return 0 if result["REHEARSAL"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
