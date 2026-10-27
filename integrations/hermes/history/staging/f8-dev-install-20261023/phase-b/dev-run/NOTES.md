# F8r4 DEV run notes (2026-10-23)

| Gate | UTC | Result |
|---|---|---|
| U-0 | 12:28 | current=f293e72-f8r2, F8R2_SHA ffaed494e2643b2d56533f63a919daebaa0b8a78e5ada8deca614c92cf96cf12 (18,212); gw 185350; api 176771, broker 3411, authority 128648, witness 127192, 0 restarts; no pending reload; jobs 0; apt-daily 20:05; DR-5 EQUAL |
| G-2 | 12:29 | scp 38 s; tarball OK; MANIFEST 14,307 bd8bcec1…fd82; gate.json b652422f… |
| G-1 | 12:30 | upgrade-pre-20261023T123016Z (gateway.sock ignored by tar, expected) |
| G-1b | 12:30 | DR-5 EQUAL 7fe21378… (155 lines, 142 DENIED, 0 ALLOWED, 0 FAIL) |
| U-1 | 12:31 | F8R2_PRESERVED f8r2-preserved-20261023T123117Z quarantine rollback-20261023T123157Z files=18411 |
| G-3 / G-3b | | F8_INSTALL_STAGED f293e72-f8r4 (only .env MISSING); DR-5 EQUAL |
| G-4 | | F7 19/19 OK |
| G-5 | | console token prefix 873f72f28328; F8_VERIFY_PASS full f293e72-f8r4; credentials dir root 700, empty |

## Procedural note N-1 (not a gate failure)

After U-1, `hermes-gateway-dev` showed ActiveState=failed:
- The F8r2 process (185350) exited status 1 on the SIGTERM sent by F8r2's own R-1 stop (journal 12:31:18). R-1 reported F8_ROLLBACK_STOPPED.
- NRestarts=0, NeedDaemonReload=no.
- Old InvocationID 299f431e…; 1 G-6 start replaces it.
- No reset-failed was run (it is not in the runbook).

## G-6 STOP → R-1 → Option A re-run (owner-authorized)

- **First G-6 (12:42):** G6_FAIL. The wrapper checked 9911 at +9 s; the gate binds at about +30 s. R-1 applied; parity EQUAL; 0 requests. See STOP-G6.md.
- **G-6 re-run (12:51:55):** G6_PASS (`G-6r-6b.txt` sha `a4f3b06a…235f3b`).
  - Readiness: 9901 at +6 s, 9911 + gate START at +31 s (limit 90).
  - Gate pid 221436: uid/gid 64597 (dynamic `hermes-provider-gate-dev`), CapEff/CapBnd 0, NoNewPrivs 1, Seccomp 2.
  - Gateway pid 221439 (lilith).
  - Both active/running/0 restarts/static; listeners exactly `127.0.0.1:9901` and `127.0.0.1:9911`.
  - Budget key_loaded true, 0/5, available; the ledger holds only the initial RESET line; 0 FORWARDED.
  - No pending reload; protected services unchanged.
- **G-6b:** sandbox probe 23/23 (P7 HOSTS_ONLY, no packets); `F8_GATE_PROBE_PASS` (Q1–Q10; key not in environ; lilith cannot read the credential). The gateway has 0 non-loopback connections and the gate 0 established. Observation EQUAL to G-1 (6/6); DR-5 EQUAL; Core API ok.
- **Observed, not a gate:** the gate takes about 31 s from fork to bind, reproducibly. The cause has not been investigated.
- **Stop point:** the gateway and gate are running, awaiting authorization for G-7 (first real Groq requests).

## A0 (owner-authorized, 13:27–13:28 UTC): A0_PASS (`A0.txt` sha d3682a28…4268)

- **Harness staged:** `/var/tmp/f8/amend` (root 0700). The tgz ed4fe9d6… and all 3 SHA256SUMS lines are OK.
- **Budget from the ledger:** used 1/5 (remaining 4), 1 RESET line (initial only), prior request `0d00769ac01a`.
- **Router V2 decisions log:** 1 line: f8b-s1, mode social, live false, platform lilith_os.
- **turn1_evidence:** the WAL was 370,832 bytes, so it read a private copy, and the copy was removed.
  - Session `20261023_125745_4cab16ae` (source lilith_os, chat_id f8b-s1): msg 1 user = the exact turn-1 prompt; msg 2 assistant, 172 chars, no error notice; msg 3 session_meta.
  - Result: TURN1_REPLY_OK.
- **Originals unchanged (sha256 before = after):** state.db 83bdf9ff…, -wal c88054b2…, -shm c2df3a7c…, ledger ca3c5c5b…, decisions 9b8ecdd3…, HERMES_HOME listing 84506d2b….
- **Parity:** verify full PASS; observation EQUAL to G-1 (6/6); DR-5 EQUAL; Core API ok.
- **Protected services unchanged:** api 176771, broker 3411, authority 128648, witness 127192, 0 restarts.
- **Stopped state kept:** gateway failed/stopped and gate inactive; 9901 and 9911 closed.
- **Observation (not a check failure):** the turn-1 reply was 2 sentences, not the one requested. It advertised `/help` and invited the user to "share a bit about yourself" (persona/system-prompt behaviour). That is relevant to the synthetic-only and privacy limits.
