# Preserved from PR #311 (historical record, redacted)

These documents were proposed in PR #311 (2026-10-31, branch `docs/cutover-2-plan-v0.1`) and are kept here as the
historical record of the Cutover 1 and Cutover 2 preparation. They are **unchanged except for redaction**:
- local operator paths became `<operator-local-path>`;
- cloud resource ids became `<id>`;
- private IPs became `<private-ip>`.

Status headers such as "NOT APPROVED, NOT RUN" describe the moment each file was written. They are not current status.

**What happened afterwards** (`OPERATOR-REPORTED`; see `docs/engineering/prod-work-note-2026-11-07.md`):
- **Cutover 1:** completed 2026-11-01 and accepted by the owner.
- **Cutover 2:** deployed on PROD 2026-11-03 and accepted by the owner 2026-11-04, with exception E-T4 open.
- **E-T4:** fixed by #351 and owner-confirmed 2026-11-08.

**Not preserved here:** PR #311's one-off drivers, simulators and PowerShell/shell scripts for those completed windows.
They embedded operator-specific account and infrastructure details and have no further use. They remain reachable in
PR #311's history if ever needed.
