# G-0: owner authorization record (F8r4 Phase B, lilith-dev-01)

- Owner O-6 received 2026-10-23 in chat: "I authorize O-6: the controlled F8r4 Phase B installation on lilith-dev-01, strictly following the reviewed RUNBOOK-f8r4.md."
- Approved package sha256: `16c7417dc97a11ba6cf65fe44ef639e255bff22257f65d5f9bcefaab1af9d41a`. The local file was re-hashed and matches; MANIFEST `bd8bcec1…fd82` (14,307 entries).
- Owner-reported O-1..O-5 (non-secret):
  - organization "Personal"; DEV project `lilith-dev-f8`;
  - global Zero Data Retention enabled;
  - model allowed `openai/gpt-oss-120b`;
  - project limits 5 RPM, 10 RPD, 8,000 TPM, 30,000 TPD;
  - billing free tier;
  - key display name `f8-dev-gate` (value never in chat, logs or arguments).
- Conditions (owner, 1-10):
  1. full hash and every precondition;
  2. preserve F8r2 as the rollback baseline;
  3. reviewed gates only, stop on any failure;
  4. DR-5 and protected Core API, broker, authority and witness boundaries;
  5. G-5b key entered privately by the owner at the hidden prompt;
  6. at most 5 synthetic provider requests;
  7. verify real replies, gate budget and Router V2 shadow decisions;
  8. tools, lanes, owner recording and canonical admission stay disabled;
  9. no personal content;
  10. no PROD, GitHub, IAM, firewall or UI changes.
- On failure: approved rollback only (R-1..R-3v). After validation: STOP and report. First Memory and unrestricted conversations are NOT authorized.
- Precondition 2 (no DEV deploy since b9eb32c): GitHub is out of scope for this authorization, so it is checked on DEV instead (DR-5 byte-equal to the b9eb32c block, Core API observation unchanged vs the G-1 baseline).
