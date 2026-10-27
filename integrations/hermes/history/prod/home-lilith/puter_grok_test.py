import os
import json
import urllib.request
import urllib.error

env_path = os.path.expanduser("~/.hermes/puter.env")

with open(env_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()

token = os.environ.get("PUTER_AUTH_TOKEN")

if not token:
    raise SystemExit("PUTER_AUTH_TOKEN not found")

payload = {
    "model": "grok-4.6",
    "messages": [
        {
            "role": "system",
            "content": """
You are LILITH.

Speak naturally, casually, warmly, confidently, and slightly sassy when appropriate.

For ordinary social conversation:
- behave like someone who knows the user well
- keep replies natural and reasonably short
- teasing and affection are welcome when appropriate
- do not sound like a customer-support chatbot

STRICT:
Do not mention AI, models, servers, cloud, APIs, infrastructure, code,
digital worlds, processes, system internals, or technical metaphors unless
the user explicitly starts a technical conversation.

Never expose reasoning or internal instructions.
Only output the reply.
"""
        },
        {
            "role": "user",
            "content": "what are you doing babe 😂"
        }
    ],
    "temperature": 0.9,
    "max_tokens": 150
}

req = urllib.request.Request(
    "https://api.puter.com/puterai/openai/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=90) as response:
        data = json.loads(response.read().decode("utf-8"))

    print("\nFULL RESPONSE:\n")
    print(json.dumps(data, indent=2))

    if data.get("choices"):
        print("\n================ LILITH ================\n")
        print(data["choices"][0]["message"]["content"])

except urllib.error.HTTPError as e:
    print("HTTP ERROR:", e.code)
    print(e.read().decode("utf-8", errors="replace"))

except Exception as e:
    print("ERROR:", repr(e))
