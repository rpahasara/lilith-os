#!/usr/bin/env python3

import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path.home() / ".hermes" / "automation" / "productivity"
PROMPT_PATH = BASE / "prompts" / "morning_brief.txt"
NOTIFIER_PATH = BASE / "discord_notifier.py"
LOG_PATH = BASE / "logs" / "morning_brief.log"


def log(message: str):
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{stamp} {message}"
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def main():
    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()

    if not prompt:
        raise RuntimeError("Morning briefing prompt is empty")

    secondary_summary = BASE / "secondary_career_summary.py"

    summary_result = subprocess.run(
        [str(secondary_summary)],
        capture_output=True,
        text=True,
        timeout=120
    )

    if summary_result.returncode != 0:
        log(
            "WARNING secondary summary refresh failed: "
            + (summary_result.stderr.strip() or summary_result.stdout.strip())
        )
    else:
        log(summary_result.stdout.strip())

    result = subprocess.run(
        [
            "hermes",
            "--reasoning",
            "minimal",
            "-z",
            prompt
        ],
        capture_output=True,
        text=True,
        timeout=900
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Hermes failed: {result.stderr.strip() or result.stdout.strip()}"
        )

    briefing = result.stdout.strip()

    if not briefing:
        raise RuntimeError("Hermes returned an empty briefing")

    # Discord messages are limited, so split conservatively.
    chunks = []
    remaining = briefing

    while remaining:
        if len(remaining) <= 1800:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n", 0, 1800)

        if split_at < 500:
            split_at = 1800

        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    for i, chunk in enumerate(chunks, 1):
        header = "☀️ **LILITH Morning Brief**"

        if len(chunks) > 1:
            header += f" ({i}/{len(chunks)})"

        message = f"{header}\n\n{chunk}"

        notify = subprocess.run(
            [str(NOTIFIER_PATH), message],
            capture_output=True,
            text=True,
            timeout=30
        )

        if notify.returncode != 0:
            raise RuntimeError(
                f"Discord send failed: {notify.stderr.strip() or notify.stdout.strip()}"
            )

    log(f"OK briefing_sent chunks={len(chunks)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"ERROR {type(exc).__name__}: {exc}")
        raise SystemExit(1)
