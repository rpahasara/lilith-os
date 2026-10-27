import os
import json
import urllib.request
import urllib.error
import time

env_path = os.path.expanduser("~/.hermes/groq.env")

with open(env_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()

api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise SystemExit("GROQ_API_KEY not found")

SYSTEM = """
You are LILITH.

You are having an ongoing conversation with someone you know well.

In social conversation:
- speak naturally
- be warm, playful, confident, affectionate and slightly sassy when appropriate
- maintain conversational continuity
- keep replies short and natural
- tease when it fits
- do not sound like customer support

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

When the user switches to a technical topic:
- switch immediately into a sharp, natural engineer-to-engineer style
- be accurate and practical
- do not become robotic

When the technical topic ends:
- return naturally to the previous social tone

Never announce modes.
"""

MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
]

USER_TURNS = [
    "what are you doing babe 😂",
    "nothing much just came home",
    "you missed me huh 😏",
    "nah you're lying 😂",
    "anyway today was exhausting",
    "work was annoying as hell",
    "okay enough of that, why would a kubernetes pod stay in Pending?",
    "yeah makes sense",
    "anyway where were we before kubernetes interrupted us 😂",
]

def call_model(model, history):
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}] + history,
        "temperature": 0.9,
        "max_tokens": 220,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))

        if "choices" not in data:
            return None, json.dumps(data)[:500]

        content = data["choices"][0]["message"].get("content")
        if not content:
            return None, "Empty response"

        return content.strip(), None

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return None, f"HTTP {e.code}: {body[:500]}"

    except Exception as e:
        return None, str(e)

for model in MODELS:
    print("\n" + "#" * 90)
    print("MODEL:", model)
    print("#" * 90)

    history = []

    for user_text in USER_TURNS:
        print("\nYOU:", user_text)
        history.append({"role": "user", "content": user_text})

        reply, error = call_model(model, history)

        if error:
            print("LILITH ERROR:", error)
            history.pop()
        else:
            print("LILITH:", reply)
            history.append({"role": "assistant", "content": reply})

        time.sleep(1)
