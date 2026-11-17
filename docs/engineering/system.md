# System (P1-9 PR B)

System shows what is measured or chosen, and says so when something can't be measured. Nothing on it is a
fixed status. It starts no request or polling of its own.

| Section | Source |
|---|---|
| Connection | The shell's existing health check (`ShellHealthProvider`): state, round trip, last check, HTTP status. "Check again" is its `refresh()`. |
| Platform | The `/system/status` body that the same check already fetches, read from systemd's own fields (`active`, `sub`, `result`). |
| This device | What the presence stage on the Command Center actually drew and why, with its measured frame rate (`lib/presence/renderer-report`). Also WebGL, reduced motion, the last spoken-reply result, and whether this browser keeps preferences. |
| Preferences | Lilith's presence: the existing `lilith-os:presence-pref` key, now also announced within the tab. Speak replies: the same switch as the Command Center, via one helper (`setVoiceReplies`). Motion is shown as following the device; there is no in-app override. |
| About | The version from `package.json` at build time (`NEXT_PUBLIC_LILITH_VERSION`) and the build mode. |

## Platform

- **Readable names:** "Core API" and "Conversation gateway", plus a summary of the four automations that
  links to Automations rather than duplicating it.
- **Unknown units:** a unit the backend couldn't read is Unknown. Units not listed are counted, never named.

## Presence

- **Before the stage has rendered:** until the Command Center has rendered in this tab, System says "Not
  measured yet in this tab".
- **Frame rate:** the frame-rate guard publishes each one-second window. It still degrades on the same
  rule: under 20 fps for two windows, after the avatar's startup grace.
- **Errors:** a renderer error is reported as such, not as live.
- **Development override:** the renderer override key is ignored in production builds.

## Removed

- The fixed "Client active", "Application shell — Active" and "Enabled" statuses.
- The Integrations card with its disabled Manage button.
- The Privacy & permissions statements.
- The Performance placeholder and the Advanced diagnostics note.

## Screenshots

Invented data, owner name and monogram replaced.

- `system/phone.jpg`: 320 on first load, and 375 after visiting the Command Center.
- `system/desktop-1440.jpg`: 1440.
