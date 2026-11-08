# G3 Privacy and data-handling decisions (FOR OWNER SIGNATURE, NOT SIGNED)

G3-B opens a copy of PROD's real data. It refuses to run until these are signed. **Recommendations are proposals.** A change to any of them may change the package.

| # | Decision | Recommendation | Why |
|---|---|---|---|
| 1 | **Purpose** | Only to prove Cutover 1 changes no data. No other use | Limits what's justified |
| 2 | **Who may reach the VM** | The owner account alone. The rehearsal runs under it, automated | Nobody reads anything |
| 3 | **What's copied** | **Allow-list only:** `SOUL.md`, `memories/USER.md`, `state.db` and its WAL, the three Core API databases and their WALs, `app.py`, `api-venv`. Everything else stays on the read-only disk, unopened | Stricter than excluding by name |
| 4 | **Content** | Machines read rows to digest them. **No person reads, prints or exports a row, memory or message.** `state.db` included | It's never been read, and this doesn't change that |
| 5 | **Credentials** | Not copied. The read-only disk does hold them, unopened. Throwaway tokens are generated for the run and never printed | The disk can't be made credential-free |
| 6 | **Evidence leaving the VM** | Counts, digests, verdicts and table names only | Table names and row counts are the most it reveals |
| 7 | **Copy lifetime** | The disk `lilith-rehearsal-copy` and working tree are destroyed **within 7 days** of the rehearsal, or at once on a stop or a privacy concern, under their own approval | Shortens exposure |
| 8 | **DNS** | Blocked in the guest before real data arrives, proven by test | See below |
| 9 | **Erasure** | If you ask for anything erased during the window, the copy is destroyed rather than edited. **The snapshots still hold it** until deleted | FORGET doesn't reach these. R-13 stays explicit |
| 10 | **Real replies** | **No provider at G3.** Cutover 1 changes nothing feeding the persona, so hashes prove identity here. Your judgment of replies moves to Cutover 2's rehearsal | No credential or provider near real data |
| 11 | **Default compute account** | Accept for the window: it holds `roles/editor` but has no keys, no VM uses it, and nobody can impersonate it. Reconsider at Cutover 1 | Removing it is unrelated engineering |

## The metadata server, stated exactly

**VPC firewall rules do not block `169.254.169.254`.** Traffic to it is handled on the host and never reaches the VPC. Measured on the VM: with deny-all egress, external names still resolve through it. Direct connections to those addresses stay blocked, **but DNS queries themselves could carry data out.**

The VM has no service account, so the metadata server grants no credential. The DNS path is closed only by a guest firewall rule that G3-A adds and proves. **That guard lives in the VM,** so a root process could remove it. Only the reviewed rehearsal script runs there, and it re-checks the guard before touching data.

Metadata HTTP stays open, because OS Login depends on it. The server can see instance metadata, not disk contents.

## Sign here

Reply with the decisions you accept, or "accept all as recommended". `DECISIONS-SIGNED.txt` is written from that reply and nothing else.
