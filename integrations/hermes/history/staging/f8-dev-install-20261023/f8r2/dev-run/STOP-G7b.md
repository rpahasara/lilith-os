# F8r2 Phase A on lilith-dev-01: STOPPED at G-7b (2026-10-23 ~08:06 UTC)

| Gate | Result |
|---|---|
| G-0 | authorization recorded; local hash = `269dde95…e327`; no DEV deploy since b9eb32c |
| G-2 | transfer OK; tarball sha OK; MANIFEST 14,293 OK (`171af3be…`); 12,560 MiB free, 1,365 MiB available |
| G-1 | backup `/var/backups/hermes-gateway-dev/pre-20261023T080301Z` (HERMES_HOME tar + observation; no DB opened or copied) |
| G-1b | **DR-5 byte-equal** `7fe21378…` (155 lines / 142 DENIED / 0 ALLOWED / 0 FAIL; L1c.3 / P1A-9). The `sudo -n -i -u sa_… bash -s` method is confirmed on DEV itself. |
| G-3 | `F8_INSTALL_STAGED f293e72-f8r2`; C-3 guarded reload passed; the only FAIL line is the expected `.env` MISSING |
| G-3b | DR-5 byte-equal |
| G-4 | F7 suite **19/19 OK** on DEV |
| G-5 | DEV-only token (sha256 prefix `0fb518744922`); `F8_VERIFY_PASS full`; provider.env ABSENT |
| G-6 | active / running / NRestarts 0 / static (not enabled); only listener `127.0.0.1:9901` (~8 s); timer active via `Wants=` (static); 84 MiB; no unit pending reload; existing services unchanged |
| G-7 | smoke **22/22**: S5 provider-failure reply without network; 9 slash commands not executed; S10 real Core API relay 200; S11 capture 403 `CAPTURE_INACTIVE` |
| **G-7b** | **FAIL 16/17**: `P7 name resolution metadata.google.internal: OPEN` |
| G-8 … G-10 | NOT RUN |

## Diagnosis (read-only)

- DEV `/etc/hosts` line 10: `169.254.169.254 metadata.google.internal metadata` (GCE image).
- `/etc/nsswitch.conf`: `hosts: files dns`.
- The "OPEN" is a local hosts-file lookup; no packet is involved.

In the same probe run, network access stayed blocked:
- P1: the TCP connection to 169.254.169.254:80 was BLOCKED.
- P5 and P6: DNS stub and public DNS BLOCKED.
- P8: real name resolution BLOCKED.
- P2–P4: internet, PROD and the own NIC IP were BLOCKED.

**No unauthorized network access occurred.** The WSL mirror did not have this hosts line, so the probe expectation for P7 was wrong for GCE. The defect is in `bin/sandbox_probe.sh` (a package file); fixing it changes the package hash.

## State at the stop (read-only re-check, re-read after a plink-crash exit)

- Observation vs G-1: **EQUAL** in all 6 sections: services, units, sockets, custody, coreapi, accounts.
- DR-5 byte-equal `7fe21378…`.
- Core API `/health` ok, database true.
- lilith-os-api-dev 176771/0, broker 3411/0, authority 128648/0, witness 127192/0. All identical to G-1.
- hermes-gateway-dev 185350 active, 0 restarts, still running inside the verified sandbox.
- No rollback executed. All F8 artefacts are in their allowlisted paths.

## Plink crashes

Two reads ended with rc `0xC0000005` (the known local plink 0.83 crash after completion). Both were re-read from the files saved on DEV before being used.
