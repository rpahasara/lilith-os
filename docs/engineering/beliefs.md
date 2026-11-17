# Memory → Beliefs (P1-9 PR A)

The World Model moved from the orphaned `/world` to **Memory → Beliefs** at `/memory/beliefs`. It's the
fourth Memory lens after Brain, Archive and Timeline, set apart by a divider, because beliefs are not
memories. `/world` redirects there with a 308.

## What a belief is, and what it is not

A belief is the World Model's **current interpretation** of one claim about one subject, reconciled from
evidence. It is not a memory, and it is not a verified fact.

- **Observed** means LILITH *received* the claim from a connected source, such as an email. The source
  may itself be a test or a mistake.
- **Stated by you** means you said it directly. It isn't independently verified either.
- **Verified** is the only state that means independently checked. Today nothing produces it; the backend
  path to it exists but has no callers.
- **Confidence** comes from fixed rules about the sources. It describes how consistently they agree, not
  whether a claim is true.
- **History:** earlier values aren't kept by the store yet (ADR-0013 debt). The view shows the current
  interpretation only.

The view shows the backend's epistemic and lifecycle states exactly as they are. It never upgrades them,
and it never labels a record as test data.

## Privacy

- **Owner context stays hidden:** owner-approved memories mirrored into the World Model
  (`entity_type = "owner"`) are never shown, and no count of them is shown either.
  - The read client never asks for them, and drops any that arrive.
  - The web app's read proxy (`src/server/world-visibility.ts`) applies the listing rule to single-belief
    reads too. An owner-context belief is answered exactly like an unknown key (404), and a list request
    naming the owner entity type is refused (403).
  - This only narrows access. The backend, its authority and its read gate are unchanged.
- **Superseded beliefs** are not part of the current picture and are not shown.
- **Counts:** the backend's store-wide `meta` counts include hidden beliefs, so they are not used. Every
  number on the page is counted from what is displayed.
- **Provenance** shows the source class and type, when it was observed, the evidence's confidence, and a
  readable origin for known sources ("Career pipeline record", "Career activity event").
  - Source ids, correlation ids, origin refs and free-text notes, which can hold an account name, are
    dropped when the data is first normalised and never displayed.

## The view

- **Subjects:** beliefs are grouped into readable subjects (for a career application, its role and
  company) with their facts in a natural order. Subjects with a conflict come first.
- **Filters:** by lifecycle (Current, Conflicted, Stale); by how a belief was received, shown only when
  more than one kind is present; and by text across subjects and values.
- **Counts:** "17 beliefs about 4 subjects", and "Showing N beliefs about M subjects" when filtered.
- **Inspector** (the shared drawer) re-reads one belief under the same visibility rules and shows:
  - the current interpretation, how LILITH received it, and its status;
  - any unresolved conflict (the competing value isn't exposed by the store yet);
  - confidence and the rule behind it, in words;
  - its timeline and its evidence.
- **Unavailable store:** the shared honest workspace state, with a retry. No sample data is ever shown.

## Screenshots

All data is invented, and the owner name and monogram are replaced.

- `beliefs/phone.jpg`: 320 and 375, the inspector at 375, and the Atlas switch before and after.
- `beliefs/desktop-1440.jpg`: the view at 1440.
- `beliefs/inspector-1440.jpg`: the inspector at 1440.
