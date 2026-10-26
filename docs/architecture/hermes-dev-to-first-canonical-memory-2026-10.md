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


---

# Detailed continuity journal — operational decisions, proof and follow-on source

These sections expand the chronological summary above. Their purpose is to preserve the engineering reasons for decisions, the exact stopped-versus-completed distinctions, and what a future developer must **not** accidentally repeat. They do not turn a reported live run into evidence independently fetched from a VM.

## 9. Timeline and PR crosswalk (chronological source record)

| Time, Oct 2026 | Repo source milestone | What became possible, or remained blocked |
| --- | --- | --- |
| ~23–25 | Hermes DEV F8/F9 work, gateway release f293e72-f9c2 | Synthetic conversational DEV integration; separate Hermes conversation storage; provider limit exhausted at Groq 5/5; no canonical admission |
| 24–25 | #249 F9-C, merge 3f6b909 | Core API ownership, Privacy erasure and suppression integration; preserved one-time F9c2 synthetic FORGET |
| 25 | #251, merge 57bff671 | K-PAN witness Privacy anchor, K-PCK checkpoint and freshness fail-closed contracts; no live activation by merge alone |
| 25 | #252 and #253, merge 7684666 | Attested E-23 release and operator tooling for live witness/signer replacement |
| 25 | #254, merge 571eb46 | Corrected E5 witness-owner/group classifier, exact consumed-record adjudication, control-only no deploy |
| 25 | #255, merge 0cb7e4e | E-23 installed release completion and DR-5 target; run 40228604800 gave EQUAL |
| 25–26 | #256, merge d3cd8d6 | Privacy root host steps and mandatory durable-before-FORGET barrier; subsequent live genesis, owner checkpoint and boot unlock approved separately |
| 26 | #257, merge 45fc250 | First Memory composition, governed RR-39 synthetic owner evidence, release layout V3 |
| 26 | #258, merge e2324a5 | DEV signer issuance wiring, evidence-use operations, narrow root-privileged bridge, unprivileged memory host, owner-device credential and L04 migration tooling |
| 26 | #259, merge 7702b01 | FM-1 controlled signer/witness shared-selector transition tools; this was tooling, not the live transition |
| 26 | #260, merge 33b3ab4 | Exact adjudication of a successful-but-STOP-recorded FM-1 stage after Windows plink crash |
| 26 | #261, merge 99fe281 | Exact FM-1 WITNESS_START adjudication, plus single clean read-only recheck for post-status Windows plink crash |
| 26, operator-reported | FM-1 F7, owner credential, ACL, live First Memory | First admitted L04 codename and fresh-session CLI recall; later creation returned DISABLED and recall still succeeded |
| 26, draft | #262, history documentation | This one-file continuity record; source-only, no mutation or approval |
| 26, draft | #263, relationship-origin source | New typed, governed personal-memory family and read-only Hermes context adapter **offline only**; no origin text provided or admitted |

The PR list is not a substitute for the actual install record. For example, the final DEV CLI First Memory admission and owner-side signing were out-of-repository owner-approved operations. Likewise the future production service inventory cannot be read from GitHub alone.

## 10. The Hermes/F9c2 baseline worth preserving

**Topology and ownership.** The F8/F9 path separated Hermes gateway conversation state, the provider gate, Core API ownership/Privacy state, and canonical L04. The runtime text/persona and ordinary transcript were not made canonical identity. The gateway was an untrusted, replaceable consumer; Privacy/FORGET must erase or suppress live and backup conversational traces rather than allowing them to become a new memory. The Core API relay import boundary remained protected.

**F8 versus First Memory.** Five live synthetic conversations were useful proof of provider/gateway interaction but never proved memory admission, authority, or cross-session canonical recall. After all five Groq allowance slots were exhausted, the owner declined more calls until a new exact approval. Do not confuse synthetic role-play continuity with durable L04 truth.

**F9c2 one-time FORGET event.** DEV synthetic approval and receipt name: owner-g0-f9c2-drill-20261025. The live operator reported 24/24 PASS checks, 73 synthetic backup items tombstoned, zero remaining live Hermes sessions/messages, suppression epoch 1, one canonical Privacy suppression row and receipt, no outstanding intent, no extra provider forwards. The forgotten selector was FIRST_INTERACTION_IDENTITY. The preserved legacy approval was consumed exactly once. Subsequent source changes deliberately left the suppression/tombstone/receipt intact. A new memory family MUST NOT reuse that forgotten identity.

**Isolation that mattered later.** The historical F9c2 Privacy DB and L04 cognitive DB were under the DEV Hermes F9-drill tree, not under the stale Core API durability-probe path. The First Memory toolchain deliberately bound the existing F9-drill Privacy DB rather than fabricating a second source of truth. Other deployed units (provider gate, gateway and broker) kept their accepted process identities during the E-23 and FM-1 freezes.

**Operability note.** A source-only PR or a green CI job does not say the live Hermes service was reconfigured. First Memory's only proven live conversational interface at this point was the separate CLI root bridge; Hermes-native natural-chat recall was still an engineering objective.

## 11. E-23 transition and Privacy activation: detailed run notes

### E-23 authority release and failure recovery

The release replacement sequence was **old 129f2bed… → new 57bff671…**, with explicit single-use step markers and per-step owner gos. Each stage was allowed only from its exact preceding phase. The witness payload and authority custody were protected, with the **K-PAN** credential separately added for witness Privacy anchoring.

| Phase | Concrete operation and result |
| --- | --- |
| E0 → E1 | One attested archive/stamp transfer and one STAGE. NEW staged beside OLD; current still OLD, units unchanged |
| E1 → E2 | SIGNER_STOP: signer service/socket stopped; witness still ran OLD |
| E2 → E3 | WITNESS_STOP: witness service plus two sockets stopped |
| E3 → E4 | SELECT: current switched to new 57bff671 while all authority units inactive |
| E4 → E5 | WITNESS_UNITS: new unit/tmpfiles bytes installed, host daemon-reload performed, correct 0700 anchor directory created, but status classified it MIXED and reported STOP |
| E5 adjudication | A read-only stat proved anchor owner/group lilith-recovery-witness:lilith-recovery-witness 0700; older witness state directory was lilith-recovery-witness:lilith-authority-dev 2750. Tool's comparison, **not the host install**, was wrong. #254 fixed it and pinned the exact consumed E5 STOP; E5 never ran again |
| E5 → E6 | WITNESS_START: replacement witness 86ba4cc2…/281470, K-WIT and K-PAN loaded; verified and owner-accepted |
| E6 → E7 | SIGNER_START: replacement signer 639a814d…/281830, third K-ACT DEV_SYNTHETIC load; verified and owner-accepted |
| E7 → E8 | RETIRE: OLD tree removed after checking for no process using it |
| Post-E8 | #255 made accepted post-transition installed-release re-pins; DEV deploy 40228604800 succeeded and DR-5 comparison was EQUAL |

The E-23 E5 incident illustrates a critical rule: a tool STOP is not proof that a remote operation failed. The host effect must be examined read-only before any recovery decision. Never repeat a consumed mutation to turn its bookkeeping green.

**Pinned public/custody distinctions.** The owner generated K-PCK on the owner WSL device; K-PAN was a separate DEV_SYNTHETIC encrypted credential installed for the witness. K-PAN key id kpan.dev-synthetic.01 had public fingerprint SHA-256 a9a4dfdc9d989fe1064e7b17e101f5ae1307f7cf686212fc36ffa19b75de984a; K-PCK key id kpck.dev-synthetic.01 used its separate off-host private custody and pin. None of these is an interchangeable K-ROOT/K-WIT signer credential. No private key belongs in this Markdown record.

### Live Privacy activation (separate approvals after E-23)

1. **Readiness:** Confirmed the earlier expected data/privacy_governance.dev.db was missing, while the **real historical suppression entry** lived in /home/lilith/.hermes/lilith-os-dev/f9-drill/privacy_governance.f9drill.db. The owner chose to anchor the latter existing DB, matching the one prior FORGET receipt; the activation driver pinned the DB inode and failed if the stale path appeared. No automatic SQLite DB creation was authorized.
2. **PINS:** Installed two public pin files under /etc/lilith-privacy-fresh, no private material and no restart. The exact files were independently hash checked.
3. **GENESIS:** One witness K-PAN genesis at anchor v1 over exactly one old F9c2 suppression. Anchor digest c3c0dc33b2a4036637da2a9f2148aebe7aac3f7de608827ca799ae7a00fdd023. The existing local Privacy set head was fd00181cc766a336510d20cdb75975bd5c8f6ea48a473b96ecf207e574df5e6c. The chain file was witness-owned, with no other unexpected entry.
4. **Owner CHECKPOINT:** One owner-signed K-PCK checkpoint seq 1 over the exact anchor; checkpoint digest abc549e1c9a8f73a4b9d5d6ceee34902c8fe1bbfb3ec3a78966ef6c617a1e01f; off-host custody had one checkpoint and zero alarms.
5. **BOOT UNLOCK:** DEV root issued a single-use challenge for boot cb0d71da-32a7-402b-b85e-5748da012bff. The owner WSL tool verified FRESH against the actual chain/checkpoint and signed the matching unlock. DEV verified it and wrote the current-boot marker /run/lilith-privacy-fresh/verified, root-controlled on tmpfs, consuming the challenge.
6. **READY:** Gate and durability READY, anchored suppression current, zero pending entries. The live step did **not** exercise an intentional older-VM rollback; forged/older/diverged/replayed/unverifiable cases were covered by offline integration tests.

**Why this was necessary.** A VM backup can restore a database to an older state after a legitimate FORGET. The off-host owner checkpoint and witness-held anchor prevent treating that old restored copy as authorized memory. The rule is **Privacy FORGET outranks stale restored memory**, regardless of whether the OS restore otherwise succeeds. Anchor genesis was over an already-forgotten historical selector, not over an empty fabricated history.

**Operational detail:** The SQLite root read created a harmless empty WAL and shared-memory sidecar beside the F9c2 Privacy DB, with the database contents remaining unchanged. After a reboot the tmpfs marker disappears; a fresh owner unlock is required. A checkpoint is not a substitute for that current-boot gate.

## 12. RR-39, release V3 and the real First Memory trust path

**Initial reason for PARTIAL.** The first-memory composition existed offline, but the installed signer rejected ISSUE_OWNER_EVIDENCE in every runtime state (RR-39): no issuer wired, minter not constructed, and ledger writer lacked the issuance operation. Owner proof in its original test context was also not valid for fixed DEV synthetic identity/environment. The new path could not bypass that with an LLM utterance, test broker or handwritten DB rows.

**Source solution.** RR-39 added a registry-bound, challenge-specific, single-use signed OwnerEvidenceV2 flow. The signer checks the registered public owner credential and proof, signed registry/key, epoch, action, hold-store snapshot, ledger/witness consistency and purpose; writes PREPARE/CONSUME/ISSUE; and withholds evidence if the witness cannot confirm. The First Memory vertical subsequently added RESERVE/CONFIRM/ABANDON and read-only LOOKUP, so applying a memory consumes one evidence use instead of creating an ungoverned second authority.

**Privilege incident before activation.** The first proposed host dropped only effective uid and could recover root while importing source from a staged tree. That would have let application-owned code cross into root authority. PR #258 corrected it: the root-controlled release bridge performs the root-only signer/hold operations and permanently drops the host's real/effective/saved uid/gid to lilith, with no supplementary groups. An inherited one-shot fd 3 carries only the closed signer operations. The bridge refuses symlinks or group/other-writable code paths, accepts no arbitrary path/command, and supplies the root-trusted complete hold snapshot itself. The application host never temporarily regains root.

**No shortcut in the conversation relay.** The existing app.py /os/conversation protection forbids direct lilith_memory imports. The separately staged DEV host was the reviewed composition. It used both the historical F9c2 Privacy database and the existing canonical L04 cognitive database with the freshness-gated hold resolver.

**V3 release shape.** The final, attested release was built from PR #258 merge e2324a5f89200aa5f374c4a43a13cb76b36376f9, not from a throwaway rehearsal commit: manifest a2f32664133bf3aff48f621e475f4b8455c3cff51ddb029df53c45ab191db859; archive SHA-256 prefix 6924ed9f; Windows/WSL reproducible and attestation check PASS. The E-23 and closed historical layouts/installers were left intact.

## 13. FM-1 live DEV deployment: detailed operator incidents

The post-#258 signer release needed an FM-1-specific governed transition because the E-22/E-23 tools pinned different OLD/NEW pairs. The witness was **also stopped** before changing the shared current selector, even though its payload was unchanged: if it had restarted automatically while OLD was selected, the resulting executable path would have silently changed.

| Phase | Reported state and decision |
| --- | --- |
| F0 | Only OLD 57bff671 installed, selected; signer 639a814d…/281830, witness 86ba4cc2…/281470 running. Hold RELEASED, ledger consistent, Privacy READY, anchor v1 intact. Archive/stamp transfer verified separately |
| F1 | One STAGE succeeded on DEV and produced F1_NEW_STAGED, but Windows plink 0.83 returned process-exit crash 0xC0000005 for the local post-status read. One independent clean F1 read showed the same bytes. Operator recorded STAGE_STOP; marker consumed |
| F1 adjudication | PR #260 added an exact SHA-256 adjudication of consumed STEP.json b82b4a5b94451313b84818860a5b8d0e06fc4815c275966c8b35d252f5e7fb4e. It counted as reached **for the chain only**, not as a retry authorization |
| F2 | SIGNER_STOP ran once: signer and socket inactive, witness still OLD |
| F3 | WITNESS_STOP ran once: service + both sockets inactive, no process using OLD |
| F4 | SELECT ran once: current → e2324a5; signer and witness still stopped; K-WIT, K-PAN and Privacy anchor unchanged |
| F5 | WITNESS_START ran once and actually succeeded: replacement efa7040c…/294978 with K-WIT + K-PAN. Post-read hit the same 0xC0000005 plink crash; an independent clean read again proved F5. Operator recorded another STOP, without repeating start |
| F5 adjudication | PR #261 pinned consumed WITNESS_START STEP.json 61e7624d971c1e5eddfd15b46a0ebfcbe0a17245c68eff8385d0a5555d62c2fa. It also allowed one clean independent read-only recheck ONLY after a mutation had itself returned rc 0 and the following status read had exactly the known client crash. It never treats crashed bytes as proof; a second crash or a crashed mutation remains STOP |
| WITNESS VERIFIED | Fresh proof against F0, no reasons; owner accepted witness efa7040c…/294978; privacy and foreign units unchanged |
| F6 | SIGNER_START ran once: replacement signer 5e439b2d…/298274 with owner-actor-signing-key, fourth K-ACT DEV_SYNTHETIC load; verified and owner accepted |
| F7 | RETIRE ran once after the two accepted processes were observed on NEW and no process used OLD executable/mappings/cwd; only new e2324a5 installed and selected |

**Transport lesson:** The only reviewed Windows control routes used the same pinned plink client. Adding an unapproved alternative SSH key/host trust would have created a new security boundary. The minimum adopted recovery was an independent clean read with no mutation retry and only under the exact known exit-crash circumstance. Do not “fix” a status crash by rerunning the original destructive action.

**F0 baseline preserved:** The Core API, Hermes gateway, provider gate and broker process identities, credential metadata, Privacy anchor and checkpoint, F9c2 receipt/tombstone and exhausted Groq ledger remained unchanged through FM-1, as reported by the operator. The signer/witness were intentionally restarted through the approved release sequence and individually accepted.

## 14. Actual DEV First Memory: setup, access defect and final proof

### Credential, installation and schema

The owner approved one owner-device-only P-256 synthetic software credential creation and one DEV setup bundle. The DEV credential id was ocred.dev-synthetic.4b456d5206ba4bee; only public registration was sent to DEV and bound to release e2324a5. The private key remained a root-permissioned file on the owner WSL device. Proof of possession and the registration parser passed. **No claim of browser/hardware-backed biometric verification was made.**

On DEV, the operator installed a root-controlled first-memory host tree and the public registration, backed up the cognitive L04 DB and applied a single admission-link-table migration. Configuration started with canonicalLtmEnabled=false and no active capabilities. The signer and witness stayed running, and zero admissions/links were present immediately after setup.

### Read-permission defect and bounded remediation

The first root-bridge recall dry-run was refused, **not** because a real FORGET was pending, but because the permanently dropped lilith host could not prove the intent directory was empty. The intent directory was root:lilith-forget with mode 1770; the host had no supplementary group membership. The Privacy gate correctly reported a pending/unverifiable intent rather than ignoring permission denied.

A locally approved, narrowly scoped DEV root operation installed the Ubuntu acl package 2.3.2-1build1.1 with needrestart suspended and granted only **user:lilith:r-x** on /var/lib/hermes-forget/intent. The lilith host could then list/traverse but **could not create, replace or delete** an intent; actual intent file bodies remained separately permission-protected. Services/Privacy receipts were unchanged. The next read-only recall returned NOTHING_RECALLED — the correct baseline with zero memories.

**Do not repair this with supplementary groups.** That alternative would re-grant write reach over the forget spool to the unprivileged memory host and would require another signer release. The bounded ACL was a measured read-only exception, not a general Privacy relaxation.

### Exact first memory and result

| Field | Owner-reported result |
| --- | --- |
| Owner's final value | **Hello Lilith. Your story begins here** |
| Why a period | Commas were rejected by the closed codename normalizer. The exact final 36-character phrase passed unchanged |
| Typed memory | SYNTHETIC_PROJECT_CODENAME_FACT / project.synthetic / codename |
| Approved utterance | remember my project codename is Hello Lilith. Your story begins here |
| Creation gate | Owner-authorized enable for the codename capability only; no new family or general transcript capture |
| Owner proof | One registered DEV_SYNTHETIC WSL software-key signature over the challenge, verified by the live signer |
| Evidence | aev.7732670f… (operator-reported prefix), ledger uses witnessed and single-use |
| Admission | madm.ccb20162be02446fa1d60737c37e56fe |
| Revision | mrev.633aeba39dbc49d794c5e36d914c6ff2 |
| Stored JSON | {"codename":"Hello Lilith. Your story begins here"} |
| L04 counts | One admission, one canonical revision, one admission link |
| Ledger afterward | Sequence 6, internally consistent and witness CONSISTENT |
| New-session test | Session fm-fresh-recall-s2 in an independent bridge process/composition, asked "What is my project codename?" |
| New-session answer | **RECALLED: Hello Lilith. Your story begins here**; evidence-use lookup read-only, no ledger increment |
| Privacy | READY for the then-current boot, no new anchor/suppression or FORGET changes |
| Later safe state | The owner authorized FM-GO-CREATION-DISABLE (SHA-256 prefix 4edd949d). New admissions DISABLED again; another new-session recall still worked afterward (operator seal-12) |
| Scope | **DEV CLI first canonical memory proved**; no ordinary Hermes chat integration, no real-world human identity attestation, no PROD |

The codename is a **project fact containing a poetic welcome sentence**. It is not a formal identity-profile edit, autobiographical episode, or declaration that LILITH has experienced the welcome as a person. Its value nevertheless makes a meaningful historical marker for the first persisted governed DEV memory.

### The real single-source-of-truth proof

The initiating host process was gone at the time of recall. The fresh host used canonical L04 via the accepted-memory read facade and current Privacy gate; no session transcript storage or Hermes history table fed the answer. Future models and runtimes should read the same canonical source, subject to authority/Privacy, rather than duplicating the fact into a SOUL prompt.

### Durable evidence locator

The operator's working evidence folder is reported as:
**C:\Users\edufo\lilith-fm1-transition-7702b01\**.
Final summary: RESULT.md; first-memory acceptance seal: SHA256SUMS.seal-11 (prefix 60c1fdac); later disable + read-only recall seal: SHA256SUMS.seal-12 (prefix 1c90147c). These remain **off-repository evidence references**, not files embedded into this Markdown. Never publish credentials/private keys or copy operational DBs merely to fill a documentation gap.

## 15. Next owner-origin memory source: PR #263 (Oct 26, draft)

After the First Memory success, the user asked for a **genuine personal/relationship-origin memory**—not another codename pretending to be biography. The user has **not supplied** any relationship-origin text and has not approved any personal-memory admission. This must remain explicit in every future handoff.

**Source:** [PR #263](https://github.com/rpahasara/lilith-os/pull/263) at commit e4ef8b62cb00d7ad0d93bb05a40f7fb82248bb56, opened against main, unmerged. Its local source tests and report are not live DEV activation.

| Property | Proposed narrow contract |
| --- | --- |
| New identity | OWNER_PROVIDED_RELATIONSHIP_ORIGIN / lilith.core.relationship / origin.owner-statement |
| Purpose | LONG_TERM_OWNER_RELATIONSHIP_ORIGIN_RECALL |
| Capability | canonical_memory.relationship_origin.create (CREATE only) |
| Input | The owner's own statement, NFC-normalized and trimmed, maximum 600 characters; never invented, silently rephrased or auto-admitted |
| Provenance | USER_ASSERTED (the owner's assertion, not demonstrated objective biography) |
| Sensitivity | OWNER_PERSONAL |
| Offer directive | remember our origin: … |
| Recall directive | what is our origin? |
| Durable storage | Existing governed L04 rows, evidence-use ledger/witness, action-bound consent, new owner-ledger schema v3 after explicit backup and migration |
| Privacy | Existing freshness/hold/suppression and FORGET semantics; a real operator-owned FORGET route for this new family is NOT yet implemented |
| Hermes context | Read-only LilithCanonicalMemoryContextV1; returns only authorized canonical memories, with owner-channel restriction for personal data; no transcript writer |
| What remains | New signer purpose in installed release, active host tree + schema v3, safe FORGET operation, exact owner statement and consent, and a governed Hermes gateway read route |

The only changed signer runtime source proposed by this PR is **protocol.py**; the signer release layout/member set is unchanged. The new owner memory family uses existing contracts rather than widening the codename purpose or resurrecting the suppressed First Interaction identity.

**Offline tests reported:** Core API 335 passed versus 322 baseline; owner-memory-control 2223 vs 2217; authority-dev 301 vs 296; recovery-witness 59 vs 59; cognitive regressions 382 vs 382. The WSL-root broker validation failure reportedly reproduced on unmodified main, so it was not treated as a new product failure. All these statements are **offline test evidence**. None shows a new human-provided origin fact exists on DEV.

**Live Hermes gap:** The DEV Hermes gateway is unprivileged and currently cannot invoke the root bridge used by the canonical read path. PR #263's memory-context note is a **source-only adapter**; it has not been wired to the running gateway. A new restricted read transport must not grant the gateway arbitrary root access, signer mutations or memory admission authority.

**Activation sequencing:** Do not merge PR #263 into PROD, or activate it in DEV, solely because tests pass. Its owner-personal sensitivity requires a governed FORGET path and exact owner consent before a first personal-origin admission. Source merge is a separate decision and would count as DEPLOY_REQUIRED for current Core API source.

## 16. Repo/workspace cleanup and what not to delete (Oct 26)

**GitHub verified:** Existing security [PR #250](https://github.com/rpahasara/lilith-os/pull/250) was closed unmerged because both Next.js package and lock files on main were **byte-identical** to that PR's security pin (Next.js 16.4.3). Draft [PR #227](https://github.com/rpahasara/lilith-os/pull/227), a manually dispatched isolated self-hosted CI-runner smoke experiment explicitly marked do-not-merge, was also closed unmerged. GitHub main remained 99fe281… at the time of this record. Open source PRs were #262 (this document) and #263 (new personal-origin source).

**Owner/Claude local workspace report:** The UI's +7,493/-55 count mostly reflected untracked local work, **not** thousands of committed differences on main. Eleven disposable .codex-snapshot-release-* outputs and eight obsolete/duplicate lilith_*.patch files were moved, not destroyed, to a local quarantine folder. Two large .codex-stage3-a2-* working trees were reported safe-to-delete but left untouched. A roughly 252 MB artifacts/ folder and a differing Hsin animation (hsin-relaxed-idle.vrma) were explicitly **uncertain** and retained. The old review/a1-a7-atomicity-fix commit was already in main through #233. Never delete the artifacts or animation solely because they look like test data; Stage III evidence and Hsin assets may still matter.

**No accidental cleanup of past proofs.** Old phase records, consumed step markers, signer pin digests, K-PAN/K-PCK custody, Privacy databases/sidecars, L04 backups and the FORGET spool are governed state or audit evidence, not disposable CI trash. Changing their path or hash can invalidate historical verification even if a unit test still passes.

## 17. DEV vs PROD snapshot boundary (for the later read-only reconciliation)

| Dimension | Original PROD: what is actually established so far | DEV: what is actually established so far |
| --- | --- | --- |
| VM | Original lilith-01; earlier engineering records report live PROD deployments in Sept 2026 | lilith-dev-01; F8/F9, E-23, FM-1 and first L04 memory operator reported live |
| Older cognitive work | Earlier PROD-only world-model/working-memory, goals, reasoning, global workspace, motivation, planning and ethics were historically reported | New DEV authority, privacy and memory path proven; actual parity with PROD's older cognition **unknown** |
| Signer/witness | Current live state **unknown** pending separate read-only PROD inventory | Owner-accepted new FM-1 signer/witness from e2324a5, four DEV_SYNTHETIC K-ACT loads total |
| Privacy | Actual PROD anchors, owner keys, erased history and current boot readiness **not surveyed** | K-PAN witness anchor v1, owner K-PCK checkpoint seq 1, current-boot unlock when tested; historical F9c2 suppression preserved |
| Canonical memories | Live PROD canonical L04 inventory **not surveyed** | First DEV codename admission and fresh CLI recall reported; creation returned DISABLED |
| Hermes and Hsin | Runtime and version parity **unknown** | DEV Hermes gateway exists; first canonical memory not yet integrated into ordinary Hermes chat |
| Authority and keys | PROD credentials and trust must remain independently scoped | Synthetic DEV owner key and registry/proof are NOT valid PROD substitutes |
| Deployment | PROD main workflow historically only pushed narrow app.py payload | DEV has newer Core API rollout, pinned releases and staged owner/go procedures; no automatic equivalence |

**Mandatory promotion discipline:** first inventory both machines read-only; classify each feature by source version, real live unit/process, database/schema and backup, key/credential custody, memory lineage, privacy/FORGET history and provider/runtime configuration. Plan **selective** DEV→PROD capability upgrades, never raw DEV synthetic DB/VM/credential cloning. No PROD write, restart, import or promotion without a new specific owner GO. The first DEV memory's meaning and evidence may be deliberately carried forward under a separate PROD-native consent/migration policy—not assumed by copying bytes.

## 18. Current handoff checklist (verified scope vs unresolved work)

**Completed / do not repeat:** F9c2 one-time FORGET; E-23 witness and signer replacement; Privacy genesis/anchor/checkpoint/boot-unlock on the observed boot; FM-1 F0→F7 signer and witness replacement; synthetic owner software credential enrollment; L04 admission-link migration; smallest read ACL; first DEV codename L04 admission; independent fresh-session recall; owner-authorized return to creation DISABLED; cleanup of stale PR #250 and draft #227.

**Pending (distinct goals):** Review/merge this retrospective documentation; review source-only PR #263 and close the missing owner-personal FORGET path before live personal admission; obtain the owner's **exact** origin wording; add a genuinely narrow read-only canonical memory transport to the live Hermes gateway; prove ordinary Hermes fresh-chat recall; inventory original PROD versus DEV read-only; then propose separate PROD-native, owner-approved promotion. Richer autobiographical context/personality, model/runtime portability and renewed cognition engineering remain future DEV slices.

**Non-goals:** Recreating the forgotten First Interaction identity; treating a SOUL prompt as a canonical identity owner; making additional Groq calls from the exhausted 5/5 ledger; treating DEV_SYNTHETIC proof as PROD-authenticated human proof; conflating source merge with installed runtime; auto-admitting full conversations; running historical mutation ceremonies again to “freshen” reports; inventing an origin text because a schema exists.

**Reminder for the next session:** This document is deliberately one durable context note. The signed owner gos, exact STEP.json evidence, original seal files and live DEV/PROD machine state have their own owners. If the record disagrees with a fresh verified host observation, investigate; do not silently mutate canonical memory or privacy state to make the narrative consistent.
