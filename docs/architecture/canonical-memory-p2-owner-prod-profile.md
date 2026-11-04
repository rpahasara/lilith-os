# Canonical memory P2: the OWNER_PROD profile (source only, 2026-11-04)

Status: SOURCE ONLY. Nothing was merged, deployed or installed. No key was created and no provider request was used.
Stacked on the release-preparation branch, which is on draft PR rpahasara/lilith-os#312. The plan is
`canonical-memory-prod-release-plan.md`.

## 1. What P2 implements

One production profile, `OWNER_PROD` (environment `prod`), beside `DEV_SYNTHETIC`. The two are disjoint: each refuses
the other's values. No new contract, operation, store, module or release member is added.

| Area | Change |
|---|---|
| Selection | A root-installed `/etc/lilith-authority-dev/deployment.json` names the host's profile. It must be exactly `{"environment":"prod","profile":"OWNER_PROD"}`, root-owned, 0644 and canonical JSON. No file means DEV, which is every DEV host today, unchanged. Any other content refuses (fail closed, never a fallback). The signer and witness servers also require `LILITH_ENV` to match; the root CLI and the First Memory host read the file once |
| Trust roots | `authority_verifier`, `rotation_contracts` (2 sites) and `recovery_contracts` require a `prod.` registry root or `prod.witness.` anchor under a `prod` verification context. A `test-only.` root is refused there. Every `dev`/`test` context keeps the B1b-3a rule exactly. Refusals reuse the existing codes (`ENVIRONMENT_MISMATCH`, `AUTHORIZATION_ENVIRONMENT_MISMATCH`, `WITNESS_ENVIRONMENT_MISMATCH`), so **no reason taxonomy changed** (the 44-code historical vector holds) |
| Signer | `OwnerProdSignerProfileV1` (`prod.owner-prod.actor.1`, `policy.owner-prod.v1`, `authority.owner-prod.memory`, `owner.prod.v1`); `runtime_profile(environment)`; the minter binds the profile's environment; the ledger gets a `prod` schema (only the meta CHECK literals differ; the DEV `SCHEMA` and its fingerprint are untouched); the self-view names the profile |
| Custody / witness | `OWNER_PROD_CUSTODY_PROFILE` (initial key only) and `OWNER_PROD_WITNESS_PROFILE` (`prod.witness.owner-prod.1`); `custody_profile("prod")` and `witness_profile("prod")` return them; anything else claiming `prod` keeps the DEV refusals; K-PAN `kpan.owner-prod.01`, Privacy anchor environment `OWNER_PROD` |
| Owner | registration protocol `LILITH_OWNER_REGISTRATION_PROD`: the owner's own principal, a real RP id and an `https://` origin on it; never the synthetic owner or `.invalid`. RR-39's owner check admits that context in `prod` only. `owner_proof.py` (broker-pinned) is **unchanged** |
| Privacy | D-6: the interim V1 HMAC FORGET path admits `OWNER_PROD`. The Hermes conversation-erasure owner and the Hermes floor stay DEV-only, so a PROD FORGET can name canonical records only (D-2). The activation host steps take `--environment` |
| First Memory host | deployment-selected environment, signer profile and paths. PROD paths are PROD's existing `lilith-os/data` (`cognitive_memory.db`, `privacy_governance.db`, its own 15B2a keys) |
| Context service | grant v3 lists owner channels. Channels are opaque, well-formed labels; `public` is reserved and can never be granted. A future authenticated interface (voice, for example) needs only a gateway label and a grant entry, no service change. Personal memory stays off by default and is denied to every channel the owner's grant does not list |

**Kept as they are (naming debt):** service, user and path names keep their `-dev` spelling on PROD.

## 2. Evidence

| Check | Result |
|---|---|
| DEV values, base `724da03` vs P2 head (same interpreter) | **byte-identical** (`392c1bf9…`): ledger schema and fingerprint, DEV signer, custody and witness profiles, `custody_profile("dev"/"test")`, slot contract, test-only root rule, synthetic owner |
| `authority-dev` (WSL, root) | 341 OK (main 312: +1 context-service file, +1 `test_owner_prod_profile`) |
| `owner-memory-control` (WSL) | 2260 OK, 9 skipped |
| `recovery-witness` (WSL) | 59 OK |
| `core-api` (Windows, FastAPI present) | 395 OK, 21 skipped (WSL: the same 10 FastAPI-environment errors as main) |
| PROD seam, overlay and Hermes source integrity | 15 OK |
| **Cutover 2 corpus**, PROD tree as deployed vs the same tree plus the canonical-memory overlay, **feature off** | **120/120 turns identical** (lanes, decisions, reads, writes, modes, overrides, grounding, rows changed). Store rows, goals, drafts and world status are equal. The only tree difference is the three overlay files |

**Tests that changed, and why:**
- **Re-derived historical-release deltas.** E-19, E-22, E-23, FM-1, FM-2, RR-39, M-B1, M-B3 and M-B4/5 now include the
  explicit P2 tree delta (`e23_installed.OWNER_PROD_TREE_DELTA`). Their lineage checks are anchored to main `75ca0db`.
- **Five tests state the new intended rule.** `prod` is a ledger environment; `custody_profile("prod")`;
  `PROFILE_ENVIRONMENTS`; the server's own test seams; and a `prod` registry fixture now uses a `prod.` root.
- **`SHARED_HASHES` is re-pinned for the 7 shared modules.** The closed historical operators (M-B4/5, M-B6, FM-1)
  keep pinning the releases they ran.

## 3. Limitations

1. **Ceremony tooling is not profile-aware.** The keygen, owner tool and installer still produce DEV_SYNTHETIC
   material and DEV units. They need an OWNER_PROD mode before P4 (§4).
2. **No key rotation on PROD in RC1.** Successor (K-ACT rotation) identities stay DEV-only, so a PROD key can never
   parse as a successor.
3. **D-6.** V1 HMAC FORGET authorization, with the limits recorded in the plan. The Hermes conversation store is
   never erased (D-2).
4. **Lane replies.** Ready lane replies (Reasoning, Planning, Ethics) do not see the memory note.
5. **Validation so far.** Telegram and console recall on PROD are validated offline only: unit tests, plus the
   corpus with the feature off. Owner checks come at P7 and P8.

## 4. P3: release-build requirements

1. **Merge order.** Merge #312, then this stack in order, each only when the previous main runs are green. Every
   merge is DEPLOY_REQUIRED, a routine DEV Core API deploy. DEV behaviour stays the same, because the DEV values are
   identical.
2. **One attested authority release** from the P2 merge commit: A=B reproducible build, manifest and attestation.
   - Its delta against the installed `d82f7da` is exactly `OWNER_PROD_TREE_DELTA`, 18 members, 2 of them witness
     (`credential.py`, `server.py`).
   - No broker release.
3. **One DEV transition** in the FM-2 ladder shape, with its own control-only contract PR pinning OLD `d82f7da` and
   NEW `<merge>`:
   - stop and select the signer and witness;
   - the witness restarts from NEW;
   - the K-ACT load;
   - re-derive the DR-5 target.
4. **The DEV First Memory host tree** is rebuilt from the merge, because the host modules changed.
   - Then `install_f9c.sh --repin`: the FORGET executor's frozen Core API copy includes `privacy_forget_runner`.
   - Then check Privacy READY.
5. **DEV acceptance:**
   - `cm1_window.sh check` (no-write digests equal);
   - the context probe still returns both memories to `lilith_os` and only the codename elsewhere;
   - one bounded recall turn (one provider request, by separate approval).
6. **Then the P4 preparation.** P4 cannot start until all of these exist and are reviewed:
   - the OWNER_PROD ceremony mode for the keygen (K-ACT, K-WIT, K-PAN, K-PCK) and the owner tool (K-ROOT `prod.`
     registry root, `LILITH_OWNER_REGISTRATION_PROD`);
   - an installer writing `deployment.json` and `LILITH_ENV=prod` units;
   - the owner's decision on the RP id/origin for the owner credential;
   - verified offline backups.
