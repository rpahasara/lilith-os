"""15B2b-B1b-3e PR-1S: fixed root ceremony tooling for the DEV_SYNTHETIC authority host (S-9, S-11).

Record: docs/architecture/slice-15b2b-b1b3e-pr1s-runtime-wiring.md.

Shipped in the reviewed release and exposed only through fixed CLIs in
`/usr/local/sbin` (`lilith-authority-{hold,verify,ledger,recovery}-dev`,
`lilith-recovery-witness-owner-dev`), run by the owner as root inside a
separately authorized ceremony step. There is no generic "write JSON",
"run command", "sign", or arbitrary-path operation: every record is built
from bounded arguments and the verified host state.

- `hold_store`: the RR-34 hold store's only writer and its complete observer.
- `observers`: read-only root observations (CURRENT, inventory, units,
  installed release, ledger copy, witness store).
- `verifier`: the independent root readiness verifier and the RR-38
  canonical evidence package. Read-only.
- `ledger_tool`: the one explicit ledger provisioning step (as the signer uid).
- `clients`: root clients of the signer and witness owner sockets.

Nothing here is authority, and nothing here starts, enables, or reloads a
unit, creates a credential, or signs.

    root tooling succeeded != owner acceptance
    hold release           != authority
"""

__all__ = ("hold_store", "observers", "verifier", "ledger_tool", "clients", "cli")
