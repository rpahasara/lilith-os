# Canonical memory in PROD: owner decision sheet and execution path (2026-11-05)

Record: [`canonical-memory-prod-integration-plan.md`](canonical-memory-prod-integration-plan.md) (§4, §5, §7, §13).
This sheet consolidates what the owner must decide and supply before LILITH on `lilith-01` uses canonical memory,
and the shortest path from here to that. It decides nothing and runs nothing. Every PROD mutation below is its own
owner authorization. No domain, key, credential or identity is invented, generated or chosen by this document.

## 1. Owner decision sheet

Decisions already made (unchanged): D-1 new PROD keys only; D-2 canonical-records-only FORGET; D-3 `USER.md`
authoritative; D-4 manual unlock; D-5 console first, then Telegram DM, never Discord; D-6 V1 HMAC (provisional);
D-7 isolated canonical store (merged, #318).

### D-8. Relying party: RP id, origin and principal

Three strings, fixed for the life of the PROD owner registration. Every owner proof binds them, so changing any of
them later means a new registration and new credentials. The rules are enforced by
`lilith_authority_host/inputs.py`.

| Option | For | Against |
| --- | --- | --- |
| **A. A subdomain of a domain you already own and will keep renewing** (RP id `lilith.<your-domain>`, origin `https://lilith.<your-domain>`) | no purchase; one name dedicated to LILITH | ties the registration to that domain's renewal |
| B. A dedicated domain you register for LILITH | independent of any other use | a purchase and one more renewal to keep |

**Recommendation: A**, with the D-12 software credential. That pair needs no web page served at the origin; the
origin is a binding string only. A hardware credential through a browser would need a page actually served there.

**You must provide:**
- the domain (or subdomain) for the RP id;
- confirmation that you control it and will keep renewing it;
- the principal's local part, giving `user:<name>@<domain>` (`[A-Za-z0-9._%+-]{1,64}`, never the DEV synthetic
  identity).

### D-9. PROD machine identity

**Recommendation: approve the digest pin.** The implementation (#321) is merged and its tests still pass on main
`3e81d4f` (authority-dev 358 OK). The value comes from the sealed, COMPLETE audit run 2, whose helper hashes the
exact `/etc/machine-id` bytes, the same bytes the keygens hash:

`PROD_MACHINE_ID_SHA256 = 1b1d67880b40565fda61c2944d20c9e9d90c650846e10cac3eb900e6a9ac1001`

**On approval:**
- one reviewed commit sets this constant in both `owner_prod_keygen.py` and `owner_prod_kpan_keygen.py` (a test
  already proves they must be equal);
- no raw ID is committed, and no release is rebuilt;
- at the ceremony, both keygens refuse unless the host's bytes hash to the pin, the hostname is `lilith-01`, the
  machine is not the DEV machine, and stage 1's OWNER_PROD `deployment.json` is present.

**You must provide:** the approval only.

### D-10. K-ROOT (registry root) custody and backup

K-ROOT is one Ed25519 key, PKCS#8 DER encrypted under a passphrase of at least 12 characters, written once with mode
`0600`. It signs registry v1 and every later registry change. Losing it freezes the registry, but the running
services keep working. Its theft lets the holder rewrite who LILITH trusts.

| Option | For | Against |
| --- | --- | --- |
| **A. Generate in WSL on your workstation**; passphrase in your password manager (never beside the file); one encrypted offline backup on removable media stored apart from the workstation | uses the validated tooling; fastest | the key exists on an online machine, protected by the passphrase only |
| B. Generate on a dedicated offline device; file and backup never touch an online machine | strongest custody | a device to prepare; slower ceremony |

**Recommendation: A**, with a restore test before Privacy activation: load the backup copy with the passphrase.

**You must provide:**
- the generation machine;
- the file location;
- where the passphrase is kept;
- the backup medium and where it is stored.

### D-11. K-PCK (Privacy checkpoint) custody and backup

K-PCK is a raw Ed25519 key (`kpck.key`, `0600`), **unencrypted at rest**, in a new custody directory. It signs
every post-reboot Privacy unlock and checkpoint. Losing it means PROD Privacy can never be unlocked again, and
personal recall stays off permanently.

| Option | For | Against |
| --- | --- | --- |
| **A. A new WSL custody directory on an encrypted disk** (e.g. the Windows system drive under BitLocker), plus one **encrypted** offline backup made and restore-tested **before** activation | validated tooling; the at-rest gap is covered by disk encryption | relies on the workstation's disk encryption and account security |
| B. A custody directory on an encrypted removable volume, mounted only for unlocks | the key is offline between reboots | every PROD reboot needs the volume; slower recovery |

**Recommendation: A.** Keep the backup separate from K-ROOT's, so one loss cannot take both. The DEV backup was
never made; PROD's must be made and verified before R7.

**You must provide:**
- the custody directory location, never the DEV folder;
- confirmation that its disk is encrypted;
- the backup medium and where it is stored.

### D-12. Owner credential: software or hardware

| Option | For | Against |
| --- | --- | --- |
| **A. WSL software credential** (the DEV pattern) | validated end to end on DEV; no new hardware; no served origin needed | a workstation compromise is an owner compromise |
| B. Hardware authenticator | the private key never leaves the device | owner tooling and WSL USB access (usbipd) are untested; the browser route needs the D-8 origin served. This is new engineering before the ceremony |

**Recommendation: A for the first PROD registration.** It is the fastest safe path and stays inside validated tooling.
A later move to hardware is a new registration under K-ROOT.

**You must provide:**
- A or B;
- the loss plan. On loss, a new credential means a new owner registration signed with K-ROOT.

## 2. Shortest safe execution path

Every gate is its own owner authorization (an exact go-line, rendered and checked like the P3 windows). Every STOP
gets no retry and no automatic repair; recovery is the reviewed return, under your word. The signed release stays
`88a1168`; no new architecture or infrastructure is needed.

| # | Gate | Where | What | Evidence that closes it |
| --- | --- | --- | --- | --- |
| 1 | H-1/H-2 merge | GitHub, DEV gate | merge the H-1/H-2 PR; routine DEV deploy | green validation and DEV gate; DEV invariants unchanged except the Core API |
| 2a | Owner decisions | owner | D-8, D-9, D-10, D-11, D-12 (§1) | your written answers |
| 2b | D-9 pin | GitHub | one reviewed commit: the digest in both keygens | CI green; DEV gate green |
| 2c | Final compatibility preflight | PROD, read-only | one authorized `prod_integration_audit_ro.py` run (run 3): the corrected timer and principal names and the 22 pins | `COMPLETE`, `PROD_COMPAT_PASS` |
| 3 | Snapshot and restore readiness | GCP | a fresh manual snapshot of `lilith-01` READY; the scheduled snapshot policy confirmed; the restore procedure written down. An isolated restore test (a temporary disk from the snapshot, then deleted) is optional, under its own approval | snapshot name and READY state; procedure recorded |
| 4a | Ceremony, workstation part | owner workstation | K-ROOT (D-10), owner credential (D-12), K-PCK (D-11); each offline backup made **and** restore-tested | public anchors and pins recorded; backup restore tests pass |
| 5.1 | Inert stage 1 | PROD | principals by name, isolated store dir, `/etc/lilith-authority-dev`, `deployment.json` | `FOUNDATION_INSTALLED`; live digests equal |
| 4b | Ceremony, host part | PROD | K-ACT, K-WIT, K-PAN with the pinned keygens (they require stage 1's `deployment.json`); registry v1 and anchor signed with K-ROOT | publications verified; no raw machine ID committed |
| 5.2–5.5 | Inert stages 2–5 | PROD | release `88a1168` and venv; units with the `LILITH_ENV=prod` drop-in (no reload, enable or start); host tree with `canonicalLtmEnabled=false`; context units with **no grant** | each `STAGE_*_INSTALLED`; live digests equal; each its own window and fresh snapshot |
| 6 | Privacy activation and owner registration | PROD + owner | R7: pins, genesis, K-PCK checkpoint, first unlock → READY; the owner registration with the D-8 strings and the D-12 credential | Privacy READY; registration verified; LILITH unchanged (the five-prompt identity baseline) |
| 7 | Console recall | PROD + owner | R8 records (origin statement re-admitted, importer proposals reviewed), then R9: overlay installed, settings without a Telegram id, grant v3 `[lilith_os]` | the console recalls the origin; voice and routing unchanged; corpus identical with the feature off |
| 8 | Telegram owner DM recall | PROD + owner | R10: settings gain the owner Telegram id, grant adds `telegram_owner_dm` | the DM recalls the origin; a group, another user and Discord get no personal recall |

**Still to be supplied before gate 8:** the Telegram owner-ID source, which is unresolved. This is needed only at R10.

**Not needed:** a release rebuild, a new architecture, a broker process (settled in source), and new infrastructure,
unless D-12 B is chosen (then an origin must be served).

**Return paths:** every inert stage has its verified return (H-1/H-2). Console and DM recall return by removing the
grant (one file, next turn), then restoring the overlay's base. Privacy activation and the ceremony have no return;
they rely on the verified backups of gate 4a and the snapshot of gate 3.
