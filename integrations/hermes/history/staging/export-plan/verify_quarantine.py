#!/usr/bin/env python3
"""Verify and scan an owner-run PROD export held in quarantine. Never imports or executes exported code.

Usage:
    python verify_quarantine.py <quarantine_dir> [--stage 1|2] [--allowlist ALLOWLIST.tsv]
                                [--upstream <hermes-agent-f293e72 dir>]

Inputs (written by the operator, see EXPORT-PROCEDURE.md):
    <quarantine_dir>/stage<N>.tar.b64   base64 of an uncompressed tar of the stage's allowlisted files
    <quarantine_dir>/run.py.diff.b64    stage 1 only: base64 of `git diff HEAD -- gateway/run.py`

Checks:
    1. strict base64 decode, size ceilings
    2. tar holds exactly the stage's allowlisted regular files: no extras, no omissions, no links, no absolute or
       parent paths
    3. every file's SHA-256 equals the PROD manifest value
    4. the diff touches gateway/run.py only, and upstream f293e72 run.py + diff == PROD run.py (2774eee5...)
    5. scan for secrets, personal data and confidential paths -> REVIEW.md (every value redacted)

Exit 0 = integrity verified (REVIEW.md may still list findings that need owner sign-off); 2 = integrity failure
(nothing should be used). Fails closed if the quarantine path involves a symlink/junction or if `extracted/` or
REVIEW.md already exists. Extracted files are created exclusively and read-only under <quarantine_dir>/extracted/
only after every integrity check passes; nothing is overwritten or written outside it.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
MAX_ARCHIVE = 5 * 1024 * 1024
MAX_DIFF = 512 * 1024
UPSTREAM_RUN_SHA = "2f597f5d9491315c3f2c656b91bc0130206b2497752198b8d998e1c54c7c5835"

SECRET_PATTERNS = [
    ("groq-key", r"gsk_[A-Za-z0-9]{20,}"),
    ("openai-key", r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
    ("github-token", r"gh[pousr]_[A-Za-z0-9]{30,}"),
    ("slack-token", r"xox[abpr]-[A-Za-z0-9\-]{10,}"),
    ("aws-key", r"AKIA[0-9A-Z]{16}"),
    ("google-key", r"AIza[0-9A-Za-z_\-]{30,}"),
    ("private-key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("discord-bot-token", r"[MNO][A-Za-z\d_\-]{23,25}\.[A-Za-z\d_\-]{6}\.[A-Za-z\d_\-]{27,}"),
    ("bearer-literal", r"Bearer\s+[A-Za-z0-9_\-\.]{20,}"),
    ("assigned-secret-literal",
     r"(?i)(api[_-]?key|token|secret|password|passwd)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"),
    ("long-hex-or-b64-literal", r"['\"][A-Za-z0-9+/_\-]{40,}={0,2}['\"]"),
]
PERSONAL_PATTERNS = [
    ("email", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ("phone", r"\+\d[\d\s\-]{8,}\d"),
    ("discord-or-chat-id", r"(?<!\d)-?\d{15,20}(?!\d)"),
    ("owner-name", r"(?i)\b(ravindu|pahasara)\b"),
]
CONFIDENTIAL_PATTERNS = [
    ("home-path", r"/home/[A-Za-z0-9_.\-]+"),
    ("windows-user-path", r"(?i)C:[\\/]+Users[\\/]+[^\\/\s'\"]+"),
    ("etc-path", r"/etc/[A-Za-z0-9_.\-/]+"),
    ("internal-host", r"[A-Za-z0-9\-]+\.(?:internal|local)\b"),
    ("gcp-project", r"lilith-agent-\d{6}-\d{5}"),
    ("ipv4", r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
]


class IntegrityError(Exception):
    pass


def load_allowlist(path: Path, stage: int) -> tuple[dict[str, str], str | None]:
    files, diff_result = {}, None
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    for raw in lines[1:]:
        if not raw.strip():
            continue
        row = dict(zip(header, raw.split("\t")))
        if int(row["stage"]) != stage:
            continue
        if row["kind"] == "git-diff":
            diff_result = row["expected_sha256"].split("=", 1)[1]
        else:
            files[row["prod_path"]] = row["expected_sha256"]
    return files, diff_result


def decode(path: Path, ceiling: int) -> bytes:
    if not path.is_file():
        raise IntegrityError(f"missing input: {path.name}")
    text = path.read_bytes().strip()
    try:
        data = base64.b64decode(text, validate=True)
    except binascii.Error as exc:
        raise IntegrityError(f"{path.name}: not strict base64 ({exc})") from None
    if not data or len(data) > ceiling:
        raise IntegrityError(f"{path.name}: decoded size {len(data)} outside (0, {ceiling}]")
    return data


def check_archive(data: bytes, allowed: dict[str, str]) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
        for member in tar.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise IntegrityError(f"unsafe path in archive: {member.name}")
            if not member.isreg():
                raise IntegrityError(f"non-regular member (dir/link/device): {member.name}")
            key = str(name)
            if key not in allowed:
                raise IntegrityError(f"file not on the allowlist: {key}")
            if key in found:
                raise IntegrityError(f"duplicate member: {key}")
            found[key] = tar.extractfile(member).read()
    missing = sorted(set(allowed) - set(found))
    if missing:
        raise IntegrityError(f"allowlisted files missing from archive: {missing}")
    for key, body in found.items():
        got = hashlib.sha256(body).hexdigest()
        if got != allowed[key]:
            raise IntegrityError(f"sha256 mismatch for {key}: {got} != {allowed[key]}")
    return found


def check_diff(diff: bytes, upstream: Path, expected: str) -> None:
    headers = re.findall(rb"^diff --git a/(\S+) b/(\S+)$", diff, flags=re.M)
    if headers != [(b"gateway/run.py", b"gateway/run.py")]:
        raise IntegrityError(f"diff must touch gateway/run.py only, found {headers}")
    if re.search(rb"^(GIT binary patch|new file mode|deleted file mode|rename from|old mode|new mode)", diff, re.M):
        raise IntegrityError("diff contains binary/mode/rename/new-file sections")
    source = upstream / "gateway" / "run.py"
    if hashlib.sha256(source.read_bytes()).hexdigest() != UPSTREAM_RUN_SHA:
        raise IntegrityError("upstream run.py is not the verified f293e72 file")
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "gateway" / "run.py"
        target.parent.mkdir(parents=True)
        shutil.copyfile(source, target)
        patch = Path(tmp) / "run.py.diff"
        patch.write_bytes(diff)
        proc = subprocess.run(["git", "apply", "--whitespace=nowarn", str(patch)], cwd=tmp,
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise IntegrityError(f"diff does not apply to upstream run.py: {proc.stderr.strip()[:300]}")
        got = hashlib.sha256(target.read_bytes()).hexdigest()
        if got != expected:
            raise IntegrityError(f"upstream + diff = {got}, expected PROD run.py {expected}")


def redact(text: str) -> str:
    """Every finding value is redacted; the reviewer opens the read-only extracted file at the reported line."""
    return f"[redacted {len(text)} chars]"


def scan(name: str, body: bytes) -> list[str]:
    findings = []
    try:
        lines = body.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return [f"| {name} | - | binary | not UTF-8 text: manual review required |"]
    groups = (("SECRET", SECRET_PATTERNS), ("PERSONAL", PERSONAL_PATTERNS), ("CONFIDENTIAL", CONFIDENTIAL_PATTERNS))
    for number, line in enumerate(lines, 1):
        for group, patterns in groups:
            for label, pattern in patterns:
                for match in re.finditer(pattern, line):
                    findings.append(f"| {name} | {number} | {group}:{label} | {redact(match.group(0))} |")
    return findings


def is_link(path: Path) -> bool:
    """A symlink or a Windows junction / other reparse point."""
    if path.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None and isjunction(path):
        return True
    try:
        attributes = os.lstat(path).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def safe_destination(quarantine: Path) -> tuple[Path, Path]:
    """(quarantine, extracted dir). Fails closed if any existing path component is a symlink/junction, or if the
    extraction destination or REVIEW.md already exists. Paths are made absolute without resolving links."""
    q = Path(os.path.abspath(quarantine))
    for component in (q, *q.parents):
        if os.path.lexists(component) and is_link(component):
            raise IntegrityError(f"quarantine path involves a symlink/junction: {component}")
    if not q.is_dir():
        raise IntegrityError(f"quarantine directory does not exist: {q}")
    out = q / "extracted"
    for existing in (out, q / "REVIEW.md"):
        if os.path.lexists(existing):
            raise IntegrityError(f"refusing to overwrite existing {existing.name}: {existing}")
    return q, out


def write_new(dest: Path, root: Path, body: bytes) -> None:
    """Exclusive create of a file strictly inside `root` (never overwrites, never follows a link)."""
    target = Path(os.path.abspath(dest))
    if os.path.commonpath([str(target), str(root)]) != str(root) or target == root:
        raise IntegrityError(f"refusing to write outside the extraction directory: {dest}")
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    for component in (parent, *parent.parents):
        if component == root.parent:
            break
        if is_link(component):
            raise IntegrityError(f"extraction path involves a symlink/junction: {component}")
    with open(target, "xb") as handle:
        handle.write(body)
    target.chmod(stat.S_IRUSR)                             # read-only; never executed or imported here


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("quarantine", type=Path)
    parser.add_argument("--stage", type=int, default=1, choices=(1, 2))
    parser.add_argument("--allowlist", type=Path, default=HERE / "ALLOWLIST.tsv")
    parser.add_argument("--upstream", type=Path, default=HERE.parent / "hermes-agent-f293e72")
    args = parser.parse_args()
    allowed, diff_expected = load_allowlist(args.allowlist, args.stage)
    try:
        q, out = safe_destination(args.quarantine)
        files = check_archive(decode(q / f"stage{args.stage}.tar.b64", MAX_ARCHIVE), allowed)
        diff = None
        if diff_expected:
            diff = decode(q / "run.py.diff.b64", MAX_DIFF)
            check_diff(diff, args.upstream, diff_expected)
        q, out = safe_destination(args.quarantine)         # re-check immediately before writing
        out.mkdir()                                        # fails if it appeared meanwhile
        for key, body in files.items():
            write_new(out.joinpath(*PurePosixPath(key).parts), out, body)
        if diff is not None:
            write_new(out / "hermes-agent.gateway.run.py.diff", out, diff)
    except (IntegrityError, tarfile.TarError, FileExistsError) as exc:
        print(f"INTEGRITY FAILURE: {exc}")
        return 2
    findings = []
    for key, body in sorted(files.items()):
        findings += scan(key, body)
    if diff is not None:
        findings += scan("run.py.diff", diff)
    report = [f"# Quarantine review, stage {args.stage}", "",
              f"Integrity: VERIFIED ({len(files)} files match the PROD manifest"
              + ("; upstream run.py + diff == PROD run.py" if diff is not None else "") + ").", "",
              "Nothing here has been executed or imported. Owner sign-off is required for every finding before any "
              "file leaves quarantine.", "",
              "All finding values are redacted; open the read-only file under `extracted/` at the listed line.", "",
              "| file | line | finding | redacted value |", "|---|---|---|---|", *findings]
    with open(q / "REVIEW.md", "x", encoding="utf-8") as handle:   # never overwrites a previous review
        handle.write("\n".join(report) + "\n")
    secrets = sum("| SECRET:" in f for f in findings)
    print(f"INTEGRITY VERIFIED: {len(files)} files" + (" + run.py diff" if diff is not None else ""))
    print(f"FINDINGS: {len(findings)} (secret-like: {secrets}) -> {q / 'REVIEW.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
