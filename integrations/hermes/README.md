# Hermes runtime integration source

Hermes is not LILITH. It is the replaceable conversation runtime that PROD (`lilith-01`) and DEV (`lilith-dev-01`)
run today. This directory holds the LILITH-authored source needed to rebuild what those hosts run, without vendoring
upstream Hermes:

| Path | What it holds |
|---|---|
| [UPSTREAM.md](UPSTREAM.md) | The exact upstream pin, its licence, and how the patches relate to it |
| `patches/` | LILITH's patches to upstream Hermes, one per environment, with the SHA-256 of every patched file |
| `release/dev-f9c2/` | The non-upstream members of the deployed DEV release `f293e72-f9c2`: installers, gate, Privacy FORGET executor, systemd units, profiles, offline tests, lock files and the full release manifest |
| `overlays/` | Changes installed on DEV outside the release (origin-aware FORGET executor) and one planned, undeployed change |
| `home/` | Router V2 and the `lilith_os` / Groq plugins: the `HERMES_HOME` code tree (added separately) |
| `history/` | F7–F9 build lineage: designs, results, build and simulation tooling (added separately) |
| `tools/` | Offline reconstruction and verification tools |

Nothing here is installed or run by CI or by any workflow. Changing a file here changes no host; deployment is a
separate, owner-approved operation.

## Environments are separate

- **PROD `lilith-01`** runs upstream `f293e72` plus [patches/prod-lilith-01.patch](patches/prod-lilith-01.patch)
  (Router V2 seam with the Slice 9 reasoning hook, and the Slice 15B2a containment files). The PROD virtualenv was
  not built from a lock and has drifted; it cannot be reproduced exactly. PROD-only files that are not on any
  development machine are listed in `docs/engineering/vm-only-source-gaps.md` (source-consolidation record).
- **DEV `lilith-dev-01`** runs release `f293e72-f9c2`: upstream `f293e72` plus
  [patches/dev-f9c2.patch](patches/dev-f9c2.patch), a hash-locked dependency set, and the files under
  `release/dev-f9c2/`. Every cognitive lane is off on DEV (`world_context.py` is a 723-byte import stub there).

The two patch sets share the Slice 15B2a files byte for byte; they differ in `gateway/run.py` and in two DEV-only
agent files changed by the F9 Privacy work.

## Rebuild the patched Hermes source

Needs a local clone of `https://github.com/NousResearch/hermes-agent` checked out at the pin, and Git.

```bash
python integrations/hermes/tools/reconstruct_hermes_src.py --upstream ../hermes-agent --variant dev-f9c2 --out /tmp/hermes-dev --full
```

Use `--variant prod-lilith-01` for PROD. The tool refuses any other upstream commit and exits non-zero unless every
patched file matches the recorded SHA-256.

## Rebuild the DEV f9c2 release tree

1. Rebuild the source tree as above (`--variant dev-f9c2 --full`); it becomes the release `src/`.
2. Copy `release/dev-f9c2/{bin,systemd,profiles,dr5,tests}` and the lock files into the release root, and
   `scripts/deployer_authority_boundary_proof.sh` to `dr5/`.
3. Render the four token-bearing files from custody (below).
4. Add the bundled CPython 3.11.16, uv 0.12.5 and the wheels pinned by `requirements.locked.txt`
   (`EXPECTED-DISTS.txt` lists the installed distributions).
5. Compare every member with `release/dev-f9c2/MANIFEST.sha256`.

`python integrations/hermes/tools/verify_dev_f9c2_source.py` checks offline that every release file held in Git
equals the manifest. The exact deployed tarball is not in Git: it embeds the gate client token and is kept in the
owner's encrypted recovery archive.

## Credentials stay out of Git

The DEV release embeds a 21-character, localhost-only client token that the gateway presents to the local provider
gate. It is not the Groq key. Git holds the four affected files as templates with the placeholder
`__LILITH_GATE_CLIENT_TOKEN__`:

```bash
python integrations/hermes/tools/render_dev_f9c2_templates.py --token-file /secure/path/gate-client-token --out /tmp/f9c2-rendered
```

The tool reads the value from a file, never prints it, and passes only when all four rendered files equal the
release manifest. The Groq project key and the console token are created on the host by
`release/dev-f9c2/bin/provision_provider_key.sh` and `provision_console_token.sh`; neither value exists in source.

## Verification status (2026-10-27)

| Claim | Status |
|---|---|
| Patched Hermes files for PROD and DEV rebuilt byte-exact from `f293e72` + patches | SOURCE_BUILD_VERIFIED (offline) |
| DEV release files in Git equal the deployed manifest; templates render byte-exact | SOURCE_BUILD_VERIFIED (offline) |
| Full DEV runtime rebuilt and started from this source | RUNTIME_RECONSTRUCTION not verified |
| Deployment from this directory | LIVE_DEPLOYMENT_NOT_TESTED |
