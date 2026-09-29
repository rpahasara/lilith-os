"""15B2b-B1b-3e PR-3 P3-3A: create-only publication backends (offline).

Record: docs/architecture/slice-15b2b-b1b3e-pr3-android-replica-publication.md.

The abstract property every backend must satisfy:

    AN ACCEPTED RECORD FILE MAY BE CREATED EXACTLY ONCE AT ITS CANONICAL FINAL
    NAME, AND AN EXISTING ACCEPTED FILE IS NEVER SILENTLY REPLACED.

    storage backend != record authority

A backend only changes how bytes reach their final name. The record bytes,
digest, filename, and acceptance semantics are identical across backends,
and no backend identity enters any record, envelope, or replica manifest.

Backends:

- `RENAME_NOREPLACE_V1`: an exclusive pending file, written and fsynced, then
  `renameat2(pending, final, RENAME_NOREPLACE)`, then a directory fsync. The
  rename is atomic and fails with EEXIST if the final name exists. A crash
  leaves exactly one of the two names. **Admitted; preferred.**
- `HARDLINK_PUBLISH_V1`: pending, fsync, `link(pending, final)` (fails if
  final exists), unlink pending, directory fsync. A crash can leave both
  names; strict read refuses that (pending present). **Admitted.**
- `DIRECT_O_EXCL_V1`: `open(final, O_CREAT|O_EXCL)`, write, fsync, directory
  fsync. It never overwrites, but a crash leaves a zero-length or partial
  file at the accepted name, which strict read refuses (the name binds the
  content digest). **Evaluated, not admitted in V1**: recovering from it
  would require removing a file that carries an accepted-record name.

Plain `rename()` / `os.replace()` is never used for publication: both
replace an existing destination on POSIX.
"""

from __future__ import annotations

import ctypes
import errno
import os
import platform
from pathlib import Path

RENAME_NOREPLACE_V1 = "RENAME_NOREPLACE_V1"
HARDLINK_PUBLISH_V1 = "HARDLINK_PUBLISH_V1"
DIRECT_O_EXCL_V1 = "DIRECT_O_EXCL_V1"
BACKENDS = (RENAME_NOREPLACE_V1, HARDLINK_PUBLISH_V1, DIRECT_O_EXCL_V1)
# Deterministic preference over ADMITTED backends only, by crash semantics:
# rename-noreplace has no two-name crash state; hard link does.
ADMITTED_PREFERENCE = (RENAME_NOREPLACE_V1, HARDLINK_PUBLISH_V1)
NONE = "NONE"
PENDING_PREFIX = ".pending-"

_AT_FDCWD = -100
_RENAME_NOREPLACE = 1
# renameat2 syscall numbers, used only when libc does not export renameat2.
_RENAMEAT2_SYSCALL = {"x86_64": 316, "amd64": 316, "aarch64": 276, "arm64": 276, "armv7l": 382, "armv8l": 382,
                      "i686": 353, "i386": 353}


class PublishRefused(Exception):
    def __init__(self, reason: str, detail: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class RenameNoReplaceUnavailable(OSError):
    pass


def _libc():
    try:
        return ctypes.CDLL(None, use_errno=True)
    except (OSError, TypeError):
        return None


def rename_noreplace(source: Path, target: Path) -> None:
    """renameat2(AT_FDCWD, source, AT_FDCWD, target, RENAME_NOREPLACE).

    Raises FileExistsError if the target exists, RenameNoReplaceUnavailable if
    the primitive is absent or refused (ENOSYS, EINVAL, EPERM, EACCES, no libc),
    and OSError otherwise. There is no fallback to an overwriting rename.
    """
    libc = _libc()
    if libc is None:
        raise RenameNoReplaceUnavailable(errno.ENOSYS, "no libc")
    src, dst = os.fsencode(os.fspath(source)), os.fsencode(os.fspath(target))
    function = getattr(libc, "renameat2", None)
    if function is not None:
        function.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
        function.restype = ctypes.c_int
        result = function(_AT_FDCWD, src, _AT_FDCWD, dst, _RENAME_NOREPLACE)
    else:
        number = _RENAMEAT2_SYSCALL.get(platform.machine().lower())
        syscall = getattr(libc, "syscall", None)
        if number is None or syscall is None:
            raise RenameNoReplaceUnavailable(errno.ENOSYS, "no renameat2")
        syscall.restype = ctypes.c_long
        result = syscall(ctypes.c_long(number), ctypes.c_int(_AT_FDCWD), ctypes.c_char_p(src),
                         ctypes.c_int(_AT_FDCWD), ctypes.c_char_p(dst), ctypes.c_uint(_RENAME_NOREPLACE))
    if result == 0:
        return
    code = ctypes.get_errno()
    if code == errno.EEXIST:
        raise FileExistsError(code, os.strerror(code), os.fspath(target))
    if code in (errno.ENOSYS, errno.EINVAL, errno.EPERM, errno.EACCES, errno.EOPNOTSUPP):
        raise RenameNoReplaceUnavailable(code, os.strerror(code))
    raise OSError(code, os.strerror(code), os.fspath(target))


def write_new_file(path: Path, data: bytes) -> None:
    """O_CREAT|O_EXCL (plus O_NOFOLLOW) write with a file fsync. Never replaces."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def fsync_directory(path: Path) -> str:
    if os.name != "posix":
        return "UNSUPPORTED_PLATFORM"
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return "PERFORMED"


def publish(directory: Path, final_name: str, data: bytes, *, backend: str) -> str:
    """Publish `data` at `directory/final_name` exactly once with `backend`.

    Raises PublishRefused("FINAL_EXISTS") if the final name exists; the
    existing file is never touched. Returns the directory-fsync result.
    """
    if backend not in BACKENDS:
        raise PublishRefused("UNKNOWN_BACKEND", str(backend))
    directory = Path(directory)
    final = directory / final_name
    if os.path.lexists(final):
        raise PublishRefused("FINAL_EXISTS", final_name)
    if backend == DIRECT_O_EXCL_V1:
        try:
            write_new_file(final, data)
        except FileExistsError as exc:
            raise PublishRefused("FINAL_EXISTS", final_name) from exc
        return fsync_directory(directory)
    pending = directory / f"{PENDING_PREFIX}{final_name}.tmp"
    write_new_file(pending, data)
    try:
        if backend == RENAME_NOREPLACE_V1:
            rename_noreplace(pending, final)
        else:
            os.link(pending, final)
    except FileExistsError as exc:
        os.unlink(pending)
        raise PublishRefused("FINAL_EXISTS", final_name) from exc
    except OSError:
        os.unlink(pending)
        raise
    if backend == HARDLINK_PUBLISH_V1:
        os.unlink(pending)
    return fsync_directory(directory)


def select_backend(capabilities: dict) -> str:
    """The first admitted backend whose probe passed, else NONE. Deterministic."""
    for backend in ADMITTED_PREFERENCE:
        if capabilities.get(backend) is True:
            return backend
    return NONE
