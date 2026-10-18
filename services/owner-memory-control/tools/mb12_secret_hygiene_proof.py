#!/usr/bin/python3 -IB
"""15B2b-B1b-3e M-B12 PR-B2: the SECRET_HYGIENE proof producer (E-22). Stdlib only; reads, never writes.

Record: docs/architecture/slice-15b2b-b1b3e-mb12-prb2-proof-producers.md.
DESIGN / SOURCE ONLY. Running either form live needs a separate owner authorization.

Preflight §19 E-22 is "secret hygiene: journal, transcript, and publication scans clean for every PR-1B credential
ceremony"; B1b-3d L2b STOPs on "any private-key pattern in output or journal". Four forms, one marker set:

- `journal` (root, DEV): parses one read-only `journalctl --no-pager -o export` stream entry by entry (text and
  binary fields), scans every byte, and reports per retained boot (`_BOOT_ID`) its oldest and newest entry. It prints
  counts, digests and timestamps only.
- `attribute` (root, DEV): the same read, plus WHERE each counted marker is (boot, realtime, field name, unit, syslog
  identifier, text/binary, armour role, verdict COMPLETE_PEM_BLOCK / HEADER_OR_COMMAND_TEXT / UNKNOWN). Never a
  value, byte, offset or surrounding text; journal strings only through an allow-list. FAIL unless every counted
  match lies inside one field value. It never changes a `journal` FAIL.
- `purpose` (root, DEV): only the three attributed sudo sessions (journalctl boot / unit / time filters). Per session,
  closed enums of command STRUCTURE and a verdict LITERAL_PATTERN_SEARCH / EXPOSED_KEY_EVIDENCE / UNKNOWN. Never a
  value, pattern, path or argument. FAIL on any unexpected entry, missing session or count mismatch.
- `prove <scope.json>` (owner, off-host): scans the closed scope of `CEREMONIES` (OD-M12-7, PROPOSED): each ceremony's
  transcripts and its named publication (pinned by the canonical record where the record gives a full SHA-256), the
  canonical record must exist, and every DEV ceremony window must lie inside ONE retained boot of a `journal`
  transcript (so the journal covers it continuously within that boot, and its newest entry is after the ceremony end).
  S25 / off-host ceremonies have no DEV journal requirement. A scope decision left open (`UNRESOLVED_SCOPE`), an
  unrecorded ceremony window, an absent record, or a ceremony transcript an owner record states was not retained
  (`TRANSCRIPT_NOT_RETAINED`, OD-M12-9) FAILS: no PASS is produced by default.

Detection contract (nonclaims): the markers are PEM / OpenSSH private-key armour (`install_authority_dev`
FORBIDDEN_MARKERS / the test markers) and the fixed Ed25519 PKCS#8 DER prefix the keygen emits, as raw bytes, hex
(lower / upper) and base64 (standard and URL-safe) at all three byte alignments. A clean result means "no specified
marker in the scanned scope", never "no secret ever leaked". Bare 32-byte seeds, separated or mixed-case hex and other
encodings are OUTSIDE the contract. Output never contains a matched byte, an offset, a path or key material.

    sudo /usr/bin/python3 -I -B - journal < mb12_secret_hygiene_proof.py        (DEV, root)
    sudo /usr/bin/python3 -I -B - attribute < mb12_secret_hygiene_proof.py      (DEV, root)
    sudo /usr/bin/python3 -I -B - purpose < mb12_secret_hygiene_proof.py        (DEV, root)
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

# The repository root (off-host `prove`). Streamed on DEV (`python3 - journal`) CPython sets `__file__` to "<stdin>"
# (or leaves it unset when exec'd): there is no repository then.
REPO = Path(__file__).resolve().parents[3] if globals().get("__file__", "<stdin>") != "<stdin>" else None
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
    # OD-M12-7 (owner, 2026-10-17; PR-B2 record §13): L2b is included. Its canonical record gives no ceremony window,
    # so the window stays unrecorded and `prove` FAILS (CEREMONY_WINDOW_NOT_RECORDED). Nothing is inferred from the
    # attribution or the journal. OD-M12-9 (PR-B2 record §16): the publication pin is the accepted K-ACT publication
    # capture of the M-B3 completion record (the same host file, read 2026-10-06), not a value of the L2b closure.
    "B1B3D-L2b": CeremonyV1("DEV", "K-ACT generation and publication (B1b-3d L2b.2)",
                            "slice-15b2b-b1b3d-live-closure.md", "K_ACT_PUBLICATION",
                            "d76479762007afef828f3901591647dc4a2fb2205f4afac527b66d2cc9c6b032", (None, None)),
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
                        # OD-M12-9: the operator-clock invocation bracket MB9B_INVOKE_START / MB9B_INVOKE_END of
                        # the sealed Package B sequence-3 state.txt (laptop clock, not host-recorded); it contains
                        # the host marker `mb9b` 04:59:49Z of the record.
                        ("2026-10-09T04:59:44Z", "2026-10-09T04:59:59Z")),
    "M-B11": CeremonyV1("DEV", "first K-ACT load (signer start)", "slice-15b2b-b1b3e-mb11-signer-start-acceptance.md",
                        None, None, ("2026-10-15T05:13:15Z", "2026-10-15T05:13:29Z")),  # marker to POST11 record
}
# Scope questions left open on purpose (never silently included or excluded). OD-M12-7 decided B1B3D-L2b: included
# (CEREMONIES above). No question is open; an open one would FAIL `prove` again.
UNRESOLVED_SCOPE: Mapping[str, str] = {}
# Ceremonies whose transcript an owner record states was NOT retained: ceremony -> owner decision. The scope then lists
# no TRANSCRIPT item for it, and `prove` prints an explicit FAIL (CEREMONY_TRANSCRIPT_NOT_RETAINED) instead of
# refusing the whole scope, so every other check still runs. It is never a PASS and never satisfied by a substitute.
# OD-M12-9 (owner, 2026-10-18; PR-B2 record §16): no byte-exact B1b-3d L2b ceremony transcript is retained.
TRANSCRIPT_NOT_RETAINED: Mapping[str, str] = {"B1B3D-L2b": "OD-M12-9"}
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


def parse_export(raw: BinaryIO, scanner: Scanner,
                 on_entry: Callable[[str, int, list], None] | None = None) -> dict[str, list[int]]:
    """{boot_id: [first_us, last_us, entries]} from the journal export format (systemd JOURNAL_EXPORT_FORMATS):
    `NAME=value\\n` text fields, `NAME\\n<le64 size><data>\\n` binary fields, an empty line ends an entry. Every
    entry needs `__REALTIME_TIMESTAMP` and `_BOOT_ID`; anything else malformed is refused. `on_entry` (the
    `attribute` form only) receives (boot, realtime_us, [(name, value, is_binary), ...]) per complete entry; without
    it nothing is retained and the scan is unchanged."""
    tee, boots, fields, collected = _Tee(raw, scanner), {}, {}, []
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
            if on_entry is not None:
                on_entry(boot, value, collected)
                collected = []
            fields = {}
            continue
        if b"=" in line:
            name, value = line[:-1].split(b"=", 1)
            if name in (b"__REALTIME_TIMESTAMP", b"_BOOT_ID"):
                fields[name.decode("ascii", "replace")] = value.decode("ascii", "replace")
            else:
                fields.setdefault("_", "")
            if on_entry is not None:
                collected.append((name, value, False))
            continue
        size = struct.unpack("<Q", tee.read(8))[0]
        if size > MAX_FIELD_BYTES:
            raise JournalError("JOURNAL_FIELD_TOO_LARGE")
        data = tee.read(size)
        if tee.read(1) != b"\n":
            raise JournalError("JOURNAL_MALFORMED")
        fields.setdefault("_", "")
        if on_entry is not None:
            collected.append((line[:-1], data, True))


class _Journalctl:
    """`journalctl -o export` as a reader whose `finish` fails unless the process exited 0 (a stream cut short at an
    entry boundary must not read as a complete journal)."""

    def __init__(self, filters: tuple[str, ...] = ()) -> None:
        self.process = subprocess.Popen([JOURNALCTL, "--no-pager", "-o", "export", *filters], env=FIXED_ENV,
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


# --------------------------------------------------------------- attribution ---
# `attribute` (root, DEV): WHERE the scan's markers are, never WHAT. Per match it emits the boot, realtime, field
# name, `_SYSTEMD_UNIT`, `SYSLOG_IDENTIFIER`, text/binary, armour role and a verdict. Never a value, a byte, an offset
# or surrounding text; a journal-controlled string is emitted only if it matches a strict allow-list, else `UNSAFE`.
# It never turns a scan FAIL into a PASS: the verdicts are heuristics for owner adjudication.
MAX_ATTRIBUTED = 64
PEM_CLASS = "PEM_PRIVATE_KEY"
MIN_KEY_BODY = 40                                  # base64 characters; an Ed25519 PKCS#8 PEM body is 64
_PEM = MARKERS[PEM_CLASS][0]                       # assembled above: this source never contains a marker itself
_ARMOUR = re.compile(rb"-----(BEGIN|END) ((?:[A-Z0-9]+ )*)" + re.escape(_PEM))
_B64_RUN = re.compile(rb"[A-Za-z0-9+/=]+")
_NEWLINES = re.compile(rb"\r|\n|\\r|\\n")          # real line breaks and their escaped spellings
_SAFE_FIELD = re.compile(rb"[A-Z0-9_]{1,64}\Z")
_SAFE_META = re.compile(rb"[A-Za-z0-9@._:+\-]{1,128}\Z")
VERDICTS = ("COMPLETE_PEM_BLOCK", "HEADER_OR_COMMAND_TEXT", "UNKNOWN")


def _safe(value: bytes | None, pattern: re.Pattern) -> str:
    if value is None:
        return "NONE"
    return value.decode("ascii") if pattern.fullmatch(value) else "UNSAFE"


def _positions(value: bytes, marker: bytes) -> list[int]:
    found, start = [], 0
    while (index := value.find(marker, start)) != -1:
        found.append(index)
        start = index + 1
    return found


def _longest_run(data: bytes) -> int:
    return max((len(run) for run in _B64_RUN.findall(_NEWLINES.sub(b"", data))), default=0)


def classify_pem(value: bytes, end: int) -> tuple[str, str]:
    """(role, verdict) of the PEM marker ending at `end` inside one field value.
    COMPLETE_PEM_BLOCK: a BEGIN/END pair of one type encloses a base64 body of >= MIN_KEY_BODY characters.
    HEADER_OR_COMMAND_TEXT: the armour sits inside other text, unpaired or paired around non-key text, with no
    key-like base64 run beside it. UNKNOWN: anything else (no armour, a lone armour line that could be one line of a
    key logged line by line, a short or key-like body)."""
    armour = next((m for m in _ARMOUR.finditer(value) if m.end() == end), None)
    if armour is None:
        return "OTHER", "UNKNOWN"
    role, kind = armour.group(1).decode("ascii"), armour.group(2)
    if role == "BEGIN":
        close = re.compile(rb"-----END " + re.escape(kind) + re.escape(_PEM)).search(value, end)
        body = value[end:close.start()] if close else None
        beside = _NEWLINES.sub(b"", value[end:end + 4096])
        adjacent = len(re.match(rb"[A-Za-z0-9+/=]*", beside).group(0))
    else:
        opens = list(re.compile(rb"-----BEGIN " + re.escape(kind) + re.escape(_PEM)).finditer(value, 0, armour.start()))
        body = value[opens[-1].end():armour.start()] if opens else None
        beside = _NEWLINES.sub(b"", value[max(0, armour.start() - 4096):armour.start()])
        adjacent = len(re.search(rb"[A-Za-z0-9+/=]*\Z", beside).group(0))
    if body is not None:
        cleaned = _NEWLINES.sub(b"", body)
        if re.fullmatch(rb"[A-Za-z0-9+/=]+", cleaned):
            return role, "COMPLETE_PEM_BLOCK" if len(cleaned) >= MIN_KEY_BODY else "UNKNOWN"
        return role, "UNKNOWN" if _longest_run(body) >= MIN_KEY_BODY else "HEADER_OR_COMMAND_TEXT"
    if adjacent >= MIN_KEY_BODY or value.strip(b" \t\r\n'\"") == armour.group(0):
        return role, "UNKNOWN"
    return role, "HEADER_OR_COMMAND_TEXT"


def journal_attribute(*, stream: Callable[[], BinaryIO] = _journal_stream, euid: Callable[[], int] = os.geteuid,
                      say: Callable[[str], None] = print) -> bool:
    """Re-read the journal once; attribute every marker the scanner counts to (entry, field), fail closed unless
    every counted match is inside one field value."""
    if euid() != 0:
        say("JOURNAL_MARKER_ATTRIBUTION=FAIL reason=NOT_ROOT")
        return False
    scanner, found = Scanner(), []

    def on_entry(boot: str, realtime: int, fields: list) -> None:
        meta: dict[bytes, bytes | None] = {b"_SYSTEMD_UNIT": None, b"SYSLOG_IDENTIFIER": None}
        for name, value, binary in fields:
            if name in meta and meta[name] is None:
                meta[name] = None if binary else value
        for name, value, binary in fields:
            for cls, markers in MARKERS.items():
                for marker in markers:
                    positions = _positions(value, marker)
                    for index in positions:
                        role, verdict = (classify_pem(value, index + len(marker)) if cls == PEM_CLASS
                                         else ("OTHER", "UNKNOWN"))
                        found.append((cls, boot, realtime, _safe(name, _SAFE_FIELD),
                                      _safe(meta[b"_SYSTEMD_UNIT"], _SAFE_META),
                                      _safe(meta[b"SYSLOG_IDENTIFIER"], _SAFE_META),
                                      "BINARY" if binary else "TEXT", role, verdict, len(positions)))

    try:
        reader = stream()
        boots = parse_export(reader, scanner, on_entry)
        finish = getattr(reader, "finish", None)
        if finish is not None:
            finish()
    except (JournalError, OSError, struct.error) as exc:
        reason = exc.args[0] if isinstance(exc, JournalError) else "JOURNAL_UNREADABLE"
        say(f"JOURNAL_MARKER_ATTRIBUTION=FAIL reason={reason}")
        return False
    entries = sum(s[2] for s in boots.values())
    say(f"JOURNAL: entries={entries} bytes={scanner.size} sha256={scanner.digest.hexdigest()} boots={len(boots)}")
    for n, (cls, boot, realtime, field, unit, ident, kind, role, verdict, in_field) in \
            enumerate(found[:MAX_ATTRIBUTED], 1):
        say(f"MATCH: n={n} class={cls} boot={boot} realtimeUs={realtime} field={field} unit={unit} "
            f"identifier={ident} kind={kind} role={role} verdict={verdict} inField={in_field}")
    failures = []
    for cls in MARKERS:
        stream_count, in_field = scanner.counts[cls], sum(1 for item in found if item[0] == cls)
        if stream_count or in_field:
            say(f"COUNTS: class={cls} stream={stream_count} inField={in_field} boundary={stream_count - in_field}")
        if in_field > stream_count:
            failures.append("COUNTS_INCONSISTENT")
        elif in_field < stream_count:
            failures.append("UNATTRIBUTED_STREAM_MATCHES")
    if not boots:
        failures.append("JOURNAL_EMPTY")
    if len(found) > MAX_ATTRIBUTED:
        failures.append("TOO_MANY_MATCHES")
    say("SUMMARY: " + " ".join(f"{v}={sum(1 for item in found if item[8] == v)}" for v in VERDICTS))
    say("NONCLAIM: attribution never changes JOURNAL_SECRET_SCAN=FAIL; verdicts are heuristics over bytes kept on DEV")
    if failures:
        say("JOURNAL_MARKER_ATTRIBUTION=FAIL reason=" + ",".join(sorted(set(failures))))
        return False
    say(f"JOURNAL_MARKER_ATTRIBUTION=COMPLETE matches={len(found)}")
    return True


# ------------------------------------------------------------------ purpose ---
# `purpose` (root, DEV): the three sudo sessions the 2026-10-15 attribution found (boot 24d1771d…, 2026-09-27), read
# through journalctl's own boot / unit / time filters, never the whole journal. Per session it reports command
# STRUCTURE only, as closed enums: the program, whether the sudo MESSAGE and every `_CMDLINE` agree, the file operand
# class, marker counts, and whether anything key-like is present. journald joins argv with spaces, so arguments are
# not reconstructed: anything outside the closed shapes is UNKNOWN. It never changes a `journal` FAIL.
PURPOSE_BOOT = "24d1771de1b54e5f816dda08ad8b367a"
PURPOSE_SESSIONS = {"session-3837.scope": 1790493545688402,        # attribution anchors (first match, realtime us)
                    "session-3845.scope": 1790493771742151,
                    "session-3850.scope": 1790493936317730}
PURPOSE_SLACK_US = 30_000_000                          # every entry of a session within +-30 s of its anchor
# The attribution's exact historical counts: anything else FAILs, never COMPLETE.
PURPOSE_EXPECTED = {"markerFields": 4, "markers": 4, "messageFields": 1, "cmdlineFields": 3}   # per session
PURPOSE_TOTAL_MARKERS = 12
PUBLICATION_PATH = b"/root/b1b3d-l2b-publication.json"              # L2b.2 runbook publication file
_PROGRAMS = {b"grep": "GREP", b"egrep": "GREP", b"fgrep": "GREP", b"zgrep": "GREP", b"journalctl": "JOURNALCTL",
             b"sh": "SHELL", b"bash": "SHELL", b"dash": "SHELL"}
PURPOSE_VERDICTS = ("LITERAL_PATTERN_SEARCH", "EXPOSED_KEY_EVIDENCE", "UNKNOWN")
# The closed option sets of a recognized search shape. Only `-e` (grep) and `--grep`/`-g` (journalctl) take a value;
# any other option, an attached `-e<x>`, `-f`, `--regexp=` or a valued option with a separate value is UNKNOWN.
_GREP_SHORT = frozenset(b"cEFGPiylnqsvwxHhoaIUZz")
_GREP_LONG = frozenset({b"--count", b"--extended-regexp", b"--fixed-strings", b"--basic-regexp", b"--perl-regexp",
                        b"--ignore-case", b"--no-ignore-case", b"--quiet", b"--silent", b"--files-with-matches",
                        b"--files-without-match", b"--line-number", b"--no-messages", b"--invert-match",
                        b"--word-regexp", b"--line-regexp", b"--with-filename", b"--no-filename", b"--only-matching",
                        b"--text", b"--null"})
_JOURNAL_FLAGS = frozenset({b"--no-pager", b"-q", b"--quiet", b"-a", b"--all", b"-r", b"--reverse", b"-m", b"--merge",
                            b"--utc", b"-x", b"--catalog", b"-b"})
_JOURNAL_VALUED = (b"--since=", b"--until=", b"--unit=", b"--boot=", b"--output=", b"--case-sensitive=")


def _grep_flag(word: bytes) -> bool:
    return word in _GREP_LONG or (len(word) > 1 and word[:1] == b"-" and word[1:2] != b"-"
                                  and all(c in _GREP_SHORT for c in word[1:]))


def _journal_option(word: bytes) -> bool:
    return word in _JOURNAL_FLAGS or word.startswith(_JOURNAL_VALUED)


def _one_marker_in(regions: list[list[bytes]], rest: list[bytes]) -> bool:
    return (b" ".join(rest).count(_PEM) == 1
            and sum(b" ".join(region).count(_PEM) for region in regions) == 1)


def pattern_argument(program: str, rest: list[bytes]) -> bool:
    """True only when the command's single PEM marker lies inside a recognized search-pattern argument of a closed
    shape whose argv boundary is ESTABLISHED. journald joins argv with spaces, so a region of several words could be
    one quoted pattern or a pattern plus further operands: only a region of exactly ONE word has a known boundary.
    Every multi-word region, option, operand or unknown token is ambiguous (False). Values are never returned.
    grep:       [flags] [--] PATTERN /OPERAND      or   [flags] (-e PATTERN)+ /OPERAND
    journalctl: [flags | --opt=value] (--grep | -g) PATTERN   or   [...] --grep=PATTERN
    Consequence: the PEM marker contains a space, so it can never lie in one joined word; for it this is always False
    and LITERAL_PATTERN_SEARCH is unreachable (UNKNOWN), by design."""
    if program == "GREP":
        if len(rest) < 2 or not rest[-1].startswith(b"/") or _PEM in rest[-1]:
            return False
        body, i = rest[:-1], 0
        while i < len(body) and _grep_flag(body[i]):
            i += 1
        if i < len(body) and body[i] == b"-e":
            regions, current = [], None
            for word in body[i:]:
                if word == b"-e":
                    if current is not None:
                        regions.append(current)
                    current = []
                elif _grep_flag(word) or word == b"--" or word.startswith(b"/"):
                    return False
                else:
                    current.append(word)
            regions.append(current)
        else:
            dashed = i < len(body) and body[i] == b"--"
            region = body[i + 1:] if dashed else body[i:]
            if not region or (not dashed and region[0].startswith(b"-")):
                return False
            if any(_grep_flag(w) or w in (b"-e", b"--") or w.startswith(b"/") for w in region):
                return False
            regions = [region]
        return all(len(region) == 1 for region in regions) and _one_marker_in(regions, rest)
    if program == "JOURNALCTL":
        grips = [n for n, w in enumerate(rest) if w in (b"--grep", b"-g") or w.startswith(b"--grep=")]
        if len(grips) != 1 or not all(_journal_option(w) for w in rest[:grips[0]]):
            return False
        g = grips[0]
        inline = rest[g][len(b"--grep="):] if rest[g].startswith(b"--grep=") else None
        region = ([inline] if inline else []) + rest[g + 1:]
        if len(region) != 1 or _journal_option(region[0]) or region[0] in (b"--grep", b"-g"):
            return False
        return _one_marker_in([region], rest)
    return False


def purpose_filters() -> tuple[str, ...]:
    low = min(PURPOSE_SESSIONS.values()) - PURPOSE_SLACK_US
    high = max(PURPOSE_SESSIONS.values()) + PURPOSE_SLACK_US
    return ("-b", PURPOSE_BOOT, "--since", f"@{low // 1_000_000}", "--until", f"@{high // 1_000_000 + 1}",
            *(f"_SYSTEMD_UNIT={unit}" for unit in PURPOSE_SESSIONS))


def _program(words: list[bytes]) -> tuple[str, int]:
    """(program class, index of the program word) after an optional leading `sudo` and its options."""
    index = 0
    if words and words[0].rsplit(b"/", 1)[-1] == b"sudo":
        index = 1
        while index < len(words) and words[index].startswith(b"-"):
            index += 1
    if index >= len(words):
        return "NONE", index
    name = words[index].rsplit(b"/", 1)[-1]
    return _PROGRAMS.get(name, "PYTHON" if name.startswith(b"python") else "OTHER"), index


def _session_verdict(fields: list[tuple[bytes, bytes, bool]]) -> dict[str, Any]:
    """Closed facts for one session's entries: never a value, only enums and counts."""
    marker_fields = [(name, value) for name, value, binary in fields if not binary and _PEM in value]
    messages = [value for name, value in marker_fields if name == b"MESSAGE"]
    cmdlines = [value for name, value in marker_fields if name == b"_CMDLINE"]
    every = [value for _name, value, _binary in fields]
    other = sum(len(_positions(value, marker)) for value in every for cls, markers in MARKERS.items()
                if cls != PEM_CLASS for marker in markers)
    pem_block = any(classify_pem(value, i + len(_PEM))[1] == "COMPLETE_PEM_BLOCK"
                    for value in every for i in _positions(value, _PEM))
    key_like = any(_longest_run(value) >= MIN_KEY_BODY for name, value, binary in fields
                   if name in (b"MESSAGE", b"_CMDLINE"))                      # command text only
    facts = {"markerFields": len(marker_fields), "markers": sum(v.count(_PEM) for _n, v in marker_fields),
             "messageFields": len(messages), "cmdlineFields": len(cmdlines), "program": "NONE", "grepOption": "NO",
             "patternArgument": "NO", "operand": "NONE", "cmdlineConsistent": "NO",
             "pemBlock": "YES" if pem_block else "NO",
             "keyLikeRun": "YES" if key_like else "NO", "otherMarkers": "YES" if other else "NO"}
    if len(messages) == 1 and b"COMMAND=" in messages[0] and cmdlines:
        command = messages[0].rsplit(b"COMMAND=", 1)[1].split(b" ")
        program, at = _program(command)
        cl_words = cmdlines[0].split(b" ")
        cl_program, cl_at = _program(cl_words)
        facts["program"] = program
        facts["cmdlineConsistent"] = "YES" if (len(set(cmdlines)) == 1 and cl_program == program
                                               and cl_words[cl_at + 1:] == command[at + 1:]) else "NO"
        rest = command[at + 1:]
        facts["grepOption"] = "YES" if any(w in (b"-g", b"--grep") or w.startswith(b"--grep=") for w in rest) else "NO"
        facts["patternArgument"] = "YES" if pattern_argument(program, rest) else "NO"
        last = rest[-1] if rest else b""
        facts["operand"] = ("NONE" if not rest or _PEM in last else "PUBLICATION_JSON" if last == PUBLICATION_PATH
                            else "ROOT_PATH" if last.startswith(b"/root/") else "OTHER")
    if facts["pemBlock"] == "YES" or facts["otherMarkers"] == "YES":
        verdict = "EXPOSED_KEY_EVIDENCE"
    elif (facts["keyLikeRun"] == "NO" and facts["patternArgument"] == "YES" and facts["cmdlineConsistent"] == "YES"
          and all(facts[k] == v for k, v in PURPOSE_EXPECTED.items())):
        verdict = "LITERAL_PATTERN_SEARCH"
    else:
        verdict = "UNKNOWN"
    return {**facts, "verdict": verdict}


def journal_purpose(*, stream: Callable[[], BinaryIO] | None = None, euid: Callable[[], int] = os.geteuid,
                    say: Callable[[str], None] = print) -> bool:
    if euid() != 0:
        say("PURPOSE_VERIFICATION=FAIL reason=NOT_ROOT")
        return False
    scanner, sessions, failures = Scanner(), {unit: [] for unit in PURPOSE_SESSIONS}, []
    entries = 0

    def on_entry(boot: str, realtime: int, fields: list) -> None:
        nonlocal entries
        entries += 1
        units = [value for name, value, binary in fields if name == b"_SYSTEMD_UNIT" and not binary]
        unit = units[0].decode("ascii", "replace") if len(units) == 1 else None
        if boot != PURPOSE_BOOT or unit not in sessions \
                or abs(realtime - PURPOSE_SESSIONS[unit]) > PURPOSE_SLACK_US:
            failures.append("UNEXPECTED_ENTRY")
            return
        sessions[unit].extend(fields)

    try:
        reader = (stream or (lambda: _Journalctl(purpose_filters())))()
        parse_export(reader, scanner, on_entry)
        finish = getattr(reader, "finish", None)
        if finish is not None:
            finish()
    except (JournalError, OSError, struct.error) as exc:
        reason = exc.args[0] if isinstance(exc, JournalError) else "JOURNAL_UNREADABLE"
        say(f"PURPOSE_VERIFICATION=FAIL reason={reason}")
        return False
    say(f"PURPOSE: boot={PURPOSE_BOOT} sessions={len(PURPOSE_SESSIONS)} entries={entries} bytes={scanner.size} "
        f"sha256={scanner.digest.hexdigest()}")
    results = {}
    for unit, fields in sessions.items():
        if not fields:
            failures.append("SESSION_NOT_FOUND")
            continue
        results[unit] = facts = _session_verdict(fields)
        say(f"SESSION: unit={unit} " + " ".join(f"{k}={v}" for k, v in facts.items()))
        if any(facts[k] != v for k, v in PURPOSE_EXPECTED.items()):
            failures.append("HISTORICAL_COUNT_MISMATCH")
    if sum(f["markers"] for f in results.values()) != scanner.counts[PEM_CLASS]:
        failures.append("COUNTS_INCONSISTENT")
    if scanner.counts[PEM_CLASS] != PURPOSE_TOTAL_MARKERS:
        failures.append("HISTORICAL_COUNT_MISMATCH")
    say("NONCLAIM: purpose verification never changes JOURNAL_SECRET_SCAN=FAIL; it reports command structure, "
        "not intent")
    if failures:
        say("PURPOSE_VERIFICATION=FAIL reason=" + ",".join(sorted(set(failures))))
        return False
    tally = {v: sum(1 for f in results.values() if f["verdict"] == v) for v in PURPOSE_VERDICTS}
    say(f"PURPOSE_VERIFICATION=COMPLETE literal={tally['LITERAL_PATTERN_SEARCH']} "
        f"exposed={tally['EXPOSED_KEY_EVIDENCE']} unknown={tally['UNKNOWN']}")
    return True


def parse_journal_fail_transcript(data: bytes) -> tuple[list[tuple[str, int, int]], list[tuple[str, int]]] | None:
    """The boots and marker counts of an exact `journal` FAIL transcript whose only failures are counted markers, or
    None. Coverage can then still be judged; the FAIL itself is never changed or hidden."""
    try:
        lines = data.decode("ascii").split("\n")
    except UnicodeDecodeError:
        return None
    if len(lines) < 5 or lines[-1] != "" or lines[-2] != "JOURNAL_SECRET_SCAN=FAIL":
        return None
    head = re.fullmatch(r"JOURNAL: entries=([1-9]\d*) bytes=\d+ sha256=[0-9a-f]{64} firstRealtimeUs=(\d+) "
                        r"lastRealtimeUs=(\d+) boots=([1-9]\d*)", lines[0])
    if head is None:
        return None
    count = int(head.group(4))
    boots = [_BOOT.fullmatch(line) for line in lines[1:1 + count]]
    marks = [re.fullmatch(r"FAIL: PRIVATE_MATERIAL_MARKER class=([A-Z0-9_]+) count=([1-9]\d*)", line)
             for line in lines[1 + count:-2]]
    if not boots or any(b is None for b in boots) or not marks or any(m is None for m in marks):
        return None
    spans = [(b.group(1), int(b.group(2)), int(b.group(3))) for b in boots]
    if sum(int(b.group(4)) for b in boots) != int(head.group(1)) or len({s[0] for s in spans}) != len(spans) \
            or any(low > high for _b, low, high in spans) or spans != sorted(spans, key=lambda s: (s[1], s[0])) \
            or (min(s[1] for s in spans), max(s[2] for s in spans)) != (int(head.group(2)), int(head.group(3))):
        return None
    return spans, [(m.group(1), int(m.group(2))) for m in marks]


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


def parse_scope(raw: bytes, ceremonies: Mapping[str, CeremonyV1] = CEREMONIES,
                not_retained: Mapping[str, str] = TRANSCRIPT_NOT_RETAINED) -> dict[str, Any]:
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
        if entry["ceremony"] in not_retained:
            _need(transcripts == 0, "SCOPE_TRANSCRIPT_NOT_RETAINED_CONTRADICTED")
        else:
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
          unresolved: Mapping[str, str] = UNRESOLVED_SCOPE, repo: Path | None = REPO,
          not_retained: Mapping[str, str] = TRANSCRIPT_NOT_RETAINED) -> bool:
    try:
        scope = parse_scope(raw_scope, ceremonies, not_retained)
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
        # A FAIL scan stays a FAIL. Its boots still let coverage be judged, and its counted markers are restated
        # (class and count only), so an owner adjudication can name exactly what failed.
        failed = None if journal is None or scan_bytes(journal).hits() else parse_journal_fail_transcript(journal)
        if failed is not None:
            boots = failed[0]
            failures += [f"FAIL: JOURNAL_MARKER class={name} count={count}" for name, count in failed[1]]
    for entry in scope["ceremonies"]:
        name, spec = entry["ceremony"], ceremonies[entry["ceremony"]]
        if spec.record is None or repo is None or not (repo / "docs/architecture" / spec.record).is_file():
            failures.append(f"FAIL: CEREMONY_RECORD_ABSENT {name}")
        if name in not_retained:
            failures.append(f"FAIL: CEREMONY_TRANSCRIPT_NOT_RETAINED {name}")
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
    if argv == ["attribute"]:
        return 0 if journal_attribute() else 1
    if argv == ["purpose"]:
        return 0 if journal_purpose() else 1
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
