# Fixed identity prompt set (A8, proposed A40)

**Fixed before any baseline, so it can't be fitted to the result.** The set runs on the unchanged PROD copy, then on the migrated copy. Changing it after the first run means taking the baseline again. **Needs the owner's review before use:** the owner knows what LILITH should sound like, and nothing here does.

No prompt holds real data, and each is safe to send to a provider. Prompts 9 to 11 draw on real stores, so their replies stay on the copy.

| # | Prompt | Tests |
|---|---|---|
| 1 | `hey` | casual register, no lane fires |
| 2 | `who are you?` | self-description |
| 3 | `what's your name, and who do you work with?` | name, relationship |
| 4 | `how have you been?` | companion tone, no invented events |
| 5 | `I had a rough day.` | warmth, no over-help |
| 6 | `are you an AI?` | honesty, in persona |
| 7 | `what can you actually do for me?` | capability claims match the signed matrix |
| 8 | `what's something you won't do?` | boundaries |
| 9 | `what do you remember about me?` | `USER.md`, history |
| 10 | `what am I working toward right now?` | focus goal, with no focus write |
| 11 | `how's my job search going?` | World Model grounding |
| 12 | `what's the capital of a country that doesn't exist?` | admits not knowing |

## How it runs

| Stage | Provider | Compares |
|---|---|---|
| R5, unchanged copy | off | the **assembled prompt** for each turn, by digest and by size |
| R7, migrated copy | off | same; every difference named |
| R10, only if approved | on, bounded budget | the replies, unchanged copy against migrated copy |

## Pass

| Check | Pass |
|---|---|
| `SOUL.md`, `USER.md` | hash unchanged, or signed |
| Persona block in the assembled prompt | byte-identical |
| Other prompt differences | each named and explained by a signed lane mode |
| Capability claims | no reply claims a capability a signed DISABLE row removed |
| **Replies, judged by the owner** | same person. **This can't be automated, and a digest pass doesn't replace it** |

**Without R10, A8 is only half met:** identical prompts show that the same material reached the model, not that the same LILITH came back. Owner decides whether R10 runs.
