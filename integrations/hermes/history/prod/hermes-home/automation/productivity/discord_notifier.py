#!/usr/bin/env python3

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


ENV_PATH = Path.home() / ".hermes" / ".env"


def load_env(path: Path) -> dict:
    values = {}

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        values[key.strip()] = value

    return values


def get_discord_config():
    env = load_env(ENV_PATH)

    token = env.get("DISCORD_BOT_TOKEN", "").strip()
    channel = env.get("DISCORD_HOME_CHANNEL", "").strip()

    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is missing")

    if not channel:
        raise RuntimeError("DISCORD_HOME_CHANNEL is missing")

    return token, channel


def send_discord(message: str):
    token, channel = get_discord_config()

    url = f"https://discord.com/api/v10/channels/{channel}/messages"

    body = json.dumps({
        "content": message[:1900],
        "allowed_mentions": {"parse": []}
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "LILITH-Productivity/1.0"
        }
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status not in (200, 201):
                raise RuntimeError(
                    f"Discord returned HTTP {response.status}"
                )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Discord HTTP {exc.code}: {detail[:300]}"
        ) from exc


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        _, channel = get_discord_config()
        print("DISCORD CONFIG OK")
        print("Home channel configured:", bool(channel))
        return 0

    if len(sys.argv) == 2 and sys.argv[1] == "--test":
        send_discord(
            "😈 **LILITH Productivity v2**\n"
            "Discord urgent-alert channel test successful."
        )
        print("DISCORD TEST SENT")
        return 0

    if len(sys.argv) < 2:
        print("Usage:")
        print("  discord_notifier.py --check")
        print("  discord_notifier.py --test")
        print("  discord_notifier.py 'message'")
        return 1

    send_discord(sys.argv[1])
    print("DISCORD MESSAGE SENT")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
