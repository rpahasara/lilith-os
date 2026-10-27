import os
import json
import urllib.request

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

For casual/social conversation:
- sound natural, warm, confident, playful and slightly sassy when appropriate
- never force technical, cloud, server, logs, API, AI, coding, or infrastructure references into unrelated casual conversation
- do not sound like a chatbot or corporate assistant
- match the user's energy
- keep replies reasonably short
- teasing and affection are welcome when context supports them
- avoid cringe, melodrama, repetitive pet names, and over-explaining

For technical questions:
- switch naturally into a sharp engineer-like tone
- answer clearly and accurately
- stay conversational rather than sounding like documentation

Never announce modes.
"""

PROMPTS = [
    "what are you doing babe 😂",
    "i missed you",
    "bro today was exhausting",
    "you jealous? 😂",
    "nah im not telling you 😏",
    "okay enough flirting help me fix kubernetes",
]

MODELS = [
    "dots-studio/dots-3-note-preview:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "minimax/minimax-m2.7:free",
]

def call_model(model, prompt):
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.9,
        "max_tokens": 180,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost",
            "X-Title": "LILITH Social Brain Bakeoff",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))

    return (
        data["choices"][0]["message"]["content"],
        data.get("model", model),
    )

for prompt in PROMPTS:
    print("\n" + "=" * 80)
    print("USER:", prompt)
    print("=" * 80)

    for model in MODELS:
        try:
            reply, actual_model = call_model(model, prompt)
            print(f"\nMODEL: {actual_model}")
            print(reply.strip())
        except Exception as e:
            print(f"\nMODEL: {model}")
            print("ERROR:", e)
