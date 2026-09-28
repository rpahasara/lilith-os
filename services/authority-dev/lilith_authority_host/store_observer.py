"""Read-only listings over the real filesystem (PR-1S).

Every entry is `lstat`-classified (never followed); regular files are read
through `O_NOFOLLOW` descriptors with a size bound. Used for the witness
state directory (shared by the witness store, the signer's read-only view,
and the root verifier). Readers never repair: a partial state is reported
as it is, and only the witness's own recovery may roll a pointer forward.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from lilith_owner_memory import witness_readiness as WR

MAX_ENTRY_BYTES = 256 * 1024
MAX_ENTRIES = 100_000


class ObservationError(OSError):
    pass


def read_regular(path: Path | str, *, limit: int = MAX_ENTRY_BYTES, dir_fd: int | None = None) -> bytes:
    """Bytes of one regular file, never through a symlink, bounded."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
            raise ObservationError("not a bounded regular file")
        chunks, total = [], 0
        while chunk := os.read(fd, 65536):
            total += len(chunk)
            if total > limit:
                raise ObservationError("file grew beyond its bound")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def kind_of(mode: int) -> str:
    if stat.S_ISLNK(mode):
        return WR.SYMLINK
    if stat.S_ISDIR(mode):
        return WR.DIRECTORY
    if stat.S_ISREG(mode):
        return WR.REGULAR
    return WR.OTHER


def list_directory(directory: Path | str) -> tuple[WR.StoreEntryV1, ...]:
    """Every entry of `directory`, sorted by name, with regular-file bytes."""
    directory = Path(directory)
    found = []
    with os.scandir(directory) as iterator:
        for item in iterator:
            if len(found) >= MAX_ENTRIES:
                raise ObservationError("directory too large")
            kind = kind_of(os.lstat(item.path).st_mode)
            data = read_regular(item.path) if kind == WR.REGULAR else None
            found.append(WR.StoreEntryV1(item.name, kind, data))
    return tuple(sorted(found, key=lambda entry: entry.name))


def observe_witness_state(state_dir: Path | str) -> WR.WitnessStoreObservationV1:
    """Story 4: one read of the witness state directory (absent -> empty)."""
    state_dir = Path(state_dir)
    try:
        meta = os.lstat(state_dir)
    except FileNotFoundError:
        return WR.WitnessStoreObservationV1(())
    if not stat.S_ISDIR(meta.st_mode):
        return WR.WitnessStoreObservationV1((WR.StoreEntryV1(".", kind_of(meta.st_mode)),))
    state = list_directory(state_dir)
    kinds = {entry.name: entry.kind for entry in state}
    chain = list_directory(state_dir / WR.CHAIN_DIRECTORY) if kinds.get(WR.CHAIN_DIRECTORY) == WR.DIRECTORY else ()
    retained = (list_directory(state_dir / WR.AUTHORIZATION_DIRECTORY)
                if kinds.get(WR.AUTHORIZATION_DIRECTORY) == WR.DIRECTORY else ())
    return WR.WitnessStoreObservationV1(state, chain, retained)
