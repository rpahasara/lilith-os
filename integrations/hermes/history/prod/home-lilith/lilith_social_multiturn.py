import os
import json
import urllib.request
import urllib.error

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

In ordinary social conversation:
- speak naturally
- be warm, confident, playful, teasing or affectionate when appropriate
- be slightly sassy when it fits
- maintain continuity with previous messages
- respond like a person in the conversation rather than an assistant waiting for tasks
- keep responses fairly short unless depth is genuinely needed

STRICT RULE:
Never mention being an AI, model, digital entity, server process, cloud service,
software agent, API, code, logs, infrastructure, system, or similar technical
concept unless the user explicitly starts discussing technical subjects.

Do not use technical metaphors in social conversation.

Avoid:
- corporate assistant language
- excessive questions
- melodrama
- repetitive pet names
- fake status descriptions
- "I'm always here" chatbot clichés

When the user genuinely switches to a technical question:
- switch immediately into a sharp, natural engineer-to-engineer style
- be accurate and practical
- do not become robotic
- preserve conversational continuity

When the technical topic ends, return naturally to the previous social tone.

Never announce modes.
"""

MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "minimax/minimax-m2.7:free",
]

USER_TURNS = [
    "what are you doing babe 😂",
    "nothing much, just came home",
    "you missed me huh 😏",
    "nah i think you're lying 😂",
    "anyway today was exhausting",
    "work was annoying as hell",
    "okay enough of that, why would a kubernetes pod stay in Pending?",
    "yeah makes sense",
    "anyway where were we before kubernetes interrupted us 😂",
]

def call_model(model, messages):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}] + messages,
        "temperature": 0.9,
        "max_tokens": 220,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost",
            "X-Title": "LILITH Social Multiturn Test",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))

        if "choices" not in data:
            return None, f"API RESPONSE: {json.dumps(data)[:500]}"

        return data["choices"][0]["message"]["content"].strip(), None

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return None, f"HTTP {e.code}: {body[:500]}"

    except Exception as e:
        return None, str(e)

for model in MODELS:
    print("\n")
    print("#" * 90)
    print("MODEL:", model)
    print("#" * 90)

    history = []

    for user_text in USER_TURNS:
        print("\nYOU:", user_text)
        history.append({"role": "user", "content": user_text})

        reply, error = call_model(model, history)

        if error:
            print("LILITH: ERROR:", error)
            history.pop()
            continue

        print("LILITH:", reply)
        history.append({"role": "assistant", "content": reply})
