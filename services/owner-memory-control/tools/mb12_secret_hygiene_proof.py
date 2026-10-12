#!/usr/bin/python3 -IB
"""15B2b-B1b-3e M-B12 PR-B2: the SECRET_HYGIENE proof producer (E-22). Stdlib only; reads, never writes.

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb2-proof-producers.md.
DESIGN / SOURCE ONLY. Running either form live needs a separate owner authorization.

Preflight §19 E-22 is "secret hygiene: journal, transcript, and publication scans clean for every PR-1B credential
ceremony"; B1b-3d L2b STOPs on "any private-key pattern in output or journal". Two forms, one marker set:

- `journal` (root, DEV): streams `journalctl --no-pager -o export` once (read-only), scans it, and prints counts and
  digests only. Coverage: the oldest retained entry must be at or before `JOURNAL_COVERAGE_NOT_AFTER` (the start of
  the first DEV PR-1B credential ceremony, M-B2); a rotated / volatile journal FAILS, never passes.
- `prove <scope.json>` (owner, off-host): scans every item of a closed scope manifest (ceremony transcripts and
  publications, each bound by its SHA-256) plus the `journal` transcript, and requires every ceremony of
  `PR1B_CREDENTIAL_CEREMONIES` (OD-M12-7, PROPOSED) with its required roles.

Output never contains a matched byte, an offset, a file path or a key: only a marker CLASS and a count. Markers: PEM /
OpenSSH private-key armour (the `install_authority_dev.FORBIDDEN_MARKERS` / test markers) and the fixed Ed25519
PKCS#8 DER prefix the keygen produces (`lilith_authority_keygen_dev`, PKCS8 DER), raw, hex and base64. A scan finds
known encodings of private material; it cannot prove the absence of every possible encoding (nonclaim).

    sudo /usr/bin/python3 -I -B - journal < mb12_secret_hygiene_proof.py        (DEV, root)
    python3 mb12_secret_hygiene_proof.py prove <scope.json>                      (off-host)

Last lines: `JOURNAL_SECRET_SCAN=PASS coverageFromUs=<t>` / `…=FAIL`, and `SECRET_HYGIENE_PROOF=PASS scope=<d>` /
`…=FAIL`; exit 0 only on PASS, 1 on FAIL, 2 on usage.

    scan clean != no secret ever existed;  SECRET_HYGIENE PASS != custody;  proof != authority
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

JOURNALCTL = "/usr/bin/journalctl"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
CHUNK = 1 << 20
MAX_ITEM_BYTES = 64 * 1024 * 1024

# Marker classes (assembled so this source never contains a marker itself).
_DER = bytes.fromhex("302e020100300506032b65700422" + "0420")
MARKERS: Mapping[str, tuple[bytes, ...]] = {
    "PEM_PRIVATE_KEY": (b"PRIVATE" + b" KEY-----",),
    "OPENSSH_PRIVATE_KEY": (b"OPENSSH" + b" PRIVATE",),
    "ED25519_PKCS8_DER": (_DER,),
    "ED25519_PKCS8_HEX": (_DER.hex().encode("ascii"), _DER.hex().upper().encode("ascii")),
    "ED25519_PKCS8_BASE64": (b"MC4CAQAwBQYDK2Vw" + b"BCIEI",),
}
_OVERLAP = max(len(m) for ms in MARKERS.values() for m in ms) - 1

# The first DEV PR-1B credential ceremony (M-B2 / GENERATE_K_WIT window start, M-B2 completion record).
JOURNAL_COVERAGE_NOT_AFTER_US = 1_791_277_199_000_000            # 2026-10-06T08:59:59Z in microseconds
# OD-M12-7 (PROPOSED): the PR-1B credential ceremonies and the roles each must contribute.
PR1B_CREDENTIAL_CEREMONIES: Mapping[str, tuple[str, ...]] = {
    "M-B1": ("TRANSCRIPT", "PUBLICATION"),      # K-ROOT generation (owner, S25)
    "M-B2": ("TRANSCRIPT", "PUBLICATION"),      # K-WIT keygen (root, DEV)
    "M-B11": ("TRANSCRIPT",),                   # first K-ACT load (signer start; publishes nothing)
}
ROLES = ("TRANSCRIPT", "PUBLICATION")
SCOPE_TYPE = "LILITH_MB12_SECRET_HYGIENE_SCOPE"
SCOPE_FIELDS = frozenset({"scopeType", "schemaVersion", "environment", "ceremonies", "journalScan"})
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
JOURNAL_FINAL = re.compile(r"JOURNAL_SECRET_SCAN=PASS coverageFromUs=(\d+)\Z")


class Scanner:
    """Streaming marker counter. Holds no matched bytes beyond the overlap window."""

    def __init__(self) -> None:
        self.counts = {name: 0 for name in MARKERS}
        self.digest = hashlib.sha256()
        self.size = 0
        self._tail = b""

    def feed(self, chunk: bytes) -> None:
        self.digest.update(chunk)
        self.size += len(chunk)
        window = self._tail + chunk
        boundary = len(self._tail)
        for name, markers in MARKERS.items():
            for marker in markers:
                start = 0
                while (found := window.find(marker, start)) != -1:
                    if found + len(marker) > boundary:          # not already counted in the previous window
                        self.counts[name] += 1
                    start = found + 1
        self._tail = window[-_OVERLAP:] if _OVERLAP else b""

    def hits(self) -> list[tuple[str, int]]:
        return [(name, count) for name, count in self.counts.items() if count]


def scan_bytes(data: bytes) -> Scanner:
    scanner = Scanner()
    for offset in range(0, len(data), CHUNK):
        scanner.feed(data[offset:offset + CHUNK])
    if not data:
        scanner.feed(b"")
    return scanner


# ------------------------------------------------------------------ journal ---

def _journal_stream() -> Iterable[bytes]:
    with subprocess.Popen([JOURNALCTL, "--no-pager", "-o", "export"], env=FIXED_ENV, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL) as process:
        assert process.stdout is not None
        while chunk := process.stdout.read(CHUNK):
            yield chunk
        if process.wait(timeout=600) != 0:
            raise OSError("journalctl failed")


def _first_realtime(head: bytes) -> int | None:
    match = re.search(rb"(?m)^__REALTIME_TIMESTAMP=(\d+)$", head)
    return int(match.group(1)) if match else None


def journal_scan(*, stream: Callable[[], Iterable[bytes]] = _journal_stream, euid: Callable[[], int] = os.geteuid,
                 say: Callable[[str], None] = print) -> bool:
    if euid() != 0:
        say("JOURNAL_SECRET_SCAN=FAIL reason=NOT_ROOT")
        return False
    scanner, head, entries, tail = Scanner(), b"", 0, b"\n"      # the stream start counts as a line start
    entry = b"\n__CURSOR="
    try:
        for chunk in stream():
            if len(head) < 65536:
                head += chunk[:65536 - len(head)]
            window, start = tail + chunk, 0
            while (found := window.find(entry, start)) != -1:
                if found + len(entry) > len(tail):                # not counted in the previous window
                    entries += 1
                start = found + 1
            tail = window[-(len(entry) - 1):]
            scanner.feed(chunk)
    except OSError:
        say("FAIL: JOURNAL_UNREADABLE")
        say("JOURNAL_SECRET_SCAN=FAIL reason=JOURNAL_UNREADABLE")
        return False
    first = _first_realtime(head)
    failures = [f"FAIL: PRIVATE_MATERIAL_MARKER class={name} count={count}" for name, count in scanner.hits()]
    if entries == 0 or first is None:
        failures.append("FAIL: JOURNAL_EMPTY")
    elif first > JOURNAL_COVERAGE_NOT_AFTER_US:
        failures.append("FAIL: JOURNAL_COVERAGE_INCOMPLETE")
    say(f"JOURNAL: entries={entries} bytes={scanner.size} sha256={scanner.digest.hexdigest()} "
        f"firstRealtimeUs={first if first is not None else 'NONE'}")
    for line in failures:
        say(line)
    say("JOURNAL_SECRET_SCAN=FAIL" if failures else f"JOURNAL_SECRET_SCAN=PASS coverageFromUs={first}")
    return not failures


# -------------------------------------------------------------------- scope ---

class ScopeError(ValueError):
    pass


def _need(condition: Any, reason: str) -> None:
    if not condition:
        raise ScopeError(reason)


def scope_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_scope(raw: bytes) -> dict[str, Any]:
    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        _need(len(keys) == len(set(keys)), "SCOPE_DUPLICATE_KEY")
        return dict(pairs)
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ScopeError(getattr(exc, "args", ["SCOPE_MALFORMED"])[0]
                         if isinstance(exc, ScopeError) else "SCOPE_MALFORMED") from exc
    _need(isinstance(doc, dict) and set(doc) == SCOPE_FIELDS and doc["scopeType"] == SCOPE_TYPE
          and type(doc["schemaVersion"]) is int and doc["schemaVersion"] == 1 and doc["environment"] == "dev",
          "SCOPE_MALFORMED")
    _need(isinstance(doc["ceremonies"], list) and isinstance(doc["journalScan"], dict)
          and set(doc["journalScan"]) == {"path", "sha256"}, "SCOPE_MALFORMED")
    names = [c.get("ceremony") if isinstance(c, dict) else None for c in doc["ceremonies"]]
    _need(names == list(PR1B_CREDENTIAL_CEREMONIES), "SCOPE_CEREMONIES_NOT_EXACT")
    for ceremony in doc["ceremonies"]:
        _need(set(ceremony) == {"ceremony", "items"} and isinstance(ceremony["items"], list) and ceremony["items"],
              "SCOPE_MALFORMED")
        for item in ceremony["items"]:
            _need(isinstance(item, dict) and set(item) == {"role", "path", "sha256"} and item["role"] in ROLES
                  and isinstance(item["path"], str) and isinstance(item["sha256"], str)
                  and _HEX64.fullmatch(item["sha256"]), "SCOPE_ITEM_MALFORMED")
        roles = {item["role"] for item in ceremony["items"]}
        _need(set(PR1B_CREDENTIAL_CEREMONIES[ceremony["ceremony"]]) <= roles, "SCOPE_ROLE_MISSING")
    _need(isinstance(doc["journalScan"]["sha256"], str) and _HEX64.fullmatch(doc["journalScan"]["sha256"]),
          "SCOPE_MALFORMED")
    return doc


def _read_bound(path: str, sha256: str) -> bytes | None:
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    if len(data) > MAX_ITEM_BYTES or hashlib.sha256(data).hexdigest() != sha256:
        return None
    return data


def journal_transcript_ok(data: bytes) -> bool:
    """The `journal` form's PASS transcript: exactly a JOURNAL line and the PASS line."""
    try:
        lines = data.decode("ascii").split("\n")
    except UnicodeDecodeError:
        return False
    return (len(lines) == 3 and lines[2] == "" and re.fullmatch(
        r"JOURNAL: entries=[1-9]\d* bytes=\d+ sha256=[0-9a-f]{64} firstRealtimeUs=\d+", lines[0]) is not None
        and (m := JOURNAL_FINAL.fullmatch(lines[1])) is not None
        and int(m.group(1)) <= JOURNAL_COVERAGE_NOT_AFTER_US and lines[0].endswith(f"firstRealtimeUs={m.group(1)}"))


def prove(raw_scope: bytes, *, read: Callable[[str, str], "bytes | None"] = _read_bound,
          say: Callable[[str], None] = print) -> bool:
    try:
        scope = parse_scope(raw_scope)
    except ScopeError as exc:
        say(f"SECRET_HYGIENE_PROOF=FAIL reason={exc.args[0]}")
        return False
    digest = scope_digest(raw_scope)
    say(f"SCOPE: sha256={digest} ceremonies={','.join(PR1B_CREDENTIAL_CEREMONIES)}")
    failures = []
    for ceremony in scope["ceremonies"]:
        for item in ceremony["items"]:
            data = read(item["path"], item["sha256"])
            if data is None:
                failures.append(f"FAIL: ITEM_UNREADABLE_OR_DIGEST_MISMATCH {ceremony['ceremony']} {item['role']}")
                continue
            hits = scan_bytes(data).hits()
            if hits:
                failures += [f"FAIL: PRIVATE_MATERIAL_MARKER {ceremony['ceremony']} {item['role']} class={n} count={c}"
                             for n, c in hits]
            else:
                say(f"ITEM: {ceremony['ceremony']} {item['role']} sha256={item['sha256']} bytes={len(data)} CLEAN")
    journal = read(scope["journalScan"]["path"], scope["journalScan"]["sha256"])
    if journal is None or not journal_transcript_ok(journal) or scan_bytes(journal).hits():
        failures.append("FAIL: JOURNAL_SCAN_NOT_PASS")
    else:
        say(f"JOURNAL_SCAN: sha256={scope['journalScan']['sha256']} PASS")
    for line in failures:
        say(line)
    say(f"SECRET_HYGIENE_PROOF={'FAIL' if failures else 'PASS'} scope={digest}")
    return not failures


def main(argv: list[str]) -> int:
    if argv == ["journal"]:
        return 0 if journal_scan() else 1
    if len(argv) == 2 and argv[0] == "prove":
        try:
            raw = Path(argv[1]).read_bytes()
        except OSError:
            print("SECRET_HYGIENE_PROOF=FAIL reason=SCOPE_UNREADABLE")
            return 1
        return 0 if prove(raw) else 1
    print("SECRET_HYGIENE_PROOF=FAIL reason=USAGE")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
