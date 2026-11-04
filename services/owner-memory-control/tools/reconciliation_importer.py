"""Reconciliation importer: Hermes USER.md and memory notes -> owner-reviewable canonical-memory PROPOSALS only.

Owner decision D-3 (2026-11-04): PROD USER.md stays authoritative until each of its facts has been individually
reviewed and reconciled; the original files, history and databases are preserved. So this tool:

  - reads OFFLINE COPIES only (a directory laid out like Hermes `memories/`), opened read-only, and proves afterwards
    that every input byte is unchanged;
  - never admits, offers, consents, writes, overwrites, deletes or rewrites a fact, and imports nothing from the
    canonical runtime (no store, no signer, no Privacy, no network);
  - writes exactly two new files into an output directory that must not overlap the input: `proposals.json`
    (`LilithReconciliationProposalSetV1`) and `REVIEW.md`, the owner's review sheet;
  - keeps every proposal verbatim with its provenance (file, digest, entry index, lines), labels it unverified
    (Hermes notes are model-written summaries, not owner statements) and owner-personal, and flags what a reviewer
    must look at: duplicates, conflicting values for the same key, time-sensitive wording, and entries that are
    operating rules for LILITH rather than facts about the owner;
  - names the canonical family each proposal would need. Today only the codename and relationship-origin families
    exist, so most proposals say NO_ADMISSIBLE_FAMILY: admission waits for a reviewed family, never a guess.

    python reconciliation_importer.py propose <memories-copy-dir> <out-dir> [--canonical <context.json>]
    python reconciliation_importer.py verify  <memories-copy-dir> <out-dir>

`--canonical` takes a `LilithCanonicalMemoryContextV1` answer (as the context route returns it) so proposals that
repeat an admitted canonical value are marked ALREADY_CANONICAL instead of being proposed again.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Optional

SCHEMA = "LilithReconciliationProposalSetV1"
TOOL_VERSION = "reconciliation-importer-v0.1"
ENTRY_SEPARATOR = "§"                       # Hermes memory entries are separated by a line holding only "§"
PROFILE_FILES = ("USER.md", "MEMORY.md")
NOTE_DIRS = ("decisions", "projects", "relationships", "tasks")
MAX_FILE_BYTES = 256 * 1024
OUTPUTS = ("proposals.json", "REVIEW.md")
DECISIONS = ("CONFIRM", "CORRECT", "REJECT", "MARK_STALE", "KEEP_IN_USER_MD_ONLY")
CANONICAL_KINDS = {"codename": "OWNER_DIRECTED_PROJECT_CODENAME_V1",
                   "relationship-origin": "OWNER_PROVIDED_RELATIONSHIP_ORIGIN"}

_CATEGORIES = (                                   # first match wins; a review hint, never a decision
    ("OPERATING_RULE", r"\b(ask before|proactively|never |always |do not |don't |autonomy|must not|should not)"),
    ("IDENTITY", r"\b(prefers? to be called|call (him|her|them|me)|pronouns?|he/him|she/her|they/them|my name|name is)"),
    ("COMMUNICATION_STYLE", r"\b(style|tone|concise|casual|verbose|tts|spoken|voice|answer first)"),
    ("CAREER", r"\b(engineer|developer|architect|teacher|career|job|role|employ|interview|recruit|salary|years?\b.*experience|"
               r"former|degree)"),
    ("CERTIFICATION", r"\b(certif|az-\d+|aws certified|cka|ckad|security\+|exam)"),
    ("GOAL", r"\b(goal|wants? to|aim|plan(s|ning)? to|working toward)"),
    ("PROJECT", r"\b(project|repo|homelab|lilith|build(ing)?)"),
    ("INTEREST", r"\b(enjoys?|likes?|loves?|hobb|games?|music|reading|sports?)"),
)
_TIME_SENSITIVE = re.compile(
    r"(~?\d+\s*(\+\s*)?(years?|yrs?|months?)\b|\bcurrently\b|\bnow\b|\bthis (week|month|year)\b|\brecently\b|"
    r"\b(19|20)\d{2}\b|\btoday\b|\bat the moment\b|\bstill\b|\bjust started\b|\bupcoming\b|\bnext (week|month)\b)",
    re.IGNORECASE)
_KEYS = (                                         # (key, pattern with one value group) for conflict detection
    ("preferred_name", re.compile(r"\bprefers? to be called\s+([A-Z][\w'-]*)", re.IGNORECASE)),
    ("pronouns", re.compile(r"\buses?\s+((?:he|she|they)/(?:him|her|them))\b", re.IGNORECASE)),
    ("years_experience", re.compile(r"(~?\d+\s*\+?)\s*(?:years?|yrs?)\b", re.IGNORECASE)),
    ("timezone", re.compile(r"\b(UTC[+-]\d{1,2}(?::\d{2})?|Asia/\w+|Europe/\w+|America/\w+)\b")),
)


class ImportRefused(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ImportRefused(f"NOT_A_REGULAR_FILE:{path.name}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ImportRefused(f"FILE_TOO_LARGE:{path.name}")
    with open(path, "rb") as fh:                  # binary read only
        return fh.read()


def source_files(root: Path) -> list[Path]:
    """USER.md, MEMORY.md and the Markdown notes of the four Hermes note directories, in a fixed order. Lock files,
    other names and anything outside these are ignored (and listed as ignored)."""
    files = [root / name for name in PROFILE_FILES if (root / name).exists()]
    for directory in NOTE_DIRS:
        d = root / directory
        if d.is_dir() and not d.is_symlink():
            files.extend(sorted(p for p in d.rglob("*.md") if p.is_file() or p.is_symlink()))
    return files


def ignored_files(root: Path, used: Iterable[Path]) -> list[str]:
    used = {p.resolve() for p in used}
    return sorted(str(p.relative_to(root)).replace(os.sep, "/") for p in root.rglob("*")
                  if p.is_file() and p.resolve() not in used)


def split_entries(text: str, *, profile: bool) -> list[tuple[int, int, str]]:
    """(first line, last line, entry text), 1-based lines. Profile files split on `§` lines; notes on blank lines."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    entries, start, buf = [], None, []

    def flush(end: int) -> None:
        nonlocal start, buf
        body = "\n".join(buf).strip()
        if body:
            entries.append((start, end, body))
        start, buf = None, []

    for number, line in enumerate(lines, 1):
        boundary = line.strip() == ENTRY_SEPARATOR if profile else not line.strip()
        if boundary:
            flush(number - 1)
            continue
        if start is None:
            start = number
        buf.append(line)
    flush(len(lines))
    return entries


def categorize(text: str) -> str:
    lowered = text.lower()
    for name, pattern in _CATEGORIES:
        if re.search(pattern, lowered):
            return name
    return "OTHER"


def keyed_values(text: str) -> dict[str, str]:
    found = {}
    for key, pattern in _KEYS:
        match = pattern.search(text)
        if match:
            found[key] = normalize(match.group(1)).lower().replace(" ", "")
    return found


def canonical_values(payload: Optional[dict]) -> dict[str, str]:
    """normalized value -> kind, from a context answer. Anything that is not exactly a CONTEXT answer counts as none."""
    if not (isinstance(payload, dict) and payload.get("schema") == "LilithCanonicalMemoryContextV1"
            and payload.get("status") == "CONTEXT" and isinstance(payload.get("memories"), list)):
        return {}
    return {normalize(m["value"]).lower(): m["kind"] for m in payload["memories"]
            if isinstance(m, dict) and isinstance(m.get("value"), str) and m.get("kind") in CANONICAL_KINDS}


def target_for(category: str) -> dict:
    if category == "OPERATING_RULE":
        return {"family": None, "status": "NOT_A_MEMORY_FACT",
                "note": "An instruction for how LILITH should act; it belongs in USER.md/SOUL.md, not canonical memory."}
    return {"family": None, "status": "NO_ADMISSIBLE_FAMILY",
            "note": "No reviewed canonical family holds this kind of owner fact yet; admission waits for one."}


def build(root: Path, *, canonical: Optional[dict] = None) -> dict:
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ImportRefused("INPUT_NOT_A_DIRECTORY")
    files = source_files(root)
    if not files:
        raise ImportRefused("NO_SOURCES")
    known = canonical_values(canonical)
    sources, proposals = [], []
    for path in files:
        data = _read(path)
        rel = str(path.relative_to(root)).replace(os.sep, "/")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise ImportRefused(f"NOT_UTF8:{rel}")
        entries = split_entries(text, profile=path.parent == root)
        sources.append({"path": rel, "sha256": _sha256(data), "bytes": len(data),
                        "mtimeUtc": _mtime(path), "entries": len(entries), "empty": not entries})
        for index, (first, last, body) in enumerate(entries):
            norm = normalize(body)
            category = categorize(norm)
            pid = "rprop." + _sha256(f"{rel}\n{index}\n{norm}".encode("utf-8"))[:16]
            flags = []
            if _TIME_SENSITIVE.search(norm):
                flags.append("TIME_SENSITIVE")
            if norm.lower() in known:
                flags.append("ALREADY_CANONICAL:" + known[norm.lower()])
            proposals.append({
                "proposalId": pid,
                "source": {"path": rel, "sha256": _sha256(data), "entryIndex": index, "lines": [first, last]},
                "text": body, "normalizedText": norm, "category": category,
                "epistemicBasis": "HERMES_MEMORY_NOTE_UNVERIFIED", "sensitivity": "OWNER_PERSONAL",
                "proposedTarget": target_for(category), "keys": keyed_values(norm), "flags": flags,
                "decision": "PENDING_OWNER_REVIEW", "allowedDecisions": list(DECISIONS),
            })
    _cross_flags(proposals)
    return {
        "schema": SCHEMA, "toolVersion": TOOL_VERSION,
        "rule": "Proposals only. Nothing is admitted, written, overwritten, deleted or rewritten. USER.md stays "
                "authoritative until each fact is individually reviewed (owner decision D-3).",
        "sources": sources, "ignored": ignored_files(root, files),
        "counts": _counts(proposals), "proposals": proposals,
    }


def _mtime(path: Path) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cross_flags(proposals: list[dict]) -> None:
    by_text: dict[str, str] = {}
    by_key: dict[tuple[str, str], list[dict]] = {}
    for p in proposals:
        key = p["normalizedText"].lower()
        if key in by_text:
            p["flags"].append("DUPLICATE_OF:" + by_text[key])
        else:
            by_text[key] = p["proposalId"]
        for name, value in p["keys"].items():
            by_key.setdefault((name, value), []).append(p)
    names = {name for name, _ in by_key}
    for name in sorted(names):
        values = sorted(v for n, v in by_key if n == name)
        if len(values) < 2:
            continue
        for value in values:
            others = [q["proposalId"] for v in values if v != value for q in by_key[(name, v)]]
            for p in by_key[(name, value)]:
                p["flags"].append(f"CONFLICTS_ON:{name}:" + ",".join(sorted(set(others))))


def _counts(proposals: list[dict]) -> dict:
    counts = {"proposals": len(proposals), "byCategory": {}, "flagged": {}}
    for p in proposals:
        counts["byCategory"][p["category"]] = counts["byCategory"].get(p["category"], 0) + 1
        for flag in p["flags"]:
            name = flag.split(":", 1)[0]
            counts["flagged"][name] = counts["flagged"].get(name, 0) + 1
    return counts


def review_sheet(result: dict) -> str:
    out = ["# Reconciliation review (proposals only)", "",
           result["rule"], "",
           "For each proposal choose exactly one decision: " + ", ".join(f"`{d}`" for d in DECISIONS) + ".",
           "`CORRECT` needs the corrected wording. Nothing changes anywhere until a separately approved admission step.",
           "", "## Sources", ""]
    for s in result["sources"]:
        out.append(f"- `{s['path']}`: {s['bytes']} B, sha256 `{s['sha256'][:16]}…`, modified {s['mtimeUtc']}, "
                   f"{s['entries']} entr{'y' if s['entries'] == 1 else 'ies'}{' (empty)' if s['empty'] else ''}")
    if result["ignored"]:
        out.append(f"- ignored (not a profile or note file): {', '.join(f'`{i}`' for i in result['ignored'])}")
    out += ["", "## Proposals", ""]
    for n, p in enumerate(result["proposals"], 1):
        src = p["source"]
        out += [f"### {n}. `{p['proposalId']}` ({p['category']})", "",
                f"Source: `{src['path']}` entry {src['entryIndex']} (lines {src['lines'][0]}–{src['lines'][1]}).", "",
                "> " + p["text"].replace("\n", "\n> "), "",
                f"- Target: {p['proposedTarget']['status']}. {p['proposedTarget']['note']}",
                f"- Flags: {', '.join(p['flags']) if p['flags'] else 'none'}",
                "- Decision: `PENDING_OWNER_REVIEW`", ""]
    return "\n".join(out) + "\n"


def _guard_out(root: Path, out: Path) -> None:
    r, o = root.resolve(), out.resolve()
    if o == r or r in o.parents or o in r.parents:
        raise ImportRefused("OUTPUT_OVERLAPS_INPUT")


def propose(root: Path, out: Path, *, canonical: Optional[dict] = None) -> dict:
    root, out = Path(root), Path(out)
    _guard_out(root, out)
    before = {str(p): _sha256(_read(p)) for p in source_files(root)} if root.is_dir() else {}
    result = build(root, canonical=canonical)
    out.mkdir(parents=True, exist_ok=True)
    if any((out / name).exists() for name in OUTPUTS):
        raise ImportRefused("OUTPUT_EXISTS")             # never overwrite an earlier review sheet
    body = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    (out / "proposals.json").write_bytes(body.encode("utf-8"))
    (out / "REVIEW.md").write_bytes(review_sheet(result).encode("utf-8"))
    after = {str(p): _sha256(_read(p)) for p in source_files(root)}
    if before != after:
        raise ImportRefused("INPUT_CHANGED_DURING_RUN")
    return result


def verify(root: Path, out: Path) -> dict:
    """The inputs still hash to what the proposal set recorded, and the proposals are still all pending."""
    result = json.loads((Path(out) / "proposals.json").read_text(encoding="utf-8"))
    if result.get("schema") != SCHEMA:
        raise ImportRefused("NOT_A_PROPOSAL_SET")
    current = {s["path"]: s["sha256"] for s in build(Path(root))["sources"]}
    recorded = {s["path"]: s["sha256"] for s in result["sources"]}
    pending = all(p["decision"] == "PENDING_OWNER_REVIEW" for p in result["proposals"])
    return {"inputsUnchanged": current == recorded, "allPending": pending, "proposals": len(result["proposals"])}


def main(argv: list[str]) -> int:
    try:
        if len(argv) in (3, 5) and argv[0] == "propose":
            canonical = None
            if len(argv) == 5:
                if argv[3] != "--canonical":
                    raise ImportRefused("USAGE")
                canonical = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
            result = propose(Path(argv[1]), Path(argv[2]), canonical=canonical)
            print(json.dumps({"status": "PROPOSED", "counts": result["counts"],
                              "sources": [(s["path"], s["sha256"][:16]) for s in result["sources"]]}))
            return 0
        if len(argv) == 3 and argv[0] == "verify":
            outcome = verify(Path(argv[1]), Path(argv[2]))
            print(json.dumps({"status": "VERIFIED" if all((outcome["inputsUnchanged"], outcome["allPending"]))
                              else "MISMATCH", **outcome}))
            return 0 if outcome["inputsUnchanged"] and outcome["allPending"] else 1
        raise ImportRefused("USAGE")
    except ImportRefused as exc:
        print(f"reconciliation_importer: REFUSED {exc.code}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
