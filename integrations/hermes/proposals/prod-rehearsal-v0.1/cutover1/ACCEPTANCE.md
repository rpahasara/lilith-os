# Cutover 1 acceptance (for owner signature; NOT SIGNED)

Fixed before the window, so it can't be fitted to the result. To sign, create `ACCEPTANCE-SIGNED.txt` here with the date.

| Check | Pass | Checked by |
|---|---|---|
| Fingerprints | `SOUL.md`, `USER.md`, `config.yaml`, `router.yaml` unchanged | `w5` |
| Data | No unexpected table difference; integrity ok; no rows lost | `w5` |
| Auth | Stranger gets 401 on reads and writes; owner read 200 | `w3`, `w4` |
| Router | Reads 200; write reaches validation | `w3`, `w4` |
| Gateway | Same process; no new failed unit | `w5` |
| Tokens | Root only, none in the journal | `w5` |
| Reply | The five post-window turns: same person | Owner |
| Command Center | Real pages load; one reply | Owner |
| Route in | Deployer on `lilith-01` port 22 only; Core API refuses anyone without a credential | Prepare, `w4` |

**Scope.** Cutover 1 brings no seven-lane work to PROD: its detectors and the Ethics suppression bug stay until Cutover 2. FORGET stays deferred under R-13, so OAuth repair and new real-data capture remain off. A pass doesn't mean erasure works.

**Stays open afterwards:** A17 FORGET on PROD, A23 to A25 provider exposure and budget, Hermes tools on Telegram and Discord.
