# Slice 15B2b-B1b-3e — Package C Sequence 4: Record 1 and Acceptance Envelope 1 Completed (2026-10-10)

Status:

- **OWNER ACCEPTANCE RECORD (APPEND-ONLY).** It records Package C sequence 4 (`e6b7a3334cda25efe9259741cda1b3ae`)
  on control `896716e8c7bd705bcbe6e25f154afff4ae1d4dba`. Record 1 was appended to Replica A (C2) and Replica B (C3).
  Acceptance envelope 1 was appended to copy A (C4A) and copy B (C4B). Each owner-record act ran exactly once and
  was verified. The owner then accepted the whole package verbatim (C5, §7).
- `PACKAGE_C = COMPLETED / OWNER-ACCEPTED` (`PC5_PACKAGE_C_ACCEPTED`). Record 1 freshness is **AUTHENTIC + CURRENT**.
  Acceptance is **`ACCEPTANCE_COMPLETE`**. The Package C freeze has **ended**.
- **The earlier records are unchanged.** The [Package C design record](slice-15b2b-b1b3e-pkgc-record1-envelope-package.md)
  §17 (record 1 absent; Package C not run) was correct when written and is not rewritten. Its OD-C1 … OD-C9 status is
  not changed by this record. This record supersedes it on the Package C outcome only, from 2026-10-10.
- **Documentation and governance only.** Package C completion does not write HELD, does not start the signer, does
  not make Registry V1 effective and does not activate authority. M-B10 HELD, signer start, authority activation,
  First Memory and PROD stay **NOT AUTHORIZED**.
- **Writing this record contacted no live system.** The evidence stays in the owner's local evidence directory,
  sealed as stated in §9.

```text
record 1 on A and B (AUTHENTIC + CURRENT) != acceptance envelope 1 on copies A and B (ACCEPTANCE_COMPLETE)
ACCEPTANCE_COMPLETE != HELD != signer != Registry V1 effective != authority active
C5 accepted != this record merged != first post-C5 deploy EQUAL;  completion != FIRST_MEMORY_READY
```

## 1. Identities

| Item | Value |
| --- | --- |
| control | `896716e8c7bd705bcbe6e25f154afff4ae1d4dba` (merge of PR #178, the C1 environment fix) |
| control deploy | `37945605981`, "Deploy LILITH Core API to DEV", success; the last DEV deploy before and throughout the sequence |
| sequence | `e6b7a3334cda25efe9259741cda1b3ae`, opened 2026-10-09T16:39:25Z; C1 opening record SHA-256 `99955da4ba8453ab77778f1f0aceb727b6b6d7def9b0cdcc2f22c0aa5ef13015` |
| operator | `services/owner-memory-control/tools/pkgc_operator.py`, SHA-256 `c5e5a5cc265f48721715e43b4bec40ccbaf865c4149d095c86c853331c2767c0` (`pins` = `PKGC_TOOL_PINS_EXACT`) |
| owner freshness tool | `owner_freshness_tool.py`, SHA-256 `fd7abe2aa5e5efae41b87553efe8fe8058b437748accf866c2fa5ee71c8a7c27` (unchanged; the only writer, run by the owner) |
| binding | `BINDING.json` SHA-256 `bd1c35e79c3833710196f51186741160e81c0532632f5050fd5134fc0ca70793` |
| bound evidence | `PR2_REVALIDATION` `d541b3ce3bc6bc9de5daf1e0ed108a78b7fec54cede0ba4650d01a52015d815c`; `P3_3_INDEPENDENCE` `a3e1018f6f454ebab72e7248ba607a3e8ba3f591ae0f989e57cb0398d4af4863` (OD-C7 definitions, owner adjudication SHA-256 `3b874b5c989929c9c0e826882d6a77c7ba41bffd6e2cf99b8f90488114c19bcb`) |
| committed witness genesis | `ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4`; `chain/1.json` `252c32204bebf3fa1ca0981d8791115e2abb6cd8ddb0925285c64213317cfb99` |
| witness incarnation | InvocationID `8af12bd64d024d0eba56bbcedbc534a6`, MainPID `1580`, NRestarts 0 (the owner-accepted post-reboot incarnation; [re-pin record](slice-15b2b-b1b3e-post-reboot-witness-broker-repin.md)) |
| boot id | `cb0d71da-32a7-402b-b85e-5748da012bff`; `REBOOT_REQUIRED=absent` at every acquisition |
| S25 bundle | SHA-256 `77eeb7d57c7e2e67365fc61207e99c0e817cf2bc685ea18f2f226799faa06610` (77 files, source `896716e`) |
| Replica A / B | `owner-primary-dev-synthetic-01` (laptop WSL) / `owner-offline-dev-synthetic-01` (S25 Termux) |
| acceptance copies A / B | store `owner-primary-dev-synthetic-01` (laptop WSL) / store `owner-offline-dev-synthetic-01` (S25 Termux) |

## 2. Earlier sequences on the same control (historical, non-reusable)

Each ended without an owner-record write. Replica A was unchanged in each, and no evidence from them was reused.

| Sequence | Ended at | Cause |
| --- | --- | --- |
| 1 `6dff580d71f521d0c566c6af159e7b93` | after the C2 marker | the owner's WSL launch triggered an MSI repair; the append never ran |
| 2 `f360367e05b44a6208652f701f4491fc` | after the C2 marker | the interactive WSL launch entered distro first-run setup; the append never ran |
| 3 `03553f6a31bdf32938fb265bcc33d64f` | after the C2 marker | the append refused `OWNER_CONFIRMATION_MISMATCH` (an unreplaced placeholder digest); nothing written |

Before sequence 4, the owner approved the non-interactive execution path `WINDOWS_SYSTEM32_WSL_EXEC_BASH_LC` and a
read-only owner-digest preflight, run before each arm.

## 3. The owner acts of sequence 4

Every go passed the operator's `check_text` for its canonical template and its last exact gate. Each marker was
written once.

| Act | Go SHA-256 | Gate | Marker (UTC) | Result |
| --- | --- | --- | --- | --- |
| C1 open (read-only) | `977e51617bfa9482a022928cb52717805056f2599fe8b6c68c40ae4190a188c8` | — | — | `PC1_BOUND_KNOWN_EMPTY` |
| C2 `APPEND_RECORD_1_REPLICA_A` | `ecb304cadc0bdd988254c432903e43609dd7a099923da3b309c62e134954ec38` | `01-C2` `3a87fd726a2d6cb1e114aabeb4b1a1fb486e54db1a2af3e7d72eecef6b36d0fe` | 2026-10-09T18:56:12Z | `PC2_RECORD1_A_PARTIAL` |
| C3 `APPEND_RECORD_1_REPLICA_B` | `87123a3035ea897255428224f9de2b98bcf85e85ab1587f34dc411e35e26fdce` | `02-C3` `6ad845b6f5860ef9e1ed7df11b5a35c95cb91d9bda6ee2bcafc8c1a7f726bc0e` | 2026-10-10T06:50:25Z | `PC3_RECORD1_CURRENT` |
| C4A `APPEND_ENVELOPE_1_COPY_A` | `a28b5113706086cf4fac051ebd649711022b0826b1cdd305651255a76882c811` | `03-C4A` `fc0a29a017fde637376fb2b72d502c126215a3b446855f4f373e6ddcc5aef6e2` | 2026-10-10T07:35:10Z | `PC4A_ENVELOPE_A_PARTIAL` |
| C4B `APPEND_ENVELOPE_1_COPY_B` | `c8464a09aee9f0f1fdf083f22be70b772f18edc3dfae6c6d7e6494b319b7ac1d` | `04-C4B` `8982d7f0fb1c3a20e28adddb8b48f7b5cd6f010dee818443f7e3cd9cdcf5f238` | 2026-10-10T08:02:49Z | `PC4B_ENVELOPE_COMPLETE` |
| C5 Package C acceptance | `6161ffcd438bef1f7e030cc94569655747cd44327bb81604fdfcefd2d81060dd` | `05-C5` `962aa9579a51ce607661a084017e54fae2ae0584cc019be5d3b41beba7f6b18e` | — (no marker; recorded 2026-10-10T08:16:22Z) | `PC5_PACKAGE_C_ACCEPTED` |

Every gate returned `PKGC_GATE_PASS` with events `[]` and route `CONTINUE`. Each was taken over a new,
receipt-bound acquisition run from the Windows side (`acquire-windows`, record §12.2):

| Acquisition | Completed (UTC) | Receipt SHA-256 | Used by |
| --- | --- | --- | --- |
| `01-2cf096606fba99180ac44a57cfd83288` | 2026-10-09T16:41:59Z | `4dca84f27b7c6cfeebfff3c1633e5b94af3bd2f14fe52a660526ddf4c82510d1` | `bind` |
| `02-806598a71cc5086b55053c779127c22e` | 2026-10-09T18:49:37Z | `d80dc12a580e8503873758faf95c270a927894106c5bbe42109bb0b13ae5dc07` | gate C2 |
| `03-dcb16bd593745e84344988006cdd48ad` | 2026-10-09T19:02:07Z | `88da892b7a71a00866b216d005776744151e0e293f4a6fdfd5a49739b1c1bbe5` | gate C3 |
| `04-3b04bb74811916dd4a8670c3e99fe1be` | 2026-10-10T07:07:27Z | `71626a89d84a1119cab8199f277a55fdb64b43640ecf4ff1960cf9e07217bf5a` | gate C4A |
| `05-4d1f70c0ffa9a39993810d635005b230` | 2026-10-10T07:42:09Z | `e54ae3296d59efc768d1618f54ee05c5663c3270fb1b3e1c07a1ab368f5c451b` | gate C4B |
| `06-389151fef5335ffd29c0437880bb5034` | 2026-10-10T08:13:53Z | `a308f9f73e7d572bb729e35812ed92d6693bbd5075749b18520e89991157ecb5` | gate C5 |

Every acquisition read `W9_5_GENESIS_COMMITTED_EXACT` on the committed genesis `ac892dc2…65e4`, the incarnation
`8af12bd6…` / `1580` / 0 and the boot id `cb0d71da…`, with all result codes 0. Throughout, the last deploy stayed
`37945605981`, the workflow queue was empty and `main` stayed `896716e`.

## 4. Record 1 (C2, C3)

- **C2 (laptop, owner-run `append`, the owner typing the digest):** `RECORD_APPENDED`, replication `PEER_PENDING`,
  `RENAME_NOREPLACE_V1`. Replica A holds one record, `000001-77752db1…`, file SHA-256
  `830bf49471be61f9b5d23d02c3c783f28c9a394505b62173d5ce9f6462741683`; `REPLICA.json`
  `fbdd045c390506f8174192dbea6a6444e6f3e819c9a24e90c61155ec9238978b`. Laptop freshness was `FRESHNESS_UNKNOWN` by
  design.
- **C3 (S25, owner-run `pkgc_c3`):** `RECORD_APPENDED`, `REPLICAS_IDENTICAL`; Replica B one record, head `77752db1…`;
  `OWNER_REGISTER_VERIFIED`; `FRESHNESS=AUTHENTIC:CURRENT`; acceptance store B absent. Transcription SHA-256
  `40cc46838aed43985024470c7dc2b93ab39579cdecbdadaab441af21616afca1`; result block
  `d3eb6fb55dbd36797c3ec13c915ea62767220f66cc4662e3555743268861293b`; `s25-check C3` =
  `PKGC_S25_TRANSCRIPTION_EXACT`.
- **Laptop read-back:** peer view `replica-b-1` `2534bda866d14c0ae7c6f1e64658bbb88dc8b358ca226324a8bfd05507897c94`
  (NON_CUSTODY, bound to the C3 transcription); record bytes identical on A and B; laptop freshness
  **AUTHENTIC + CURRENT**.

**Record 1 digest: `77752db11d80eef50eaeaa8b931d65a489bb919f9e864584fbf8d00746e2cec6`** (version 1, bound to the
witness genesis `ac892dc2…65e4`). Owner review package `2e0599d2db5974b022678130654ce18b24c60ade3aa93c62ca5982e173df30c1`.

## 5. Acceptance envelope 1 (C4A, C4B)

- **C4A (laptop, owner-run `init-acceptance-store` then one `append-envelope`):** `ACCEPTANCE_STORE_INITIALIZED`;
  `ENVELOPE_APPENDED`, `PEER_PENDING`, `RENAME_NOREPLACE_V1`. Store A holds one envelope, file SHA-256
  `43166b801c28e5171a19257a169c38a21c762e8937605df240ab6f5c4a1e2bdd`; `ACCEPTANCE.json`
  `ced439e967dcc9601fc49cc47df44b97dcacdcfcfd90e38c61702ed31eb3990a`. Acceptance `ACCEPTANCE_PARTIAL`.
- **C4B eligibility:** a read-only S25 `pkgc_c4b_pre` after gate `04-C4B` (transcription
  `6ea01e8e5f6fee24877e3ddd00959de052a301b55b4fa164eb13ca94ee0980a1`, result block
  `8e9da6cbf4a5eb0f41aa272b7111c3d96e63d526675a286d09c58b914376f464`, exact), then `c4b-eligibility` =
  `PKGC_C4B_ELIGIBLE`, SHA-256 `7b239cf599f2c54e1c701be0c906cccf32f9df119f4f7356b345f18b45e250a7`: exactly
  `ACCEPTANCE_PARTIAL`, copy A exact, copy B absent.
- **C4B (S25, owner-run `pkgc_c4b`):** `ACCEPTANCE_STORE_INITIALIZED` (store B manifest
  `df7737bd6ae55a292c002e0020dfd71e2421de233aa9c2e8686115100503c6c4`), `ENVELOPE_APPENDED`, `COPIES_IDENTICAL`,
  `ACCEPTANCE=ACCEPTANCE_COMPLETE`, `FRESHNESS=AUTHENTIC:CURRENT`. Transcription SHA-256
  `94e8738aea3496bb0e9c45d57bc39102ad1b5cf9315cac95aae8cce6c0379a45`; result block
  `7c59fe6833f1eb152f11648533d30681577909fd0fe10d714a22a4a7dbf5e7b1` (24 lines); `s25-check C4B` =
  `PKGC_S25_TRANSCRIPTION_EXACT`.
- **Laptop read-back:** peer view `store-b-1` `5cb0bc77318a91a02d8890ac0ad636960d8432a387e055ba13f7eebe05ed56d1`
  (NON_CUSTODY, bound to the C4B transcription); envelope bytes identical on copies A and B; `classify-acceptance` =
  `ACCEPTANCE_COMPLETE`, evidenced record version 1; no pending files.

**Envelope 1 digest: `95da36cd6edd49c2bae244611cc429a174dee72ec2454c4f73c57a83bfcb0f0c`** (bound to record 1
version 1, the review package `2e0599d2…30c1`, previous envelope null).

## 6. The C5 gate (read-only)

Freeze facts unchanged (deploy `37945605981`, queue empty, `main` `896716e`). Acquisition `06-389151fe…` was clean.
Gate `05-C5` passed. On the laptop: freshness AUTHENTIC + CURRENT; acceptance `ACCEPTANCE_COMPLETE`; Replica A one
record `77752db1…`; store A and the store-B view each one envelope `95da36cd…`, byte-identical; the C2 and C4B
markers match; no pending file; no `C5_ACCEPTANCE.json` and no `STOP.json`. The C5 statement was rendered from the
files (five lines, SHA-256 `982dc9bae65b770899fb3e1fd98a00dff8763ef73989706ce2bf76876bf95390`) and passed
`check_text`.

## 7. C5 owner acceptance (verbatim)

Owner acceptance text SHA-256 (the text exactly as issued, one paragraph, no terminal LF):
`6161ffcd438bef1f7e030cc94569655747cd44327bb81604fdfcefd2d81060dd`.

> I accept Package C for this sequence: record 1 on Replica A and Replica B and acceptance envelope 1 on copies A and B are COMPLETED. Record 1 digest: 77752db11d80eef50eaeaa8b931d65a489bb919f9e864584fbf8d00746e2cec6. Envelope digest: 95da36cd6edd49c2bae244611cc429a174dee72ec2454c4f73c57a83bfcb0f0c. Binding SHA-256: bd1c35e79c3833710196f51186741160e81c0532632f5050fd5134fc0ca70793. Freshness: AUTHENTIC + CURRENT. Acceptance: ACCEPTANCE_COMPLETE. REGISTRY_EFFECTIVE remains NO. AUTHORITY_ACTIVE remains NO. authorityGranted remains false. The signer remains inactive. This acceptance authorizes nothing further: not HELD, the signer, authority activation, First Memory or PROD. The Package C freeze ends now.

`pkgc_operator.py record <workdir> C5 <statement> <paths>` returned `PKGC_PACKAGE_C_ACCEPTED` and wrote only
`C5_ACCEPTANCE.json`, SHA-256 `16afa08a0e5dae54d1a9dbf0cceb4857ca6bf34284515bd6a97a6d69ca4cf755` (its
`statementSha256` is the hash above). No owner record was written by C5.

**Process note (historical only).** The first `record` invocation passed the statement text where the form takes
the statement file path. It failed while reading that argument, before the statement was checked, and wrote
nothing. C5 has no attempt marker, so nothing was consumed. The second invocation, with the file path, is the
accepted C5 event.

C5 ended the Package C freeze and authorized nothing further. The owner then authorized this completion record, its
merge and the first post-C5 preservation deploy as routine preservation work (2026-10-10).

## 8. The first post-C5 deploy (not yet occurred)

Record 1 and the envelopes are not host-observable, so Package C adds no DR-5 line (record §7). The merge of this
record triggers the first post-C5 deploy. It must:

1. establish, by a fresh read-only W9 read, `W9_5_GENESIS_COMMITTED_EXACT` on the committed genesis
   `ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4`;
2. compare `EQUAL` (`mb9_operator.py dr5 <repo> W9_5_GENESIS_COMMITTED_EXACT <deploy-log>`) to the accepted
   running-witness phase-bound target: 192 lines `593c90e1778b0e90326cdf96314b328948c00b2207960d27be2b41874d05ff65`,
   DR-5 block `ace51f27ac17a2d719ec19da582d09e21f0c7fb4be7b6ec81e1dd53cb369fd5a`, pre-deploy
   `f50870420c10149914b8d2a02116708ec89ea5a8f746a847fbe88df058f54cae`;
3. leave record 1 AUTHENTIC + CURRENT and acceptance `ACCEPTANCE_COMPLETE`, with the authority boundary (§10)
   unchanged.

The deploy must not intentionally reboot the host or restart the witness or broker. A deploy or comparison that is
not exact, or any unexpected substrate or runtime drift, is a STOP and enters revalidation; it is never treated as
success. The verification is technical preservation evidence; it is not a new owner acceptance loop.

```text
FIRST_POST_C5_DEPLOY = NOT YET OCCURRED
```

## 9. Evidence seal

- Final sequence-4 evidence seal (`SHA256SUMS`, 195 entries, every evidence file except the seal files):
  `f702128b36b2fac8a3b78f4f232c55e5ec86e061cb4aa59a0a9ffec245443470`. It covers the verbatim C5 file and the C5
  closing archive.
- Preserved byte-identically beside it: the pre-C5 seal
  `709ab556a9a9f219e0ee7a9bde7f66ff7fc6715275dbd9a7b678e19baba31871` (184 entries).
- S25 evidence is `OWNER_SCREEN_TRANSCRIPTION` (record §8.4), not machine-captured: C1 transcription
  `09a1d240de1e27d1df85d655e4d45755a4ab5f81ec6e22f544b4baf00a9e795e` (result block
  `5dff460c8daa31c484801023d1c53af6e51ff8befdba1911f3e9aad26cde4e3c`), C3, C4B_PRE and C4B as in §4 and §5.

## 10. Boundaries

| Fact | State |
| --- | --- |
| Package C sequence 4 | COMPLETED / OWNER-ACCEPTED |
| Package C sequences 1, 2, 3 | ENDED / HISTORICAL / NON-REUSABLE |
| Package C freeze | ENDED by C5 |
| record 1 | PRESENT on Replica A and Replica B; AUTHENTIC + CURRENT |
| acceptance envelope 1 | PRESENT on copies A and B; `ACCEPTANCE_COMPLETE` |
| P3-5 bootstrap position | `OWNER_ACCEPTANCE_EVIDENCED` (step 11b) |
| witness genesis | COMMITTED / IRREVERSIBLE (`ac892dc2…65e4`) |
| `REGISTRY_EFFECTIVE` | **NO** |
| `AUTHORITY_ACTIVE` | **NO** |
| `authorityGranted` | false |
| signer | **INACTIVE** |
| HELD (M-B10) | **NOT WRITTEN / NOT AUTHORIZED** |
| authority activation | **NOT AUTHORIZED** |
| First Memory | **NOT AUTHORIZED**; `FIRST_MEMORY_READY` NOT REACHED |
| PROD | **NOT AUTHORIZED** |

M-B10 HELD, signer start and authority activation are later stages. Each needs its own owner authorization; none
follows from Package C completion.

**First Memory boundary.** Tooling must not infer, choose, draft or write LILITH's First Memory merely because later
bootstrap stages become technically ready. If the system eventually reaches `FIRST_MEMORY_READY`, the process
**STOPS** there. Owner discussion is required before any First Memory content is selected or written.

## 11. State

```text
PACKAGE_C = COMPLETED / OWNER-ACCEPTED
PACKAGE_C_STATE = PC5_PACKAGE_C_ACCEPTED
PACKAGE_C_SEQUENCE = e6b7a3334cda25efe9259741cda1b3ae
PACKAGE_C_CONTROL = 896716e8c7bd705bcbe6e25f154afff4ae1d4dba
PACKAGE_C_SEQUENCES_1_2_3 = ENDED / HISTORICAL / NON-REUSABLE
BINDING_SHA256 = bd1c35e79c3833710196f51186741160e81c0532632f5050fd5134fc0ca70793
RECORD_1_DIGEST = 77752db11d80eef50eaeaa8b931d65a489bb919f9e864584fbf8d00746e2cec6
RECORD_1 = PRESENT ON REPLICA A AND REPLICA B
RECORD_1_FRESHNESS = AUTHENTIC + CURRENT
ENVELOPE_1_DIGEST = 95da36cd6edd49c2bae244611cc429a174dee72ec2454c4f73c57a83bfcb0f0c
ENVELOPE_1 = PRESENT ON COPIES A AND B
ACCEPTANCE = ACCEPTANCE_COMPLETE
C4B_RESULT_BLOCK_SHA256 = 7c59fe6833f1eb152f11648533d30681577909fd0fe10d714a22a4a7dbf5e7b1
C5_GATE_SHA256 = 962aa9579a51ce607661a084017e54fae2ae0584cc019be5d3b41beba7f6b18e
C5_ACCEPTANCE_TEXT_SHA256 = 6161ffcd438bef1f7e030cc94569655747cd44327bb81604fdfcefd2d81060dd
C5_ACCEPTANCE_JSON_SHA256 = 16afa08a0e5dae54d1a9dbf0cceb4857ca6bf34284515bd6a97a6d69ca4cf755
PACKAGE_C_EVIDENCE_SEAL = f702128b36b2fac8a3b78f4f232c55e5ec86e061cb4aa59a0a9ffec245443470
PACKAGE_C_FREEZE = ENDED
WITNESS_GENESIS_DIGEST = ac892dc2b14ca7db108400258abfcf2320ff498f2a674058058e16a8a6fb65e4
WITNESS_INVOCATION_ID = 8af12bd64d024d0eba56bbcedbc534a6
FIRST_POST_C5_DEPLOY = NOT YET OCCURRED
REGISTRY_EFFECTIVE = NO
AUTHORITY_ACTIVE = NO
authorityGranted = false
SIGNER = INACTIVE
HELD = NOT WRITTEN
HELD = NOT AUTHORIZED
AUTHORITY ACTIVATION = NOT AUTHORIZED
FIRST_MEMORY = NOT AUTHORIZED
FIRST_MEMORY_READY = NOT REACHED
PROD = NOT AUTHORIZED
```
