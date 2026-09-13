# Engineering Journal

The journal records how LILITH evolves: the problem encountered, evidence gathered, options considered, decision made, what failed, what was learned, and what should change next time.

It is intentionally separate from authoritative architecture. Journal entries may be incomplete or wrong; validated conclusions should update architecture, ADRs, research questions, tests, or the threat model.

## Entry workflow

1. Copy [entry-template.md](entry-template.md).
2. Name it `YYYY-MM-DD-short-topic.md`.
3. Link relevant RQs, ADRs, issues, pull requests, traces, and experiments.
4. Mark sensitive operational details and create a sanitized public narrative separately.

## Public-writing pipeline

Each strong entry can yield:

- internal engineering evidence;
- a lesson or pattern for the architecture documentation;
- a research experiment or open question;
- a portfolio case study, technical article, or concise professional post.

Public writing should center on real decisions and measured outcomes, not generic claims. Remove personal data, secret values, exploitable details, and private connector content.

Potential themes from the current direction include idempotency for durable agent state, honest degraded-source behavior, moving from local client state to canonical state, approval binding, verification beyond HTTP success, and separating a persistent AI identity from its runtime.
