#!/usr/bin/env python3
"""M-B3 / SIGN_REGISTRY_V1 S25 ceremony script (DEV_SYNTHETIC). Two phases: PREPARE, then SIGN.

Record: docs/architecture/slice-15b2b-b1b3e-mb3-registry-ceremony-package.md.

Run ONLY on the owner's S25, in a LOCAL Termux session (never SSH, never ADB,
never automation), with USB unplugged and airplane mode ON. This file is
transferred beside the bundle and pinned separately by its SHA-256.

    python -B mb3_phone_ceremony.py prepare --control-sha <40hex> --bundle-sha256 <64hex> \\
        --kact-publication-sha256 <64hex>
    python -B mb3_phone_ceremony.py sign --control-sha <40hex> --bundle-sha256 <64hex> \\
        --manifest-sha256 <64hex>

NOTHING IN THIS SCRIPT IS AUTHORIZATION. Its arguments, prompts, tokens, and
the candidate manifest authorize nothing. Only the owner's separate, explicit,
written M-B3 go authorizes the one SIGN run, and only for the exact values it
names.

- PREPARE never touches K-ROOT: it does not stat, list, open, load, or
  decrypt anything under ~/lilith-kroot-dev-synthetic/, and it asks for no
  passphrase. It freezes one candidate and stops.
- SIGN runs the unchanged `registry-v1` form exactly once. The K-ROOT
  passphrase is typed only into that form's `getpass` on this phone's TTY.
  It is never an argument, an environment variable, a file, or a transcript
  line. Entering SIGN consumes the attempt: a second SIGN is refused, and
  nothing is ever retried.
- Nothing is ever deleted. After any STOP, report for review.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

sys.dont_write_bytecode = True

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
LIBRARY = "services/owner-memory-control/tools/mb3_registry_ceremony.py"
OWNER_TOOL = "services/authority-dev/ceremony/lilith_authority_owner_dev.py"
KACT_DOWNLOAD = "mb3-kact-publication.json"
KWIT_DOWNLOAD = "mb3-kwit-publication.json"
CONFIRM_PREFIX = "SIGN-ONCE"
NOT_AUTHORIZATION = "THIS SCRIPT, ITS FLAGS, PROMPTS, TOKENS AND THE MANIFEST ARE NOT AUTHORIZATION."
PRIVATE_PREFIXES = ("/data/data/com.termux/", "/data/user/0/com.termux/")
FORBIDDEN_EXPORT_PARTS = ("k-root", ".der", "lilith-kroot-dev-synthetic/", "passphrase", ".cred", "secret", ".pem")

SUCCESS_EXPORT = (
    "lilith-mb3-registry-public/authority-registry.v1.digest",
    "lilith-mb3-registry-public/authority-registry.v1.json",
    "lilith-mb3/evidence.sha256",
    "lilith-mb3/evidence/prepare.txt",
    "lilith-mb3/evidence/sign-outcome.json",
    "lilith-mb3/evidence/verify-s25.txt",
    "lilith-mb3/inputs/kact-publication.json",
    "lilith-mb3/inputs/kwit-publication.json",
    "lilith-mb3/inputs/root-anchor.json",
    "lilith-mb3/inputs/witness-anchor.json",
    "lilith-mb3/mb3-inputs.json",
    "lilith-mb3/registry-signing-bytes.bin",
    "lilith-mb3/sign/attempt.json",
    "lilith-mb3/sign/registry-v1.exit",
    "lilith-mb3/sign/registry-v1.stderr",
    "lilith-mb3/unsigned-registry.json",
)
# The failure export never holds the success-format public copy. It may hold
# the signer stdout (public signed bytes, if any) and the burn record.
FAILURE_EXPORT_REQUIRED = (
    "lilith-mb3/evidence.sha256",
    "lilith-mb3/evidence/prepare.txt",
    "lilith-mb3/evidence/sign-outcome.json",
    "lilith-mb3/mb3-inputs.json",
    "lilith-mb3/sign/attempt.json",
)
FAILURE_EXPORT_OPTIONAL = (
    "lilith-mb3/burn/real-registry-burn.json",
    "lilith-mb3/evidence/verify-s25.txt",
    "lilith-mb3/inputs/kact-publication.json",
    "lilith-mb3/inputs/kwit-publication.json",
    "lilith-mb3/inputs/root-anchor.json",
    "lilith-mb3/inputs/witness-anchor.json",
    "lilith-mb3/registry-signing-bytes.bin",
    "lilith-mb3/sign/registry-v1.exit",
    "lilith-mb3/sign/registry-v1.stderr",
    "lilith-mb3/sign/registry-v1.stdout",
    "lilith-mb3/unsigned-registry.json",
)


class Stop(Exception):
    """The only STOP path. A STOP is never retried in place."""


def _stop(message: str) -> None:
    raise Stop(message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _signer_subprocess(argv: list[str], stdout_fd: int, stderr_fd: int, env: dict[str, str]) -> int:
    """The one real invocation. stdin is /dev/null: `getpass` reads the passphrase from /dev/tty only."""
    return subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=stdout_fd, stderr=stderr_fd, env=env,
                          check=False).returncode


def _tty_confirm(prompt: str) -> str:
    # Separate write-only and read-only handles: a terminal is not seekable, and text-mode "r+"
    # (BufferedRandom) refuses it with UnsupportedOperation (M-B3 attempt-1 incident).
    with open("/dev/tty", "w", encoding="utf-8") as out, open("/dev/tty", "r", encoding="utf-8") as tty:
        out.write(prompt)
        out.flush()
        return tty.readline().strip()


def _tty_show(text: str) -> None:
    with open("/dev/tty", "w", encoding="utf-8") as tty:
        tty.write(text)


@dataclass
class Phone:
    """Everything the ceremony reads from or writes to the phone. Only tests replace it (as the keygen `Host`)."""

    home: Path = field(default_factory=lambda: Path(os.path.expanduser("~")))
    require_termux_private: bool = True
    proc: Path = Path("/proc")
    environ: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    interactive: Callable[[], bool] = lambda: os.isatty(0) and os.access("/dev/tty", os.R_OK | os.W_OK)
    confirm: Callable[[str], str] = _tty_confirm
    show: Callable[[str], None] = _tty_show
    run_signer: Callable[[list[str], int, int, dict[str, str]], int] = _signer_subprocess
    token_hex: Callable[[int], str] | None = None
    now: Callable[[], datetime] | None = None
    accepted: Any = None
    script: Path = field(default_factory=lambda: Path(__file__).resolve())
    out: Callable[[str], None] = print

    @property
    def downloads(self) -> Path:
        return self.home / "storage" / "downloads"

    @property
    def work(self) -> Path:
        return self.home / "lilith-mb3"

    @property
    def public(self) -> Path:
        return self.home / "lilith-mb3-registry-public"

    @property
    def export(self) -> Path:
        return self.home / "lilith-mb3-export.tar"

    @property
    def failure_export(self) -> Path:
        return self.home / "lilith-mb3-failure-export.tar"

    @property
    def root_anchor(self) -> Path:
        return self.home / "lilith-kroot-dev-synthetic-public" / "k-root-anchor.json"

    def key_path(self) -> Path:
        """SIGN only. PREPARE never calls this."""
        return self.home / "lilith-kroot-dev-synthetic" / "k-root.der"


def _top(control_sha: str) -> str:
    return f"lilith-mb3-registry-{control_sha[:7]}"


def _check_args(control_sha: str, *hexes: str) -> None:
    SHA40.fullmatch(control_sha or "") or _stop("--control-sha is not 40 lowercase hex")
    for value in hexes:
        HEX64.fullmatch(value or "") or _stop("a SHA-256 argument is not 64 lowercase hex")


def _private(phone: Phone, path: Path) -> bool:
    if not phone.require_termux_private:
        return True
    return (os.path.realpath(path) + "/").startswith(PRIVATE_PREFIXES)


def _gates(phone: Phone, log: list[str]) -> None:
    """G0, read-only: local Termux private storage, no SSH, an interactive phone terminal."""
    _private(phone, phone.home) or _stop("HOME is not Termux private storage")
    log.append("HOME_TERMUX_PRIVATE")
    any(phone.environ.get(v) for v in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY")) and _stop("SSH session")
    log.append("NOT_AN_SSH_SESSION")
    for comm in sorted(phone.proc.glob("[0-9]*/comm")):
        try:
            name = comm.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        name in ("sshd", "adbd") and _stop(f"{name} is running")
    log.append("NO_SSHD_OR_ADBD_VISIBLE")
    phone.interactive() or _stop("no interactive phone terminal")
    log.append("PHONE_TERMINAL_OK")


def _write_new(path: Path, data: bytes, mode: int = 0o600) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _read_regular(path: Path) -> bytes:
    info = os.lstat(path)
    stat.S_ISREG(info.st_mode) or _stop(f"{path.name} is not a regular file")
    return path.read_bytes()


def _stage_bundle(phone: Phone, control_sha: str, bundle_sha256: str, log: list[str]) -> Path:
    """Copy the transport tar into private staging, verify its external pin, extract safely, verify SHA256SUMS."""
    top = _top(control_sha)
    tar_name = top + ".tar"
    source = phone.downloads / tar_name
    raw = _read_regular(source)
    _sha(raw) == bundle_sha256 or _stop("bundle SHA-256 differs from --bundle-sha256")
    staged = phone.work / tar_name
    _write_new(staged, raw)
    log.append("BUNDLE_SHA256_MATCHES_EXTERNAL_PIN")
    _extract(staged, phone.work, top)
    return _verify_bundle(phone.work / top, control_sha, log)


def _extract(tar_path: Path, into: Path, top: str) -> None:
    with tarfile.open(tar_path, "r:") as tar:
        members = tar.getmembers()
        for member in members:
            name = PurePosixPath(member.name)
            (name.is_absolute() or ".." in name.parts or name.parts[0] != top) and _stop("unsafe bundle member")
            (member.isfile() or member.isdir()) or _stop("bundle member is not a file or directory")
        for member in members:
            target = into / member.name
            if member.isdir():
                target.mkdir(mode=0o700, exist_ok=True)
            else:
                _write_new(target, tar.extractfile(member).read(), 0o600)


def _verify_bundle(bundle: Path, control_sha: str, log: list[str]) -> Path:
    sums = (bundle / "SHA256SUMS").read_text(encoding="ascii")
    listed = {}
    for line in sums.splitlines():
        digest, name = line.split("  ", 1)
        listed[name] = digest
    actual = sorted(p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file())
    actual == sorted(set(listed) | {"SHA256SUMS"}) or _stop("bundle file set differs from SHA256SUMS")
    for name, digest in listed.items():
        _sha((bundle / name).read_bytes()) == digest or _stop(f"bundle member {name} differs")
    (bundle / "SOURCE_COMMIT").read_text(encoding="ascii").strip() == control_sha \
        or _stop("bundle SOURCE_COMMIT differs from --control-sha")
    log.append("BUNDLE_SHA256SUMS_VERIFIED")
    log.append("SOURCE_COMMIT_EQUALS_CONTROL")
    return bundle


def _load_modules(bundle: Path) -> tuple[Any, Any]:
    for sub in ("vendor", "services/core-api", "services/owner-memory-control"):
        path = str(bundle / sub)
        if path not in sys.path:
            sys.path.insert(0, path)

    def load(name: str, relative: str):
        spec = importlib.util.spec_from_file_location(name, bundle / relative)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    return load("mb3_registry_ceremony", LIBRARY), load("mb3_owner_tool", OWNER_TOOL)


def _accepted(phone: Phone, library: Any) -> Any:
    return phone.accepted if phone.accepted is not None else library.ACCEPTED


# ------------------------------------------------------------------- PREPARE ---

def prepare(phone: Phone, *, control_sha: str, bundle_sha256: str, kact_publication_sha256: str) -> int:
    """Freeze ONE candidate. Never touches K-ROOT. Ends with an owner STOP."""
    _check_args(control_sha, bundle_sha256, kact_publication_sha256)
    log: list[str] = []
    _gates(phone, log)
    for path in (phone.work, phone.public, phone.export, phone.failure_export):
        (path.exists() or path.is_symlink()) and _stop(
            f"{path.name} already exists: a prior M-B3 candidate needs reviewed disposal; nothing is reused")
    log.append("NO_PRIOR_MB3_STATE")
    _private(phone, phone.root_anchor) or _stop("root anchor is not in Termux private storage")
    phone.work.mkdir(mode=0o700)
    for sub in ("inputs", "evidence"):
        (phone.work / sub).mkdir(mode=0o700)
    bundle = _stage_bundle(phone, control_sha, bundle_sha256, log)
    library, tool = _load_modules(bundle)
    accepted = _accepted(phone, library)
    inputs = phone.work / "inputs"

    kact_raw = _read_regular(phone.downloads / KACT_DOWNLOAD)
    kwit_raw = _read_regular(phone.downloads / KWIT_DOWNLOAD)
    root_raw = _read_regular(phone.root_anchor)
    try:
        _, root = library.verify_root_anchor_bytes(root_raw, accepted)
        log.append("ROOT_FINGERPRINT_E21")
        kact_value, kact = library.verify_kact_publication_bytes(kact_raw, kact_publication_sha256, accepted)
        log.append("KACT_PUBLICATION_PINNED_AND_RECOMPUTED")
        kwit_value, kwit = library.verify_kwit_publication_bytes(kwit_raw, accepted)
        log.append("KWIT_PUBLICATION_ACCEPTED")
        anchor_raw = library.canonical_bytes(library.witness_anchor(kwit))
        _write_new(inputs / "kact-publication.json", kact_raw)
        _write_new(inputs / "kwit-publication.json", kwit_raw)
        _write_new(inputs / "root-anchor.json", root_raw)
        _write_new(inputs / "witness-anchor.json", anchor_raw)

        # exactly once each, generated here, for this candidate only
        epoch_random = library.new_epoch_random(*(() if phone.token_hex is None else (phone.token_hex,)))
        issued_at = library.new_issued_at(*(() if phone.now is None else (phone.now,)))
        candidate = library.capture_candidate(tool.registry_v1, kact_value, epoch_random=epoch_random,
                                              policy_version=library.POLICY_VERSION, issued_at=issued_at)
        log.append("CANDIDATE_BUILT_BY_OWNER_TOOL_WITHOUT_KEY")
        log += library.presign_tokens(candidate, root=root, kact_value=kact_value, kact=kact,
                                      kwit_value=kwit_value, kwit=kwit, epoch_random=epoch_random,
                                      policy_version=library.POLICY_VERSION, issued_at=issued_at)
        manifest = library.build_manifest(
            control_sha=control_sha, bundle_sha256=bundle_sha256, source_commit=control_sha,
            script_sha256=_sha(phone.script.read_bytes()), accepted=accepted, root_anchor_sha256=_sha(root_raw),
            kact_publication_sha256=kact_publication_sha256, kact=kact, kwit_publication_sha256=_sha(kwit_raw),
            witness_anchor_sha256=_sha(anchor_raw), epoch_random=epoch_random, issued_at=issued_at,
            candidate=candidate,
            input_files={"kact-publication.json": _sha(kact_raw), "kwit-publication.json": _sha(kwit_raw),
                         "root-anchor.json": _sha(root_raw), "witness-anchor.json": _sha(anchor_raw)},
            presign=list(log))
    except library.Mb3Refusal as refusal:
        _stop("PREPARE refused: " + refusal.code)
    manifest_raw = library.canonical_bytes(manifest)
    _write_new(phone.work / "unsigned-registry.json", library.canonical_bytes(candidate.unsigned), 0o444)
    _write_new(phone.work / "registry-signing-bytes.bin", candidate.signing_bytes, 0o444)
    _write_new(phone.work / library.MANIFEST_NAME, manifest_raw, 0o444)
    log.append("MB3_PREPARED")
    _write_new(phone.work / "evidence" / "prepare.txt", ("\n".join(log) + "\n").encode("ascii"), 0o444)
    summary = [
        *log,
        f"MANIFEST_SHA256 {_sha(manifest_raw)}",
        f"EXPECTED_REGISTRY_DIGEST {candidate.registry_digest}",
        f"EPOCH_RANDOM {epoch_random}",
        f"ISSUED_AT {issued_at}",
        f"POLICY_VERSION {library.POLICY_VERSION}",
        f"KACT_PUBLICATION_SHA256 {kact_publication_sha256}",
        f"KACT_PUBLIC_KEY_SHA256 {manifest['kactPublicKeySha256']}",
        f"BUNDLE_SHA256 {bundle_sha256}",
        f"SCRIPT_SHA256 {manifest['scriptSha256']}",
        "K-ROOT WAS NOT ACCESSED. NO PASSPHRASE WAS REQUESTED. NOTHING WAS SIGNED.",
        NOT_AUTHORIZATION,
        "STOP: the owner decides whether to give the separate one-attempt M-B3 signing go naming these values.",
    ]
    for line in summary:
        phone.out(line)
    return 0


# ---------------------------------------------------------------------- SIGN ---

def sign(phone: Phone, *, control_sha: str, bundle_sha256: str, manifest_sha256: str) -> int:
    """The one real signing attempt. Entering past the argument checks consumes it."""
    _check_args(control_sha, bundle_sha256, manifest_sha256)
    log: list[str] = []
    work = phone.work
    (work / "mb3-inputs.json").is_file() or _stop("no prepared candidate")
    (work / "evidence" / "prepare.txt").is_file() or _stop("PREPARE did not complete")
    sign_dir = work / "sign"
    try:
        sign_dir.mkdir(mode=0o700)            # the attempt marker: created once, before any gate, never removed
    except FileExistsError:
        _stop("ATTEMPT_ALREADY_CONSUMED: SIGN ran before for this candidate. No retry; a new sequence is required")
    attempt = {"attemptStartedAt": _utc(), "manifestSha256": manifest_sha256, "controlSha": control_sha,
               "bundleSha256": bundle_sha256, "invocationsPermitted": 1, "authorization": "NOT_THIS_FILE"}
    _write_new(sign_dir / "attempt.json", (json.dumps(attempt, sort_keys=True) + "\n").encode("ascii"), 0o444)
    log.append("ATTEMPT_CONSUMED_ON_ENTRY")

    outcome: dict[str, Any] = {"outcome": None, "invoked": False}
    library = None
    manifest_raw = b""
    try:
        _gates(phone, log)
        for path in (phone.public, phone.export, phone.failure_export):
            (path.exists() or path.is_symlink()) and _stop(f"{path.name} already exists")
        manifest_raw = _read_regular(work / "mb3-inputs.json")
        _sha(manifest_raw) == manifest_sha256 or _stop("manifest SHA-256 differs from --manifest-sha256")
        top = _top(control_sha)
        staged = _read_regular(work / (top + ".tar"))
        _sha(staged) == bundle_sha256 or _stop("staged bundle differs from --bundle-sha256")
        bundle = _verify_bundle(work / top, control_sha, log)
        library, tool = _load_modules(bundle)
        accepted = _accepted(phone, library)
        try:
            manifest = library.parse_manifest(manifest_raw, accepted)
        except library.Mb3Refusal as refusal:
            _stop("manifest invalid: " + refusal.code)
        (manifest["controlSha"] == control_sha and manifest["bundleSha256"] == bundle_sha256) \
            or _stop("manifest does not bind these pins")
        manifest["scriptSha256"] == _sha(phone.script.read_bytes()) or _stop("this script changed since PREPARE")
        log.append("MANIFEST_BINDS_GO_PINS")
        for name, digest in manifest["inputFiles"].items():
            _sha(_read_regular(work / "inputs" / name)) == digest or _stop(f"input {name} changed since PREPARE")
        try:
            kact_value, _ = library.verify_kact_publication_bytes(
                _read_regular(work / "inputs" / "kact-publication.json"), manifest["kactPublicationSha256"], accepted)
        except library.Mb3Refusal as refusal:
            _stop("K-ACT publication invalid: " + refusal.code)
        again = library.capture_candidate(tool.registry_v1, kact_value, epoch_random=manifest["epochRandom"],
                                          policy_version=manifest["policyVersion"], issued_at=manifest["issuedAt"])
        (again.registry_digest == manifest["expectedRegistryDigest"]
         and again.signing_bytes == _read_regular(work / "registry-signing-bytes.bin")) \
            or _stop("frozen candidate does not reproduce")
        log.append("FROZEN_CANDIDATE_REPRODUCED")

        key = phone.key_path()
        info = os.lstat(key)
        (stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600) or _stop("K-ROOT file not regular 0600")
        parent = os.lstat(key.parent)
        stat.S_IMODE(parent.st_mode) == 0o700 or _stop("K-ROOT directory not 0700")
        sorted(os.listdir(key.parent)) == ["k-root.der"] or _stop("unexpected entry beside the K-ROOT file")
        _private(phone, key) or _stop("K-ROOT is not in Termux private storage")
        log.append("KROOT_FILE_CUSTODY_SHAPE_OK")

        digest = manifest["expectedRegistryDigest"]
        phone.show(f"\nCANDIDATE {digest}\nEPOCH_RANDOM {manifest['epochRandom']}\nISSUED_AT {manifest['issuedAt']}\n"
                   f"{NOT_AUTHORIZATION}\nOnly the owner's separate written go naming these exact values authorizes "
                   f"this one attempt.\n")
        expected = f"{CONFIRM_PREFIX} {digest[:16]}"
        answer = phone.confirm(f"Type '{expected}' to run the ONE signing attempt (anything else STOPs): ")
        answer == expected or _stop("owner did not confirm on the phone; the attempt is consumed")
        log.append("OWNER_TYPED_CONFIRMATION_NOT_AUTHORIZATION")

        argv = [sys.executable, "-B", str(bundle / OWNER_TOOL), "registry-v1", str(key),
                str(work / "inputs" / "kact-publication.json"), manifest["epochRandom"], manifest["policyVersion"],
                manifest["issuedAt"]]
        env = {"PATH": phone.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(phone.home),
               "PYTHONPATH": os.pathsep.join(str(bundle / p) for p in
                                             ("vendor", "services/core-api", "services/owner-memory-control")),
               "PYTHONDONTWRITEBYTECODE": "1"}
        out_fd = os.open(sign_dir / "registry-v1.stdout", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        err_fd = os.open(sign_dir / "registry-v1.stderr", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        outcome["invoked"] = True
        try:
            code = phone.run_signer(argv, out_fd, err_fd, env)   # exactly once; never in a loop
        finally:
            os.close(out_fd)
            os.close(err_fd)
        _write_new(sign_dir / "registry-v1.exit", f"exit={code}\n".encode("ascii"), 0o444)
        stdout = (sign_dir / "registry-v1.stdout").read_bytes()
        stderr = (sign_dir / "registry-v1.stderr").read_bytes()
        kind = library.classify_signer_exit(exit_code=code, stdout=stdout, stderr=stderr)
        outcome.update({"exitCode": code, "signerClass": kind})
        if kind != library.OUTCOME_B:
            outcome["outcome"] = kind
            _stop(f"signer did not produce an accepted output ({kind})")
        check = library.verify_signed_registry(
            registry_raw=stdout, manifest_raw=manifest_raw, root_anchor_raw=_read_regular(work / "inputs/root-anchor.json"),
            kact_raw=_read_regular(work / "inputs/kact-publication.json"),
            kwit_raw=_read_regular(work / "inputs/kwit-publication.json"), accepted=accepted,
            registry_v1=tool.registry_v1)
        _write_new(work / "evidence" / "verify-s25.txt",
                   ("\n".join(check.tokens) + f"\nVERIFIED={check.verified}\nREASON={check.reason}\n").encode("ascii"),
                   0o444)
        if not check.verified:
            outcome.update({"outcome": library.OUTCOME_C, "verificationReason": check.reason,
                            "signedDigest": check.registry_digest})
            _stop(f"S25 verification failed: {check.reason}")
        log += list(check.tokens)
        phone.public.mkdir(mode=0o700)
        _write_new(phone.public / "authority-registry.v1.json", stdout, 0o444)
        _write_new(phone.public / "authority-registry.v1.digest", (check.registry_digest + "\n").encode("ascii"), 0o444)
        outcome.update({"outcome": library.OUTCOME_B, "registryDigest": check.registry_digest,
                        "technicalState": library.TERMINAL_STATE, "ownerAcceptance": "REQUIRED_SEPARATELY"})
        _write_new(work / "evidence" / "sign-outcome.json", (json.dumps(outcome, sort_keys=True) + "\n").encode(),
                   0o444)
        _seal(work)
        names = _build_export(phone, phone.export, SUCCESS_EXPORT, ())
        tuple(names) == SUCCESS_EXPORT or _stop("export is not exactly the public allowlist")
        phone.show(f"\nREGISTRY V1 DIGEST (write it down): {check.registry_digest}\n")
        for line in [*log, f"MB3_REGISTRY_DIGEST {check.registry_digest}",
                     f"PHONE_SIDE_EXPORT_SHA256 {_sha(phone.export.read_bytes())}",
                     f"MB3_TECHNICAL_STATE={library.TERMINAL_STATE}",
                     "REGISTRY_SIGNED IS NOT INSTALLED, NOT EFFECTIVE, AND NOT OWNER-ACCEPTED.",
                     "STOP: separate owner acceptance is required. M-B4/M-B5 NOT AUTHORIZED.",
                     "Copy ONLY the export tar and the transcript. NEVER copy ~/lilith-kroot-dev-synthetic/."]:
            phone.out(line)
        return 0
    except (Stop, Exception, KeyboardInterrupt) as stopped:
        reason = str(stopped) if isinstance(stopped, Stop) else f"unexpected {type(stopped).__name__}: {stopped}"
        _fail(phone, outcome, reason, library, manifest_raw, control_sha)
        raise Stop(reason) from None


def _fail(phone: Phone, outcome: dict[str, Any], reason: str, library: Any, manifest_raw: bytes,
          control_sha: str) -> None:
    """Record the consumed attempt and any burn. Never deletes, never retries, never re-signs.

    Not invoked -> A (no signature, no burn). Invoked with an uncertain result -> D: the
    pre-sign frozen digest is burned. A signed but invalid output -> C: its digest is burned.
    """
    work = phone.work
    if outcome.get("outcome") is None:
        outcome["outcome"] = "D_SIGNATURE_UNCERTAIN_BURN_FROZEN" if outcome.get("invoked") else "A_NO_SIGNATURE"
    outcome["stop"] = reason
    try:
        manifest = json.loads(manifest_raw) if manifest_raw else None
    except ValueError:
        manifest = None
    burn = None
    if library is not None and outcome["outcome"] in (library.OUTCOME_C, library.OUTCOME_D):
        signed = outcome.get("signedDigest")
        if outcome["outcome"] == library.OUTCOME_C and signed:
            burn = library.known_real_registry_burn(
                registry_digest=signed, digest_source="SIGNED_OUTPUT", case="C_VERIFICATION_FAILED",
                control_sha=control_sha, manifest_sha256=_sha(manifest_raw), recorded_at=_utc())
        elif manifest is not None:
            burn = library.known_real_registry_burn(
                registry_digest=manifest["expectedRegistryDigest"], digest_source="PRE_SIGN_FROZEN_MANIFEST",
                case="D_OUTPUT_LOST_OR_UNCERTAIN", control_sha=control_sha, manifest_sha256=_sha(manifest_raw),
                recorded_at=_utc())
        else:
            burn = library.unknown_real_registry_burn(
                failure_window="SIGN after invocation", control_sha=control_sha, manifest_sha256=None,
                provenance="manifest unavailable at failure time; no digest is inferred", recorded_at=_utc())
    outcome["burnRecorded"] = burn is not None
    try:
        if burn is not None:
            (work / "burn").mkdir(mode=0o700, exist_ok=True)
            _write_new(work / "burn" / "real-registry-burn.json",
                       (json.dumps(burn, sort_keys=True) + "\n").encode("ascii"), 0o444)
        if (work / "evidence").is_dir() and not (work / "evidence" / "sign-outcome.json").exists():
            _write_new(work / "evidence" / "sign-outcome.json",
                       (json.dumps(outcome, sort_keys=True, default=str) + "\n").encode(), 0o444)
        _seal(work)
        if not phone.failure_export.exists() and not phone.export.exists():
            _build_export(phone, phone.failure_export, FAILURE_EXPORT_REQUIRED, FAILURE_EXPORT_OPTIONAL)
            phone.out(f"PHONE_SIDE_FAILURE_EXPORT_SHA256 {_sha(phone.failure_export.read_bytes())}")
    except (OSError, Stop) as exc:
        phone.out(f"MB3_FAILURE_RECORD_INCOMPLETE: {exc}. Do not delete anything; report for review.")
    phone.out(f"MB3_ATTEMPT_CONSUMED outcome={outcome['outcome']} burn={'yes' if burn else 'no'}")
    phone.out("MB3_INCIDENT: the go is consumed. NO RETRY. A replacement needs a new sequence and a new owner go.")


def _seal(work: Path) -> None:
    names = sorted(p for p in work.rglob("*") if p.is_file() and p.parent.name in ("evidence", "sign", "burn", "inputs")
                   and p.name != "registry-v1.stdout")
    lines = "".join(f"{_sha(p.read_bytes())}  {p.relative_to(work).as_posix()}\n" for p in names)
    seal = work / "evidence.sha256"
    if seal.exists():
        seal.chmod(0o600)
        seal.rename(work / f"evidence.sha256.superseded-{len(list(work.glob('evidence.sha256.*')))}")
    _write_new(seal, lines.encode("ascii"), 0o444)


def _build_export(phone: Phone, target: Path, required: tuple[str, ...], optional: tuple[str, ...]) -> list[str]:
    """Explicit allowlist only. Never walks a directory; never names private material."""
    names = [n for n in sorted(set(required) | set(optional)) if (phone.home / n).is_file()]
    for name in required:
        name in names or _stop(f"export member missing: {name}")
    for name in names:
        any(part in name.lower() for part in FORBIDDEN_EXPORT_PARTS) and _stop(f"export names private material: {name}")
        _private(phone, phone.home / name) or _stop("export member outside private storage")
    with tarfile.open(target, "x", format=tarfile.USTAR_FORMAT) as tar:
        for name in names:
            tar.add(phone.home / name, arcname=name, recursive=False)
    with tarfile.open(target, "r:") as tar:
        listed = sorted(m.name for m in tar.getmembers())
    listed == names or _stop("export listing differs from the allowlist")
    return listed


def main(argv: list[str], phone: Phone | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mb3_phone_ceremony.py", description=NOT_AUTHORIZATION)
    modes = parser.add_subparsers(dest="mode", required=True)
    p = modes.add_parser("prepare")
    s = modes.add_parser("sign")
    for sub in (p, s):
        sub.add_argument("--control-sha", required=True)
        sub.add_argument("--bundle-sha256", required=True)
    p.add_argument("--kact-publication-sha256", required=True)
    s.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args(argv)
    phone = phone or Phone()
    phone.out(f"M-B3 {args.mode.upper()} (DEV_SYNTHETIC). {NOT_AUTHORIZATION}")
    try:
        if args.mode == "prepare":
            return prepare(phone, control_sha=args.control_sha, bundle_sha256=args.bundle_sha256,
                           kact_publication_sha256=args.kact_publication_sha256)
        return sign(phone, control_sha=args.control_sha, bundle_sha256=args.bundle_sha256,
                    manifest_sha256=args.manifest_sha256)
    except Stop as stopped:
        phone.out(f"STOP: {stopped}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
