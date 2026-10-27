# G-0: owner authorization record (F8r2 Phase A, lilith-dev-01)

- Owner D-0 received 2026-10-23 in chat: "I authorize D-0: the strictly scoped F8r2 Phase A installation on lilith-dev-01."
- Approved package sha256: `269dde950eb024155235b3237a4658c93039975c600fa2f40d638ff02945e327`. The local file matches.
- Runbook: `RUNBOOK-f8r2.md` G-0 … G-10. Phase A only. Phase B is not authorized.
- Conditions:
  - Stop on any failed gate, host drift, DR-5 mismatch, service PID or restart change, or unauthorized filesystem or network access.
  - Use only the documented paths and operations; roll back per the runbook only.
  - No credentials, tools, lanes or owner capture; synthetic text only.
  - No PROD, commits, pushes, firewall or IAM changes, snapshots or UI changes; no paid calls.
- Precondition 4: the latest DEV deploys (39798993803 at b9eb32c, 39781661322) are unchanged; main is still b9eb32c. The expected DR-5 block `7fe21378…` is still current.
- Freeze: the owner did not state a freeze. The D-0 instruction to proceed is taken as confirmation that no DEV operation conflicts.
