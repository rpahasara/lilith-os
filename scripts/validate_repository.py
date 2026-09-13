#!/usr/bin/env python3
"""Validate the documentation-first LILITH repository without dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "docs/README.md",
    "docs/glossary.md",
    "docs/architecture/README.md",
    "docs/architecture/as-is.md",
    "docs/architecture/target.md",
    "docs/architecture/runtime-boundary.md",
    "docs/research/research-question-register.md",
    "docs/research/method.md",
    "docs/adr/README.md",
    "docs/adr/0000-template.md",
    "docs/roadmap/roadmap.md",
    "docs/security/threat-model.md",
    "docs/security/trust-boundaries.md",
    "docs/engineering/development.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/ci.yml",
    ".github/workflows/deploy.yml.example",
)

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
RQ_ROW = re.compile(r"^\|\s*(RQ-\d{3})\s*\|", re.MULTILINE)
ADR_NAME = re.compile(r"^\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
ADR_STATUS = re.compile(
    r"^- \*\*Status:\*\* (Proposed|Accepted|Rejected|Deprecated|Superseded by ADR-\d{4})$",
    re.MULTILINE,
)


def markdown_files() -> list[Path]:
    ignored = {".git", "node_modules", ".venv"}
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(part in ignored for part in path.parts)
    )


def validate_required(errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")


def validate_markdown(errors: list[str], warnings: list[str]) -> None:
    for path in markdown_files():
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"empty Markdown file: {relative}")
            continue
        if not text.endswith("\n"):
            errors.append(f"missing final newline: {relative}")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.endswith((" ", "\t")):
                errors.append(f"trailing whitespace: {relative}:{line_number}")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_path = unquote(target.split("#", 1)[0])
            if not target_path:
                continue
            resolved = (path.parent / target_path).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"link escapes repository: {relative} -> {target}")
                continue
            if not resolved.exists():
                errors.append(f"broken local link: {relative} -> {target}")
        if "OWNER/REPOSITORY" in text:
            warnings.append(f"publishing placeholder remains in {relative}")


def validate_research_register(errors: list[str]) -> None:
    path = ROOT / "docs/research/research-question-register.md"
    if not path.exists():
        return
    ids = RQ_ROW.findall(path.read_text(encoding="utf-8"))
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"duplicate research rows: {', '.join(duplicates)}")
    if len(ids) < 25:
        errors.append(f"research register has only {len(ids)} indexed questions; expected at least 25")
    expected = [f"RQ-{number:03d}" for number in range(1, len(ids) + 1)]
    if ids != expected:
        errors.append("research question rows must be unique and sequential from RQ-001")


def validate_adrs(errors: list[str]) -> None:
    adr_directory = ROOT / "docs/adr"
    for path in sorted(adr_directory.glob("*.md")):
        if path.name in {"README.md", "0000-template.md"}:
            continue
        if not ADR_NAME.fullmatch(path.name):
            errors.append(f"invalid ADR filename: {path.relative_to(ROOT).as_posix()}")
        text = path.read_text(encoding="utf-8")
        if not ADR_STATUS.search(text):
            errors.append(f"missing or invalid ADR status: {path.relative_to(ROOT).as_posix()}")


def validate_repository_invariants(errors: list[str]) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required_phrases = (
    "Hermes is not LILITH",
    "Production is a deployment target, not a development environment",
    "Execution is not success",
    )
    for phrase in required_phrases:
        if phrase not in readme:
            errors.append(f"README is missing repository invariant: {phrase!r}")

    active_deployments = [
        path
        for path in (ROOT / ".github/workflows").glob("deploy.y*ml")
        if path.suffix in {".yml", ".yaml"}
    ]
    if active_deployments:
        names = ", ".join(path.name for path in active_deployments)
        errors.append(f"deployment must remain inactive until its ADR is accepted: {names}")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    validate_required(errors)
    validate_markdown(errors, warnings)
    validate_research_register(errors)
    validate_adrs(errors)
    validate_repository_invariants(errors)

    for warning in sorted(set(warnings)):
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"Repository validation failed with {len(errors)} error(s).")
        return 1

    register = (ROOT / "docs/research/research-question-register.md").read_text(
        encoding="utf-8"
    )
    rq_count = len(RQ_ROW.findall(register))
    adr_count = len(
        [
            path
            for path in (ROOT / "docs/adr").glob("*.md")
            if path.name not in {"README.md", "0000-template.md"}
        ]
    )
    print(
        f"Repository validation passed: {len(markdown_files())} Markdown files, "
        f"{rq_count} research questions, and {adr_count} decision ADRs."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
