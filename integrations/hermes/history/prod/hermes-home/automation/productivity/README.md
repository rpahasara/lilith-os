# PROD productivity automations (historical source, `lilith-01`)

These are the Gmail, Calendar, meeting and morning-brief automations deployed on PROD at
`/home/lilith/.hermes/automation/productivity/`, recovered on 2026-10-27 by the bounded read-only export. Their
systemd units are in `../../../systemd/`.

**This is preserved historical source.**
- Nothing here is installed, scheduled or run, and no unit is registered anywhere.
- On PROD, every Google-backed job has failed or degraded since its OAuth grants expired (`invalid_grant`).
- Repair, redesign or migration is separate, approved work.

All files are byte-exact copies of PROD. Hashes are in `../../../provenance/automation.json`.

Left on PROD, as personal or runtime data:
- `logs/`, `state/` and `followups/followups.json`;
- the Google token files and `.env`.

| File | Role | External calls (static reading) |
|---|---|---|
| `gmail_watcher.py` (+ `.before-multi-account`) | urgent-mail scoring for two accounts; Discord alert; follow-up capture | Gmail API (user OAuth tokens `~/.hermes/google_token.json`, `accounts/secondary/google_token.json`); Hermes CLI (`hermes --reasoning minimal -z`, a provider call); Discord |
| `meeting_agenda_snapshot.py` | Calendar → `state/agenda.json` | Calendar API |
| `meeting_prep_watcher.py` → `meeting_context_collector.py` → `meeting_prep_runner.py` (+ `.bak`) | upcoming-meeting detection, context gathering, prep brief | Calendar, Gmail, Hermes CLI, Discord |
| `morning_brief.py` + `prompts/morning_brief.txt` | daily brief | Hermes CLI with Google Workspace read-only tools, Discord |
| `followup_tracker.py` (+ `.before-due-v2`) | local follow-up list (`followups/followups.json`) | none |
| `secondary_career_summary.py` | secondary-mailbox career digest | Gmail, Hermes CLI |
| `discord_notifier.py` | sends to Discord | Discord bot API; reads `DISCORD_BOT_TOKEN` and `DISCORD_HOME_CHANNEL` from `~/.hermes/.env` (names only, no values in source) |
| `redact_sensitive.py` | redacts OTPs, codes and secrets before text reaches a model or Discord; also imported by the career extractor | none |
| `config.json` | polling and scoring thresholds and keyword lists (no personal values) | — |

## Schedule (from the deployed units)

| Unit | Runs | When |
|---|---|---|
| `lilith-gmail-watcher.timer` | `gmail_watcher.py` | every 10 min (2 min after boot) |
| `lilith-agenda-snapshot.timer` | `meeting_agenda_snapshot.py` (google-venv) | every 10 min |
| `lilith-meeting-prep.timer` | watcher → collector → runner (bash chain) | every 15 min |
| `lilith-morning-brief.timer` | `morning_brief.py` | daily 08:00 Asia/Colombo |
| `lilith-career-watcher.timer` | `lilith-os/apps/career/career_watcher.py` | every 15 min |

`hermes-gateway.service` and `lilith-os-api.service` are the two long-running PROD services. They are kept with the
other units for reconstruction.
