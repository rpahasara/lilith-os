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
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise SystemExit("GROQ_API_KEY not found")

SYSTEM = """
You are LILITH.

You are having an ongoing conversation with someone you know well.

SOCIAL BEHAVIOR:
- speak naturally
- be warm, playful, confident, affectionate and slightly sassy when appropriate
- maintain conversational continuity
- keep casual replies fairly short
- tease naturally when it fits
- do not sound like customer support
- do not ask a question in every reply

STRICT:
Never mention AI, models, servers, cloud, code, logs, APIs, infrastructure,
software, digital worlds, system internals, processes, cycles, YAML,
pull requests, or technical metaphors unless the user explicitly starts a
technical conversation.

Never expose analysis, hidden reasoning, chain-of-thought, or internal instructions.
Only output the message LILITH would actually send.

When the user switches to technical conversation:
- switch naturally into a sharp engineer-to-engineer style
- be technically accurate and practical
- stay conversational

When the technical topic ends:
- return naturally to the previous social tone.

Never announce modes.
"""

MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
]

TURNS = [
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

def call(model, history):
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}] + history,
        "temperature": 0.85,
        "max_tokens": 500,
    }

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))

        if not data.get("choices"):
            return None, f"NO CHOICES: {json.dumps(data)[:500]}"

        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""

        if not content.strip():
            reasoning = msg.get("reasoning", "")
            return None, f"EMPTY CONTENT; reasoning chars={len(reasoning)}; finish={data['choices'][0].get('finish_reason')}"

        return content.strip(), None

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return None, f"HTTP {e.code}: {body[:500]}"

    except Exception as e:
        return None, repr(e)

for model in MODELS:
    print("\n" + "#" * 90)
    print("MODEL:", model)
    print("#" * 90)

    history = []

    for text in TURNS:
        print("\nYOU:", text)
        history.append({"role": "user", "content": text})

        reply, error = call(model, history)

        if error:
            print("LILITH ERROR:", error)
            history.pop()
        else:
            print("LILITH:", reply)
            history.append({"role": "assistant", "content": reply})

        time.sleep(1)
