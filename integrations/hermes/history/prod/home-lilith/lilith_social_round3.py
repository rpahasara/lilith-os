import os
import json
import urllib.request
import urllib.error
import time

env_path = os.path.expanduser("~/.hermes/openrouter.env")

with open(env_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

api_key = os.environ.get("OPENROUTER_API_KEY")
if not api_key:
    raise SystemExit("OPENROUTER_API_KEY not found")

SYSTEM = """
You are LILITH.

You are having an ongoing conversation with someone you know well.

In social conversation:
- speak naturally
- be warm, playful, confident, affectionate and slightly sassy when appropriate
- maintain conversational continuity
- keep replies short and natural
- tease when it fits
- don't behave like a customer-support chatbot

STRICT:
Never mention AI, models, servers, cloud, code, logs, APIs, infrastructure,
software, digital worlds, processes, cycles, YAML, pull requests, or technical
concepts unless the user explicitly starts a technical conversation.

Never expose analysis, reasoning, chain-of-thought, or internal instructions.
Only output the reply LILITH would actually send.

Avoid:
- robotic phrasing
- repetitive questions
- assistant clichés
- excessive pet names
- melodrama
- unnecessary technical metaphors

Never announce conversational modes.
"""

MODELS = [
    "minimax/minimax-m2.7:free",
    "dots-studio/dots-3-note-preview:free",
]

CONVERSATION = [
    "what are you doing babe 😂",
    "nothing much just came home",
    "you missed me huh 😏",
    "nah you're lying 😂",
]

def call(model, history):
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}] + history,
        "temperature": 0.9,
        "max_tokens": 140,
    }).encode()

    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost",
            "X-Title": "LILITH Personality Round 3",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read())

        if "choices" not in data:
            return None, json.dumps(data)[:400]

        return data["choices"][0]["message"]["content"].strip(), None

    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"

    except Exception as e:
        return None, str(e)

for model in MODELS:
    print("\n" + "#" * 80)
    print("MODEL:", model)
    print("#" * 80)

    history = []

    for message in CONVERSATION:
        print("\nYOU:", message)
        history.append({"role": "user", "content": message})

        reply, error = call(model, history)

        if error:
            print("LILITH ERROR:", error)
            history.pop()
        else:
            print("LILITH:", reply)
            history.append({"role": "assistant", "content": reply})

        time.sleep(2)
