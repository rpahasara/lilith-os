#!/usr/bin/python3 -IB
"""15B2b-B1b-3e M-B12 PR-B2: the SECRET_HYGIENE proof producer (E-22). Stdlib only; reads, never writes.

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb2-proof-producers.md.
DESIGN / SOURCE ONLY. Running either form live needs a separate owner authorization.

Preflight §19 E-22 is "secret hygiene: journal, transcript, and publication scans clean for every PR-1B credential
ceremony"; B1b-3d L2b STOPs on "any private-key pattern in output or journal". Two forms, one marker set:

- `journal` (root, DEV): parses one read-only `journalctl --no-pager -o export` stream entry by entry (text and
  binary fields), scans every byte, and reports per retained boot (`_BOOT_ID`) its oldest and newest entry. It prints
  counts, digests and timestamps only.
- `prove <scope.json>` (owner, off-host): scans the closed scope of `CEREMONIES` (OD-M12-7, PROPOSED): each ceremony's
  transcripts and its named publication (pinned by the canonical record where the record gives a full SHA-256), the
  canonical record must exist, and every DEV ceremony window must lie inside ONE retained boot of a `journal`
  transcript (so the journal covers it continuously within that boot, and its newest entry is after the ceremony end).
  S25 / off-host ceremonies have no DEV journal requirement. A scope decision left open (`UNRESOLVED_SCOPE`), an
  unrecorded ceremony window, or an absent record FAILS: no PASS is produced by default.

Detection contract (nonclaims): the markers are PEM / OpenSSH private-key armour (`install_authority_dev`
FORBIDDEN_MARKERS / the test markers) and the fixed Ed25519 PKCS#8 DER prefix the keygen emits, as raw bytes, hex
(lower / upper) and base64 (standard and URL-safe) at all three byte alignments. A clean result means "no specified
marker in the scanned scope", never "no secret ever leaked". Bare 32-byte seeds, separated or mixed-case hex and other
encodings are OUTSIDE the contract. Output never contains a matched byte, an offset, a path or key material.

    sudo /usr/bin/python3 -I -B - journal < mb12_secret_hygiene_proof.py        (DEV, root)
    python3 mb12_secret_hygiene_proof.py prove <scope.json>                      (off-host)

Last lines: `JOURNAL_SECRET_SCAN=PASS firstRealtimeUs=<a> lastRealtimeUs=<b>` / `…=FAIL`, and
`SECRET_HYGIENE_PROOF=PASS scope=<d>` / `…=FAIL`; exit 0 only on PASS, 1 on FAIL, 2 on usage.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Mapping, NamedTuple

# The repository root (off-host `prove`); streamed on DEV over stdin there is no `__file__` and no repository.
REPO = Path(__file__).resolve().parents[3] if "__file__" in globals() else None
JOURNALCTL = "/usr/bin/journalctl"
FIXED_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "HOME": "/nonexistent"}
CHUNK = 1 << 20
MAX_ITEM_BYTES = 64 * 1024 * 1024
MAX_FIELD_BYTES = 16 * 1024 * 1024            # one journal field; larger is refused, never truncated

# ------------------------------------------------------------------ markers ---
# Assembled so this source never contains a marker itself.
_DER = bytes.fromhex("302e020100300506032b65700422" + "0420")


def _base64_markers(prefix: bytes) -> tuple[bytes, ...]:
    """The base64 / base64url text that encodes `prefix` whatever its byte alignment in a larger blob: for k leading
    bytes, only the 4-character groups that depend on `prefix` bytes alone are kept."""
    found = []
    for k in (0, 1, 2):
        text = base64.b64encode(b"\x00" * k + prefix)
        start = 0 if k == 0 else 4
        end = ((k + len(prefix)) // 3) * 4
        for variant in (text[start:end], text[start:end].replace(b"+", b"-").replace(b"/", b"_")):
            if variant not in found:
                found.append(variant)
    return tuple(found)


MARKERS: Mapping[str, tuple[bytes, ...]] = {
    "PEM_PRIVATE_KEY": (b"PRIVATE" + b" KEY-----",),
    "OPENSSH_PRIVATE_KEY": (b"OPENSSH" + b" PRIVATE",),
    "ED25519_PKCS8_DER": (_DER,),
    "ED25519_PKCS8_HEX": (_DER.hex().encode("ascii"), _DER.hex().upper().encode("ascii")),
    "ED25519_PKCS8_BASE64": _base64_markers(_DER),
}
_OVERLAP = max(len(m) for ms in MARKERS.values() for m in ms) - 1


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
        self._tail = window[-_OVERLAP:]

    def hits(self) -> list[tuple[str, int]]:
        return [(name, count) for name, count in self.counts.items() if count]


def scan_bytes(data: bytes) -> Scanner:
    scanner = Scanner()
    for offset in range(0, len(data), CHUNK):
        scanner.feed(data[offset:offset + CHUNK])
    return scanner


# ---------------------------------------------------------------- ceremonies ---

class CeremonyV1(NamedTuple):
    """One PR-1B private-material ceremony (OD-M12-7, PROPOSED). Values come from the canonical record only.
    A NamedTuple, not a dataclass: the producer is streamed (no module file) and loaded by the builder without a
    `sys.modules` entry, where `dataclasses` cannot resolve its module."""

    venue: str                                  # "DEV" (journal required) or "S25" (off-host; no DEV journal)
    material: str
    record: str | None                          # docs/architecture/<record>; None = no record exists yet
    publication: str | None                     # the named publication kind, None = the ceremony publishes nothing
    publication_sha256: str | None              # the full SHA-256 the record gives, None = the record gives none
    window: tuple[str | None, str | None] | None    # DEV only: (start, end) from the record; None part = unrecorded


CEREMONIES: Mapping[str, CeremonyV1] = {
    "M-B1": CeremonyV1("S25", "K-ROOT generation and publication", "slice-15b2b-b1b3e-mb1-kroot-completion.md",
                       "K_ROOT_PUBLIC_EXPORT", "740cf10ab9042b95eef192af6ca9e63b661cf91af3a36fe5d0aafbd2b3547db5", None),
    "M-B2": CeremonyV1("DEV", "K-WIT generation and publication", "slice-15b2b-b1b3e-mb2-kwit-completion.md",
                       "K_WIT_PUBLICATION", None, ("2026-10-06T08:45:54Z", "2026-10-06T09:11:38Z")),
    "M-B3": CeremonyV1("S25", "K-ROOT signing Registry V1", "slice-15b2b-b1b3e-mb3-registry-sign-completion.md",
                       "SIGNED_REGISTRY_V1", "3f0a59c0a104934730184d28bc16e1c9215bdaa6ec1f9d94753722862f486156", None),
    "M-B9a": CeremonyV1("DEV", "first K-WIT load (witness start)", "slice-15b2b-b1b3e-mb9-package-b-completion.md",
                        None, None, ("2026-10-09T04:44:18Z", "2026-10-09T04:59:49Z")),
    "M-B9b": CeremonyV1("DEV", "K-WIT signing the V2 genesis", "slice-15b2b-b1b3e-mb9-package-b-completion.md",
                        "GENESIS_CHAIN_1", "252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99",
                        ("2026-10-09T04:59:49Z", None)),      # the record gives the marker, not the end
    "M-B11": CeremonyV1("DEV", "first K-ACT load (signer start)", "slice-15b2b-b1b3e-mb11-signer-start-acceptance.md",
                        None, None, ("2026-10-15T05:13:15Z", "2026-10-15T05:13:29Z")),  # marker to POST11 record
}
# Scope questions left open on purpose (never silently included or excluded).
UNRESOLVED_SCOPE: Mapping[str, str] = {
    "B1B3D-L2b": "K-ACT generation (B1b-3d L2b, before PR-1B): include, cite, or exclude is OD-M12-7",
}
SCOPE_TYPE = "LILITH_MB12_SECRET_HYGIENE_SCOPE"
SCOPE_FIELDS = frozenset({"scopeType", "schemaVersion", "environment", "ceremonies", "journalScan"})
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_BOOT = re.compile(r"BOOT: ([0-9a-f]{32}) firstRealtimeUs=(\d+) lastRealtimeUs=(\d+) entries=([1-9]\d*)\Z")


def to_us(instant: str) -> int:
    return int(datetime.strptime(instant, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()) * 1_000_000


# ------------------------------------------------------------------ journal ---

class JournalError(ValueError):
    pass


class _Tee:
    """A reader that feeds every byte it returns to the scanner."""

    def __init__(self, raw: BinaryIO, scanner: Scanner):
        self.raw, self.scanner = raw, scanner

    def readline(self, limit: int) -> bytes:
        line = self.raw.readline(limit)
        self.scanner.feed(line)
        return line

    def read(self, size: int) -> bytes:
        data, left = [], size
        while left:
            chunk = self.raw.read(min(left, CHUNK))
            if not chunk:
                raise JournalError("JOURNAL_TRUNCATED")
            self.scanner.feed(chunk)
            data.append(chunk)
            left -= len(chunk)
        return b"".join(data)


def parse_export(raw: BinaryIO, scanner: Scanner) -> dict[str, list[int]]:
    """{boot_id: [first_us, last_us, entries]} from the journal export format (systemd JOURNAL_EXPORT_FORMATS):
    `NAME=value\\n` text fields, `NAME\\n<le64 size><data>\\n` binary fields, an empty line ends an entry. Every
    entry needs `__REALTIME_TIMESTAMP` and `_BOOT_ID`; anything else malformed is refused."""
    tee, boots, fields = _Tee(raw, scanner), {}, {}
    while True:
        line = tee.readline(MAX_FIELD_BYTES + 2)
        if line == b"":
            if fields:
                raise JournalError("JOURNAL_TRUNCATED")
            return boots
        if not line.endswith(b"\n"):
            raise JournalError("JOURNAL_FIELD_TOO_LARGE" if len(line) > MAX_FIELD_BYTES else "JOURNAL_TRUNCATED")
        if line == b"\n":
            if not fields:
                raise JournalError("JOURNAL_MALFORMED")
            realtime, boot = fields.get("__REALTIME_TIMESTAMP"), fields.get("_BOOT_ID")
            if realtime is None or not realtime.isdigit() or boot is None or re.fullmatch("[0-9a-f]{32}", boot) is None:
                raise JournalError("JOURNAL_ENTRY_MALFORMED")
            value = int(realtime)
            span = boots.setdefault(boot, [value, value, 0])
            span[0], span[1], span[2] = min(span[0], value), max(span[1], value), span[2] + 1
            fields = {}
            continue
        if b"=" in line:
            name, value = line[:-1].split(b"=", 1)
            if name in (b"__REALTIME_TIMESTAMP", b"_BOOT_ID"):
                fields[name.decode("ascii", "replace")] = value.decode("ascii", "replace")
            else:
                fields.setdefault("_", "")
            continue
        size = struct.unpack("<Q", tee.read(8))[0]
        if size > MAX_FIELD_BYTES:
            raise JournalError("JOURNAL_FIELD_TOO_LARGE")
        tee.read(size)
        if tee.read(1) != b"\n":
            raise JournalError("JOURNAL_MALFORMED")
        fields.setdefault("_", "")


class _Journalctl:
    """`journalctl -o export` as a reader whose `finish` fails unless the process exited 0 (a stream cut short at an
    entry boundary must not read as a complete journal)."""

    def __init__(self) -> None:
        self.process = subprocess.Popen([JOURNALCTL, "--no-pager", "-o", "export"], env=FIXED_ENV,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        assert self.process.stdout is not None
        self.readline, self.read = self.process.stdout.readline, self.process.stdout.read

    def finish(self) -> None:
        self.process.stdout.close()
        if self.process.wait(timeout=600) != 0:
            raise OSError("journalctl failed")


def _journal_stream() -> BinaryIO:
    return _Journalctl()  # type: ignore[return-value]


def journal_scan(*, stream: Callable[[], BinaryIO] = _journal_stream, euid: Callable[[], int] = os.geteuid,
                 say: Callable[[str], None] = print) -> bool:
    if euid() != 0:
        say("JOURNAL_SECRET_SCAN=FAIL reason=NOT_ROOT")
        return False
    scanner = Scanner()
    try:
        reader = stream()
        boots = parse_export(reader, scanner)
        finish = getattr(reader, "finish", None)
        if finish is not None:
            finish()
    except (JournalError, OSError, struct.error) as exc:
        reason = exc.args[0] if isinstance(exc, JournalError) else "JOURNAL_UNREADABLE"
        say(f"FAIL: {reason}")
        say(f"JOURNAL_SECRET_SCAN=FAIL reason={reason}")
        return False
    failures = [f"FAIL: PRIVATE_MATERIAL_MARKER class={name} count={count}" for name, count in scanner.hits()]
    if not boots:
        failures.append("FAIL: JOURNAL_EMPTY")
        first = last = None
    else:
        first, last = min(s[0] for s in boots.values()), max(s[1] for s in boots.values())
    entries = sum(s[2] for s in boots.values())
    say(f"JOURNAL: entries={entries} bytes={scanner.size} sha256={scanner.digest.hexdigest()} "
        f"firstRealtimeUs={first if first is not None else 'NONE'} lastRealtimeUs={last if last is not None else 'NONE'} "
        f"boots={len(boots)}")
    for boot, (low, high, count) in sorted(boots.items(), key=lambda item: (item[1][0], item[0])):
        say(f"BOOT: {boot} firstRealtimeUs={low} lastRealtimeUs={high} entries={count}")
    for line in failures:
        say(line)
    say("JOURNAL_SECRET_SCAN=FAIL" if failures else f"JOURNAL_SECRET_SCAN=PASS firstRealtimeUs={first} "
        f"lastRealtimeUs={last}")
    return not failures


def parse_journal_transcript(data: bytes) -> list[tuple[str, int, int]] | None:
    """The boots of an exact `journal` PASS transcript, or None."""
    try:
        lines = data.decode("ascii").split("\n")
    except UnicodeDecodeError:
        return None
    if len(lines) < 4 or lines[-1] != "":
        return None
    head = re.fullmatch(r"JOURNAL: entries=([1-9]\d*) bytes=\d+ sha256=[0-9a-f]{64} firstRealtimeUs=(\d+) "
                        r"lastRealtimeUs=(\d+) boots=([1-9]\d*)", lines[0])
    final = re.fullmatch(r"JOURNAL_SECRET_SCAN=PASS firstRealtimeUs=(\d+) lastRealtimeUs=(\d+)", lines[-2])
    if head is None or final is None or (head.group(2), head.group(3)) != final.groups():
        return None
    boots = [_BOOT.fullmatch(line) for line in lines[1:-2]]
    if not boots or any(b is None for b in boots) or len(boots) != int(head.group(4)):
        return None
    spans = [(b.group(1), int(b.group(2)), int(b.group(3))) for b in boots]
    if sum(int(b.group(4)) for b in boots) != int(head.group(1)) or len({s[0] for s in spans}) != len(spans) \
            or any(low > high for _b, low, high in spans) or spans != sorted(spans, key=lambda s: (s[1], s[0])) \
            or (min(s[1] for s in spans), max(s[2] for s in spans)) != (int(final.group(1)), int(final.group(2))):
        return None
    return spans


# -------------------------------------------------------------------- scope ---

class ScopeError(ValueError):
    pass


def _need(condition: Any, reason: str) -> None:
    if not condition:
        raise ScopeError(reason)


def scope_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_scope(raw: bytes, ceremonies: Mapping[str, CeremonyV1] = CEREMONIES) -> dict[str, Any]:
    def no_duplicates(pairs):
        keys = [k for k, _ in pairs]
        _need(len(keys) == len(set(keys)), "SCOPE_DUPLICATE_KEY")
        return dict(pairs)
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    except ScopeError:
        raise
    except (UnicodeDecodeError, ValueError) as exc:
        raise ScopeError("SCOPE_MALFORMED") from exc
    _need(isinstance(doc, dict) and set(doc) == SCOPE_FIELDS and doc["scopeType"] == SCOPE_TYPE
          and type(doc["schemaVersion"]) is int and doc["schemaVersion"] == 1 and doc["environment"] == "dev",
          "SCOPE_MALFORMED")
    _need(isinstance(doc["ceremonies"], list) and isinstance(doc["journalScan"], dict)
          and set(doc["journalScan"]) == {"path", "sha256"} and isinstance(doc["journalScan"]["sha256"], str)
          and _HEX64.fullmatch(doc["journalScan"]["sha256"]), "SCOPE_MALFORMED")
    names = [c.get("ceremony") if isinstance(c, dict) else None for c in doc["ceremonies"]]
    _need(names == list(ceremonies), "SCOPE_CEREMONIES_NOT_EXACT")
    for entry in doc["ceremonies"]:
        _need(set(entry) == {"ceremony", "items"} and isinstance(entry["items"], list), "SCOPE_MALFORMED")
        spec = ceremonies[entry["ceremony"]]
        transcripts = publications = 0
        for item in entry["items"]:
            _need(isinstance(item, dict) and set(item) == {"role", "kind", "path", "sha256"}
                  and isinstance(item["path"], str) and isinstance(item["sha256"], str)
                  and _HEX64.fullmatch(item["sha256"]), "SCOPE_ITEM_MALFORMED")
            if item["role"] == "TRANSCRIPT" and item["kind"] is None:
                transcripts += 1
            elif item["role"] == "PUBLICATION" and spec.publication is not None and item["kind"] == spec.publication:
                publications += 1
            else:
                raise ScopeError("SCOPE_ITEM_NOT_IN_CONTRACT")
        _need(transcripts >= 1, "SCOPE_TRANSCRIPT_MISSING")
        _need(publications == (1 if spec.publication else 0), "SCOPE_PUBLICATION_NOT_EXACT")
    return doc


def _read_bound(path: str, sha256: str) -> bytes | None:
    """The file's bytes only if a regular file (no symlink) within the bound whose SHA-256 is `sha256`."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return None
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_ITEM_BYTES:
            return None
        chunks, total = [], 0
        while chunk := os.read(fd, CHUNK):
            total += len(chunk)
            if total > MAX_ITEM_BYTES:
                return None
            chunks.append(chunk)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    return data if hashlib.sha256(data).hexdigest() == sha256 else None


def prove(raw_scope: bytes, *, read: Callable[[str, str], "bytes | None"] = _read_bound,
          say: Callable[[str], None] = print, ceremonies: Mapping[str, CeremonyV1] = CEREMONIES,
          unresolved: Mapping[str, str] = UNRESOLVED_SCOPE, repo: Path | None = REPO) -> bool:
    try:
        scope = parse_scope(raw_scope, ceremonies)
    except ScopeError as exc:
        say(f"SECRET_HYGIENE_PROOF=FAIL reason={exc.args[0]}")
        return False
    digest = scope_digest(raw_scope)
    say(f"SCOPE: sha256={digest} ceremonies={','.join(ceremonies)}")
    failures = [f"FAIL: SCOPE_DECISION_UNRESOLVED {key}" for key in sorted(unresolved)]
    journal = read(scope["journalScan"]["path"], scope["journalScan"]["sha256"])
    boots = None if journal is None or scan_bytes(journal).hits() else parse_journal_transcript(journal)
    if boots is None:
        failures.append("FAIL: JOURNAL_SCAN_NOT_PASS")
    for entry in scope["ceremonies"]:
        name, spec = entry["ceremony"], ceremonies[entry["ceremony"]]
        if spec.record is None or repo is None or not (repo / "docs/architecture" / spec.record).is_file():
            failures.append(f"FAIL: CEREMONY_RECORD_ABSENT {name}")
        for item in entry["items"]:
            label = item["role"] if item["kind"] is None else f"{item['role']}:{item['kind']}"
            if item["kind"] is not None and spec.publication_sha256 is not None \
                    and item["sha256"] != spec.publication_sha256:
                failures.append(f"FAIL: PUBLICATION_NOT_THE_RECORDED_ONE {name} {label}")
                continue
            data = read(item["path"], item["sha256"])
            if data is None:
                failures.append(f"FAIL: ITEM_UNREADABLE_OR_DIGEST_MISMATCH {name} {label}")
                continue
            hits = scan_bytes(data).hits()
            failures += [f"FAIL: PRIVATE_MATERIAL_MARKER {name} {label} class={n} count={c}" for n, c in hits]
            if not hits:
                say(f"ITEM: {name} {label} sha256={item['sha256']} bytes={len(data)} CLEAN")
        if spec.venue == "S25":
            say(f"OFFHOST: {name} S25 (no DEV journal)")
            continue
        start, end = spec.window if spec.window else (None, None)
        if start is None or end is None:
            failures.append(f"FAIL: CEREMONY_WINDOW_NOT_RECORDED {name}")
            continue
        low, high = to_us(start), to_us(end)
        covering = [boot for boot, first, last in (boots or []) if first <= low and high <= last]
        if not covering:
            failures.append(f"FAIL: JOURNAL_DOES_NOT_COVER {name}")
        else:
            say(f"COVERED: {name} boot={covering[0]} window={start}/{end}")
    if boots is not None and not any(line.startswith("FAIL: JOURNAL") for line in failures):
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
