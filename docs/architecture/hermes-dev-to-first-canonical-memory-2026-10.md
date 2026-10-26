# LILITH OS — Hermes DEV to First Canonical Memory (October 2026)

**Status:** Retrospective integration and operational handoff, updated 2026-10-26. **First real DEV canonical memory: OWNER-REPORTED PASS.** Normal Hermes-chat memory, richer autobiographical memory, and PROD promotion: **not completed**. This record does not authorize any operation.

**Purpose:** One chronological account of the work from the initial Hermes DEV conversational integration through the first persisted, newly recalled canonical L04 memory. The earlier [slice history](../research/slice-history.md) ends at **2026-09-26** and must be read as historical, not as a claim about October's live state. This record complements, rather than rewrites, the individual ADRs, PRs, transition contracts, signed owner go records, and off-repository operator evidence.

## Evidence and interpretation

- **REPO:** Merged source/contract or a recorded GitHub workflow. A green source test is not proof that the corresponding service is activated.
- **OWNER/OPERATOR-REPORTED DEV:** A read-only or owner-authorized live DEV run reported in the operator's dated, sealed local evidence. The detailed transcripts, local approvals, and original checksum-sealed files live with the owner and were not copied into this GitHub record.
- **TEST:** Offline, synthetic or simulated proof only, clearly distinct from an actual DEV admission.
- **NOT DONE:** Capability not yet demonstrated. Avoid treating a design, release artifact, memory proposal, or transcript as authoritative canonical state.

The current DEV evidence was reported after the latest source merge, so this record is deliberately a **retrospective** rather than an assertion that a GitHub commit alone installed or admitted a memory.

## 1. Identity and architectural boundary

LILITH is **one continuing governed identity**, not a Hermes model instance, persona prompt, chat session, cloud VM, Hsin expression layer, or job title. The canonical identity/memory/goals/authority owners must survive replaceable models, runtimes and hosts. Hermes is a replaceable conversation runtime. The temporary Hermes `SOUL.md` is a runtime-side projection, **not** the canonical identity or personality owner ([ADR-0008](../adr/0008-canonical-personality-ownership-soul-projection.md)); see [principles](principles.md), especially P-01/P-02/P-07.

The intended trust path is **owner intent → authenticated and action-bound consent → governed evidence issuance → durable canonical L04 admission → Privacy-gated recall**. A memory is neither an LLM inference nor a silently retained chat transcript. A legitimate Privacy FORGET continues to dominate rollback/recovery and must never be undone to reach First Memory.

## 2. Hermes live DEV baseline, F8 and F9 (approximately Oct 23–25)

**OWNER/OPERATOR-REPORTED DEV:**

1. A Hermes gateway/live-conversation path was installed and exercised on `lilith-dev-01`. F8 exercised **five synthetic conversations** through the live DEV path. The Groq allowance reached **5/5**; all subsequent steps kept the budget exhausted, with **no unapproved provider forwards**. The F8 proof was a runtime/conversation proof, **not canonical-memory admission**.
2. F9-A onboarding and F9-B logging were prepared locally. F9-C introduced Core API integration and ownership/Privacy wiring. [PR #249](https://github.com/rpahasara/lilith-os/pull/249) merged as `3f6b909f8b4c73a132c49626da585ee998cddda1` and its routine DEV deploy succeeded (operator-reported run `40174180477`).
3. The F9c2 Hermes gateway release `f293e72-f9c2` supported the owner-approved single-use Privacy/FORGET operation. The accepted synthetic run used receipt `owner-g0-f9c2-drill-20261025`: **24/24 checks**, one consumed approval, one completed suppression and receipt, **73 synthetic backup items tombstoned**, **0 live Hermes sessions and messages** afterward, and no provider calls. The historical First Interaction memory identity was suppressed and must **never** be reintroduced through a new memory proposal. This was **synthetic FORGET evidence**, not permission to delete arbitrary future memories.
4. Post-F9c2 read-only preservation checks after subsequent source/deploy changes reported no change in receipt, suppression epoch, tombstone, protected signer/witness/broker state or Groq exhaustion.

**REPO:** [PR #249](https://github.com/rpahasara/lilith-os/pull/249), Core API modules `hermes_erasure_owner.py`, `hermes_erasure_spool.py`, `privacy_forget_runner.py`, `privacy_forget_intent.py`, and the F9-C tests. The direct Hermes runtime installation and full F8/F9c2 transcripts are **off-repository operator evidence**, not independently established solely by this PR.

## 3. Track B Privacy rollback protection and E-23 (Oct 25–26)

### 3.1 Source and release

- [PR #251](https://github.com/rpahasara/lilith-os/pull/251), merge `57bff671fbfe5df4e59248d5d69338dc0ba05846`: K-PAN witness Privacy anchor and K-PCK owner-side checkpoint contracts, fail-closed freshness rules, release layout V2 and the E-23 transition contract. K-PAN and K-PCK are **separate** from existing K-WIT and K-ROOT authority; no key authority is silently transferred.
- [PR #252](https://github.com/rpahasara/lilith-os/pull/252): reproducible pinned E-23 release. New archive SHA-256 `a8cadbfa75023ed19c6939b17841e56f1ad9d0b83a6f854755621e32ed174486`, manifest SHA-256 `fc29a23cbb411704f2799b418f8c7fd7fadf215489174e9ac9d370db2e78368c`.
- [PR #253](https://github.com/rpahasara/lilith-os/pull/253): bounded E0→E8 operator and host-transition stages, each critical mutation requiring separate owner approval. No automatic deployment from opening the PR.
- [PR #254](https://github.com/rpahasara/lilith-os/pull/254): corrected E5 anchor-directory group comparison. The E5 host change had already succeeded but the classifier incorrectly compared the new anchor's witness-primary group with the older witness-state directory's signer group. The one consumed E5 attempt was adjudicated against exact evidence, not retried.
- [PR #255](https://github.com/rpahasara/lilith-os/pull/255), merge `0cb7e4ea96d53c8b448281adc681744350661951`: E-23 completion and installed-release re-pins. DEV deploy `40228604800` on that SHA succeeded; post-deploy **E23_DR5=EQUAL** across result, DR5, and predeploy blocks. See [E-23 completion](trackb-e23-completion.md).

### 3.2 Live activation

**OWNER/OPERATOR-REPORTED DEV:**

- Encrypted DEV_SYNTHETIC K-PAN credential `kpan.dev-synthetic.01` was generated once, loaded by the replacement witness alongside the existing K-WIT. E-23 ended at `E8_OLD_RETIRED`: signer and witness accepted from `57bff671…`; OLD release `129f2bed…` retired. No unauthorized restarts or changed protected services were reported.
- [PR #256](https://github.com/rpahasara/lilith-os/pull/256), merge `d3cd8d6f22aa6bf3058489cd366abb27828f1c74`: root Privacy host-step integration, mandatory FORGET durability barrier, owner checkpoint/unlock and focused synthetic proof ([source record](trackb-privacy-activation.md)).
- The intended `data/privacy_governance.dev.db` was **absent**, while the historical F9c2 Privacy suppression/receipt was in `/home/lilith/.hermes/lilith-os-dev/f9-drill/privacy_governance.f9drill.db`. DEV activation explicitly bound to the latter *existing file* for the first-memory proof; a second DB at the old path is a STOP.
- Installed the K-PAN and owner-side K-PCK **public pins**, ran witness **anchor genesis v1** over the one historical F9c2 suppression (anchor digest `c3c0dc33b2a4036637da2a9f2148aebe7aac3f7de608827ca799ae7a00fdd023`), signed **off-host checkpoint seq 1** (digest `abc549e1c9a8f73a4b9d5d6ceee34902c8fe1bbfb3ec3a78966ef6c617a1e01f`), and performed the owner-signed challenge/unlock for boot `cb0d71da-32a7-402b-b85e-5748da012bff`.
- Privacy gate and durability were **READY**, anchor CURRENT, pending entries **zero**, custody **one checkpoint / zero alarms**. Private K-PCK stayed on the owner device. The boot marker is **tmpfs-bound**: reboot requires a fresh challenge and owner unlock; this record does **not** assert that a previous boot marker remains valid after reboot.
- Offline rollback, divergence, replay, forged state and pending-FORGET refusals were tested; a live destructive rollback experiment was **not** run.

**Important:** An anchored and checkpointed Privacy set is not automatically unlocked. FRESH means the held local set equals its anchored/checkpointed authority at the moment checked; it is not a permanent waiver of future Privacy checks.

## 4. Unblocking genuine First Memory source (Oct 26)

### 4.1 Minimum offline path

- [PR #257](https://github.com/rpahasara/lilith-os/pull/257), merge `45fc25074520d7641b8cd6f01cc900dd41445b2b`: minimum `first_memory_conversation.py` composition, governed RR-39 DEV_SYNTHETIC owner-evidence issuance and release layout V3.
- The original First Interaction identity had been FORGOTTEN. The valid initial tuple instead used **`SYNTHETIC_PROJECT_CODENAME_FACT / project.synthetic / codename`**, with the existing restricted project-codename signer purpose; it did **not** resurrect the forgotten identity.
- The old signer refused all `ISSUE_OWNER_EVIDENCE` requests (RR-39). Source then reused the evidence minter, root-verified hold/readiness, signed registry, recovery witness, durable single-use ledger and owner-proof verifier. The local offline proof admitted/recalled one fact with synthetic custody, *not* a live DEV signing claim. The DEV software owner credential remains **synthetic key-possession proof**, not hardware-backed real-human user verification.
- [PR #258](https://github.com/rpahasara/lilith-os/pull/258), merge `e2324a5f89200aa5f374c4a43a13cb76b36376f9`: final DEV vertical slice. The narrow root bridge executes trusted root-controlled release code while the memory host runs permanently as unprivileged `lilith` with no supplementary groups. Adds signer issuance/use transport, owner-device credential tooling, L04 admission-link migration and separate DEV CLI host. The host deliberately **does not import memory into `/os/conversation`**, preserving the relay boundary. Synthetic tests covered no-consent, forged proof, wrong boot, stale Privacy, FORGET and fresh-session recall.
- The release built from `e2324a5…` was reproducible on Windows/WSL: archive SHA-256 begins `6924ed9f`, manifest SHA-256 `a2f32664133bf3aff48f621e475f4b8455c3cff51ddb029df53c45ab191db859`. Rehearsal packages from earlier commits were **not** installed as the final release.

### 4.2 FM-1 signer/witness installation

**REPO:** [PR #259](https://github.com/rpahasara/lilith-os/pull/259), merge `7702b01243427006f952448f2945686ed9d04793`, provided the FM-1 F0→F7 transition contract and operator, without a routine Core API deployment. Both signer **and witness** needed controlled restart because the witness's unchanged unit also follows shared `current`: leaving it running from OLD would permit an unapproved switch if restarted later.

**OWNER/OPERATOR-REPORTED DEV:**

- F0 preflight exact. Transferred/staged NEW alongside OLD; F1 reached, but the Windows Cloud SDK `plink` 0.83 crashed **after** a successful read-only post-status, so the operator recorded STOP despite a clean independent F1 read. [PR #260](https://github.com/rpahasara/lilith-os/pull/260) precisely adjudicated that **consumed** STAGE record without staging again.
- F2 signer stopped; F3 witness stopped; F4 selector switched to NEW while both units stopped. F5 witness start succeeded once with unchanged K-WIT and K-PAN. The same client-side `plink` exit crash occurred on its post-read; an independent clean F5 read established the real state. [PR #261](https://github.com/rpahasara/lilith-os/pull/261), merge `99fe28196db365e85ecedfda3f992a9bbcc24c8a`, adjudicated exactly that second consumed STOP and provided **at most one independent clean read-only recheck** for future post-status crashes. A crashed mutation is **never** treated as successful.
- Witness verified and owner-accepted: `efa7040c6ad94de69bfeadd496ba1ac3` / PID 294978, from NEW with K-WIT + K-PAN loaded. Signer started once (fourth K-ACT load), verified and owner-accepted: `5e439b2dfd434367a14ac5870b9a6316` / PID 298274, from NEW.
- F7 `OLD_RETIRED` passed with no process using OLD (cwd/executable/mappings checked). Only `e2324a5…` remained installed and selected. The existing Privacy chain, marker/hold, F9c2 FORGET evidence and protected foreign services were reported unchanged.

## 5. Owner credential, actual canonical admission and independent recall (Oct 26)

**OWNER/OPERATOR-REPORTED DEV; not claimed solely by a source PR:**

1. Generated one owner-device **DEV_SYNTHETIC software P-256 credential**. The private key stayed on the owner's WSL device. Installed only its verified public registration, bound to release `e2324a5…`.
2. Installed a hash-checked, root-owned host source tree; took a verified L04 cognitive DB backup; applied **one** admission-link-table migration, starting with zero links and admissions; installed the canonical configuration with creation **DISABLED**.
3. A separate real CLI root-bridge recall dry-run initially refused with `PRIVACY_FRESHNESS_NOT_READY:FORGET_INTENT_PENDING`: the permanently unprivileged `lilith` process could not list the root/`lilith-forget` intent directory and correctly failed closed. The owner authorized a minimal read/traverse ACL for `lilith` on `/var/lib/hermes-forget/intent` (no write permission); the pinned Ubuntu `acl` package was installed with service restart suppression. A new recall dry-run returned `NOTHING_RECALLED` with creation still disabled and no memory written.
4. The owner selected the exact normalized codename **`Hello Lilith. Your story begins here`**. Comma punctuation was refused by the existing codename validator; the final string, with a period, passed unchanged.
5. Under the explicit single-use `FM-GO-FIRST-MEMORY`, creation was enabled **only for the codename capability**. The DEV host offered the exact utterance `remember my project codename is Hello Lilith. Your story begins here`; the owner-device credential signed that offer's challenge; the real installed signer issued governed evidence, and the adapter reserved/committed/confirmed exactly one canonical memory admission and link.
6. **FIRST_MEMORY_DEV = PASS**, as reported from live DEV: admission `madm.ccb20162be02446fa1d60737c37e56fe`, revision `mrev.633aeba39dbc49d794c5e36d914c6ff2`; stored JSON `{"codename":"Hello Lilith. Your story begins here"}`. L04 held exactly **1 admission, 1 revision, 1 link**. Signer ledger reached seq **6**, consistent; witness CONSISTENT.
7. The initial process exited. A completely fresh CLI-root-bridge process/composition/session `fm-fresh-recall-s2` asked `What is my project codename?` and returned **`RECALLED: Hello Lilith. Your story begins here`** via canonical L04 and the accepted-memory read facade. No Hermes transcript or previous-session state supplied the answer. Recall was read-only; the ledger remained at seq 6.
8. Privacy gate/durability were READY on that boot; anchor v1 and checkpoint seq 1, suppression, FORGET receipt, tombstone, epoch log and provider budget were reported unchanged. No PROD operation occurred. The owner evidence folder contains `RESULT.md` and `SHA256SUMS.seal-11` (reported prefix `60c1fdac`).

**Creation closed again (OWNER/OPERATOR-REPORTED DEV):** Creation stayed ENABLED after admission until a separate single-use owner go, `FM-GO-CREATION-DISABLE` (`4edd949d`), replaced the canonical configuration with the DISABLED form (SHA-256 prefix `4fa82ae6`, `canonicalLtmEnabled=false`, no active capabilities). Afterwards L04 still held exactly 1 admission and 1 link, a further fresh recall session `fm-post-disable-recall-s3` returned the same value (a read does not need the mutate capability), and the ledger stayed at seq 6. The owner evidence folder records this as `SHA256SUMS.seal-12-disabled` (prefix `1c90147c`). The admitted memory was not deleted, revoked or forgotten. This record does not claim any later DEV state.

## 6. What this proves — and what it does not

**Proven/reported:** DEV has executed one governed, owner-device-signed, Privacy-gated canonical L04 codename admission; a fresh independently created CLI session retrieved its exact value; consent, signer ledger, accepted-memory facade and historical FORGET constraints remained in effect.

**Not proven / still open:**

- Natural **Hermes** chat has not yet been wired to this canonical memory service. The proof used an explicit DEV **CLI bridge**, not ordinary Hermes conversation.
- The codename value is a **project fact**, not a governed autobiographical/relationship/origin memory. Its welcome-like text is **not** itself a canonical personality/identity mutation. Meaningful personal memory needs a *new, narrow governed memory capability*, provenance and consent; don't mislabel a 64-character codename as a complete autobiographical system.
- The DEV owner software authenticator proves synthetic **key possession**, not real-world human identity with hardware/platform user verification.
- No PROD promotion, DEV→PROD memory transfer, whole-machine resilience claim, model/provider portability in production, or current PROD feature inventory is established by this DEV result.
- This result does not establish that the legacy original PROD cognitive stack (world model, working memory, goals, reasoning, global workspace, motivation, planning, ethics) is currently equivalent to DEV. That requires a **fresh read-only inventory** of both VMs.
- No later privacy boot-unlock state is implied by the accepted current-boot report.

## 7. Minimal next work, in priority order

1. **Close the live admission:** done. Codename creation is DISABLED again (go `4edd949d`, seal-12) and the admitted memory and its recall are preserved. Do not repeat the admission.
2. **Hermes canonical-memory read integration on DEV:** connect a scoped Hermes conversational client to the already-governed read facade. Maintain the `/os/conversation` boundary, no automatic transcript dump, no additional identity or authority. Verify natural new-chat recall without the CLI shortcut.
3. **Meaningful origin/relationship memory on DEV:** define one typed governed personal-memory capability with exact owner-provided text, provenance, revision, sensitivity, explicit authenticated consent, safe retrieval and FORGET semantics. Reuse L04, the signer, the witness/ledger, and Privacy. No new independent agent, generic memory platform or unreviewed auto-admission. Start with one intentionally approved origin memory, then recall it across independent conversations.
4. **DEV vs original PROD reconciliation:** read-only inventory **both** machines before proposing any promotion. PROD may retain earlier PROD-only world-model/working-memory/goals/planning/ethics capabilities that DEV lacks; DEV now has newer Hermes, synthetic signer and anchored Privacy. Record diffs for source, units, artifacts, data schemas, cognitive features, memory provenance, secrets/custody, DR-5, runtime/provider config and backup/rollback. Do not assume `main` equals either live VM.
5. **Owner-controlled PROD promotion:** propose selective, reversible, environment-correct changes; migrate approved features in dependency order, retain PROD canonical history, legitimate FORGET, independent PROD keys/trust/credentials, and owner-approved memories. **Never clone a DEV_SYNTHETIC DB, software credential, VM disk, boot marker or anchor directly into PROD.** Preserve the approved memory's content/provenance only through an explicitly approved PROD-native admission/migration contract with separate real owner authorization.
6. **Beyond First Memory:** resume richer cognition/autonomy and personal presence engineering **on DEV**, verify each useful slice, then promote only successful reviewed slices to PROD under separate go. Preserve LILITH as one identity above model, Hermes, Hsin and hosting.

## 8. High-value references

| Subject | Source |
| --- | --- |
| Historical baseline through September | [slice-history.md](../research/slice-history.md) |
| Replaceable Hermes persona | [ADR-0008](../adr/0008-canonical-personality-ownership-soul-projection.md) |
| Architectural continuity, truth and privacy | [principles](principles.md) |
| F9-C Hermes Privacy ownership | [PR #249](https://github.com/rpahasara/lilith-os/pull/249) |
| Track B rollback anchor | [PR #251](https://github.com/rpahasara/lilith-os/pull/251) |
| E-23 operational transition | [E-23 completion](trackb-e23-completion.md) |
| Activated Privacy source | [Track B Privacy activation](trackb-privacy-activation.md), [PR #256](https://github.com/rpahasara/lilith-os/pull/256) |
| Governed issuance and First Memory composition | [PR #257](https://github.com/rpahasara/lilith-os/pull/257) |
| Final First Memory source and privilege fix | [First Memory vertical slice](first-memory-dev-vertical-slice.md), [PR #258](https://github.com/rpahasara/lilith-os/pull/258) |
| FM-1 transition tooling, incidents and exact adjudications | [FM-1 transition](first-memory-fm1-release-transition.md), [PR #259](https://github.com/rpahasara/lilith-os/pull/259), [PR #260](https://github.com/rpahasara/lilith-os/pull/260), [PR #261](https://github.com/rpahasara/lilith-os/pull/261) |

**Note to future operators:** Some earlier source-only records still say “no live memory” or “Privacy not activated”. Those labels describe their original **time and change scope**. They must not override the later bounded owner-reported DEV acceptance in this retrospective. Equally, this retrospective cannot be substituted for the original signed and checksum-sealed operational evidence when a future promotion requires cryptographic provenance.
