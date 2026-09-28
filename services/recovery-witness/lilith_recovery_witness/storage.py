"""The live-capable witness storage port over the real filesystem (PR-1S, S-7).

Implements the Source Prep A `WitnessStoragePortV1` semantics against one
fixed state directory (`/var/lib/lilith-recovery-witness`, or a temporary
directory in tests):

- every operation is relative to a directory descriptor opened
  `O_DIRECTORY|O_NOFOLLOW`; no path component is ever followed as a link;
- `create_exclusive` is `O_CREAT|O_EXCL|O_NOFOLLOW` and writes every byte;
- nothing is durable until `fsync_file` (contents) and `fsync_directory`
  (the entry): the writer, not this port, decides the order;
- `replace` is an atomic same-directory `rename`;
- `lock` is `flock(LOCK_EX|LOCK_NB)` on `witness.lock` (a name the Prep A
  recovery scan admits); a second holder is refused, never waited for;
- files are `0640` and directories `0750`. The state directory is
  `lilith-recovery-witness:lilith-authority-dev 2750` (installer-created),
  so entries inherit the signer's group for read-only verification without
  the witness account belonging to that group.

The port never interprets bytes, never picks a head, and never repairs.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Iterator

from lilith_authority_host.store_observer import list_directory
from lilith_owner_memory import witness_readiness as WR

STATE = ""
FILE_MODE = 0o640
DIRECTORY_MODE = 0o750
_SUBDIRECTORIES = frozenset({WR.CHAIN_DIRECTORY, WR.AUTHORIZATION_DIRECTORY})
_O_DIR = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)


class StorageLocked(RuntimeError):
    """Another holder has the witness lock. Nothing was done."""


class StorageRefused(OSError):
    """A request named something outside the fixed store layout."""


class FilesystemWitnessStorageV1:
    """The one writer's storage. Directories are `STATE`, `chain`, `authorizations`."""

    def __init__(self, state_dir: Path | str):
        self.state_dir = Path(state_dir)

    def _directory(self, directory: str) -> int:
        if directory == STATE:
            return os.open(self.state_dir, _O_DIR)
        if directory not in _SUBDIRECTORIES:
            raise StorageRefused("unknown store directory")
        parent = os.open(self.state_dir, _O_DIR)
        try:
            return os.open(directory, _O_DIR, dir_fd=parent)
        finally:
            os.close(parent)

    @staticmethod
    def _name(name: str) -> str:
        if not isinstance(name, str) or not name or "/" in name or name in (".", ".."):
            raise StorageRefused("invalid entry name")
        return name

    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
        import fcntl

        directory = self._directory(STATE)
        try:
            fd = os.open(WR.LOCK_NAME, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, FILE_MODE,
                         dir_fd=directory)
        finally:
            os.close(directory)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise StorageLocked("witness.lock is held") from exc
            yield
        finally:
            os.close(fd)

    def listing(self, directory: str) -> tuple[WR.StoreEntryV1, ...]:
        if directory == STATE:
            return list_directory(self.state_dir)
        if directory not in _SUBDIRECTORIES:
            raise StorageRefused("unknown store directory")
        return list_directory(self.state_dir / directory)

    def make_directory(self, directory: str) -> None:
        if directory not in _SUBDIRECTORIES:
            raise StorageRefused("unknown store directory")
        parent = self._directory(STATE)
        try:
            try:
                os.mkdir(directory, DIRECTORY_MODE, dir_fd=parent)
            except FileExistsError:
                fd = os.open(directory, _O_DIR, dir_fd=parent)  # must already be a real directory
                os.close(fd)
        finally:
            os.close(parent)

    def _write(self, directory: str, name: str, data: bytes, flags: int) -> None:
        folder = self._directory(directory)
        try:
            fd = os.open(self._name(name), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC | flags,
                         FILE_MODE, dir_fd=folder)
        finally:
            os.close(folder)
        try:
            view = memoryview(bytes(data))
            while view:
                view = view[os.write(fd, view):]
        finally:
            os.close(fd)

    def create_exclusive(self, directory: str, name: str, data: bytes) -> None:
        self._write(directory, name, data, os.O_EXCL)

    def write_scratch(self, directory: str, name: str, data: bytes) -> None:
        if (directory, name) != (STATE, WR.POINTER_SCRATCH_NAME):
            raise StorageRefused("scratch is only the pointer scratch")
        self._write(directory, name, data, os.O_TRUNC)

    def fsync_file(self, directory: str, name: str) -> None:
        folder = self._directory(directory)
        try:
            fd = os.open(self._name(name), os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=folder)
        finally:
            os.close(folder)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def fsync_directory(self, directory: str) -> None:
        folder = self._directory(directory)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)

    def replace(self, directory: str, source: str, target: str) -> None:
        if (directory, source, target) != (STATE, WR.POINTER_SCRATCH_NAME, WR.POINTER_NAME):
            raise StorageRefused("the only rename is scratch -> pointer")
        folder = self._directory(directory)
        try:
            os.rename(source, target, src_dir_fd=folder, dst_dir_fd=folder)
        finally:
            os.close(folder)

    def remove(self, directory: str, name: str) -> None:
        if (directory, name) != (STATE, WR.POINTER_SCRATCH_NAME):
            raise StorageRefused("the only removal is discardable pointer scratch")
        folder = self._directory(directory)
        try:
            os.unlink(name, dir_fd=folder)
        finally:
            os.close(folder)
