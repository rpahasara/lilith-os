# PROD lilith-01 read-only Hermes inspection (2026-10-22, owner-approved)

Metadata only. No file contents were exported; one export pass was refused by the Claude Code permission classifier and was not retried.

- Hermes upstream: https://github.com/NousResearch/hermes-agent.git at f293e7206b4ddd66042329442c6afebc19a8808d
  (2026-08-23, branch main), hermes-agent 0.20.5, install_method git, venv Python 3.11.16. There is no pip in the venv;
  111 installed dists are listed in 02. Upstream was fetched publicly into ../hermes-agent-f293e72. Its HEAD hashes for
  the modified files, plus uv.lock, pyproject.toml, package-lock.json and personality.py, match PROD.
- Local PROD modifications: gateway/run.py (+75/-5, Router V2 seam + Slice 9), agent/background_review.py,
  tools/{memory_tool,skill_manager_tool,write_approval}.py (Slice 15B2a), and the new tools/legacy_canonical_containment.py.
  The repo's slice-15b2a patcher applied to upstream reproduces the four 15B2a files byte for byte (with LF line endings).
- Gateway: hermes-gateway.service, `venv/bin/python -m hermes_cli.main gateway run`, RSS about 245 MB.
