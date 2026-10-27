# DEV release `f293e72-f9c2`

The release installed on `lilith-dev-01` on 2026-10-25 (Track A, F9c2), taken from the release package
`hermes-gateway-dev-f293e72-f9c2.tar.gz` (159,267,402 bytes, SHA-256
`4b0b0110dde1cccd585203ea9a92cfe8b8cbe31d8e1a6e4edb461ba2c09c3ba5`). `MANIFEST.sha256` is the package's own manifest
of all 14,324 members.

| Path | Members | Held how |
|---|---|---|
| `bin/` | install, rollback, preserve/restore, provider gate, Privacy FORGET executor and restore guard, probes, smoke and drill tools, provisioning helpers | byte-exact, except `verify_release.py` (template) |
| `systemd/` | gateway, retention, provider gate and Privacy FORGET units and drop-ins | byte-exact |
| `profiles/operate/` | the OPERATE profile applied by `bin/apply_profile.sh` | byte-exact, except `config.yaml` (template) |
| `dr5/` | `expected-dev-block-b9eb32c.txt` | byte-exact; the proof script is `scripts/deployer_authority_boundary_proof.sh` |
| `tests/` | F7, F9a and F9b offline tests with their fixture `HERMES_HOME` | byte-exact |
| `templates/` | `home/config.yaml`, `profiles/operate/config.yaml`, `gate/gate.json`, `bin/verify_release.py` | token replaced by `__LILITH_GATE_CLIENT_TOKEN__` |
| `RELEASE_ID`, `EXPECTED-DISTS.txt`, `requirements.locked.txt` | release identity and the hash-locked dependency set | byte-exact |
| `src/` | patched upstream Hermes | rebuilt from `../../patches/dev-f9c2.patch` |
| `home/` | Router V2 and plugins | `integrations/hermes/home/` |
| `python/`, `uv/`, `wheelhouse/`, `buildbackend/` | CPython 3.11.16, uv 0.12.5, wheels, setuptools | third-party binaries, rebuilt from the lock; not in Git |

`home/router.yaml` (DEV: shadow mode, every lane off) and `home/config.yaml` are runtime configuration for this
release. `home/config.yaml` and the operate profile disable Hermes memory, profile onboarding, background review,
curator, cron and every tool for the console platform; read them before changing anything about DEV behaviour.

The install, rollback and provisioning scripts act on a host as root. They are kept here for reconstruction and
review; nothing in the repository runs them.
